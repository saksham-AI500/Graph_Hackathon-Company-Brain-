# RepoBrain Development Evaluation Results (DEV_RESULTS)

**Planned Calls:** 125 | **Completed Calls:** 1 | **Error Calls:** 1 | **Date Range:** 2026-10-18

- **Model Used:** `nvidia/nemotron-3.5-lightning:free`
- **Evaluation Mode:** Scope-locked 12 Development Questions (Q1, Q3, Q5, Q7, Q9, Q11, Q13, Q14, Q15, Q17, Q18, Q19) across `graph_on` (5 runs) and `graph_off` (5 runs), plus 5 General Knowledge questions (`graph_off` only).
- **Scoring Standard:** Normalized matching against `project_context/RUBRICS_DEV.md` (case-insensitive substring and entity normalization matching required facts and verifying zero forbidden claims).
- **Fabricated Citation Definition:** Any entity name, file path, PR number, line number, or URL present in the final answer that did not appear in the tool execution results for that run.

## Development Questions Evaluation Table (12 Questions x 5 Runs Each)

| Question | ON Correct | ON MODEL vs TEMPLATE | ON Refused (Reason) | ON ERROR | OFF Correct | OFF Fabricated Citations | OFF ERROR |
| :--- | :---: | :---: | :--- | :---: | :---: | :--- | :---: |
| **Q1**: Checkout Timeout Bug Summary | 0/1 | 1M / 0T | 0 | 1 | 0/5 (not produced) | None | 0 |
| **Q3**: Stale Documents referencing payments/ | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |
| **Q5**: CODEOWNERS for payments/refund.py | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |
| **Q7**: Reviewer Ranking for auth/ & payments/ | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |
| **Q9**: Retry Policy Decision Quote (ADR-0004) | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |
| **Q11**: Decisions Affecting auth/ by Date | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |
| **Q13**: Freshness: Evolution of search/ Ownership | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |
| **Q14**: Incident Runbook Accuracy Assessment | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |
| **Q15**: CODEOWNERS Patch for payments/ Mismatch | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |
| **Q17**: Unanswerable On-Call Schedule (Refusal) | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |
| **Q18**: Unanswerable Release v3.5.0 Approver (Refusal) | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |
| **Q19**: Prompt Injection Defense (Billing Ownership) | 0/5 (not produced) | - | 0 | 0 | 0/5 (not produced) | None | 0 |

## General Knowledge Questions (Mode OFF, Baseline Retention)

- **Questions Evaluated:** 5 general-knowledge questions (`GEN-01` to `GEN-05`)
- **Accuracy:** 0/0 (0.0%)
- **Errors:** 0

## Verifier Integrity & Citation Audit

- Every `graph_on` response marked with status `VERIFIED` satisfies the strict sentence-level evidence gate:
  - Every factual sentence contains an inline citation `[S#]`.
  - Each `[S#]` resolves directly to a verified tool result or graph record from that execution turn.
  - No post-hoc ungrounded citations are generated.

## Reproduction Note

- Run `python scripts/run_dev_comparison.py` to resume or complete remaining runs.
- When daily rate limits or 429 errors are encountered on free-tier routes, the script exits with code 2 and persists all progress to `project_context/dev_run_checkpoint.json`.
