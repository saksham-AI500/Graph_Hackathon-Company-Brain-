"""Comprehensive test suite for Phase 4: Knowledge Logic, Ownership Intelligence & Temporal Reasoning."""

from datetime import datetime, timezone
import math
import pytest
from src.db import FalkorDBClient
from src.graph.algorithms import find_explanation_path, run_maintainer_pagerank
from src.graph.writer import GraphWriter
from src.knowledge.scoring import (
    AUTHORED_WEIGHT,
    COMMENTED_WEIGHT,
    DEFAULT_HALF_LIFE_DAYS,
    REVIEWED_WEIGHT,
    calculate_knows_for_file,
    calculate_knows_for_person,
    get_top_experts_for_file,
    is_bot_account,
)
from src.knowledge.stale_docs import (
    audit_repository_documentation_staleness,
    check_document_staleness,
)
from src.knowledge.temporal import (
    is_edge_active_at,
    is_node_active_at,
    is_timestamp_prior_or_equal,
    normalize_utc_timestamp,
)
from src.ownership.codeowners import CodeownersParser
from src.ownership.discrepancy import evaluate_ownership_discrepancy
from src.ownership.metrics import calculate_bus_factor, calculate_bus_factor_detailed
from src.ownership.orphaned import detect_orphaned_ownership


@pytest.fixture
def falkordb_client():
    c = FalkorDBClient()
    c.ping()
    return c


@pytest.fixture
def graph_writer(falkordb_client):
    return GraphWriter(falkordb_client)


def _cleanup_test_data(client):
    client.query("MATCH (d:Document {path: 'docs/test_staleness_doc.md'}) DETACH DELETE d")
    client.query("MATCH (f:File {path: 'src/test_knowledge_file.c'}) DETACH DELETE f")
    client.query("MATCH (pr:PullRequest) WHERE pr.number IN [7701, 7702, 7703] DETACH DELETE pr")
    client.query("MATCH (p:Person) WHERE p.login IN ['test_alice', 'test_bob', 'test_carol', 'test_bot[bot]'] DETACH DELETE p")
    client.query("MATCH (r:OwnershipRule) WHERE r.pattern IN ['/src/test_sub/'] DETACH DELETE r")
    client.query("MATCH (c:Comment) WHERE c.id IN ['comm_test_1', 'comm_test_2'] DETACH DELETE c")


@pytest.fixture(autouse=True)
def clean_test_env(falkordb_client):
    _cleanup_test_data(falkordb_client)
    yield
    _cleanup_test_data(falkordb_client)


# 1. Declared vs. Observed Ownership and Precedence
def test_declared_vs_observed_ownership_and_overlapping_rules(falkordb_client):
    codeowners_text = """
/src/               @FalkorDB/general-team
/src/test_sub/      @FalkorDB/specialist-team
"""
    parser = CodeownersParser(content=codeowners_text)
    match = parser.match("src/test_sub/engine.c")
    assert match.matched is True
    assert match.rule_pattern == "/src/test_sub/"
    assert "@FalkorDB/specialist-team" in match.owners
    # Overlapping rules
    assert len(match.overlapping_rules) == 2
    assert match.overlapping_rules[0].pattern == "/src/"
    assert match.overlapping_rules[1].pattern == "/src/test_sub/"


# 2. KNOWS Scoring Weights and 90-day Exponential Decay
def test_knows_scoring_weights_and_exponential_decay(graph_writer, falkordb_client):
    test_file = "src/test_knowledge_file.c"
    graph_writer.upsert_node(
        label="File",
        identity=test_file,
        properties={"path": test_file, "url": f"https://github.com/FalkorDB/FalkorDB/blob/main/{test_file}"},
        run_id="knows_test",
    )

    # Alice authored PR #7701 merged at T0 (2026-07-01T00:00:00Z)
    graph_writer.upsert_node(
        label="PullRequest",
        identity=7701,
        properties={
            "number": 7701,
            "title": "Alice commit",
            "url": "https://github.com/FalkorDB/FalkorDB/pull/7701",
            "created_at": "2026-06-30T10:00:00Z",
            "merged_at": "2026-07-01T00:00:00Z",
        },
        run_id="knows_test",
    )
    graph_writer.upsert_node(
        label="Person",
        identity="test_alice",
        properties={"login": "test_alice", "url": "https://github.com/test_alice"},
        run_id="knows_test",
    )
    graph_writer.upsert_edge(
        rel_type="AUTHORED",
        source_label="Person",
        source_identity="test_alice",
        target_label="PullRequest",
        target_identity=7701,
        properties={"source_url": "https://github.com/FalkorDB/FalkorDB/pull/7701"},
        run_id="knows_test",
    )
    graph_writer.upsert_edge(
        rel_type="MODIFIES",
        source_label="PullRequest",
        source_identity=7701,
        target_label="File",
        target_identity=test_file,
        properties={"source_url": "https://github.com/FalkorDB/FalkorDB/pull/7701"},
        run_id="knows_test",
    )

    # Bob reviewed PR #7701 at T0
    graph_writer.upsert_node(
        label="Person",
        identity="test_bob",
        properties={"login": "test_bob", "url": "https://github.com/test_bob"},
        run_id="knows_test",
    )
    graph_writer.upsert_edge(
        rel_type="REVIEWED",
        source_label="Person",
        source_identity="test_bob",
        target_label="PullRequest",
        target_identity=7701,
        properties={"source_url": "https://github.com/FalkorDB/FalkorDB/pull/7701#pullrequestreview-1"},
        run_id="knows_test",
    )
    # Set submitted_at on REVIEWED edge
    falkordb_client.query(
        """
        MATCH (p:Person {login: 'test_bob'})-[r:REVIEWED]->(pr:PullRequest {number: 7701})
        SET r.submitted_at = '2026-07-01T00:00:00Z'
        """
    )

    # Evaluate at T = 2026-07-01 (age = 0 days):
    scores_t0 = calculate_knows_for_file(falkordb_client, test_file, as_of="2026-07-01T00:00:00Z")
    alice_s0 = next(s for s in scores_t0 if s.person_login == "test_alice")
    bob_s0 = next(s for s in scores_t0 if s.person_login == "test_bob")

    # At age 0: exp(0) = 1.0 -> weights should be exact: authored=3.0, reviewed=2.0
    assert alice_s0.score == AUTHORED_WEIGHT
    assert alice_s0.raw_score == AUTHORED_WEIGHT
    assert bob_s0.score == REVIEWED_WEIGHT
    assert bob_s0.raw_score == REVIEWED_WEIGHT

    # Evaluate at T = 90 days later (2026-09-29T00:00:00Z):
    # age = 90 days -> decay factor = exp(-90/90) = exp(-1.0) = ~0.367879
    scores_t90 = calculate_knows_for_file(falkordb_client, test_file, as_of="2026-09-29T00:00:00Z")
    alice_s90 = next(s for s in scores_t90 if s.person_login == "test_alice")
    bob_s90 = next(s for s in scores_t90 if s.person_login == "test_bob")

    expected_decay = math.exp(-1.0)
    assert math.isclose(alice_s90.score, 3.0 * expected_decay, rel_tol=1e-3)
    assert math.isclose(bob_s90.score, 2.0 * expected_decay, rel_tol=1e-3)
    # Raw un-decayed score should remain intact
    assert alice_s90.raw_score == 3.0
    assert bob_s90.raw_score == 2.0


# 3. Bot Exclusion in KNOWS and PageRank
def test_bot_exclusion_in_knows_scores(graph_writer, falkordb_client):
    test_file = "src/test_knowledge_file.c"
    graph_writer.upsert_node(
        label="File",
        identity=test_file,
        properties={"path": test_file, "url": f"https://github.com/FalkorDB/FalkorDB/blob/main/{test_file}"},
        run_id="bot_test",
    )
    graph_writer.upsert_node(
        label="PullRequest",
        identity=7702,
        properties={
            "number": 7702,
            "title": "Dependabot update",
            "url": "https://github.com/FalkorDB/FalkorDB/pull/7702",
            "created_at": "2026-08-01T10:00:00Z",
            "merged_at": "2026-08-02T12:00:00Z",
        },
        run_id="bot_test",
    )
    graph_writer.upsert_node(
        label="Person",
        identity="test_bot[bot]",
        properties={"login": "test_bot[bot]", "url": "https://github.com/apps/test_bot"},
        run_id="bot_test",
    )
    graph_writer.upsert_edge(
        rel_type="AUTHORED",
        source_label="Person",
        source_identity="test_bot[bot]",
        target_label="PullRequest",
        target_identity=7702,
        properties={"source_url": "https://github.com/FalkorDB/FalkorDB/pull/7702"},
        run_id="bot_test",
    )
    graph_writer.upsert_edge(
        rel_type="MODIFIES",
        source_label="PullRequest",
        source_identity=7702,
        target_label="File",
        target_identity=test_file,
        properties={"source_url": "https://github.com/FalkorDB/FalkorDB/pull/7702"},
        run_id="bot_test",
    )

    scores = calculate_knows_for_file(falkordb_client, test_file, include_bots=False)
    assert not any(s.person_login == "test_bot[bot]" for s in scores)


# 4. Bus Factor Explainability & Zero-Activity Cases
def test_bus_factor_calculations_and_edge_cases():
    # Edge case 1: Empty activity -> bus factor = 0, HIGH risk
    empty_report = calculate_bus_factor_detailed([])
    assert empty_report.bus_factor == 0
    assert empty_report.risk_level == "HIGH"
    assert empty_report.is_insufficient_evidence is True

    # Edge case 2: Single-person monopoly (100% share) -> bus factor = 1, HIGH risk
    single_person = [
        {"login": "monopolist", "weight": 10.0, "timestamp": "2026-10-01T00:00:00Z"}
    ]
    report_single = calculate_bus_factor_detailed(single_person, cutoff_timestamp="2026-10-02T00:00:00Z")
    assert report_single.bus_factor == 1
    assert report_single.risk_level == "HIGH"
    assert report_single.key_contributors == ["monopolist"]

    # Edge case 3: Balanced distribution across 5 contributors -> bus factor = 3, LOW risk
    balanced = [
        {"login": f"dev_{i}", "weight": 2.0, "timestamp": "2026-10-01T00:00:00Z"}
        for i in range(1, 6)
    ]
    report_balanced = calculate_bus_factor_detailed(balanced, cutoff_timestamp="2026-10-02T00:00:00Z")
    assert report_balanced.bus_factor == 3
    assert report_balanced.risk_level == "LOW"
    assert len(report_balanced.key_contributors) >= 3

    # Edge case 4: Tied contributions sorting deterministically
    tied = [
        {"login": "zeta", "weight": 5.0, "timestamp": "2026-10-01T00:00:00Z"},
        {"login": "alpha", "weight": 5.0, "timestamp": "2026-10-01T00:00:00Z"},
    ]
    report_tied = calculate_bus_factor_detailed(tied, cutoff_timestamp="2026-10-02T00:00:00Z")
    # alpha comes before zeta alphabetically
    assert report_tied.ranked_contributors[0]["login"] == "alpha"
    assert report_tied.ranked_contributors[1]["login"] == "zeta"


# 5. Stale-Document Detection with Grounded File Links & Cutoff
def test_stale_document_detection_with_grounded_links(graph_writer, falkordb_client):
    doc_path = "docs/test_staleness_doc.md"
    file_path = "src/test_knowledge_file.c"

    # 1. Document created at 2026-05-01
    graph_writer.upsert_node(
        label="Document",
        identity=doc_path,
        properties={
            "path": doc_path,
            "title": "Architecture Guide",
            "url": f"https://github.com/FalkorDB/FalkorDB/blob/main/{doc_path}",
            "observed_at": "2026-05-01T12:00:00Z",
            "file_type": "documentation",
        },
        run_id="stale_test",
    )
    graph_writer.upsert_node(
        label="File",
        identity=file_path,
        properties={"path": file_path, "url": f"https://github.com/FalkorDB/FalkorDB/blob/main/{file_path}"},
        run_id="stale_test",
    )
    # Direct grounded link
    graph_writer.upsert_edge(
        rel_type="REFERENCES",
        source_label="Document",
        source_identity=doc_path,
        target_label="File",
        target_identity=file_path,
        properties={"reference_text": file_path, "reference_type": "file", "source_url": "https://github.com/FalkorDB/FalkorDB/docs"},
        run_id="stale_test",
    )

    # 2. File was modified later at 2026-06-15 by PR #7703
    graph_writer.upsert_node(
        label="PullRequest",
        identity=7703,
        properties={
            "number": 7703,
            "title": "Refactor engine",
            "url": "https://github.com/FalkorDB/FalkorDB/pull/7703",
            "created_at": "2026-06-14T10:00:00Z",
            "merged_at": "2026-06-15T10:00:00Z",
        },
        run_id="stale_test",
    )
    graph_writer.upsert_edge(
        rel_type="MODIFIES",
        source_label="PullRequest",
        source_identity=7703,
        target_label="File",
        target_identity=file_path,
        properties={"source_url": "https://github.com/FalkorDB/FalkorDB/pull/7703"},
        run_id="stale_test",
    )

    # 3. Check staleness at as_of = 2026-07-01 (PR 7703 is visible) -> POTENTIALLY_STALE
    findings_late = check_document_staleness(falkordb_client, doc_path, as_of="2026-07-01T00:00:00Z")
    assert len(findings_late) == 1
    f_late = findings_late[0]
    assert f_late.status == "POTENTIALLY_STALE"
    assert f_late.diff_days > 40.0
    assert len(f_late.modifying_prs) == 1
    assert f_late.modifying_prs[0]["pr_number"] == 7703

    # 4. Check staleness at as_of = 2026-05-10 (before PR 7703) -> UP_TO_DATE (future PR excluded!)
    findings_early = check_document_staleness(falkordb_client, doc_path, as_of="2026-05-10T00:00:00Z")
    assert len(findings_early) == 1
    assert findings_early[0].status == "UP_TO_DATE"


# 6. Orphaned Owner Detection with Configurable Threshold
def test_orphaned_owner_detection_threshold(graph_writer, falkordb_client):
    # Rule declared for test_carol who has no observed activity
    graph_writer.upsert_node(
        label="OwnershipRule",
        identity="/src/test_sub/",
        properties={"pattern": "/src/test_sub/", "source_url": "https://github.com/FalkorDB/FalkorDB/blob/main/CODEOWNERS"},
        run_id="orphan_test",
    )
    graph_writer.upsert_node(
        label="Person",
        identity="test_carol",
        properties={"login": "test_carol", "url": "https://github.com/test_carol"},
        run_id="orphan_test",
    )
    graph_writer.upsert_edge(
        rel_type="DECLARES_OWNER",
        source_label="OwnershipRule",
        source_identity="/src/test_sub/",
        target_label="Person",
        target_identity="test_carol",
        properties={"source_url": "https://github.com/FalkorDB/FalkorDB/blob/main/CODEOWNERS"},
        run_id="orphan_test",
    )

    rep = detect_orphaned_ownership(falkordb_client, inactivity_threshold_days=90.0, as_of="2026-10-15T00:00:00Z")
    carol_finding = next((f for f in rep.findings if f.owner_name == "test_carol"), None)
    assert carol_finding is not None
    assert carol_finding.status == "NO_OBSERVED_ACTIVITY"
    assert carol_finding.rule_pattern == "/src/test_sub/"


# 7. As-Of Boundary Exclusion (T-1, T, T+1)
def test_temporal_as_of_boundary_conditions():
    cutoff = "2026-10-15T12:00:00Z"
    t_minus_1 = "2026-10-15T11:59:59Z"
    t_exact = "2026-10-15T12:00:00Z"
    t_plus_1 = "2026-10-15T12:00:01Z"

    # Prior and equal are valid
    assert is_timestamp_prior_or_equal(t_minus_1, cutoff) is True
    assert is_timestamp_prior_or_equal(t_exact, cutoff) is True
    # Future is strictly excluded
    assert is_timestamp_prior_or_equal(t_plus_1, cutoff) is False

    # Edge validity: [valid_from, valid_to)
    assert is_edge_active_at("2026-10-01T00:00:00Z", "2026-10-15T12:00:00Z", t_minus_1) is True
    # At exact valid_to, edge is closed
    assert is_edge_active_at("2026-10-01T00:00:00Z", "2026-10-15T12:00:00Z", t_exact) is False
    assert is_edge_active_at("2026-10-01T00:00:00Z", "2026-10-15T12:00:00Z", t_plus_1) is False

    # Tombstoned node active before tombstone
    assert is_node_active_at("2026-10-01T00:00:00Z", "2026-10-15T12:00:00Z", t_minus_1) is True
    assert is_node_active_at("2026-10-01T00:00:00Z", "2026-10-15T12:00:00Z", t_exact) is False


# 8. PageRank and Shortest Path Explanations
def test_pagerank_and_shortest_path_algorithms(falkordb_client):
    ranks = run_maintainer_pagerank(falkordb_client, limit=5, include_bots=False)
    assert len(ranks) > 0
    # Every reviewer must be human
    assert all("[bot]" not in r["login"].lower() for r in ranks)

    # Explanation path from PR #3339 to linked issue #3338
    path = find_explanation_path(falkordb_client, pr_number=3339, target_identifier=3338)
    assert path is not None
    assert path["hop_count"] >= 1
    assert "PullRequest" in path["readable_summary"]
    assert "Issue" in path["readable_summary"]
    assert len(path["evidence_urls"]) > 0
