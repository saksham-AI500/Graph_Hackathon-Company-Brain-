# RepoBrain — Phase A Baseline Report
**Date:** October 15, 2026  
**Operating Standard:** Ponytail Full-Level + Superpowers Verification-Before-Completion  
**Workspace:** `D:\grraph Hackathon\RepoBrain`  
**Primary Target:** Graph Hacks 2026 — Track 03: Company Brain  

---

## 1. Test Suite Verification
Pre-repair test suite executed via:
`& ".\.venv\Scripts\python.exe" -m pytest -v`

- **Total Collected Tests:** 61
- **Passed:** 61 (100%)
- **Failed:** 0
- **Duration:** 12.36 seconds
- **Test Modules Covered:** 10 test modules (`test_db`, `test_evaluation`, `test_graph_queries`, `test_ingestion`, `test_integrity`, `test_investigation`, `test_milestone_1`, `test_ownership_drift`, `test_prompt_injection`, `test_ui`).

---

## 2. 5-Run Benchmark Evaluation Results
Benchmark was executed 5 consecutive times across all 20 questions in all 3 modes:
1. Mode A: Graph ON (FalkorDB relationship traversal with temporal cutoffs)
2. Mode B: Vector Baseline (Local TF-IDF semantic retrieval over raw text)
3. Mode C: Graph OFF (Direct heuristic baseline without relationship traversal)

Raw evaluation artifacts preserved at:
- `project_context/baselines/run_1.json`
- `project_context/baselines/run_2.json`
- `project_context/baselines/run_3.json`
- `project_context/baselines/run_4.json`
- `project_context/baselines/run_5.json`

### Performance Metrics Across 5 Runs

| Mode | Run | Overall Correct | Refusal Correct | GT Matched Evidence | Unsupported Claims | Total Latency (ms) | Avg Latency / Q (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Graph ON** | 1 | 20 / 20 (100%) | 4 / 4 (100%) | 47 / 73 (64.4%) | 0 (0.0%) | 88.48 | 4.42 |
| | 2 | 20 / 20 (100%) | 4 / 4 (100%) | 47 / 73 (64.4%) | 0 (0.0%) | 100.75 | 5.04 |
| | 3 | 20 / 20 (100%) | 4 / 4 (100%) | 47 / 73 (64.4%) | 0 (0.0%) | 108.66 | 5.43 |
| | 4 | 20 / 20 (100%) | 4 / 4 (100%) | 47 / 73 (64.4%) | 0 (0.0%) | 280.54 | 14.03 |
| | 5 | 20 / 20 (100%) | 4 / 4 (100%) | 47 / 73 (64.4%) | 0 (0.0%) | 109.79 | 5.49 |
| **Vector Baseline** | 1 | 15 / 20 (75.0%) | 4 / 4 (100%) | 8 / 46 (17.4%) | 0 (0.0%) | 318.94 | 15.95 |
| | 2 | 15 / 20 (75.0%) | 4 / 4 (100%) | 8 / 46 (17.4%) | 0 (0.0%) | 378.09 | 18.90 |
| | 3 | 15 / 20 (75.0%) | 4 / 4 (100%) | 8 / 46 (17.4%) | 0 (0.0%) | 488.33 | 24.42 |
| | 4 | 15 / 20 (75.0%) | 4 / 4 (100%) | 8 / 46 (17.4%) | 0 (0.0%) | 419.16 | 20.96 |
| | 5 | 15 / 20 (75.0%) | 4 / 4 (100%) | 8 / 46 (17.4%) | 0 (0.0%) | 511.48 | 25.57 |
| **Graph OFF** | 1 | 2 / 20 (10.0%) | 0 / 4 (0.0%) | 16 / 17 (94.1%) | 6 (30.0%) | 31.95 | 1.60 |
| | 2 | 2 / 20 (10.0%) | 0 / 4 (0.0%) | 16 / 17 (94.1%) | 6 (30.0%) | 39.51 | 1.98 |
| | 3 | 2 / 20 (10.0%) | 0 / 4 (0.0%) | 16 / 17 (94.1%) | 6 (30.0%) | 37.66 | 1.88 |
| | 4 | 2 / 20 (10.0%) | 0 / 4 (0.0%) | 16 / 17 (94.1%) | 6 (30.0%) | 35.17 | 1.76 |
| | 5 | 2 / 20 (10.0%) | 0 / 4 (0.0%) | 16 / 17 (94.1%) | 6 (30.0%) | 40.05 | 2.00 |

### Determinism Verification
- **Answer Decision Stability:** 100% identical across all 5 runs for all 20 questions in all 3 modes.
- **Evidence URL Stability:** 100% identical lists of evidence URLs emitted.
- **Refusal Decision Stability:** 100% identical refusal triggering.
- **Latency Jitter:** Small local OS scheduling variance (Graph ON total range: 88.5ms - 280.5ms; average ~137.6ms across 20 questions, which is ~6.88ms per query).

---

## 3. Git State & Remote Verification
- **Active Branch:** `main`
- **Remote `origin`:** `https://github.com/saksham-AI500/Graph_Hackathon-Company-Brain-.git`
- **Current Commit:** `6474fc8` (verified pushed to public remote)
- **Working Tree:** Modifications from Phase 9 pre-flight test hardening present in working tree (`src/investigation/models.py`, `src/ui/app.py`, `tests/test_investigation.py`, `tests/test_ui.py`).

---

## 4. FalkorDB Graph State
- **Container Host:** `localhost:6379`
- **Active Graph:** `repo_kg`
- **Connection Ping:** 1.69 ms roundtrip (Status: `healthy`)
- **Total Nodes:** 266
  - `PullRequest`: 50
  - `File`: 105
  - `Issue`: 36
  - `Person`: 75
- **Total Relationships:** 482
  - `MODIFIES`: 204
  - `RESOLVES`: 34
  - `REVIEWED`: 119
  - `AUTHORED`: 50
  - `REPORTED`: 75

---

## 5. Defect Analysis: Confirmed vs. Unconfirmed

| Item | Review Observation | Status | Exact Root Cause & Responsible Code |
| :--- | :--- | :--- | :--- |
| **B.1** | Fresh clone cannot run offline because `.cache/github/` is gitignored. | **CONFIRMED DEFECT** | `.gitignore:25` ignores `.cache/`. `src/ingestion/github_client.py:20,54-95` writes to `.cache/github/` only during live fetch, and does not provide a checked-in seed fixture fallback. Ingestion on fresh clone hits unauthenticated rate limits (60/hr). |
| **C.1** | Metric "47/73 valid URLs" is misleading; it measures ground-truth matches, not HTTP reachability. | **CONFIRMED DEFECT** | `src/evaluation/evaluator.py:86-92,153-158` scores `valid_evidence_count` based on whether citation starts with benchmark ground truth URL, NOT whether HTTP link is reachable. README and UI inappropriately describe this as "valid URLs". |
| **D.1** | Temporal cutoff logic has subtle leaks: allows `submitted_at IS NULL` and uses strict `<` instead of inclusive `<=`, lacks timezone normalization. | **CONFIRMED DEFECT** | `src/evaluation/temporal.py:44-45,115` has `(r.submitted_at IS NULL OR r.submitted_at < $cutoff)`. Null timestamps must not enter historical evidence. Cutoff contract must be inclusive as-of (`<=`) and timestamps must be normalized to timezone-aware UTC. |
| **D.2** | Missing mutation tests for verifier edge cases (fabricated PR, unrelated maintainer, future review, prompt injection). | **CONFIRMED GAP** | `tests/test_ownership_drift.py` and `tests/test_investigation.py` test basic rejections, but lack parameterized mutation tests covering 1-sec boundary mutations, null timestamps, and URL-claim mismatch. |
| **E.1** | Ownership discrepancy matching is calculated entirely in Python, not graph-native in FalkorDB. | **CONFIRMED ARCHITECTURAL DEFECT** | `src/ownership/discrepancy.py:73-75` calls Python `CodeownersParser.match(file_path)` instead of querying graph relationships. FalkorDB has NO `OwnershipRule` nodes, NO `[:DECLARES_OWNER]` or `[:COVERS]` edges. |
| **F.1** | No real FalkorDB graph algorithm executed or surfaced; visual evidence path missing in UI. | **CONFIRMED DEFECT** | Code only ran standard Cypher pattern matching. FalkorDB native `CALL algo.pageRank('Person', 'REVIEWED')` and `shortestPath((src)-[*..4]-(dst))` are supported on the running container, but were not integrated or rendered in the UI. |
| **I.1** | Unsubstantiated claims ("Zero Hallucination", "Autonomous institutional intelligence engine", "5.9x more valid citations"). | **CONFIRMED DOC DEFECT** | Absolute marketing claims in `README.md`, `blog_post.md`, and `demo_script.md` contradict honest reporting and the exact nature of the 20-question single-repo benchmark. |

---

## 6. Execution Plan & Next Steps
With Phase A baseline established and determinism verified across 5 runs, proceeding immediately to:
1. **Phase B:** Create checked-in seed data fixture `src/ingestion/fixtures/seed_repo_data.json` with metadata, enable seamless offline ingestion on clean clone without credentials, and verify idempotency on isolated test graph `test_kg_temp`.
2. **Phase C:** Implement opt-in URL auditor (`src/evaluation/url_auditor.py`), separate Ground-Truth Match vs HTTP Reachability vs Claim Support, audit 10 evidence URLs, and fix metric labels.
3. **Phase D:** Normalize UTC timestamps, enforce inclusive as-of cutoff (`<=`), exclude null timestamps, and add comprehensive verifier mutation regression tests.
4. **Phase E:** Add graph-native `OwnershipRule`, `[:DECLARES_OWNER]`, and `[:COVERS]` into FalkorDB and implement Cypher-native ownership drift query.
5. **Phase F:** Implement FalkorDB `algo.pageRank` for maintainer centrality and `shortestPath` for visual evidence paths, and render them in the Streamlit UI.
6. **Phase G & H:** Doc/comment evidence, UI edge cases, prompt injection verification, and browser smoke test.
7. **Phase I & Documentation:** Refine benchmark reporting, remove ungrounded claims, and update submission docs.
