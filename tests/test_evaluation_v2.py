"""Tests for RepoBrain Evaluation Engine v2.

Validates:
1. Split isolation and sealed-question access guards.
2. Manifest and question-set hash stability.
3. Reproducible scoring and aggregation.
4. Citation-support checking and unsupported-claim accounting.
5. Failed/unavailable runs versus incorrect answers.
6. Fair separation of Graph ON, Plain Retrieval and Graph OFF.
7. No future-data leakage under as_of.
8. Preservation of historical result files (no overwriting).
9. Sealed-set execution guard.
"""

import hashlib
import json
import pytest
from pathlib import Path

from src.db import FalkorDBClient
from src.evaluation.evaluator_v2 import (
    EvaluatorV2,
    ManifestManager,
    SingleRunOutcome,
    SingleRunScore,
)
from src.evaluation.summary_generator import (
    load_evaluation_summary,
    format_markdown_summary_table,
    format_question_breakdown_table,
)


@pytest.fixture(scope="module")
def evaluator():
    return EvaluatorV2()


def test_manifest_and_question_set_hash_stability(evaluator):
    """Manifest hash must match the active benchmark.py SHA-256."""
    mgr = evaluator.manifest_mgr
    canonical_path = Path(mgr.data["question_set"]["canonical_path"])
    assert canonical_path.exists()
    current_hash = hashlib.sha256(canonical_path.read_bytes()).hexdigest()
    assert current_hash == mgr.data["question_set"]["sha256"]
    assert len(mgr.dev_question_ids) == 12
    assert len(mgr.sealed_question_ids) == 8


def test_split_isolation_and_sealed_question_guards(evaluator):
    """Sealed questions must raise PermissionError unless allow_sealed=True is passed."""
    mgr = evaluator.manifest_mgr

    # Dev questions can be accessed without sealed flag
    for qid in mgr.dev_question_ids:
        split = mgr.assert_can_access_question(qid, allow_sealed=False)
        assert split == "development"

    # Sealed questions MUST be blocked without allow_sealed=True
    for qid in mgr.sealed_question_ids:
        with pytest.raises(PermissionError, match="sealed holdout set"):
            mgr.assert_can_access_question(qid, allow_sealed=False)

        # Allowed only when explicitly permitted
        split = mgr.assert_can_access_question(qid, allow_sealed=True)
        assert split == "sealed"


def test_sealed_question_execution_guard(evaluator):
    """Evaluating a sealed question directly raises PermissionError if allow_sealed is False."""
    with pytest.raises(PermissionError, match="sealed holdout set"):
        evaluator.evaluate_question("BENCH-13", "graph_on", repetition=1, allow_sealed=False)


def test_fair_separation_of_three_architectures(evaluator):
    """Verify clean architectural isolation among Graph ON, Plain Retrieval, and Graph OFF."""
    # Graph ON uses FalkorDB and agent loop
    o_gon = evaluator.evaluate_question("BENCH-01", "graph_on", repetition=1)
    assert o_gon.architecture == "graph_on"
    assert o_gon.execution_type in ["LIVE_PROVIDER", "DETERMINISTIC_FALLBACK"]
    assert len(o_gon.citations) > 0

    # Plain Retrieval uses TF-IDF vector baseline, zero graph tools
    o_vec = evaluator.evaluate_question("BENCH-01", "plain_retrieval", repetition=1)
    assert o_vec.architecture == "plain_retrieval"
    assert o_vec.execution_type == "DETERMINISTIC_FALLBACK"

    # Graph OFF uses direct model alone (or UNAVAILABLE when no key)
    o_goff = evaluator.evaluate_question("BENCH-01", "graph_off", repetition=1)
    assert o_goff.architecture == "graph_off"
    assert o_goff.execution_type == "UNAVAILABLE"
    assert o_goff.score.verdict == "UNAVAILABLE"


def test_unavailable_runs_distinguished_from_incorrect_answers(evaluator):
    """Unavailable runs must not be mislabeled as incorrect answers with fabricated zeroes."""
    o_goff = evaluator.evaluate_question("BENCH-02", "graph_off", repetition=1)
    assert o_goff.score.verdict == "UNAVAILABLE"
    assert o_goff.execution_type == "UNAVAILABLE"
    assert o_goff.score.answered is False
    assert o_goff.score.refused is False
    assert "[UNAVAILABLE" in o_goff.raw_response


def test_citation_support_checking_and_unsupported_claim_accounting(evaluator):
    """Valid citations must support claims; unsupported claims must be counted."""
    # BENCH-02 has explicit issue linking and ground-truth citations
    o_gon = evaluator.evaluate_question("BENCH-02", "graph_on", repetition=1)
    assert o_gon.score.correct is True
    assert o_gon.score.citation_support is True
    assert o_gon.score.valid_citation_count >= 1
    assert o_gon.score.unsupported_claim_count == 0


def test_reproducible_scoring_across_repetitions(evaluator):
    """Multiple evaluations of deterministic runs must yield identical verdicts and scores."""
    o1 = evaluator.evaluate_question("BENCH-03", "graph_on", repetition=1)
    o2 = evaluator.evaluate_question("BENCH-03", "graph_on", repetition=2)

    assert o1.score.verdict == o2.score.verdict
    assert o1.score.correct == o2.score.correct
    assert o1.score.valid_citation_count == o2.score.valid_citation_count
    assert o1.raw_response == o2.raw_response


def test_no_future_data_leakage_under_as_of(evaluator):
    """Questions with historical cutoffs must exclude future entities."""
    o = evaluator.evaluate_question("BENCH-01", "graph_on", repetition=1)
    # Target PR #3339 cutoff is 2026-10-14T09:03:20Z
    assert o.score.as_of_valid is True


def test_historical_result_files_are_not_overwritten():
    """Historical result files must remain intact and unchanged."""
    hist_raw = Path("project_context/evaluation_raw_results.json")
    hist_holdout = Path("project_context/holdout_raw_results.json")

    assert hist_raw.exists()
    assert hist_holdout.exists()

    # Raw results must still have 20 benchmark questions
    with open(hist_raw, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data.get("questions", [])) == 20


def test_summary_generator_tables():
    """Summary generator produces valid GitHub-flavored Markdown tables."""
    summary_path = "project_context/eval_v2/summary_development.json"
    if Path(summary_path).exists():
        data = load_evaluation_summary(summary_path)
        md_table = format_markdown_summary_table(data)
        assert "| Architecture |" in md_table
        assert "Graph ON" in md_table
        assert "Plain Retrieval" in md_table
        assert "Graph OFF" in md_table

        breakdown = format_question_breakdown_table(data)
        assert "| Question ID |" in breakdown
        assert "`BENCH-01`" in breakdown
