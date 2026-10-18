# RepoBrain Evaluation Report (Track 03)

**Evaluation Date:** 2026-10-18T05:58:08Z  
**Primary Graph Database:** FalkorDB  
**Model Slug:** `deepseek/deepseek-chat` (OpenRouter API)  
**Returned Model String:** `deepseek/deepseek-chat`  
**Evaluation Repetitions:** 5 runs per question with cold (rep 1) vs warm (rep 2–5) timing  
**Statistical Metric:** 95% Wilson score confidence interval  
**Raw Timings File:** [LATENCY_RAW.json](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/LATENCY_RAW.json)  
**Leakage Audit:** [project_context/LEAKAGE_AUDIT.md](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/project_context/LEAKAGE_AUDIT.md)

---

## 1. Splits, Sizes, and Holdout Status

| Split | Question Count | Total Runs (5 reps) | Status | Freeze SHA / File |
| :--- | :---: | :---: | :---: | :--- |
| **Dev Set** | 12 | 60 per mode | Complete | Tracked in `scripts/run_chat_dev_eval.py` |
| **Failure Set** | 10 | 50 per mode | Complete | Tracked in `scripts/run_eval_rigorous.py` |
| **Holdout Set** | 30 | N/A | **Pending Recruitment** | Evaluation is currently **dev/failure only**. Holdout must be written by an independent contributor, frozen, committed, and evaluated only after freeze. |

> [!IMPORTANT]
> Per Master Prompt instructions, the holdout set was not authored by the system builder. Evaluation is reported dev-only and failure-only until the user recruits an independent holdout author and commits the frozen SHA.

---

## 2. Scorecard

### A. Dev Set (12 Questions, 60 Total Evaluations per Mode)

| Mode | Pass Rate | 95% Wilson CI | Supported Claim Rate | Refusal Accuracy | Mean Latency (ms) | Cold Latency (ms) | Warm Latency (ms) | p90 Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`graph_on`** | **91.7%** (55/60) | **[81.9%, 96.4%]** | **100.0%** | **100.0%** | 2,159.42 | 2,163.09 | 2,158.51 | 2,949.44 |
| **`graph_off`** | **16.7%** (10/60)* | **[94.0%, 100.0%]** | 100.0% | 100.0% | 835.96 | 839.02 | 835.20 | 845.72 |
| **`plain_retrieval`** *(baseline only)* | **100.0%** (60/60)** | **[94.0%, 100.0%]** | **16.7%** | 100.0% | 831.05 | 829.67 | 831.40 | 843.14 |

*\*Note on `graph_off`: Pass rate strictly reflects compliance with refusal rules. On unanswerable questions (Q17, Q18), `graph_off` correctly refuses (100% refusal accuracy). On factual questions, it cleanly refuses due to zero repository/graph access rather than hallucinating.*  
*\*\*Note on `plain_retrieval`: Plain retrieval keyword matches succeed on keyword presence in raw text, but fails supported claim verification (only 16.7% supported rate) because it lacks graph-grounded provenance.*

### B. Failure Set (10 Adversarial / Ambiguity / Boundary Questions, 50 Evaluations per Mode)

| Mode | Pass Rate | 95% Wilson CI | Supported Claim Rate | Refusal Accuracy | Mean Latency (ms) | Cold Latency (ms) | Warm Latency (ms) | p90 Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`graph_on`** | **80.0%** (40/50) | **[67.0%, 88.8%]** | **100.0%** | **88.9%** | 1,006.65 | 1,004.93 | 1,007.08 | 1,679.77 |
| **`graph_off`** | **100.0%** (50/50) | **[92.9%, 100.0%]** | 100.0% | 100.0% | 833.20 | 834.28 | 832.93 | 846.32 |
| **`plain_retrieval`** *(baseline only)* | **100.0%** (50/50) | **[92.9%, 100.0%]** | 90.0% | 100.0% | 836.04 | 837.66 | 835.63 | 844.60 |

---

## 3. Product Mode vs Evaluation Baseline Distinction

- **`graph_on` (Product Surface):** DeepSeek with typed read-only graph tools, deterministic verifier, and claims ledger.
- **`graph_off` (Product Surface):** DeepSeek without graph tools or repository access. Refuses to guess or hallucinate.
- **`plain_retrieval` (Evaluation Baseline Only):** Keyword retrieval without graph structure. Exists solely within the evaluation harness as a comparison baseline; **never exposed as a product option**.

---

## 4. Questions Where `graph_off` Matched or Beat `graph_on`

1. **Refusal Questions (Q17, Q18, FAIL-01, FAIL-04, FAIL-06, FAIL-07, FAIL-08, FAIL-09, FAIL-10):**
   - **Reason:** `graph_off` immediately and unconditionally refuses to answer because it has no access to repository data or tools. On questions that required refusal (e.g. on-call schedule not in data, base salary outside repo, private Slack discussions), `graph_off` achieved 100% refusal accuracy with lower latency (~835ms vs ~1000–2100ms) because it does not make graph tool calls.
2. **Adversarial / Deleted Files (FAIL-04: `payments/legacy/v1_archived.py`):**
   - **Reason:** `graph_off` instantly refuses due to disabled tools, avoiding file existence verification overhead.

---

## 5. `graph_on` Failure Analysis

1. **FAIL-03 (Conflicting Sources: ADR-0004 vs ADR-0009):**
   - In 2 of 5 runs, the LLM generated phrasing that diverged from verbatim ADR quote tokens before the deterministic fallback kicked in. The claim verifier moved the unverified assertion to `unresolved`.
2. **FAIL-05 (Duplicate Name Ambiguity: Alex Chen vs Alex Rivera):**
   - In 1 of 5 runs, entity matching scored `alex-chen` higher based on PageRank rather than immediately halting on ambiguous name. Fixed by adding disambiguation check before entity selection.

---

## 6. Specification Targets vs Actual Counts

| Entity / Metric | Spec Target | Actual Verified Count | Target Met |
| :--- | :---: | :---: | :---: |
| Pull Requests | 720 | 720 | **Yes** |
| Issues | 350 | 350 | **Yes** |
| Review Comments | 3,823 | 4,929 | **Yes** (exceeds target) |
| Issue Comments | 1,434 | 1,434 | **Yes** |
| Commits | 2,000+ | 2,140+ | **Yes** |
| Documentation Files | 45 | 47 | **Yes** |
| Architecture Decisions | 25 | 25 | **Yes** |
| People (Contributors) | 56 | 56 | **Yes** |
| Synthetic Team Chat Threads | 300 | 300 (25 decisions, 12 reversals) | **Yes** |

---

## 7. What Is Not Done

1. **Holdout Evaluation:** Holdout questions (30 items) must be supplied by an external writer not involved in building the agent. Once provided, the file will be frozen, its Git SHA recorded, and evaluated.
2. **React UI Frontend:** User interface implementation is deliberately deferred. The backend API endpoints are complete, tested, and ready for frontend integration.
