"""Generate, hash, score, and analyze the 40-pair Builder NLI Calibration Set.

Builder set composition (40 pairs total):
- 15 Entailed pairs (true factual paraphrases / entailments)
- 15 Contradicted pairs (direct factual contradictions)
- 10 Hard Negative pairs (shared entity/topic, exactly one fact differs):
    - 2 wrong number
    - 2 wrong date
    - 2 negation
    - 2 wrong entity
    - 2 wrong scope
"""

import hashlib
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, ".")
from src.agent.nli_verifier import get_default_nli_verifier

BUILDER_PAIRS = [
    # -------------------------------------------------------------------------
    # 15 Entailed Pairs
    # -------------------------------------------------------------------------
    {
        "id": "E01",
        "category": "entailed",
        "premise": "Elena Rostova merged PR #142 to enable Redis clustering in production.",
        "hypothesis": "Redis clustering was enabled in production when Elena Rostova merged PR #142.",
    },
    {
        "id": "E02",
        "category": "entailed",
        "premise": "Marcus Vance refactored the database connection pool in PR #236 to fix timeout errors.",
        "hypothesis": "Database connection pool was refactored in PR #236 by Marcus Vance to resolve timeout issues.",
    },
    {
        "id": "E03",
        "category": "entailed",
        "premise": "We decided in ADR-002 that all internal microservice communication must use gRPC with mTLS.",
        "hypothesis": "ADR-002 specifies that microservices communicate using gRPC and mTLS.",
    },
    {
        "id": "E04",
        "category": "entailed",
        "premise": "CODEOWNERS declares that the auth/ module is owned by @acme/identity.",
        "hypothesis": "The auth/ directory is maintained by @acme/identity according to CODEOWNERS.",
    },
    {
        "id": "E05",
        "category": "entailed",
        "premise": "Issue #44 describes checkout timeouts occurring when concurrency exceeds 200 requests per second.",
        "hypothesis": "Checkout timeouts were reported during high concurrency load in Issue #44.",
    },
    {
        "id": "E06",
        "category": "entailed",
        "premise": "The search cluster migration was completed on 2026-08-15 without data loss.",
        "hypothesis": "Search cluster migration finished on 2026-08-15.",
    },
    {
        "id": "E07",
        "category": "entailed",
        "premise": "ADR-005 mandates that PostgreSQL connection pool size should be capped at 50 connections per pod.",
        "hypothesis": "PostgreSQL connections per pod are limited to 50 under ADR-005.",
    },
    {
        "id": "E08",
        "category": "entailed",
        "premise": "Gabriel Santos reviewed and approved PR #305 regarding token refresh rotation.",
        "hypothesis": "PR #305 on token refresh rotation received an approving review from Gabriel Santos.",
    },
    {
        "id": "E09",
        "category": "entailed",
        "premise": "The notifications service uses RabbitMQ dead-letter exchanges for failed push deliveries.",
        "hypothesis": "Failed push deliveries in notifications service are routed to dead-letter exchanges.",
    },
    {
        "id": "E10",
        "category": "entailed",
        "premise": "PR #42 updated the circuit breaker thresholds for third-party billing webhooks.",
        "hypothesis": "Circuit breaker thresholds for billing webhooks were adjusted in PR #42.",
    },
    {
        "id": "E11",
        "category": "entailed",
        "premise": "Sarah Chen deployed the distributed tracing collector to Kubernetes staging namespace.",
        "hypothesis": "Distributed tracing collector was deployed to staging by Sarah Chen.",
    },
    {
        "id": "E12",
        "category": "entailed",
        "premise": "Issue #89 tracks memory leaks in the WebSocket push gateway during long-lived connections.",
        "hypothesis": "WebSocket push gateway memory leaks are documented in Issue #89.",
    },
    {
        "id": "E13",
        "category": "entailed",
        "premise": "ADR-007 requires AES-256 encryption at rest for all customer payment tokens.",
        "hypothesis": "Customer payment tokens must be encrypted at rest with AES-256 per ADR-007.",
    },
    {
        "id": "E14",
        "category": "entailed",
        "premise": "Dmitri Volkov optimized the inverted index compression algorithm in PR #210.",
        "hypothesis": "Inverted index compression was improved by Dmitri Volkov in PR #210.",
    },
    {
        "id": "E15",
        "category": "entailed",
        "premise": "CODEOWNERS assigns frontend/dashboard to the @acme/frontend engineering team.",
        "hypothesis": "The @acme/frontend team is designated as code owner for frontend/dashboard.",
    },

    # -------------------------------------------------------------------------
    # 15 Contradicted Pairs
    # -------------------------------------------------------------------------
    {
        "id": "C01",
        "category": "contradicted",
        "premise": "Elena Rostova merged PR #142 to enable Redis clustering in production.",
        "hypothesis": "PR #142 was rejected and Redis clustering was never deployed to production.",
    },
    {
        "id": "C02",
        "category": "contradicted",
        "premise": "Marcus Vance refactored the database connection pool in PR #236 to fix timeout errors.",
        "hypothesis": "Marcus Vance closed PR #236 without modifying any database connection pool settings.",
    },
    {
        "id": "C03",
        "category": "contradicted",
        "premise": "We decided in ADR-002 that all internal microservice communication must use gRPC with mTLS.",
        "hypothesis": "ADR-002 strictly forbids gRPC and mandates plain REST over unencrypted HTTP.",
    },
    {
        "id": "C04",
        "category": "contradicted",
        "premise": "CODEOWNERS declares that the auth/ module is owned by @acme/identity.",
        "hypothesis": "The auth/ module has no code owners and is completely unowned in CODEOWNERS.",
    },
    {
        "id": "C05",
        "category": "contradicted",
        "premise": "Issue #44 describes checkout timeouts occurring when concurrency exceeds 200 requests per second.",
        "hypothesis": "Issue #44 reports that checkout latency remains zero under 50,000 requests per second.",
    },
    {
        "id": "C06",
        "category": "contradicted",
        "premise": "The search cluster migration was completed on 2026-08-15 without data loss.",
        "hypothesis": "The search cluster migration was permanently aborted after catastrophic data corruption.",
    },
    {
        "id": "C07",
        "category": "contradicted",
        "premise": "ADR-005 mandates that PostgreSQL connection pool size should be capped at 50 connections per pod.",
        "hypothesis": "PostgreSQL connections per pod are completely unlimited and uncapped under ADR-005.",
    },
    {
        "id": "C08",
        "category": "contradicted",
        "premise": "Gabriel Santos reviewed and approved PR #305 regarding token refresh rotation.",
        "hypothesis": "Gabriel Santos submitted a blocking rejection on PR #305 and refused approval.",
    },
    {
        "id": "C09",
        "category": "contradicted",
        "premise": "The notifications service uses RabbitMQ dead-letter exchanges for failed push deliveries.",
        "hypothesis": "The notifications service discards all failed push deliveries with no queueing.",
    },
    {
        "id": "C10",
        "category": "contradicted",
        "premise": "PR #42 updated the circuit breaker thresholds for third-party billing webhooks.",
        "hypothesis": "PR #42 deleted all circuit breaker logic and disabled webhook monitoring.",
    },
    {
        "id": "C11",
        "category": "contradicted",
        "premise": "Sarah Chen deployed the distributed tracing collector to Kubernetes staging namespace.",
        "hypothesis": "Sarah Chen uninstalled distributed tracing and banned OpenTelemetry.",
    },
    {
        "id": "C12",
        "category": "contradicted",
        "premise": "Issue #89 tracks memory leaks in the WebSocket push gateway during long-lived connections.",
        "hypothesis": "Issue #89 confirms zero memory usage in the WebSocket push gateway.",
    },
    {
        "id": "C13",
        "category": "contradicted",
        "premise": "ADR-007 requires AES-256 encryption at rest for all customer payment tokens.",
        "hypothesis": "ADR-007 permits plaintext unencrypted storage of customer payment tokens in log files.",
    },
    {
        "id": "C14",
        "category": "contradicted",
        "premise": "Dmitri Volkov optimized the inverted index compression algorithm in PR #210.",
        "hypothesis": "Dmitri Volkov reverted the inverted index compression and disabled indexing in PR #210.",
    },
    {
        "id": "C15",
        "category": "contradicted",
        "premise": "CODEOWNERS assigns frontend/dashboard to the @acme/frontend engineering team.",
        "hypothesis": "CODEOWNERS assigns frontend/dashboard exclusively to external guest contractors.",
    },

    # -------------------------------------------------------------------------
    # 10 Hard Negative Pairs (Shared entity/topic, exactly ONE fact differs)
    # -------------------------------------------------------------------------
    {
        "id": "HN01",
        "category": "hard_negative",
        "fact_diff": "wrong_number",
        "premise": "The background sync retry policy specifies 5 attempts before dead-letter routing.",
        "hypothesis": "The background sync retry policy specifies 3 attempts before dead-letter routing.",
    },
    {
        "id": "HN02",
        "category": "hard_negative",
        "fact_diff": "wrong_number",
        "premise": "PostgreSQL connection pool max size is set to 50 connections in production config.",
        "hypothesis": "PostgreSQL connection pool max size is set to 25 connections in production config.",
    },
    {
        "id": "HN03",
        "category": "hard_negative",
        "fact_diff": "wrong_date",
        "premise": "PR #1 merged on 2025-10-04 after notifications refactoring.",
        "hypothesis": "PR #1 merged on 2025-10-05 after notifications refactoring.",
    },
    {
        "id": "HN04",
        "category": "hard_negative",
        "fact_diff": "wrong_date",
        "premise": "ADR-004 was ratified by architecture review on 2026-04-12.",
        "hypothesis": "ADR-004 was ratified by architecture review on 2026-04-13.",
    },
    {
        "id": "HN05",
        "category": "hard_negative",
        "fact_diff": "negation",
        "premise": "PR #42 was approved by Gabriel Santos after security review.",
        "hypothesis": "PR #42 was not approved by Gabriel Santos after security review.",
    },
    {
        "id": "HN06",
        "category": "hard_negative",
        "fact_diff": "negation",
        "premise": "The payment gateway supports partial refund transactions.",
        "hypothesis": "The payment gateway does not support partial refund transactions.",
    },
    {
        "id": "HN07",
        "category": "hard_negative",
        "fact_diff": "wrong_entity",
        "premise": "Marcus Vance refactored the auth token validation service in PR #55.",
        "hypothesis": "Gabriel Santos refactored the auth token validation service in PR #55.",
    },
    {
        "id": "HN08",
        "category": "hard_negative",
        "fact_diff": "wrong_entity",
        "premise": "The payments/ module is owned by @acme/payments in CODEOWNERS.",
        "hypothesis": "The payments/ module is owned by @acme/growth in CODEOWNERS.",
    },
    {
        "id": "HN09",
        "category": "hard_negative",
        "fact_diff": "wrong_scope",
        "premise": "The new rate limiter applies strictly to payments/ API endpoints.",
        "hypothesis": "The new rate limiter applies strictly to payments/refunds/ API endpoints.",
    },
    {
        "id": "HN10",
        "category": "hard_negative",
        "fact_diff": "wrong_scope",
        "premise": "ADR-008 mandates mutual TLS for internal services in the backend/ cluster.",
        "hypothesis": "ADR-008 mandates mutual TLS for internal services in the backend/billing/ cluster.",
    },
]


def main():
    out_dir = Path("data/calibration")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "builder_calibration_pairs.json"

    # Save builder calibration pairs
    content_bytes = json.dumps(BUILDER_PAIRS, indent=2).encode("utf-8")
    json_path.write_bytes(content_bytes)

    # Compute SHA-256 of builder set
    sha256_hash = hashlib.sha256(content_bytes).hexdigest()
    print(f"Builder Calibration Set written to: {json_path}")
    print(f"Builder Calibration Set SHA-256: {sha256_hash}")

    # Score each pair using LocalNLIVerifier
    nli = get_default_nli_verifier()
    scores_by_cat = {"entailed": [], "contradicted": [], "hard_negative": []}
    detailed_results = []

    for item in BUILDER_PAIRS:
        score = nli.score_entailment(item["premise"], item["hypothesis"])
        cat = item["category"]
        scores_by_cat[cat].append(score)
        detailed_results.append({
            "id": item["id"],
            "category": cat,
            "fact_diff": item.get("fact_diff"),
            "premise": item["premise"],
            "hypothesis": item["hypothesis"],
            "score": score,
        })

    # Compute distribution statistics per class
    print("\n" + "=" * 80)
    print("SCORE DISTRIBUTIONS PER CLASS")
    print("=" * 80)
    stats_table = []
    for cat, scs in scores_by_cat.items():
        min_s = min(scs)
        med_s = statistics.median(scs)
        mean_s = statistics.mean(scs)
        max_s = max(scs)
        stats_table.append({
            "category": cat,
            "count": len(scs),
            "min": round(min_s, 4),
            "median": round(med_s, 4),
            "mean": round(mean_s, 4),
            "max": round(max_s, 4),
        })
        print(f"[{cat.upper()}] (N={len(scs)}): Min={min_s:.4f}, Median={med_s:.4f}, Mean={mean_s:.4f}, Max={max_s:.4f}")

    # Compute False Positive Rate (FPR) and False Negative Rate (FNR) at Dev Threshold = 0.50
    dev_thresh = 0.50
    # Positive = Entailed; Negative = Contradicted + Hard Negative
    fn_count = sum(1 for s in scores_by_cat["entailed"] if s < dev_thresh)
    fnr = fn_count / len(scores_by_cat["entailed"])

    fp_contradicted = sum(1 for s in scores_by_cat["contradicted"] if s >= dev_thresh)
    fp_hard_neg = sum(1 for s in scores_by_cat["hard_negative"] if s >= dev_thresh)
    total_negatives = len(scores_by_cat["contradicted"]) + len(scores_by_cat["hard_negative"])
    fpr = (fp_contradicted + fp_hard_neg) / total_negatives

    print("\n" + "=" * 80)
    print(f"DEV THRESHOLD ({dev_thresh:.2f}) ERROR RATES")
    print("=" * 80)
    print(f"False Negatives (Entailed scored < 0.50): {fn_count}/{len(scores_by_cat['entailed'])} ({fnr * 100:.2f}%)")
    print(f"False Positives (Contradicted scored >= 0.50): {fp_contradicted}/{len(scores_by_cat['contradicted'])}")
    print(f"False Positives (Hard Negatives scored >= 0.50): {fp_hard_neg}/{len(scores_by_cat['hard_negative'])}")
    print(f"Overall FPR on Negatives: {(fp_contradicted + fp_hard_neg)}/{total_negatives} ({fpr * 100:.2f}%)")

    # Compute Equal-Error Rate (EER) Threshold from data
    # Search threshold t in [0.01, 0.99] minimizing abs(FPR(t) - FNR(t))
    all_neg_scores = scores_by_cat["contradicted"] + scores_by_cat["hard_negative"]
    pos_scores = scores_by_cat["entailed"]

    best_diff = 999.0
    eer_threshold = dev_thresh
    eer_val = 0.0

    for t_int in range(1, 100):
        t = t_int / 100.0
        cur_fnr = sum(1 for s in pos_scores if s < t) / len(pos_scores)
        cur_fpr = sum(1 for s in all_neg_scores if s >= t) / len(all_neg_scores)
        diff = abs(cur_fnr - cur_fpr)
        if diff < best_diff:
            best_diff = diff
            eer_threshold = t
            eer_val = (cur_fnr + cur_fpr) / 2.0

    print(f"\nEqual-Error Threshold (EER): {eer_threshold:.2f} (EER = {eer_val * 100:.2f}%)")

    # Write project_context/NLI_CALIBRATION.md report
    cal_md_path = Path("project_context/NLI_CALIBRATION.md")
    md_content = f"""# NLI Verifier Calibration Report (Builder Set)

- **Model**: `cross-encoder/nli-MiniLM2-L6-H768` (Quantized AVX2 ONNX)
- **Builder Calibration Dataset SHA-256**: `{sha256_hash}`
- **Dataset Path**: `data/calibration/builder_calibration_pairs.json`
- **Builder Set Composition**: 40 pairs (15 Entailed, 15 Contradicted, 10 Hard Negatives)
- **Threshold Provenance**:
  - `0.50` is retained strictly as the dev threshold (tuned on 17 October outputs).
  - Equal-error rate threshold computed from builder data: `{eer_threshold:.2f}`.
- **Independent Calibration Pairs**: Pending receipt from external evaluator.

## 1. Score Distributions Per Class

| Class | Count | Min Score | Median Score | Mean Score | Max Score | Error Rate at 0.50 |
|---|---|---|---|---|---|---|
| **Entailed** | {stats_table[0]['count']} | {stats_table[0]['min']:.4f} | {stats_table[0]['median']:.4f} | {stats_table[0]['mean']:.4f} | {stats_table[0]['max']:.4f} | **{fnr*100:.1f}%** (FNR) |
| **Contradicted** | {stats_table[1]['count']} | {stats_table[1]['min']:.4f} | {stats_table[1]['median']:.4f} | {stats_table[1]['mean']:.4f} | {stats_table[1]['max']:.4f} | **{fp_contradicted/len(scores_by_cat['contradicted'])*100:.1f}%** (FPR) |
| **Hard Negatives** | {stats_table[2]['count']} | {stats_table[2]['min']:.4f} | {stats_table[2]['median']:.4f} | {stats_table[2]['mean']:.4f} | {stats_table[2]['max']:.4f} | **{fp_hard_neg/len(scores_by_cat['hard_negative'])*100:.1f}%** (FPR) |

## 2. Threshold Performance Metrics

- **Dev Threshold ($0.50$)**:
  - False Negative Rate (FNR): `{fnr * 100:.2f}%` ({fn_count}/{len(pos_scores)})
  - False Positive Rate on Contradictions: `{fp_contradicted/len(scores_by_cat['contradicted']) * 100:.2f}%` ({fp_contradicted}/{len(scores_by_cat['contradicted'])})
  - False Positive Rate on Hard Negatives: `{fp_hard_neg/len(scores_by_cat['hard_negative']) * 100:.2f}%` ({fp_hard_neg}/{len(scores_by_cat['hard_negative'])})
  - Combined Negative FPR: `{fpr * 100:.2f}%` ({(fp_contradicted + fp_hard_neg)}/{total_negatives})
- **Computed Equal-Error Rate (EER) Threshold**: `{eer_threshold:.2f}`
  - At threshold `{eer_threshold:.2f}`: FNR = `{sum(1 for s in pos_scores if s < eer_threshold)/len(pos_scores)*100:.2f}%`, FPR = `{sum(1 for s in all_neg_scores if s >= eer_threshold)/len(all_neg_scores)*100:.2f}%`

## 3. Detailed Pair Scores

| ID | Class | Sub-Type | Premise | Hypothesis | Score | Decision (at 0.50) |
|---|---|---|---|---|---|---|
"""
    for r in detailed_results:
        dec = "PASS" if (r["category"] == "entailed" and r["score"] >= 0.50) or (r["category"] != "entailed" and r["score"] < 0.50) else "MISCLASSIFIED"
        sub = r.get("fact_diff") or "-"
        md_content += f"| `{r['id']}` | {r['category']} | {sub} | {r['premise'][:40]}... | {r['hypothesis'][:40]}... | `{r['score']:.4f}` | {dec} |\n"

    cal_md_path.write_text(md_content, encoding="utf-8")
    print(f"\nReport written to: {cal_md_path}")


if __name__ == "__main__":
    main()
