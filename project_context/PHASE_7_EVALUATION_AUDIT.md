# RepoBrain — Phase 7: Evaluation Baseline Audit & Split Integrity Report

**Workspace:** `D:\grraph Hackathon\grraph Hackathon\RepoBrain`  
**Execution Timestamp:** 2026-10-17 16:45:00 IST  
**Environment:** Windows, Python 3.14 (.venv), FalkorDB 1.8.0 / 42201 on `localhost:6379`, graph `repo_kg` (298 nodes, 531 edges)  
**Controlling Specification:** `AGENT_BRIEF.md` / Phase 7 Objective  
**Audit Purpose:** Gate 0 Verification of existing benchmark history, split definition, contamination risk, and reproducibility before executing Phase 7 evaluations.

---

## 1. Executive Summary & Critical Findings

1. **Benchmark Datasets in Repository:**
   - **Canonical Benchmark (`src/evaluation/benchmark.py`):** Exactly 20 questions (`BENCH-01` through `BENCH-20`), comprising 16 answerable questions across Reviewer Routing (3), PR-to-Issue Decision Tracing (9), File Co-Change (2), Ownership Discrepancy (2), and 4 Refusals (`BENCH-13`, `BENCH-18`, `BENCH-19`, `BENCH-20`).
   - **Historical Holdout Dataset (`src/evaluation/holdout.py`):** Exactly **9** questions (`HOLD-01` through `HOLD-09`), comprising 4 answerable questions (Multi-Hop Tracing, Ownership Discrepancy, Flat-Text Parity) and 5 Refusals.

2. **Split Ambiguity (12 Dev vs. 8 Sealed):**
   - The repository has **NO explicit split definition** tagging questions into "12 development" and "8 sealed".
   - `BENCHMARK_DATASET` has 20 questions with no `split` or `is_holdout` attribute.
   - `HOLDOUT_DATASET` has **9** questions, not 8.
   - If the 20 benchmark questions were intended to be split 12/8 (e.g., `BENCH-01`..`BENCH-12` answerable vs `BENCH-13`..`BENCH-20` mixed), this was never codified in code.
   - As mandated by Gate 0: *"If the existing benchmark structure does not clearly identify the 12 development and eight sealed questions, stop and report the ambiguity instead of guessing which questions are sealed."*

3. **Prior Evaluation & Contamination Status:**
   - **All 20 questions** in `src/evaluation/benchmark.py` were executed and evaluated in historical Phase 6 runs and recorded in `project_context/evaluation_raw_results.json` and 5 baseline runs in `project_context/baselines/run_1.json`..`run_5.json`.
   - **All 9 questions** in `src/evaluation/holdout.py` were executed and evaluated in Phase 11/12 and recorded in `project_context/holdout_raw_results.json`.
   - **Continuous Test Execution:** `tests/test_evaluation.py` lines 166–185 (`test_holdout_dataset_integrity_and_execution`) actively instantiates `HoldoutEvaluator` and runs `evaluator.run_holdout()` on all 9 questions on every test run.
   - **Honest Contamination Disclosure:** Neither dataset is a pristine, unexecuted holdout. Any claim of a virgin holdout would be untruthful. Contamination risk is recorded explicitly.

4. **Sealed Question Content Protection:**
   - In accordance with Gate 0 rules, **zero question text or answer contents of the holdout questions have been printed, copied, summarized, or revealed** in this audit. Only question IDs, categories, counts, and file-level metadata were inspected.

---

## 2. Baseline Artifact Inventory & Integrity Hashes

All evaluation artifacts, question files, scripts, and historical raw result files were inventoried and hashed using SHA-256:

| Artifact Path | File Size | Last Modified (UTC) | SHA-256 Hash | Purpose / Content Description |
| :--- | :---: | :---: | :--- | :--- |
| `src/evaluation/benchmark.py` | 13,339 B | 2026-10-15T04:00:42Z | `0146f14a18ff86524af1a53eda1922bb9e5f368b076ab63e80ee55e7227593c0` | Canonical 20-question benchmark dataset (`BENCH-01`..`BENCH-20`). |
| `src/evaluation/evaluator.py` | 20,985 B | 2026-10-15T09:47:36Z | `691779642c893d5d90a37784dbf64d822fb8a5d9437e7c097ed057c8d4820b0b` | ComparativeEvaluator harness and BenchmarkJudge for 20 questions. |
| `src/evaluation/holdout.py` | 7,034 B | 2026-10-17T06:14:22Z | `885e60f6199c73531737621e089465bda3f325d03d67f0e197ca72ae849141a4` | Separately authored 9-question holdout dataset (`HOLD-01`..`HOLD-09`). |
| `src/evaluation/holdout_runner.py` | 5,900 B | 2026-10-15T12:21:10Z | `704d4a4113cc38033e6f83ccba20d77e3a0d9e6f0498f50497bf1ac5ffae83ad` | HoldoutEvaluator runner for 9-question dataset. |
| `src/evaluation/temporal.py` | 9,073 B | 2026-10-17T06:08:23Z | `886b2eb345559cdf7fbbe3707c2d17b26cdca76d08f0b3ce7c4ee5683e3a58c5` | Historical cutoff queries enforcing temporal validity boundaries. |
| `src/evaluation/vector_baseline.py` | 16,592 B | 2026-10-15T12:17:54Z | `7f4c2fc9f1104e2200dbc989074ccd5ca37ae34429774f17df66b07effc38f4b` | Local TF-IDF vector baseline over repository text corpus. |
| `src/ui/benchmark_tab.py` | 6,476 B | 2026-10-17T10:15:50Z | `8b98d365424acbc62f116b126ec0521c19a8a67a199e8822e7718200e473af3a` | Phase 6 Streamlit UI Benchmark tab rendering audited metrics. |
| `project_context/evaluation_raw_results.json` | 51,753 B | 2026-10-15T11:12:48Z | `32c3ea15a5250317f578873665d9abc6dee0056f503222d36d79143922105502` | Raw evaluation output for all 20 `BENCH` questions across 3 modes. |
| `project_context/holdout_raw_results.json` | 22,991 B | 2026-10-17T03:35:33Z | `8b19698ab376354a74fb3b9eb3afdf312f600f95d32c6239c57697c603e18911` | Raw evaluation output for all 9 `HOLD` questions across 3 modes. |
| `project_context/baselines/run_1.json` | 51,804 B | 2026-10-15T11:13:00Z | `85e8dfb0b925f6ba890fc229d47c94b436940a08e6f1f516327b876a3bcf5a4c` | Baseline run 1 of 5 testing determinism of 20 benchmark questions. |
| `project_context/baselines/run_2.json` | 51,808 B | 2026-10-15T11:13:05Z | `a8d42ea5102573e0e7a256a74cb760f9e944b25ca837eef5bf4024220b29cebe` | Baseline run 2 of 5 testing determinism of 20 benchmark questions. |
| `project_context/baselines/run_3.json` | 51,809 B | 2026-10-15T11:13:10Z | `e3579b291dbff547d21cbfd0d611848bb2483566114878a2e79e6022e0329fef` | Baseline run 3 of 5 testing determinism of 20 benchmark questions. |
| `project_context/baselines/run_4.json` | 51,808 B | 2026-10-15T11:13:15Z | `59424754593f6520b22f98642220f8622c7a3a9cfcba78811e5a59d749df670e` | Baseline run 4 of 5 testing determinism of 20 benchmark questions. |
| `project_context/baselines/run_5.json` | 51,803 B | 2026-10-15T11:13:20Z | `5cb86b8ea92c9f55e05d0e74f145be8447d0d0ebc22d14cbcae741db4b29bb88` | Baseline run 5 of 5 testing determinism of 20 benchmark questions. |
| `project_context/EVALUATION_REPORT.md` | 8,918 B | 2026-10-15T04:45:26Z | `313536081a35d254d809d0636080350553b5319f09f3d41c1c2844613010d119` | Phase 6 evaluation summary report. |
| `project_context/PHASE_11_ADVERSARIAL_ACCEPTANCE_REPORT.md` | 19,590 B | 2026-10-15T14:05:44Z | `ba29ad94651bff87cf346e8c02d0fba35f2cbe4b1c6ad0a09fe34cd1bacff986` | Phase 11 report documenting holdout evaluation. |
| `tests/test_evaluation.py` | 8,211 B | 2026-10-17T06:14:34Z | `967c12507201d8802d630559a0447d6c1dc949d559f1d5d5ba4f19d6c6212606` | Test suite containing live execution of holdout questions. |

---

## 3. Analysis of Question Sets and Existing Runners

### A. The 20 Benchmark Questions (`BENCH-01` to `BENCH-20`)
- **Location:** `src/evaluation/benchmark.py`
- **Count:** 20 questions
- **Categories:**
  - `DECISION_TRACING`: 9 questions (`BENCH-02`, `03`, `04`, `05`, `06`, `07`, `08`, `09`, `10`)
  - `REVIEWER_ROUTING`: 3 questions (`BENCH-01`, `11`, `12`)
  - `CO_CHANGE`: 2 questions (`BENCH-14`, `15`)
  - `OWNERSHIP_DISCREPANCY`: 2 questions (`BENCH-16`, `17`)
  - `REFUSAL`: 4 questions (`BENCH-13`, `18`, `19`, `20`)
- **Historical Execution:**
  - Evaluated in `project_context/evaluation_raw_results.json` on 2026-10-15.
  - Scores: Graph ON: 20/20 (100.0%), Vector: 15/20 (75.0%), Graph OFF: 2/20 (10.0%).
  - Re-run across 5 baseline runs in `project_context/baselines/run_1.json`..`run_5.json`.

### B. The 9 Holdout Questions (`HOLD-01` to `HOLD-09`)
- **Location:** `src/evaluation/holdout.py`
- **Count:** 9 questions (not 8)
- **Categories:**
  - `REFUSAL`: 5 questions (`HOLD-03`, `05`, `06`, `07`, `08`)
  - `MULTI_HOP_TRACING`: 2 questions (`HOLD-01`, `02`)
  - `OWNERSHIP_DISCREPANCY`: 1 question (`HOLD-04`)
  - `FLAT_TEXT_PARITY`: 1 question (`HOLD-09`)
- **Historical Execution:**
  - Evaluated in `project_context/holdout_raw_results.json` on 2026-10-15 (Phase 11).
  - Scores: Graph ON: 9/9 (100.0%), Vector: 3/9 (33.3%), Graph OFF: 0/9 (0.0%).
  - **Actively executed in `tests/test_evaluation.py`:** On every execution of `pytest`, all 9 questions are executed against FalkorDB and asserted to achieve 9/9.

### C. Phase 6 Benchmark UI Runner (`src/ui/benchmark_tab.py`)
- Reads `project_context/evaluation_raw_results.json` and renders top metrics.
- Provides a button `"▶️ Run Live 10-Question Benchmark"` which executes 10 questions (`Q1`..`Q10`) defined in `src/ui/benchmark_tab.py` against `AgentExecutionLoop`.
- Does NOT execute `HOLD-01`..`HOLD-09`.

---

## 4. Contamination Audit & Holdout Integrity Status

1. **Has `evaluation_raw_results.json` evaluated all 20 questions?**  
   **YES.** All 20 questions (`BENCH-01` to `BENCH-20`) are present in `project_context/evaluation_raw_results.json` with full responses for Graph ON, Vector Baseline, and Graph OFF.

2. **Does `evaluation_raw_results.json` contain questions from `src/evaluation/holdout.py`?**  
   **NO.** The IDs are disjoint: `evaluation_raw_results.json` contains only `BENCH-01`..`BENCH-20`. However, target PRs #3170 and #3181 appear in both datasets for different questions.

3. **Has the holdout dataset been previously evaluated or exposed?**  
   **YES.** `project_context/holdout_raw_results.json` contains full evaluation results for all 9 questions. Furthermore, `tests/test_evaluation.py` executes them in CI/test runs.

4. **Conclusion on Contamination:**  
   **The holdout is contaminated by prior evaluation and test integration.**  
   In compliance with Gate 0, **we explicitly disclose this limitation and do not claim a pristine holdout.**

---

## 5. Specification Ambiguity on "12 Development and Eight Sealed Questions"

The Phase 7 prompt states:
> *"If the existing benchmark structure does not clearly identify the 12 development and eight sealed questions, stop and report the ambiguity instead of guessing which questions are sealed."*

**Specific Ambiguities Identified:**
1. **Benchmark Size vs. Split:** `src/evaluation/benchmark.py` has 20 questions, but no split tags.
   - Possible Interpretation A: The 20 questions in `benchmark.py` are to be partitioned into 12 dev (`BENCH-01`..`BENCH-12`, which are all answerable) and 8 sealed (`BENCH-13`..`BENCH-20`, which includes 4 refusals and 4 answerables).
   - Possible Interpretation B: `BENCH-01`..`BENCH-12` are 12 development questions, and `HOLD-01`..`HOLD-08` (from the 9-question `holdout.py`) are the 8 sealed questions.
   - Possible Interpretation C: All 20 `BENCH` questions are development, and `HOLD-01`..`HOLD-08` (or all 9) are sealed holdout questions.

Because guessing is strictly prohibited by Gate 0, we pause here to formally present this finding and clarify the split definition before proceeding to Gate 1.
