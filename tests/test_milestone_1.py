"""Milestone 1 Acceptance Test Suite.

Verifies:
1. Schema indexes are operational in FalkorDB repo_kg.
2. Ownership drift correctly identifies author vs reviewer divergence across 3 real repository modules.
3. Every finding terminates in authentic public GitHub PR URLs with zero hallucinations.
"""

import pytest
from src.db import FalkorDBClient
from src.graph.queries.drift import detect_ownership_drift
from src.graph.schema import ensure_schema_indexes


@pytest.fixture(scope="module")
def client():
    c = FalkorDBClient()
    health = c.ping()
    assert health["status"] == "healthy"
    return c


def test_schema_indexes_operational(client):
    """Verify schema indexes exist and are operational in FalkorDB."""
    ensure_schema_indexes(client)
    res = client.ro_query("CALL db.indexes()")
    assert res and res.result_set
    # Convert result rows to set of indexed labels
    indexed_labels = set()
    for row in res.result_set:
        label = row[0]
        indexed_labels.add(label)

    assert "Person" in indexed_labels
    assert "PullRequest" in indexed_labels
    assert "Issue" in indexed_labels
    assert "File" in indexed_labels


def test_ownership_drift_module_1_pending_runtime(client):
    """Verify ownership drift for graph/src/runtime/pending.rs."""
    mod = "graph/src/runtime/pending.rs"
    drift = detect_ownership_drift(client, mod)

    assert drift["status"] == "analyzed"
    assert drift["file_path"] == mod
    assert drift["total_prs"] == 3
    assert drift["bus_factor"] == 2
    assert "AviAvni" in drift["human_authors"]
    assert "DvirDukhan" in drift["human_authors"]
    assert "DvirDukhan" in drift["human_reviewers"]
    assert "AviAvni" in drift["human_reviewers"]
    assert drift["drift_score"] > 0.0

    # Ensure authentic evidence PR URLs
    assert len(drift["evidence_prs"]) == 3
    for pr in drift["evidence_prs"]:
        assert pr["url"].startswith("https://github.com/FalkorDB/FalkorDB/pull/")
        assert pr["pr_number"] in [3339, 3307, 3189]


def test_ownership_drift_module_2_bulk_insert(client):
    """Verify ownership drift for src/commands/bulk_insert.rs."""
    mod = "src/commands/bulk_insert.rs"
    drift = detect_ownership_drift(client, mod)

    assert drift["status"] == "analyzed"
    assert drift["file_path"] == mod
    assert drift["total_prs"] == 3
    assert drift["bus_factor"] == 2
    assert "AviAvni" in drift["human_authors"]
    assert "DvirDukhan" in drift["human_authors"]
    assert drift["drift_score"] > 0.0

    for pr in drift["evidence_prs"]:
        assert pr["url"].startswith("https://github.com/FalkorDB/FalkorDB/pull/")
        assert pr["pr_number"] in [3339, 3307, 3290]


def test_ownership_drift_module_3_test_rdb_load_high_divergence(client):
    """Verify complete divergence (score=1.0) on tests/flow/test_rdb_load.py."""
    mod = "tests/flow/test_rdb_load.py"
    drift = detect_ownership_drift(client, mod)

    assert drift["status"] == "analyzed"
    assert drift["file_path"] == mod
    assert drift["total_prs"] >= 3
    assert drift["bus_factor"] == 2
    assert "swilly22" in drift["human_authors"]
    assert "AviAvni" in drift["human_authors"]

    # DvirDukhan reviewed but never authored
    assert "DvirDukhan" in drift["reviewers_without_authorship"]
    # AviAvni authored but never reviewed
    assert "AviAvni" in drift["authors_without_reviews"]

    # High divergence score
    assert drift["drift_score"] >= 0.7

    for pr in drift["evidence_prs"]:
        assert pr["url"].startswith("https://github.com/FalkorDB/FalkorDB/pull/")
        assert pr["pr_number"] > 0


def test_nonexistent_file_refusal(client):
    """Verify clear refusal message for nonexistent module (0 hallucination)."""
    fake_mod = "src/nonexistent/fake_module.c"
    drift = detect_ownership_drift(client, fake_mod)
    assert drift["status"] == "not_found"
    assert "Evidence path not found" in drift["message"]
    assert drift["bus_factor"] == 0
    assert drift["drift_score"] == 0.0
    assert len(drift["evidence_prs"]) == 0
