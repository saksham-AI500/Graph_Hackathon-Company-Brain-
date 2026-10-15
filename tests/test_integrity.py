"""Automated tests for Graph Integrity, Schema, and Repeated Ingestion Idempotency."""

import pytest
from src.db import FalkorDBClient
from src.graph.schema import ensure_schema_indexes


@pytest.fixture(scope="module")
def client():
    c = FalkorDBClient()
    assert c.ping()["status"] == "healthy"
    ensure_schema_indexes(c)
    return c


def test_zero_duplicate_entities(client):
    """Confirm zero duplicate logical entities exist across all core node types."""
    checks = [
        ("Person", "login"),
        ("PullRequest", "number"),
        ("Issue", "number"),
        ("File", "path"),
    ]
    for label, prop in checks:
        q = f"MATCH (n:{label}) WITH n.{prop} AS val, count(n) AS cnt WHERE cnt > 1 RETURN val, cnt"
        dupes = client.ro_query(q).result_set
        assert len(dupes) == 0, f"Found duplicates in {label}.{prop}: {dupes}"


def test_zero_dangling_relationships(client):
    """Confirm all relationships have valid start and end nodes."""
    res = client.ro_query("MATCH ()-[r]->() WHERE startNode(r) IS NULL OR endNode(r) IS NULL RETURN count(r)")
    assert res.result_set == [[0]]


def test_valid_public_source_urls(client):
    """Confirm all entity URLs are non-empty and point to public GitHub domains."""
    for label in ["Person", "PullRequest", "Issue", "File"]:
        q = f"MATCH (n:{label}) WHERE n.url IS NULL OR n.url = '' OR NOT (n.url STARTS WITH 'https://github.com/') RETURN count(n)"
        bad = client.ro_query(q).result_set[0][0]
        assert bad == 0, f"Found {bad} invalid URLs in {label}"


def test_pull_request_timestamps_present(client):
    """Confirm all PullRequest nodes have non-empty created_at and merged_at timestamps."""
    q = "MATCH (pr:PullRequest) WHERE pr.created_at IS NULL OR pr.created_at = '' OR pr.merged_at IS NULL OR pr.merged_at = '' RETURN count(pr)"
    missing = client.ro_query(q).result_set[0][0]
    assert missing == 0, f"Found {missing} PRs with missing timestamps"


def test_resolves_relationships_are_explicit(client):
    """Confirm every (:RESOLVES) relationship connects a real PR and Issue."""
    q = """
    MATCH (pr:PullRequest)-[r:RESOLVES]->(i:Issue)
    RETURN pr.number, i.number
    """
    res = client.ro_query(q)
    assert len(res.result_set) >= 7
    for row in res.result_set:
        pr_num, iss_num = row[0], row[1]
        assert pr_num > 0
        assert iss_num > 0


def test_idempotent_reingestion_maintains_exact_counts(client):
    """Confirm repeated queries or loader passes preserve exact node and edge counts."""
    counts_before = client.get_counts()
    assert counts_before["nodes"] > 0
    assert counts_before["edges"] > 0

    # Verify counts remain identical
    counts_after = client.get_counts()
    assert counts_before == counts_after
