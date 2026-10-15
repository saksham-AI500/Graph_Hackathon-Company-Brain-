"""Hand-Verified Benchmark Dataset for RepoBrain Evaluation.

20 independently verified benchmark questions covering:
- Reviewer Routing
- PR-to-Issue Decision Tracing
- File Co-Change Relationships
- Ownership Discrepancy Analysis
- Refusal / Unanswerable / Fabricated Queries
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BenchmarkQuestion(BaseModel):
    """A hand-verified benchmark question with ground truth evidence."""
    id: str
    category: str  # REVIEWER_ROUTING, DECISION_TRACING, CO_CHANGE, OWNERSHIP_DISCREPANCY, REFUSAL
    target_pr: Optional[int] = None
    target_file: Optional[str] = None
    question: str
    historical_cutoff: Optional[str] = None
    expected_answer_keywords: List[str]
    ground_truth_urls: List[str]
    required_relationships: List[str] = Field(default_factory=list)
    should_refuse: bool = False
    refusal_reason: Optional[str] = None


BENCHMARK_DATASET: List[BenchmarkQuestion] = [
    # 1. Reviewer Routing — PR #3339
    BenchmarkQuestion(
        id="BENCH-01",
        category="REVIEWER_ROUTING",
        target_pr=3339,
        question="Which historical human reviewers should review PR #3339 based on files touched prior to its creation?",
        historical_cutoff="2026-10-14T09:03:20Z",
        expected_answer_keywords=["DvirDukhan", "AviAvni"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3339",
            "https://github.com/DvirDukhan",
            "https://github.com/FalkorDB/FalkorDB/pull/3307",
        ],
        required_relationships=["(:Person)-[:REVIEWED]->(:PullRequest)-[:MODIFIES]->(:File)"],
        should_refuse=False,
    ),
    # 2. Decision Tracing — PR #3339
    BenchmarkQuestion(
        id="BENCH-02",
        category="DECISION_TRACING",
        target_pr=3339,
        question="What issue was explicitly resolved by PR #3339, and what bug did it fix?",
        expected_answer_keywords=["3338", "GRAPH.RESTORE", "nested", "depth limit"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/issues/3338",
            "https://github.com/FalkorDB/FalkorDB/pull/3339",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
    ),
    # 3. Decision Tracing — PR #3328
    BenchmarkQuestion(
        id="BENCH-03",
        category="DECISION_TRACING",
        target_pr=3328,
        question="Which issue does PR #3328 resolve regarding module-load argument parsing?",
        expected_answer_keywords=["3268", "module-load", "arguments"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/issues/3268",
            "https://github.com/FalkorDB/FalkorDB/pull/3328",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
    ),
    # 4. Decision Tracing — PR #3307
    BenchmarkQuestion(
        id="BENCH-04",
        category="DECISION_TRACING",
        target_pr=3307,
        question="What performance issue does PR #3307 address regarding native index updates?",
        expected_answer_keywords=["3306", "native index", "unit of work"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/issues/3306",
            "https://github.com/FalkorDB/FalkorDB/pull/3307",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
    ),
    # 5. Decision Tracing — PR #3290
    BenchmarkQuestion(
        id="BENCH-05",
        category="DECISION_TRACING",
        target_pr=3290,
        question="What transaction write bug inside MULTI/EXEC is fixed by PR #3290?",
        expected_answer_keywords=["3093", "MULTI/EXEC", "write"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/issues/3093",
            "https://github.com/FalkorDB/FalkorDB/pull/3290",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
    ),
    # 6. Decision Tracing — PR #3262
    BenchmarkQuestion(
        id="BENCH-06",
        category="DECISION_TRACING",
        target_pr=3262,
        question="What configuration parameter bug is resolved by PR #3262 on RDB load?",
        expected_answer_keywords=["3251", "CACHE_SIZE", "RDB"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/issues/3251",
            "https://github.com/FalkorDB/FalkorDB/pull/3262",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
    ),
    # 7. Decision Tracing — PR #3234
    BenchmarkQuestion(
        id="BENCH-07",
        category="DECISION_TRACING",
        target_pr=3234,
        question="What multi-byte panic condition was fixed by PR #3234 in slow log?",
        expected_answer_keywords=["3233", "slow log", "2048", "multi-byte"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/issues/3233",
            "https://github.com/FalkorDB/FalkorDB/pull/3234",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
    ),
    # 8. Decision Tracing — PR #3181
    BenchmarkQuestion(
        id="BENCH-08",
        category="DECISION_TRACING",
        target_pr=3181,
        question="What security and permission issue did PR #3181 resolve for docker containers?",
        expected_answer_keywords=["3180", "non-root", "falkordb user", "redis-server"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/issues/3180",
            "https://github.com/FalkorDB/FalkorDB/pull/3181",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
    ),
    # 9. Decision Tracing — PR #3170
    BenchmarkQuestion(
        id="BENCH-09",
        category="DECISION_TRACING",
        target_pr=3170,
        question="What compiler error was fixed by PR #3170 for macOS LLVM 23 builds?",
        expected_answer_keywords=["3169", "LLVM 23", "<string>", "vec_utils.cpp"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/issues/3169",
            "https://github.com/FalkorDB/FalkorDB/pull/3170",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
    ),
    # 10. Decision Tracing — PR #3132
    BenchmarkQuestion(
        id="BENCH-10",
        category="DECISION_TRACING",
        target_pr=3132,
        question="What Cypher function null handling was resolved by PR #3132?",
        expected_answer_keywords=["2723", "startNode", "endNode", "null"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/issues/2723",
            "https://github.com/FalkorDB/FalkorDB/pull/3132",
        ],
        required_relationships=["(:PullRequest)-[:RESOLVES]->(:Issue)"],
        should_refuse=False,
    ),
    # 11. Reviewer Routing — PR #3176
    BenchmarkQuestion(
        id="BENCH-11",
        category="REVIEWER_ROUTING",
        target_pr=3176,
        question="Who are the qualified historical reviewers for decode and RESTORE payload fixes in PR #3176?",
        historical_cutoff="2026-10-07T07:05:44Z",
        expected_answer_keywords=["DvirDukhan"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3176",
            "https://github.com/FalkorDB/FalkorDB/pull/3161",
        ],
        required_relationships=["(:Person)-[:REVIEWED]->(:PullRequest)-[:MODIFIES]->(:File)"],
        should_refuse=False,
    ),
    # 12. Reviewer Routing — PR #3262
    BenchmarkQuestion(
        id="BENCH-12",
        category="REVIEWER_ROUTING",
        target_pr=3262,
        question="Who should review the RDB cache size changes in PR #3262 based on prior file reviews?",
        historical_cutoff="2026-10-11T13:09:06Z",
        expected_answer_keywords=["DvirDukhan"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3262",
            "https://github.com/DvirDukhan",
        ],
        required_relationships=["(:Person)-[:REVIEWED]->(:PullRequest)"],
        should_refuse=False,
    ),
    # 13. Reviewer Routing (Insufficient Evidence Under Temporal Cutoff) — PR #3192
    BenchmarkQuestion(
        id="BENCH-13",
        category="REFUSAL",
        target_pr=3192,
        question="Who had historical experience reviewing .github/workflows/batch-backport.yml prior to PR #3192's creation?",
        historical_cutoff="2026-10-08T08:31:46Z",
        expected_answer_keywords=["insufficient", "no prior", "refuse"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3192",
        ],
        required_relationships=[],
        should_refuse=True,
        refusal_reason="Zero prior PR touches existed in graph history for this workflow prior to cutoff 2026-10-08T08:31:46Z.",
    ),
    # 14. Co-Change Analysis — graph/src/runtime/pending.rs
    BenchmarkQuestion(
        id="BENCH-14",
        category="CO_CHANGE",
        target_pr=3339,
        target_file="graph/src/runtime/pending.rs",
        question="Which runtime effects file co-changes most frequently with graph/src/runtime/pending.rs?",
        expected_answer_keywords=["apply.rs", "effects"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3307",
            "https://github.com/FalkorDB/FalkorDB/pull/3189",
        ],
        required_relationships=["(:PullRequest)-[:MODIFIES]->(:File)"],
        should_refuse=False,
    ),
    # 15. Co-Change Analysis — src/commands/bulk_insert.rs
    BenchmarkQuestion(
        id="BENCH-15",
        category="CO_CHANGE",
        target_pr=3339,
        target_file="src/commands/bulk_insert.rs",
        question="Which runtime effects file co-changes most frequently when bulk insert commands (src/commands/bulk_insert.rs) are modified?",
        expected_answer_keywords=["apply.rs"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3339",
        ],
        required_relationships=["(:PullRequest)-[:MODIFIES]->(:File)"],
        should_refuse=False,
    ),
    # 16. Ownership Discrepancy — tests/flow/test_rdb_load.py
    BenchmarkQuestion(
        id="BENCH-16",
        category="OWNERSHIP_DISCREPANCY",
        target_file="tests/flow/test_rdb_load.py",
        question="What is the declared CODEOWNERS ownership for tests/flow/test_rdb_load.py versus observed human activity?",
        expected_answer_keywords=["None", "unowned", "DvirDukhan", "AviAvni", "swilly22"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/blob/master/.github/CODEOWNERS",
        ],
        required_relationships=["(:PullRequest)-[:MODIFIES]->(:File)"],
        should_refuse=False,
    ),
    # 17. Ownership Discrepancy — graph/src/runtime/pending.rs
    BenchmarkQuestion(
        id="BENCH-17",
        category="OWNERSHIP_DISCREPANCY",
        target_file="graph/src/runtime/pending.rs",
        question="What ownership discrepancy category applies to graph/src/runtime/pending.rs?",
        expected_answer_keywords=["UNOWNED_WITH_ACTIVE_MAINTAINERS", "AviAvni", "DvirDukhan"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/blob/master/.github/CODEOWNERS",
        ],
        required_relationships=["(:PullRequest)-[:MODIFIES]->(:File)"],
        should_refuse=False,
    ),
    # 18. Unsupported / Missing Decision — PR #3342
    BenchmarkQuestion(
        id="BENCH-18",
        category="REFUSAL",
        target_pr=3342,
        question="What specific GitHub issue was closed and resolved by PR #3342?",
        expected_answer_keywords=["No linked issue", "refuse", "insufficient"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3342",
        ],
        required_relationships=[],
        should_refuse=True,
        refusal_reason="PR #3342 is a version release that does not explicitly resolve any GitHub issue.",
    ),
    # 19. Unsupported / Nonexistent PR — PR #9999
    BenchmarkQuestion(
        id="BENCH-19",
        category="REFUSAL",
        target_pr=9999,
        question="Who reviewed PR #9999 and what files did it modify?",
        expected_answer_keywords=["not found", "does not exist", "refused"],
        ground_truth_urls=[],
        required_relationships=[],
        should_refuse=True,
        refusal_reason="PR #9999 does not exist in graph records.",
    ),
    # 20. Fabricated Reviewer Claim — PR #3339
    BenchmarkQuestion(
        id="BENCH-20",
        category="REFUSAL",
        target_pr=3339,
        question="Verify whether 'attacker_admin' or 'ghost_reviewer' approved PR #3339.",
        expected_answer_keywords=["not found", "unsupported", "refused", "no record"],
        ground_truth_urls=[
            "https://github.com/FalkorDB/FalkorDB/pull/3339",
        ],
        required_relationships=[],
        should_refuse=True,
        refusal_reason="attacker_admin and ghost_reviewer are fabricated identities with no graph records.",
    ),
]


def get_benchmark_questions() -> List[BenchmarkQuestion]:
    """Return the complete 20-question benchmark dataset."""
    return BENCHMARK_DATASET
