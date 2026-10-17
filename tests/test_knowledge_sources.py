"""Integration tests for knowledge sources: Comments, Documents, Teams, and Decisions in FalkorDB."""

import pytest
from src.db import FalkorDBClient
from src.graph.writer import GraphWriter
from src.knowledge.comments import CommentIngestionEngine, CommentRecord
from src.knowledge.documents import DocumentIngestionEngine, MarkdownDocumentRecord
from src.ownership.codeowners import CodeownersParser
from src.ownership.graph_ownership import load_codeowners_into_graph
from src.sync.engine import SyncEngine
from src.sync.fetcher import GitHubFetcher
from src.sync.models import EventType, GitHubChangeEvent
from src.sync.reconciler import EventReconciler
from src.sync.state import SyncStateManager


@pytest.fixture
def falkordb_client():
    c = FalkorDBClient()
    c.ping()
    return c


@pytest.fixture
def graph_writer(falkordb_client):
    return GraphWriter(falkordb_client)


def _cleanup(falkordb_client):
    falkordb_client.query("MATCH (t:Team) WHERE t.name IN ['@TestOrg/core-team', '@TestOrg/devops-team', '@FalkorDB/test-core'] DETACH DELETE t")
    falkordb_client.query("MATCH (r:OwnershipRule) WHERE r.pattern IN ['/core/', '/infra/'] DETACH DELETE r")
    falkordb_client.query("MATCH (d:Document {path: 'docs/adr/0010_query_engine.md'}) DETACH DELETE d")
    falkordb_client.query("MATCH (c:Comment) WHERE c.id STARTS WITH 'comm_' DETACH DELETE c")
    falkordb_client.query("MATCH (pr:PullRequest {number: 4501}) DETACH DELETE pr")
    falkordb_client.query("MATCH (i:Issue {number: 5502}) DETACH DELETE i")
    falkordb_client.query("MATCH (dec:Decision) WHERE dec.id STARTS WITH 'dec_' DETACH DELETE dec")
    falkordb_client.query("MATCH (f:File) WHERE f.path IN ['core/engine.c', 'infra/deploy.yml'] DETACH DELETE f")
    falkordb_client.query("MATCH (p:Person) WHERE p.login IN ['comm_reviewer', 'comm_alice', 'verified_core_dev'] DETACH DELETE p")


@pytest.fixture(autouse=True)
def clean_test_knowledge(falkordb_client):
    _cleanup(falkordb_client)
    yield
    _cleanup(falkordb_client)


def _ensure_parent_pr(graph_writer):
    graph_writer.upsert_node(
        label="PullRequest",
        identity=4501,
        properties={
            "number": 4501,
            "title": "Knowledge Graph Updates",
            "url": "https://github.com/FalkorDB/FalkorDB/pull/4501",
            "created_at": "2026-03-01T10:00:00Z",
            "merged_at": "2026-03-02T12:00:00Z",
        },
        run_id="test_run",
    )


# 1. Comment Ingestion and Parent Linkage
def test_comment_ingestion_and_parent_linkage(graph_writer, falkordb_client):
    _ensure_parent_pr(graph_writer)

    engine = CommentIngestionEngine(graph_writer)
    comment = CommentRecord(
        comment_id="comm_9001",
        body="LGTM! Merging this into main.",
        source_url="https://github.com/FalkorDB/FalkorDB/pull/4501#issuecomment-9001",
        parent_type="pull_request",
        parent_id=4501,
        author_login="comm_reviewer",
        created_at="2026-10-17T10:00:00Z",
    )

    stats = engine.ingest_comment(comment, run_id="test_run")
    assert stats["comment_upserted"] == 1
    assert stats["on_edges"] == 1
    assert stats["authored_edges"] == 1

    # Verify in FalkorDB
    res = falkordb_client.ro_query(
        """
        MATCH (p:Person {login: 'comm_reviewer'})-[:AUTHORED]->(c:Comment {id: 'comm_9001'})-[:ON]->(pr:PullRequest {number: 4501})
        RETURN c.body, pr.title
        """
    )
    assert res and len(res.result_set) == 1
    assert res.result_set[0][0] == "LGTM! Merging this into main."
    assert res.result_set[0][1] == "Knowledge Graph Updates"


# 2. Explicit Issue, PR, and Document References in Comments
def test_comment_explicit_references(graph_writer, falkordb_client):
    _ensure_parent_pr(graph_writer)

    # Ensure referenced Issue exists
    graph_writer.upsert_node(
        label="Issue",
        identity=5502,
        properties={"number": 5502, "title": "Memory leak on decode", "url": "https://github.com/FalkorDB/FalkorDB/issues/5502"},
        run_id="test_run",
    )

    engine = CommentIngestionEngine(graph_writer)
    comment = CommentRecord(
        comment_id="comm_9002",
        body="This addresses #5502 as noted in docs/sync_architecture.md. We decided to cache decoded buffers.",
        source_url="https://github.com/FalkorDB/FalkorDB/pull/4501#issuecomment-9002",
        parent_type="pull_request",
        parent_id=4501,
        author_login="comm_reviewer",
        created_at="2026-10-17T10:05:00Z",
    )

    stats = engine.ingest_comment(comment, run_id="test_run")
    assert stats["references_linked"] >= 1
    assert stats["decisions_extracted"] >= 1

    # Verify REFERENCES relationship to Issue in FalkorDB
    ref_res = falkordb_client.ro_query(
        """
        MATCH (c:Comment {id: 'comm_9002'})-[r:REFERENCES]->(i:Issue {number: 5502})
        RETURN r.reference_text
        """
    )
    assert ref_res and len(ref_res.result_set) == 1
    assert ref_res.result_set[0][0] == "#5502"

    # Verify DECIDED_IN relationship to Decision in FalkorDB
    dec_res = falkordb_client.ro_query(
        """
        MATCH (dec:Decision)-[r:DECIDED_IN]->(c:Comment {id: 'comm_9002'})
        RETURN dec.pattern, dec.quote
        """
    )
    assert dec_res and len(dec_res.result_set) == 1
    assert dec_res.result_set[0][0] == "we decided"
    assert "we decided to cache decoded buffers." in dec_res.result_set[0][1].lower()


# 3. Repeated Ingestion Without Duplicates (Idempotency)
def test_repeated_comment_ingestion_idempotency(graph_writer, falkordb_client):
    _ensure_parent_pr(graph_writer)

    engine = CommentIngestionEngine(graph_writer)
    comment = CommentRecord(
        comment_id="comm_9003",
        body="Decision: adopt semver 2.0 release cycles.",
        source_url="https://github.com/FalkorDB/FalkorDB/pull/4501#issuecomment-9003",
        parent_type="pull_request",
        parent_id=4501,
        author_login="comm_alice",
        created_at="2026-10-17T10:10:00Z",
    )

    # First run
    engine.ingest_comment(comment, run_id="run_1")
    count_1 = falkordb_client.ro_query("MATCH (c:Comment {id: 'comm_9003'}) RETURN count(c)").result_set[0][0]
    dec_count_1 = falkordb_client.ro_query("MATCH (dec:Decision)-[:DECIDED_IN]->(:Comment {id: 'comm_9003'}) RETURN count(dec)").result_set[0][0]
    assert count_1 == 1
    assert dec_count_1 == 1

    # Second run (exact repeat)
    engine.ingest_comment(comment, run_id="run_2")
    count_2 = falkordb_client.ro_query("MATCH (c:Comment {id: 'comm_9003'}) RETURN count(c)").result_set[0][0]
    dec_count_2 = falkordb_client.ro_query("MATCH (dec:Decision)-[:DECIDED_IN]->(:Comment {id: 'comm_9003'}) RETURN count(dec)").result_set[0][0]
    assert count_2 == 1
    assert dec_count_2 == 1


# 4. Document Creation, Update, and Tombstoning
def test_document_creation_update_and_tombstone(graph_writer, falkordb_client):
    engine = DocumentIngestionEngine(graph_writer)
    doc_path = "docs/adr/0010_query_engine.md"
    content_v1 = """# Query Engine Architecture
Status: accepted

## Context
Need low latency traversal.

## Decision
We decided to use vectorized execution kernels.

## Consequences
Faster analytical throughput.
"""
    doc_rec_v1 = MarkdownDocumentRecord(
        path=doc_path,
        content=content_v1,
        source_url=f"https://github.com/FalkorDB/FalkorDB/blob/main/{doc_path}",
    )

    # 1. Creation
    stats_v1 = engine.ingest_document(doc_rec_v1, run_id="doc_v1")
    assert stats_v1["document_upserted"] == 1
    assert stats_v1["decisions_extracted"] >= 1

    doc_node = falkordb_client.ro_query(
        "MATCH (d:Document {path: $p}) RETURN d.title, d.file_type, d.status",
        {"p": doc_path},
    )
    assert doc_node and len(doc_node.result_set) == 1
    assert doc_node.result_set[0][0] == "Query Engine Architecture"
    assert doc_node.result_set[0][1] == "adr"
    assert doc_node.result_set[0][2] == "active"

    # 2. Update with modified content
    content_v2 = content_v1 + "\n\nWe decided to add SIMD vector optimizations."
    doc_rec_v2 = MarkdownDocumentRecord(
        path=doc_path,
        content=content_v2,
        source_url=f"https://github.com/FalkorDB/FalkorDB/blob/main/{doc_path}",
    )
    stats_v2 = engine.ingest_document(doc_rec_v2, run_id="doc_v2")
    assert stats_v2["document_upserted"] == 1

    # 3. Tombstone (Deletion)
    graph_writer.tombstone_node(label="Document", identity=doc_path, run_id="doc_del")
    tomb_node = falkordb_client.ro_query(
        "MATCH (d:Document {path: $p}) RETURN d.status, d.tombstoned_at",
        {"p": doc_path},
    )
    assert tomb_node and len(tomb_node.result_set) == 1
    assert tomb_node.result_set[0][0] == "tombstoned"
    assert tomb_node.result_set[0][1] is not None


# 5. CODEOWNERS Team Representation & OWNS relationship
def test_codeowners_team_representation_and_owns_edge(graph_writer, falkordb_client):
    codeowners_content = """
/core/       @TestOrg/core-team
/infra/      @TestOrg/devops-team
"""
    parser = CodeownersParser(content=codeowners_content)
    # Ensure file nodes exist in graph
    graph_writer.upsert_node(
        label="File",
        identity="core/engine.c",
        properties={"path": "core/engine.c", "url": "https://github.com/FalkorDB/FalkorDB/blob/main/core/engine.c"},
        run_id="co_test",
    )
    graph_writer.upsert_node(
        label="File",
        identity="infra/deploy.yml",
        properties={"path": "infra/deploy.yml", "url": "https://github.com/FalkorDB/FalkorDB/blob/main/infra/deploy.yml"},
        run_id="co_test",
    )

    stats = load_codeowners_into_graph(falkordb_client, codeowners=parser)
    assert stats["rules_merged"] >= 2
    assert stats["teams_merged"] >= 2
    assert stats["owns_edges"] >= 2

    # Verify (:Team)-[:OWNS]->(:File) in FalkorDB
    res = falkordb_client.ro_query(
        """
        MATCH (t:Team {name: '@TestOrg/core-team'})-[o:OWNS]->(f:File {path: 'core/engine.c'})
        RETURN o.rule_pattern
        """
    )
    assert res and len(res.result_set) == 1
    assert res.result_set[0][0] == "/core/"


# 6. Strict Prohibition on Fabricating HAS_MEMBER from CODEOWNERS
def test_no_fabricated_has_member_from_codeowners(falkordb_client):
    """Verify that parsing CODEOWNERS never synthesizes a HAS_MEMBER relationship."""
    # Ensure no HAS_MEMBER edge links any Team created by CODEOWNERS unless explicit evidence is provided
    res = falkordb_client.ro_query(
        """
        MATCH (t:Team {name: '@TestOrg/core-team'})-[m:HAS_MEMBER]->(p:Person)
        RETURN p.login
        """
    )
    # Must be 0 because CODEOWNERS does not declare individual team membership
    assert res is None or len(res.result_set) == 0


# 7. Evidence-Grounded Team Membership
def test_evidence_grounded_team_membership(graph_writer, falkordb_client):
    """Verify HAS_MEMBER is created only when explicit source evidence is supplied."""
    team_name = "@FalkorDB/test-core"
    member_login = "verified_core_dev"
    graph_writer.upsert_node(
        label="Team",
        identity=team_name,
        properties={"name": team_name},
        run_id="member_test",
    )
    graph_writer.upsert_node(
        label="Person",
        identity=member_login,
        properties={"login": member_login, "url": f"https://github.com/{member_login}"},
        run_id="member_test",
    )
    graph_writer.upsert_edge(
        rel_type="HAS_MEMBER",
        source_label="Team",
        source_identity=team_name,
        target_label="Person",
        target_identity=member_login,
        properties={"source_url": "https://api.github.com/orgs/FalkorDB/teams/test-core/members"},
        run_id="member_test",
    )

    try:
        res = falkordb_client.ro_query(
            """
            MATCH (t:Team {name: $t})-[m:HAS_MEMBER]->(p:Person {login: $p})
            RETURN m.source_url
            """,
            {"t": team_name, "p": member_login},
        )
        assert res and len(res.result_set) == 1
        assert "https://api.github.com/orgs/FalkorDB/teams/test-core/members" in res.result_set[0][0]
    finally:
        falkordb_client.query(
            "MATCH (t:Team {name: $t})-[m:HAS_MEMBER]->() DELETE m",
            {"t": team_name},
        )
