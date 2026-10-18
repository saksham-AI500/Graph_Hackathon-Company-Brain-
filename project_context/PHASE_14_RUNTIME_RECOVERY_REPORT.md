# RepoBrain — Phase 14: Runtime Recovery & Execution Verification Report

**Document Status:** Official Phase 14 Environment Recovery & Verification Manifest  
**Workspace Root:** `D:\grraph Hackathon\grraph Hackathon\RepoBrain`  
**Date:** October 17, 2026  
**Auditor:** Antigravity Autonomous Pair-Programming Agent (Strict Verification Protocol)  

---

## 1. Executive Summary

Phase 14 has successfully recovered Docker Desktop, launched the FalkorDB graph database service via Docker Compose, ingested the deterministic offline repository seed data with 100% verified idempotency, verified live connectivity, and launched the Streamlit web application on `http://localhost:8501`.

The Git repository, working-tree state, staged files, and unstaged modifications remain **100% preserved**. Zero application code modifications were made.

---

## 2. Infrastructure & Service Status

| Service / Component | Status | Details & Observed Telemetry |
| :--- | :---: | :--- |
| **Docker Desktop** | **ONLINE** | Docker Desktop 4.95.0 / Engine 29.8.2 running via WSL2 backend (`docker-desktop` distro). |
| **Docker Compose** | **ONLINE** | Docker Compose v5.6.0 operational. |
| **FalkorDB Container** | **HEALTHY** | Container `falkordb` (`falkordb/falkordb:latest`, id `0adfc551b896`) running on `0.0.0.0:6379->6379/tcp`. |
| **Port 6379** | **BOUND** | FalkorDB active on `localhost:6379`. |
| **Python Client (`src/db.py`)** | **PASS** | `RETURN 1 AS ping` latency: **1.81 ms**, status: `HEALTHY`, target graph: `repo_kg`. |
| **Streamlit Application** | **ONLINE** | Serving on `http://localhost:8501` (HTTP 200 OK, Uvicorn server). |

---

## 3. Data Ingestion & Idempotency Verification

Offline seed ingestion from `src/fixtures/seed_repo_data.json` was executed into the target `repo_kg` graph:

- **Ingestion Mode:** Deterministic Seed Fixture (Offline, 0 network requests, 0 API tokens).
- **PRs Ingested:** 25 merged PR records, 16 issues, 210 repository files, 15 persons.
- **Pass 1 Ingestion Result:** **266 nodes**, **482 relationships** (Total pipeline time: 1.97s).
- **Pass 2 Idempotency Pass:** **266 nodes**, **482 relationships**.
- **Idempotency Verdict:** **100% IDENTICAL**. Zero node or edge count drift observed.
- **Graph Ownership Loading:** Ingested 3 CODEOWNERS rules, 3 teams, 3 `[:DECLARES_OWNER]` relationships, and 23 `[:COVERS]` relationships (`src/ownership/graph_ownership.py`).
- **Final Active Graph State:** **270 nodes**, **508 relationships**.
- **Graph Integrity Audit (`tests/test_integrity.py`):**
  - Duplicate entities: **0** (`test_zero_duplicate_entities` PASSED)
  - Dangling relationships: **0** (`test_zero_dangling_relationships` PASSED)
  - Public GitHub URL validity: **100%** (`test_valid_public_source_urls` PASSED)
  - Timestamp integrity: **100%** (`test_pull_request_timestamps_present` PASSED)

---

## 4. Test Suite Execution & Detailed Breakdown

Full test suite execution was performed using the active virtual environment (`.venv/Scripts/python.exe`):

- **Total Test Cases Collected:** **115** across 15 test files.
- **Passed:** **110** (95.7%)
- **Failed:** **5** (4.3%)
- **Errors:** **0**
- **Skipped:** **0**
- **Total Execution Time:** 14.91s

### Suite-by-Suite Results

| Test Suite File | Tests | Result | Status / Notes |
| :--- | :---: | :---: | :--- |
| `tests/test_db.py` | 4 | **4/4 PASS** | FalkorDB ping, read-only query, counts, empty key handling. |
| `tests/test_edge_cases_and_security.py` | 14 | **14/14 PASS** | Prompt injections, bot authors, large PRs, permissions. |
| `tests/test_evaluation.py` | 8 | **7/8 PASS** | 1 failure on `test_comparative_evaluator_runs_and_graph_on_outperforms` (see below). |
| `tests/test_graph_algorithms.py` | 5 | **2/5 PASS** | Maintainer PageRank and bot filtering pass; 3 shortestPath tests fail (see below). |
| `tests/test_graph_ownership.py` | 3 | **3/3 PASS** | Schema nodes, declared owners query, relationship dependency. |
| `tests/test_graph_queries.py` | 5 | **5/5 PASS** | Reviewer distribution, PR tracing, co-changes, decisions. |
| `tests/test_ingestion.py` | 8 | **8/8 PASS** | Models, issue extraction, caching, isolated seed ingestion. |
| `tests/test_integrity.py` | 6 | **6/6 PASS** | Zero duplicates, zero dangling edges, idempotency. |
| `tests/test_investigation.py` | 7 | **7/7 PASS** | Target PR exclusion, normalization, issue linking, refusals. |
| `tests/test_milestone_1.py` | 5 | **5/5 PASS** | Schema indexes, ownership drift on target modules. |
| `tests/test_ownership_drift.py` | 11 | **11/11 PASS** | CODEOWNERS parser, HHI concentration, discrepancy engine. |
| `tests/test_prompt_injection.py` | 8 | **8/8 PASS** | Hostile payloads, credential leakage prevention, read-only. |
| `tests/test_ui.py` | 10 | **9/10 PASS** | 1 failure on `test_ui_renders_visual_evidence_paths_and_pagerank` (shortestPath dependency). |
| `tests/test_url_auditor.py` | 6 | **6/6 PASS** | 200, 404, 429, timeouts, category aggregation. |
| `tests/test_verifier_mutations.py` | 15 | **15/15 PASS** | 1-second temporal cutoff boundary, 7 adversarial mutation checks. |

### Holdout Evaluation Benchmark (`src/evaluation/holdout_runner.py`)
- **Graph ON:** **9/9 (100.0%)** correct, 5/5 correct refusals, avg latency **25.17ms**.
- **Vector Baseline:** **3/9 (33.3%)** correct, 1/5 correct refusals, avg latency **100.58ms**.
- **Graph OFF:** **0/9 (0.0%)** correct, 0/5 correct refusals, avg latency **10.81ms**.

---

## 5. Root Cause Analysis of the 5 Test Failures

In accordance with safety rules, zero code modifications were made. The 5 test failures stem from two specific runtime/version nuances:

1. **ShortestPath Directionality in Current FalkorDB Engine (4 failures):**
   - **Failing Tests:**
     - `tests/test_graph_algorithms.py::test_find_explanation_path_pr_to_issue`
     - `tests/test_graph_algorithms.py::test_graph_algorithm_on_synthetic_graph`
     - `tests/test_graph_algorithms.py::test_find_explanation_path_edge_cases`
     - `tests/test_ui.py::test_ui_renders_visual_evidence_paths_and_pagerank`
   - **Observed Exception:**
     `redis.exceptions.ResponseError: FalkorDB does not currently support undirected shortestPath traversals`
   - **Root Cause:**
     In `src/graph/algorithms.py:93`, `find_explanation_path` executes Cypher:
     `RETURN shortestPath((src)-[*..4]-(dst)) AS path` (undirected syntax `-(dst)`).
     The newly pulled FalkorDB engine (`falkordb/falkordb:latest`, module ver 42201) enforces directed traversals for `shortestPath` (e.g., `(src)-[*..4]->(dst)`). Probed queries confirmed directed `shortestPath` executes and returns path objects cleanly.
   - **Classification:** Engine version behavior difference.

2. **Benchmark Question BENCH-15 Co-Change Tie Breaker (1 failure):**
   - **Failing Test:**
     - `tests/test_evaluation.py::test_comparative_evaluator_runs_and_graph_on_outperforms` (`assert 19 == 20`)
   - **Root Cause:**
     Question `BENCH-15` evaluates co-changes for `src/commands/bulk_insert.rs`, expecting keyword `apply.rs`. In the seed dataset, PR #3307 modified both files alongside several other files, giving multiple co-changed files identical `co_change_count = 1`. In `src/evaluation/temporal.py`, the query orders by `ORDER BY co_change_count DESC LIMIT 5` without a secondary sort key (`co_changed_file ASC`), causing `apply.rs` to land just outside the top 5 limit under the current database node ordering.
   - **Classification:** Test expectation tie-breaking sensitivity under newly seeded graph order.

---

## 6. Exact Commands for Future Operational Use

### 1. Start Docker / FalkorDB Service
```powershell
docker compose up -d
```

### 2. Verify FalkorDB Health
```powershell
& "d:\grraph Hackathon\grraph Hackathon\RepoBrain\.venv\Scripts\python.exe" -m src.db
```

### 3. Ingest Offline Seed Data (Idempotent)
```powershell
& "d:\grraph Hackathon\grraph Hackathon\RepoBrain\.venv\Scripts\python.exe" -m src.ingestion.run --seed
```

### 4. Run the Full Test Suite
```powershell
& "d:\grraph Hackathon\grraph Hackathon\RepoBrain\.venv\Scripts\python.exe" -m pytest -v
```

### 5. Run the Independent Holdout Benchmark
```powershell
& "d:\grraph Hackathon\grraph Hackathon\RepoBrain\.venv\Scripts\python.exe" -m src.evaluation.holdout_runner
```

### 6. Launch the Streamlit Web Application
```powershell
& "d:\grraph Hackathon\grraph Hackathon\RepoBrain\.venv\Scripts\python.exe" -m streamlit run app.py
```
Access in browser: `http://localhost:8501`

### 7. Stop FalkorDB Safely (Preserving Data Volume)
```powershell
docker compose stop
```
