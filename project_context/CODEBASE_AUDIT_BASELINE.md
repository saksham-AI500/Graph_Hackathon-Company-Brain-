# RepoBrain — Codebase Audit Baseline (Phase 1)

**Date & Time:** October 17, 2026, 18:59 IST  
**Auditor:** Antigravity Autonomous Pair-Programming Agent (Ponytail Minimal-Complexity Standard & Superpowers Verification)  
**Target Repository:** `D:\grraph Hackathon\grraph Hackathon\RepoBrain`  
**Git Branch & Revision:** `main` @ `96c59cd` (ahead of `origin/main` by 32 commits)  

---

## 1. Executive Summary & Verification State

RepoBrain is an evidence-backed software-repository knowledge engine built for **FalkorDB Graph Hacks 2026 (Track 03: Company Brain)**. This baseline document freezes and records the exact operational state of the repository before performing the comprehensive codebase audit, bug diagnosis, and safe optimization requested in the engineering directive.

### Current Operating Health
* **Automated Test Suite:** **220/220 passing** across 18 test suites in 30.40 seconds (`pytest tests/ -v`).
* **FalkorDB Graph (`repo_kg`):** **Healthy** (`status: healthy`, latency: `0.91ms`), containing **306 nodes** and **531 edges**.
* **Streamlit Web Application (`app.py`):** **Online** and listening on `http://localhost:8501` (HTTP 200 OK).
* **Python Runtime Environment:** Python 3.14.6 virtual environment active at `D:\grraph Hackathon\grraph Hackathon\RepoBrain\.venv`.
* **Working Tree State:** All existing modified (36) and untracked (32) files strictly preserved in-place without resets, stashes, or deletions.

---

## 2. Git Working Tree State

### Status Overview
* **Staged Changes:** 0 files.
* **Modified Files (Unstaged):** 36 files.
  - `.gitignore`, `README.md`, `demo_script.md`
  - `project_context/PROGRESS.md`, `SESSION_LOG.md`, `UI_REQUIREMENTS_BACKLOG.md`
  - `project_context/eval_v2/manifest.json`, `project_context/evaluation_raw_results.json`
  - `src/agent/client.py`, `loop.py`, `models.py`
  - `src/db.py`
  - `src/evaluation/evaluator.py`, `evaluator_v2.py`, `temporal.py`, `vector_baseline.py`
  - `src/graph/algorithms.py`, `queries/core.py`
  - `src/ingestion/github_client.py`, `loader.py`, `models.py`, `run.py`
  - `src/investigation/__init__.py`, `models.py`, `orchestrator.py`, `tools.py`, `verifier.py`
  - `src/ui/chat_tab.py`, `sidebar.py`
  - `tests/test_db.py`, `test_evaluation.py`, `test_evaluation_v2.py`, `test_graph_queries.py`, `test_ingestion.py`, `test_investigation.py`, `test_ownership_drift.py`
* **Untracked Files:** 32 files (including `.env.example`, `scripts/`, `src/fixtures/seed_repo_data.json`, new regression test files, and audit logs).

---

## 3. Verified Inventory of Codebase Components

### A. Core Database & Schema
* `src/db.py`: `FalkorDBClient` wrapper managing connection pooling, `ro_query` read-only execution, schema validation, and health checks.
* `src/graph/schema.py`: Canonical schema definitions for nodes (`Person`, `PullRequest`, `Issue`, `File`, `Team`, `OwnershipRule`, `Comment`, `Document`, `Decision`, `SyncRun`, `SyncState`) and edges (`AUTHORED`, `REVIEWED`, `MODIFIES`, `RESOLVES`, `REPORTED`, `DECLARES_OWNER`, `COVERS`, `OWNED_BY`, `CHANGED`, `ON`, `REFERENCES`, `DECIDED_IN`, `AFFECTS`, `SUPERSEDES`).
* `src/graph/writer.py`: `GraphWriter` enforcing strict transactional mutations, allowlisted labels, mandatory provenance metadata (`source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`), non-destructive `close_edge` and `tombstone_node` semantics.
* `src/graph/algorithms.py`: Maintainer PageRank calculation (`CALL algo.pageRank('Person', 'REVIEWED')`) with bot exclusion, and explanation shortest-path traversal.
* `src/graph/queries/`: `core.py` (decision tracing, documented decisions, reviewer routing) and `drift.py` (ownership drift queries).

### B. Ingestion & Incremental Sync Engine
* `src/ingestion/`: `github_client.py`, `loader.py`, `models.py`, `run.py` (offline seed loading from `src/fixtures/seed_repo_data.json` and online GitHub REST fetching).
* `src/sync/`: Decentralized sync pipeline:
  - `models.py`: Typed change events.
  - `state.py`: `SyncStateManager` with FalkorDB persistence and 300s TTL distributed concurrency locking.
  - `fetcher.py`: `GitHubFetcher` with ETag handling, backoff, and offline JSONL fixture replay.
  - `reconciler.py`: `EventReconciler` mapping events to `GraphWriter` mutation operations.
  - `engine.py`: `SyncEngine` managing execution modes (`--once`, `--watch`, `--dry-run`, `--replay`).
  - `cli.py`: CLI entrypoint.

### C. Company Brain Agent & Verifier
* `src/agent/models.py`: Typed Pydantic models: `AgentRequest`, `AgentAnswer`, `SourceItem`, `Claim`, `ToolCall`, `ToolResult`.
* `src/agent/prompt.py`: System prompt enclosing untrusted repository data in `<untrusted_data>` fences.
* `src/agent/client.py`: `OpenRouterClient` restricting model execution strictly to verified DeepSeek models (`deepseek/deepseek-chat`, `deepseek/deepseek-r1`, `deepseek/deepseek-v4.1-flash`, `deepseek/deepseek-v3.2`).
* `src/agent/tools.py`: Allowlisted registry of 14 typed graph tools (10 read, 4 action) executing read-only Cypher queries.
* `src/agent/loop.py`: `AgentExecutionLoop` running bounded ReAct tool loops (max 5 steps, max 1 retry per tool, low token budget).
* `src/agent/verifier.py`: `EvidenceVerifier` non-LLM gate verifying claims against graph records, timestamps, and exact quote character slices.

### D. PR Investigation & Ownership Intelligence
* `src/investigation/`: `models.py`, `orchestrator.py`, `tools.py`, `verifier.py` (PROnlineEvidenceVerifier).
* `src/ownership/`: `codeowners.py` (parser), `metrics.py` (bus-factor calculation with exponential decay), `discrepancy.py`, `graph_ownership.py`, `orphaned.py`, `verifier.py`.
* `src/decision/`: `extractor.py` (conservative rule-based quote extraction), `verifier.py` (ground-truth substring verification), `models.py`.
* `src/knowledge/`: `comments.py`, `documents.py`, `scoring.py` (KNOWS score), `stale_docs.py`, `temporal.py`.

### E. Evaluation Framework (v2)
* `src/evaluation/evaluator_v2.py`: Benchmark v2 tri-mode comparative evaluator (Graph ON vs Plain Retrieval vs Graph OFF).
* `src/evaluation/benchmark.py`: Canonical 20-question benchmark partitioned into Development (12 Qs) and Sealed (8 Qs).
* `src/evaluation/vector_baseline.py`: TF-IDF vector retrieval baseline with temporal filtering.
* `src/evaluation/holdout.py` & `holdout_runner.py`: Independent 9-question adversarial holdout dataset.
* `src/evaluation/url_auditor.py`: HTTP citation reachability and entity-grounding auditor.
* `src/evaluation/summary_generator.py`: Generates frozen JSON summaries in `project_context/eval_v2/`.

### F. User Interface (Streamlit)
* `app.py` & `src/ui/app.py`: Main Streamlit application with 7 feature tabs:
  1. Primary Chat ("Ask the Brain"): Interactive Q&A with claim categorization, citations, evidence graph hops, and tool traces.
  2. PR Brief: Target PR deep-dive, ownership drift, and co-changes.
  3. Knowledge Graph Explorer: Vis.js network visualization of local neighborhoods.
  4. Live Change Feed: Audit trail of `(:SyncRun)` and `(:SyncRun)-[:CHANGED]->(target)` operations.
  5. 3-Way Architecture Comparison: Side-by-side Graph ON vs Plain Retrieval vs Graph OFF.
  6. Benchmark v2: Interactive benchmark runner and raw summary inspector.
  7. Health & Diagnostics: Latency telemetry, node/edge counts, and documentation staleness audit.
* `src/ui/sidebar.py`: Ephemeral masked API key entry, model selection, `as_of` time-travel toggle, and sync triggering.

---

## 4. Known Startup & Runtime Issues (Pre-Audit)

1. **AgentAnswer Tool Calls & Refusal Field Mismatch:**
   - *Symptom:* `AttributeError: 'AgentAnswer' object has no attribute 'tool_calls'` and `'refusal_reason'` in `src/ui/chat_tab.py`.
   - *Status:* Resolved in prior turn by adding real fields and post-init synchronization in `src/agent/models.py` and guarding getters in `src/ui/chat_tab.py`. Verified working.
2. **Pydantic Model Extra Attributes vs Properties:**
   - In Pydantic v2, accessing undeclared attributes via `getattr(instance, 'field')` raises an `AttributeError` if `extra="ignore"` or default strictness is enabled, rather than safely returning defaults if properties are incomplete.
3. **Vis.js Graph Rendering in Streamlit:**
   - Visualizing large multi-hop graphs with `st.components.v1.html` prints deprecation warnings in Streamlit 1.66 (`Please replace st.components.v1.html with st.iframe`).

---

## 5. Test Suite Baseline (220 Passed)

The full test suite was executed via `pytest tests/ -v`:
* **Total Collected:** 220 tests across 18 test files.
* **Result:** **220 passed, 0 failed, 0 errors, 0 skipped** in 30.40 seconds.
* **Test Suites Covered:**
  - `tests/test_agent.py` (16 tests)
  - `tests/test_db.py` (3 tests)
  - `tests/test_decision_tracing.py` (7 tests)
  - `tests/test_deepseek_config.py` (7 tests)
  - `tests/test_edge_cases_and_security.py` (14 tests)
  - `tests/test_evaluation.py` (9 tests)
  - `tests/test_evaluation_v2.py` (10 tests)
  - `tests/test_graph_algorithms.py` (4 tests)
  - `tests/test_graph_ownership.py` (4 tests)
  - `tests/test_graph_queries.py` (5 tests)
  - `tests/test_graph_writer.py` (12 tests)
  - `tests/test_ingestion.py` (8 tests)
  - `tests/test_investigation.py` (7 tests)
  - `tests/test_knowledge_logic.py` (8 tests)
  - `tests/test_knowledge_sources.py` (8 tests)
  - `tests/test_milestone_1.py` (5 tests)
  - `tests/test_ownership_drift.py` (10 tests)
  - `tests/test_phase0_defects.py` (10 tests)
  - `tests/test_prompt_injection.py` (8 tests)
  - `tests/test_sync.py` (11 tests)
  - `tests/test_ui.py` (10 tests)
  - `tests/test_ui_phase6.py` (11 tests)
  - `tests/test_url_auditor.py` (6 tests)
  - `tests/test_verifier_mutations.py` (15 tests)

---

## 6. Audit Scope & Rules of Engagement

1. **Safety First:** No deletions, no destructive resets, no overwriting user work or historical artifacts.
2. **Ponytail Principles:** Shortest working diff, standard library first, zero speculative bloat, root-cause repair.
3. **DeepSeek Restriction:** Maintain strict enforcement of verified DeepSeek models.
4. **Preserve Benchmark Integrity:** Canonical evaluation questions, ground truths, and sealed split isolation remain 100% untouched.
