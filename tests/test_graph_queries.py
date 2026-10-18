"""Tests for the three core FalkorDB validation queries."""

import pytest
from src.db import FalkorDBClient
from src.graph.queries import (
    find_file_co_changes,
    get_reviewer_distribution,
    trace_pr_to_issues,
)


@pytest.fixture(scope="module")
def client():
    c = FalkorDBClient()
    # Confirm DB is connected
    health = c.ping()
    assert health["status"] == "healthy"
    return c


def test_reviewer_distribution_has_evidence(client):
    reviewers = get_reviewer_distribution(client, limit=5)
    assert len(reviewers) > 0
    top = reviewers[0]
    assert "reviewer" in top
    assert "reviewer_url" in top
    assert top["reviewer_url"].startswith("https://github.com/")
    assert top["review_count"] >= 1
    assert len(top["evidence_pr_urls"]) >= 1
    for url in top["evidence_pr_urls"]:
        assert url.startswith("https://github.com/FalkorDB/FalkorDB/pull/")


def test_pr_to_issue_tracing(client):
    traces = trace_pr_to_issues(client, limit=5)
    assert len(traces) > 0
    item = traces[0]
    assert item["pr_number"] > 0
    assert item["pr_url"].startswith("https://github.com/FalkorDB/FalkorDB/pull/")
    assert item["issue_number"] > 0
    assert item["issue_url"].startswith("https://github.com/FalkorDB/FalkorDB/issues/")
    assert item["issue_title"] != ""
    assert item["reporter_login"] is not None


def test_file_co_changes(client):
    co_changes = find_file_co_changes(client, limit=5)
    assert len(co_changes) > 0
    pair = co_changes[0]
    assert "file_a" in pair
    assert "file_b" in pair
    assert pair["co_change_count"] >= 1
    assert len(pair["evidence_pr_urls"]) >= 1
    for url in pair["evidence_pr_urls"]:
        assert url.startswith("https://github.com/FalkorDB/FalkorDB/pull/")


def test_trace_documented_decisions(client):
    from src.graph.queries.core import trace_documented_decisions
    decisions = trace_documented_decisions(client, limit=5)
    assert len(decisions) > 0
    d = decisions[0]
    assert d["pr_number"] > 0
    assert d["issue_number"] > 0
    assert d["pr_url"].startswith("https://github.com/FalkorDB/FalkorDB/pull/")
    assert d["issue_url"].startswith("https://github.com/FalkorDB/FalkorDB/issues/")
    assert d["decision_type"] == "EXPLICIT_ISSUE_RESOLUTION"
    assert d["decided_at"] is not None

    # Test targeted PR
    pr_3339_dec = trace_documented_decisions(client, pr_number=3339)
    assert len(pr_3339_dec) == 1
    assert pr_3339_dec[0]["issue_number"] == 3338


def test_find_source_backed_documentation(client):
    from src.graph.queries.core import find_source_backed_documentation
    docs = find_source_backed_documentation(client, limit=5)
    assert len(docs) > 0
    d = docs[0]
    assert "path" in d
    assert "url" in d
    assert d["url"].startswith("https://github.com/FalkorDB/FalkorDB/")
    assert any(d["path"].endswith(ext) for ext in (".md", ".txt", "CODEOWNERS"))

