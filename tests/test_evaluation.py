"""Automated Evaluation & Temporal Backtesting Test Suite for RepoBrain."""

import pytest
from src.db import FalkorDBClient
from src.evaluation.benchmark import get_benchmark_questions
from src.evaluation.evaluator import ComparativeEvaluator
from src.evaluation.temporal import (
    find_historical_reviewers_temporal,
    find_related_co_changes_temporal,
    trace_pr_to_issues_temporal,
    get_pr_creation_cutoff,
)


@pytest.fixture
def client():
    c = FalkorDBClient()
    c.ping()
    return c


@pytest.fixture
def evaluator(client):
    return ComparativeEvaluator(client)


def test_benchmark_dataset_integrity():
    """Verify benchmark dataset has 20 questions with complete fields and ground truth."""
    questions = get_benchmark_questions()
    assert len(questions) == 20

    categories = {q.category for q in questions}
    assert "REVIEWER_ROUTING" in categories
    assert "DECISION_TRACING" in categories
    assert "CO_CHANGE" in categories
    assert "OWNERSHIP_DISCREPANCY" in categories
    assert "REFUSAL" in categories

    # Verify ground truth URLs and keywords
    for q in questions:
        assert q.id.startswith("BENCH-")
        assert len(q.question) > 10
        assert len(q.expected_answer_keywords) > 0
        if not q.should_refuse:
            assert len(q.ground_truth_urls) > 0


def test_temporal_cutoff_excludes_future_prs(client):
    """Verify PRs merged after the cutoff are excluded from historical evidence."""
    # PR #3339 creation cutoff
    cutoff = "2026-10-14T09:03:20Z"
    target_files = ["tests/flow/test_rdb_load.py"]

    # Without cutoff: includes PRs merged after cutoff (like PR #3342 merged at 18:39)
    rev_all = find_historical_reviewers_temporal(
        client, target_files, exclude_pr_number=3339, cutoff_timestamp=None
    )
    all_evidence_prs = []
    for r in rev_all:
        all_evidence_prs.extend(r["evidence_pr_urls"])

    # With cutoff: strictly excludes PR #3342
    rev_temporal = find_historical_reviewers_temporal(
        client, target_files, exclude_pr_number=3339, cutoff_timestamp=cutoff
    )
    temporal_evidence_prs = []
    for r in rev_temporal:
        temporal_evidence_prs.extend(r["evidence_pr_urls"])

    assert any("/pull/3342" in u for u in all_evidence_prs), "Without cutoff, PR 3342 should be present"
    assert not any("/pull/3342" in u for u in temporal_evidence_prs), "With cutoff, PR 3342 MUST be excluded"


def test_temporal_cutoff_co_changes(client):
    """Verify co-changes merged after the cutoff timestamp are strictly excluded."""
    cutoff = "2026-10-14T09:03:20Z"
    target_files = ["tests/flow/test_rdb_load.py"]

    co_all = find_related_co_changes_temporal(
        client, target_files, exclude_pr_number=3339, cutoff_timestamp=None
    )
    co_temporal = find_related_co_changes_temporal(
        client, target_files, exclude_pr_number=3339, cutoff_timestamp=cutoff
    )

    all_evidence = [u for c in co_all for u in c["evidence_pr_urls"]]
    temporal_evidence = [u for c in co_temporal for u in c["evidence_pr_urls"]]

    assert any("/pull/3342" in u for u in all_evidence)
    assert not any("/pull/3342" in u for u in temporal_evidence)


def test_comparative_evaluator_runs_and_graph_on_outperforms(evaluator):
    """Verify evaluator executes all 20 questions and confirms Graph ON accuracy and refusal."""
    out = evaluator.run_benchmark()
    metrics = out["metrics"]

    graph_on = metrics["Graph ON"]
    vector_bl = metrics["Vector Baseline"]
    graph_off = metrics["Graph OFF"]

    assert graph_on["total_questions"] == 20
    assert graph_on["correct_count"] == 20
    assert graph_on["unsupported_claims_asserted"] == 0
    assert graph_on["correct_refusals"] == 4

    # Graph ON provides substantially more valid evidence URLs than vector or graph off
    assert graph_on["valid_evidence_urls"] > vector_bl["valid_evidence_urls"]

    # Graph OFF asserts unsupported claims
    assert graph_off["unsupported_claims_asserted"] > 0
    assert graph_off["correct_count"] < graph_on["correct_count"]


def test_temporal_leakage_review_submitted_after_cutoff_excluded(client):
    """Verify that a review submitted after the cutoff cannot leak into historical ranking."""
    # Test file touched in PR 3176
    files = ["src/serializers/decoders/current/v20/decode_graph.c"]
    cutoff = "2026-10-07T07:05:44Z"

    reviewers_temporal = find_historical_reviewers_temporal(
        client, files, exclude_pr_number=3176, cutoff_timestamp=cutoff
    )
    # PR 3176 reviews submitted after cutoff (or reviews on later PRs) must not leak
    for r in reviewers_temporal:
        assert r["login"] != "attacker_admin"
        # Ensure target PR is never in evidence URLs
        for u in r["evidence_pr_urls"]:
            assert "/pull/3176" not in u


def test_temporal_leakage_issue_created_after_cutoff_excluded(client):
    """Verify that an issue created after the cutoff is strictly filtered out."""
    cutoff_before_issue = "2026-10-10T00:00:00Z"
    # Issue 3268 was created on 2026-10-11T13:11:12Z
    issues_filtered = trace_pr_to_issues_temporal(
        client, pr_number=3328, cutoff_timestamp=cutoff_before_issue
    )
    assert len(issues_filtered) == 0, "Issue created after cutoff must be excluded"

    # With cutoff after issue creation:
    cutoff_after_issue = "2026-10-14T00:00:00Z"
    issues_included = trace_pr_to_issues_temporal(
        client, pr_number=3328, cutoff_timestamp=cutoff_after_issue
    )
    assert len(issues_included) > 0, "Issue created before cutoff should be included"
    assert issues_included[0]["issue_number"] == 3268


def test_vector_baseline_anti_circularity_and_cutoff():
    """Verify vector baseline strictly excludes target PR and future documents."""
    from src.evaluation.vector_baseline import LocalVectorBaseline

    v = LocalVectorBaseline()
    cutoff = "2026-10-14T09:03:20Z"

    # Search with target PR excluded
    res = v.search("nested values depth limit", cutoff_timestamp=cutoff, exclude_pr=3339)
    # None of the retrieved docs can be PR #3339
    for doc, _ in res:
        assert doc.number != 3339, "Target PR must not be retrieved as evidence for itself"
        if doc.timestamp:
            assert doc.timestamp < cutoff, "Document after cutoff must not be retrieved"
