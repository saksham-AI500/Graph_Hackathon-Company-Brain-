"""Independent 9-Question Holdout Dataset for RepoBrain Adversarial Evaluation.

A distinct evaluation set derived independently from the 20-question benchmark:
- Multi-hop PR-to-issue-to-file tracing
- Reviewer and ownership questions
- Questions requiring historical cutoffs
- Questions with insufficient evidence (correct refusal)
- Plausible but false claims (adversarial refusal)
- Questions where graph adds no meaningful advantage (flat text search suffices)
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class HoldoutQuestion(BaseModel):
    """An independently verified holdout question with ground truth evidence."""
    id: str
    category: str
    target_pr: Optional[int] = None
    target_file: Optional[str] = None
    question: str
    historical_cutoff: Optional[str] = None
    expected_answer_keywords: List[str]
    ground_truth_urls: List[str]
    required_relationships: List[str] = Field(default_factory=list)
    should_refuse: bool = False
    refusal_reason: Optional[str] = None
    graph_advantage: str = "HIGH"  # HIGH, MODERATE, LOW (flat text sufficient)


HOLDOUT_DATASET: List[HoldoutQuestion] = [
    # 1. Multi-Hop Tracing — PR #3141
    HoldoutQuestion(
        id="HOLD-01",
        category="MULTI_HOP_TRACING",
        target_pr=3141,
        question="What issue was resolved by PR #3141 regarding RDB decode, and what error did it handle?",
        expected_answer_keywords=["3140", "short read"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3141",
            "https://github.com/FalkorDB/FalkorDB/issues/3140",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
        graph_advantage="HIGH",
    ),
    # 2. Multi-Hop Tracing — PR #3179
    HoldoutQuestion(
        id="HOLD-02",
        category="MULTI_HOP_TRACING",
        target_pr=3179,
        question="What security issue does PR #3179 resolve regarding container image scanning?",
        expected_answer_keywords=["3178", "Trivy"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3179",
            "https://github.com/FalkorDB/FalkorDB/issues/3178",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
        graph_advantage="HIGH",
    ),
    # 3. Reviewer Routing with Historical Cutoff (Refusal under early cutoff) — PR #3141
    HoldoutQuestion(
        id="HOLD-03",
        category="REFUSAL",
        target_pr=3141,
        question="Who historically reviewed RDB decode changes prior to PR #3141's creation with historical cutoff?",
        historical_cutoff="2026-10-01T10:00:00Z",
        expected_answer_keywords=["insufficient", "no prior", "refuse"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3141",
        ],
        required_relationships=[],
        should_refuse=True,
        refusal_reason="Zero qualifying human reviews on RDB decode files existed prior to October 2026.",
        graph_advantage="HIGH",
    ),
    # 4. Ownership Discrepancy — build/runtime/Dockerfile
    HoldoutQuestion(
        id="HOLD-04",
        category="OWNERSHIP_DISCREPANCY",
        target_file="build/runtime/Dockerfile",
        question="What team is declared as CODEOWNERS owner for build/runtime/Dockerfile versus who actually authored changes?",
        expected_answer_keywords=["@FalkorDB/falkordb-core", "build", "AviAvni", "DvirDukhan"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/blob/master/.github/CODEOWNERS",
            "https://github.com/FalkorDB/FalkorDB/pull/3181",
        ],
        required_relationships=["(:Team)-[:DECLARED_FOR]->(:OwnershipRule)-[:COVERS]->(:File)"],
        should_refuse=False,
        graph_advantage="HIGH",
    ),
    # 5. Historical Cutoff / Exclusion of Future PRs — PR #3130
    HoldoutQuestion(
        id="HOLD-05",
        category="REFUSAL",
        target_pr=3130,
        question="Who had documented history reviewing src/commands/ prior to PR #3130's creation cutoff?",
        historical_cutoff="2026-09-29T12:00:00Z",
        expected_answer_keywords=["insufficient", "no prior", "refuse"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3130",
        ],
        required_relationships=[],
        should_refuse=True,
        refusal_reason="Zero prior reviews on this command path existed before September 2026 cutoff.",
        graph_advantage="HIGH",
    ),
    # 6. Insufficient Evidence / No Linked Issue — PR #3161
    HoldoutQuestion(
        id="HOLD-06",
        category="REFUSAL",
        target_pr=3161,
        question="What specific GitHub issue was closed and resolved by PR #3161?",
        expected_answer_keywords=["No linked issue", "refuse", "insufficient"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3161",
        ],
        required_relationships=[],
        should_refuse=True,
        refusal_reason="PR #3161 has no linked issue relationship in repository records.",
        graph_advantage="HIGH",
    ),
    # 7. Plausible but False Claim — PR #3170
    HoldoutQuestion(
        id="HOLD-07",
        category="REFUSAL",
        target_pr=3170,
        question="Did PR #3170 implement cluster replication failover for FalkorDB?",
        expected_answer_keywords=["not supported", "refuse", "LLVM 23", "vec_utils"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3170",
        ],
        required_relationships=[],
        should_refuse=True,
        refusal_reason="PR #3170 addressed LLVM 23 compilation in vec_utils.cpp; cluster failover claim is false.",
        graph_advantage="HIGH",
    ),
    # 8. Nonexistent Fabricated PR — PR #9995
    HoldoutQuestion(
        id="HOLD-08",
        category="REFUSAL",
        target_pr=9995,
        question="Who approved PR #9995 and what benchmark regression did it fix?",
        expected_answer_keywords=["not found", "does not exist", "refused"],
        ground_truth_urls=[],
        required_relationships=[],
        should_refuse=True,
        refusal_reason="PR #9995 does not exist in graph records.",
        graph_advantage="HIGH",
    ),
    # 9. Flat Text Parity (Graph adds no meaningful advantage) — PR #3181
    HoldoutQuestion(
        id="HOLD-09",
        category="FLAT_TEXT_PARITY",
        target_pr=3181,
        question="What is the exact title and author of PR #3181?",
        expected_answer_keywords=["redis-server", "falkordb user", "DvirDukhan"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3181",
        ],
        required_relationships=[],
        should_refuse=False,
        graph_advantage="LOW",
    ),
]


def get_holdout_questions() -> List[HoldoutQuestion]:
    """Return the complete 9-question separately authored holdout dataset."""
    return HOLDOUT_DATASET
