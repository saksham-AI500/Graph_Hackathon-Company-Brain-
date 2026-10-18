"""NLI Calibration Suite for RepoBrain Local Cross-Encoder Model.

Evaluates 10 entailed pairs, 10 contradicted pairs, and 10 unrelated pairs.
Measures entailment probability distribution and misclassification rates
at threshold 0.50.
"""

import sys
sys.path.insert(0, ".")
import statistics
from pathlib import Path
from src.agent.nli_verifier import get_default_nli_verifier, ENTAILMENT_THRESHOLD

PAIRS = {
    "entailed": [
        (
            "Elena Rostova merged PR #142 to enable Redis clustering in production.",
            "Redis clustering was enabled in production by merging PR #142."
        ),
        (
            "Marcus Vance refactored the database connection pool in PR #236 to fix timeout errors.",
            "Database connection pool was refactored in PR #236 to resolve timeout issues."
        ),
        (
            "We decided in ADR-002 that all internal microservice communication must use gRPC with mTLS.",
            "ADR-002 specifies that microservices communicate using gRPC and mTLS."
        ),
        (
            "CODEOWNERS declares that the auth/ module is owned by @acme/identity.",
            "The auth/ directory is maintained by @acme/identity according to CODEOWNERS."
        ),
        (
            "Issue #44 describes checkout timeouts occurring when concurrency exceeds 200 requests per second.",
            "Checkout checkout timeouts were reported during high concurrency load in Issue #44."
        ),
        (
            "Dmitri Volkov is the primary contributor to search/indexer with 42 commits over the last quarter.",
            "Dmitri Volkov actively developed the search/indexer module with numerous commits."
        ),
        (
            "The search cluster migration was completed on 2026-08-15 without data loss.",
            "Search cluster migration finished on 2026-08-15."
        ),
        (
            "ADR-005 mandates that PostgreSQL connection pool size should be capped at 50 connections per pod.",
            "PostgreSQL connections per pod are limited to 50 under ADR-005."
        ),
        (
            "Gabriel Santos reviewed and approved PR #305 regarding token refresh rotation.",
            "PR #305 on token refresh rotation received an approving review from Gabriel Santos."
        ),
        (
            "The notifications service uses RabbitMQ dead-letter exchanges for failed push deliveries.",
            "Failed push deliveries in notifications service are routed to dead-letter exchanges."
        ),
    ],
    "contradicted": [
        (
            "Elena Rostova merged PR #142 to enable Redis clustering in production.",
            "PR #142 was rejected and Redis clustering was never deployed to production."
        ),
        (
            "Marcus Vance refactored the database connection pool in PR #236 to fix timeout errors.",
            "Marcus Vance closed PR #236 without modifying any database connection pool settings."
        ),
        (
            "We decided in ADR-002 that all internal microservice communication must use gRPC with mTLS.",
            "ADR-002 strictly forbids gRPC and mandates plain REST over unencrypted HTTP."
        ),
        (
            "CODEOWNERS declares that the auth/ module is owned by @acme/identity.",
            "The auth/ module has no code owners and is completely unowned."
        ),
        (
            "Issue #44 describes checkout timeouts occurring when concurrency exceeds 200 requests per second.",
            "Issue #44 confirms that checkout response times remain under 5ms even at peak load."
        ),
        (
            "Dmitri Volkov is the primary contributor to search/indexer with 42 commits over the last quarter.",
            "Dmitri Volkov has never written a single commit to the search/indexer repository."
        ),
        (
            "The search cluster migration was completed on 2026-08-15 without data loss.",
            "The search cluster migration was aborted and abandoned after catastrophic data loss."
        ),
        (
            "ADR-005 mandates that PostgreSQL connection pool size should be capped at 50 connections per pod.",
            "PostgreSQL connections per pod are completely uncapped with no limit permitted."
        ),
        (
            "Gabriel Santos reviewed and approved PR #305 regarding token refresh rotation.",
            "Gabriel Santos submitted a blocking change request and rejected PR #305."
        ),
        (
            "The notifications service uses RabbitMQ dead-letter exchanges for failed push deliveries.",
            "The notifications service drops failed push deliveries silently without using any dead-letter queue."
        ),
    ],
    "unrelated": [
        (
            "Elena Rostova merged PR #142 to enable Redis clustering in production.",
            "The company cafeteria serves vegetarian tacos on alternating Tuesdays."
        ),
        (
            "Marcus Vance refactored the database connection pool in PR #236 to fix timeout errors.",
            "The annual corporate retreat is scheduled to take place in Denver next summer."
        ),
        (
            "We decided in ADR-002 that all internal microservice communication must use gRPC with mTLS.",
            "Bicycle racks in the underground parking lot require badge security clearance."
        ),
        (
            "CODEOWNERS declares that the auth/ module is owned by @acme/identity.",
            "The weather forecast in Seattle predicts rain showers throughout the weekend."
        ),
        (
            "Issue #44 describes checkout timeouts occurring when concurrency exceeds 200 requests per second.",
            "Employees must complete the mandatory annual cyber security training before December."
        ),
        (
            "Dmitri Volkov is the primary contributor to search/indexer with 42 commits over the last quarter.",
            "The office espresso machine is currently undergoing routine maintenance."
        ),
        (
            "The search cluster migration was completed on 2026-08-15 without data loss.",
            "Flight tickets to Tokyo should be booked through the corporate travel portal."
        ),
        (
            "ADR-005 mandates that PostgreSQL connection pool size should be capped at 50 connections per pod.",
            "The marketing team launched a brand refresh campaign across social media channels."
        ),
        (
            "Gabriel Santos reviewed and approved PR #305 regarding token refresh rotation.",
            "Conference room reservations expire after 10 minutes of no-show attendance."
        ),
        (
            "The notifications service uses RabbitMQ dead-letter exchanges for failed push deliveries.",
            "Indoor plants are watered by facility management every Monday morning."
        ),
    ],
}


def main():
    verifier = get_default_nli_verifier()
    results = {}

    print("Running NLI Calibration Benchmark (10 pairs per category)...")

    for cat, pair_list in PAIRS.items():
        cat_scores = []
        pair_details = []
        for i, (premise, hypothesis) in enumerate(pair_list, 1):
            score = verifier.score_entailment(premise, hypothesis)
            cat_scores.append(score)
            pair_details.append({
                "index": i,
                "premise": premise,
                "hypothesis": hypothesis,
                "score": score,
            })
        results[cat] = {
            "scores": cat_scores,
            "details": pair_details,
            "min": min(cat_scores),
            "max": max(cat_scores),
            "mean": statistics.mean(cat_scores),
            "median": statistics.median(cat_scores),
            "stdev": statistics.stdev(cat_scores) if len(cat_scores) > 1 else 0.0,
        }

    # Misclassification rates at threshold 0.50
    # Entailed: misclassified if score < 0.50 (False Negative)
    # Contradicted: misclassified if score >= 0.50 (False Positive)
    # Unrelated: misclassified if score >= 0.50 (False Positive)
    ent_misclassified = sum(1 for s in results["entailed"]["scores"] if s < ENTAILMENT_THRESHOLD)
    con_misclassified = sum(1 for s in results["contradicted"]["scores"] if s >= ENTAILMENT_THRESHOLD)
    unr_misclassified = sum(1 for s in results["unrelated"]["scores"] if s >= ENTAILMENT_THRESHOLD)

    ent_rate = ent_misclassified / len(results["entailed"]["scores"])
    con_rate = con_misclassified / len(results["contradicted"]["scores"])
    unr_rate = unr_misclassified / len(results["unrelated"]["scores"])

    print("\n=== SUMMARY STATISTICS ===")
    print(f"Model: {verifier.model_repo} via ONNX Runtime CPU")
    print(f"Pinned Entailment Threshold: {ENTAILMENT_THRESHOLD:.2f}\n")

    for cat in ["entailed", "contradicted", "unrelated"]:
        stats = results[cat]
        print(f"Category: {cat.upper()} (N={len(stats['scores'])})")
        print(f"  Min: {stats['min']:.4f}, Median: {stats['median']:.4f}, Mean: {stats['mean']:.4f}, Max: {stats['max']:.4f}, Stdev: {stats['stdev']:.4f}")
        for p in stats["details"][:3]:
            print(f"    [{p['index']}] score={p['score']:.4f} | '{p['hypothesis']}'")

    print("\n=== MISCLASSIFICATION AT THRESHOLD 0.50 ===")
    print(f"Entailed False Negative Rate (<0.50): {ent_rate:.1%} ({ent_misclassified}/{len(results['entailed']['scores'])})")
    print(f"Contradicted False Positive Rate (>=0.50): {con_rate:.1%} ({con_misclassified}/{len(results['contradicted']['scores'])})")
    print(f"Unrelated False Positive Rate (>=0.50): {unr_rate:.1%} ({unr_misclassified}/{len(results['unrelated']['scores'])})")

    # Generate project_context/NLI_CALIBRATION.md
    doc_lines = [
        "# NLI Verifier Calibration Report",
        "",
        f"- **Model**: `{verifier.model_repo}` (Quantized ONNX, CPU Runtime via onnxruntime)",
        f"- **Threshold**: `{ENTAILMENT_THRESHOLD:.2f}` (Pinned prior to evaluation runs)",
        "- **Evaluation Dataset**: 30 curated test pairs (10 Entailed, 10 Contradicted, 10 Unrelated)",
        "",
        "## Calibration Summary Table",
        "",
        "| Category | N | Min Score | Median Score | Mean Score | Max Score | Misclassification Rate (< 0.50 / >= 0.50) |",
        "|---|---|---|---|---|---|---|",
        f"| **Entailed** | {len(results['entailed']['scores'])} | {results['entailed']['min']:.4f} | {results['entailed']['median']:.4f} | {results['entailed']['mean']:.4f} | {results['entailed']['max']:.4f} | **{ent_rate:.1%}** ({ent_misclassified}/{len(results['entailed']['scores'])}) |",
        f"| **Contradicted** | {len(results['contradicted']['scores'])} | {results['contradicted']['min']:.4f} | {results['contradicted']['median']:.4f} | {results['contradicted']['mean']:.4f} | {results['contradicted']['max']:.4f} | **{con_rate:.1%}** ({con_misclassified}/{len(results['contradicted']['scores'])}) |",
        f"| **Unrelated** | {len(results['unrelated']['scores'])} | {results['unrelated']['min']:.4f} | {results['unrelated']['median']:.4f} | {results['unrelated']['mean']:.4f} | {results['unrelated']['max']:.4f} | **{unr_rate:.1%}** ({unr_misclassified}/{len(results['unrelated']['scores'])}) |",
        "",
        "## Detailed Pair Evaluations",
        "",
        "### 1. Entailed Pairs (Expected P(Entailment) >= 0.50)",
        "",
    ]

    for p in results["entailed"]["details"]:
        doc_lines.append(f"**Pair {p['index']}** (Score: `{p['score']:.4f}` | Decision: `{'PASS' if p['score'] >= ENTAILMENT_THRESHOLD else 'FAIL'}`)")
        doc_lines.append(f"- Premise: *\"{p['premise']}\"*")
        doc_lines.append(f"- Hypothesis: *\"{p['hypothesis']}\"*")
        doc_lines.append("")

    doc_lines.append("### 2. Contradicted Pairs (Expected P(Entailment) < 0.50)")
    doc_lines.append("")
    for p in results["contradicted"]["details"]:
        doc_lines.append(f"**Pair {p['index']}** (Score: `{p['score']:.4f}` | Decision: `{'REJECTED (CORRECT)' if p['score'] < ENTAILMENT_THRESHOLD else 'ACCEPTED (ERROR)'}`)")
        doc_lines.append(f"- Premise: *\"{p['premise']}\"*")
        doc_lines.append(f"- Hypothesis: *\"{p['hypothesis']}\"*")
        doc_lines.append("")

    doc_lines.append("### 3. Unrelated Pairs (Expected P(Entailment) < 0.50)")
    doc_lines.append("")
    for p in results["unrelated"]["details"]:
        doc_lines.append(f"**Pair {p['index']}** (Score: `{p['score']:.4f}` | Decision: `{'REJECTED (CORRECT)' if p['score'] < ENTAILMENT_THRESHOLD else 'ACCEPTED (ERROR)'}`)")
        doc_lines.append(f"- Premise: *\"{p['premise']}\"*")
        doc_lines.append(f"- Hypothesis: *\"{p['hypothesis']}\"*")
        doc_lines.append("")

    doc_path = Path("project_context/NLI_CALIBRATION.md")
    doc_path.write_text("\n".join(doc_lines), encoding="utf-8")
    print(f"\nWritten detailed calibration report to {doc_path}")


if __name__ == "__main__":
    main()
