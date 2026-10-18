"""Regression tests proving ownership drift analysis is genuinely graph-powered in FalkorDB."""

import pytest
from src.db import FalkorDBClient
from src.ownership.codeowners import CodeownersParser
from src.ownership.graph_ownership import (
    load_codeowners_into_graph,
    query_ownership_drift_graph,
)


@pytest.fixture
def client():
    c = FalkorDBClient()
    c.ping()
    return c


def test_codeowners_graph_schema_and_nodes(client):
    """Verify OwnershipRule, Team, and COVERS relationships exist in FalkorDB."""
    rules_res = client.ro_query("MATCH (r:OwnershipRule) RETURN count(r)")
    assert rules_res and rules_res.result_set[0][0] > 0

    teams_res = client.ro_query("MATCH (t:Team) RETURN count(t)")
    assert teams_res and teams_res.result_set[0][0] > 0

    covers_res = client.ro_query("MATCH ()-[c:COVERS]->() RETURN count(c)")
    assert covers_res and covers_res.result_set[0][0] > 0

    declares_res = client.ro_query("MATCH ()-[d:DECLARES_OWNER]->() RETURN count(d)")
    assert declares_res and declares_res.result_set[0][0] > 0


def test_query_ownership_drift_graph_returns_declared_owners(client):
    """Verify query_ownership_drift_graph queries FalkorDB for PR #3189 touching /build/."""
    drift = query_ownership_drift_graph(client, target_pr=3189)
    assert drift["target_pr"] == 3189
    assert drift["total_files_analyzed"] > 0

    # 1. Owned file covered by /build/ rule
    build_files = [f for f in drift["files"] if f["file_path"] == "build/Dockerfile"]
    assert len(build_files) == 1
    bf = build_files[0]
    assert bf["rule_pattern"] == "/build/"
    assert "@FalkorDB/falkordb-core" in bf["declared_owners"]

    # 2. Unowned file in the same PR without rule match
    unowned_files = [f for f in drift["files"] if f["file_path"] == "graph/src/runtime/pending.rs"]
    assert len(unowned_files) == 1
    uf = unowned_files[0]
    assert uf["rule_pattern"] is None
    assert uf["declared_owners"] == []
    assert uf["discrepancy_category"] in ("SPARSE_OR_UNRECORDED_HISTORY", "UNOWNED_WITH_ACTIVE_MAINTAINERS")


def test_ownership_drift_strictly_depends_on_graph_relationships():
    """Verify that removing graph relationships causes declared owners to be empty.

    Proves that ownership is NOT silently reconstructed in Python from flat text.
    """
    test_client = FalkorDBClient(graph_name="test_kg_ownership_dep")
    try:
        # Create minimal synthetic graph
        test_client.query("MATCH (n) DETACH DELETE n")
        test_client.query(
            """
            CREATE (pr:PullRequest {number: 9999})
            CREATE (f:File {path: 'src/core/engine.c'})
            CREATE (pr)-[:MODIFIES]->(f)
            CREATE (r:OwnershipRule {pattern: '/src/core/'})
            CREATE (t:Team {name: '@FalkorDB/core-team'})
            CREATE (r)-[:DECLARES_OWNER]->(t)
            CREATE (r)-[:COVERS]->(f)
            """
        )

        # 1. With graph relationships intact: declared owners must be resolved
        res_intact = query_ownership_drift_graph(test_client, target_pr=9999)
        assert len(res_intact["files"]) == 1
        assert res_intact["files"][0]["declared_owners"] == ["@FalkorDB/core-team"]
        assert res_intact["files"][0]["rule_pattern"] == "/src/core/"

        # 2. Delete [:COVERS] relationship in the graph
        test_client.query("MATCH ()-[c:COVERS]->() DELETE c")

        # 3. Query again: declared owners MUST be empty because graph link is broken
        res_deleted = query_ownership_drift_graph(test_client, target_pr=9999)
        assert len(res_deleted["files"]) == 1
        assert res_deleted["files"][0]["declared_owners"] == []
        assert res_deleted["files"][0]["rule_pattern"] is None

    finally:
        test_client.query("MATCH (n) DETACH DELETE n")
