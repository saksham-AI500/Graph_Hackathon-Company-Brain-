# RepoBrain — Phase 6 UI Report
**Company Brain UI, Graph Explorer & Live Evidence Dashboard**  
**Graph Hacks 2026 — Track 03: Company Brain**  
**Execution Timestamp:** 2026-10-17 16:32:00 IST  
**Environment:** Windows, Python 3.14 (.venv), FalkorDB 1.8.0 / 42201 on `localhost:6379`, graph: `repo_kg`  
**Streamlit App:** Serving on `http://localhost:8501` (HTTP 200 OK)  
**Git Branch:** `main`, HEAD: `9b6f003`  

---

## 1. Executive Summary

Phase 6 implements the **Company Brain UI, Graph Explorer & Live Evidence Dashboard** specified in `AGENT_BRIEF.md`. The interface exposes the existing knowledge graph, incremental sync engine, evidence-gated agent, interactive network visualizer, fair 3-way comparative evaluation, and live health diagnostics in a polished Streamlit application.

Key achievements:
1. **Sidebar Configuration (`src/ui/sidebar.py`):** Masked OpenRouter API key stored only in ephemeral session state (`type="password"`), model selector, central Graph ON / Plain Retrieval / Graph OFF demo switch, historical `as_of` date/time selector, live incremental sync button, and real-time FalkorDB/Sync connection telemetry.
2. **Ask the Brain Primary Chat Tab (`src/ui/chat_tab.py`):** Interactive conversation interface powered by `AgentExecutionLoop`. Displays verified structured answers with `[S1]`, `[S2]` citation anchors, clickable GitHub URLs, claim categorization (Facts, Inferences, Unresolved items), expandable multi-hop evidence graph paths, and step-by-step tool execution traces without secret leakage.
3. **Knowledge Graph Explorer Tab (`src/ui/explorer_tab.py`):** Interactive Vis.js Network canvas rendering local entity neighborhoods up to 2 hops. Visualizes color-coded entity types (`Person`, `PullRequest`, `Issue`, `File`, `Team`, `Document`, `Decision`), distinguishes active vs closed/tombstoned entities, and includes a tabular property inspector.
4. **Live Change Feed Tab (`src/ui/feed_tab.py`):** Queries `(:SyncRun)` and `(:SyncRun)-[:CHANGED]->(target)` records from FalkorDB. Displays run status, duration, repository scope, event counts, operation breakdowns (`upsert_node`, `upsert_edge`, `close_edge`, `tombstone_node`), before/after audit states, and real vs dry-run distinction.
5. **Fair 3-Way Architecture Comparison Tab (`src/ui/compare_tab.py`):** Implements side-by-side evaluation across Graph ON (Company Brain Agent), Plain Retrieval (TF-IDF Vector Baseline via `LocalVectorBaseline`), and Graph OFF (direct LLM). Reports latency (ms), source support, refusal discipline, and honest engine labeling (Live LLM vs Deterministic Fallback).
6. **Benchmark Tab (`src/ui/benchmark_tab.py`):** Surfaces audited evaluation results from `project_context/evaluation_raw_results.json` (Graph ON 100% vs Vector 75% vs OFF 10%), historical question cards, and an interactive live 10-question test runner executing against active `repo_kg`.
7. **Health & Diagnostics Tab (`src/ui/health_tab.py`):** Displays real-time FalkorDB status, latency, node counts by label, relationship counts by type, stale-document audit metrics (`audit_repository_documentation_staleness`), and runtime environment dependencies.
8. **PR Investigation Brief Preservation (`src/ui/pr_brief_tab.py`):** Preserved 100% of existing deterministic PR investigation capabilities, ownership drift risk findings, maintainer review PageRank, and visual evidence paths.
9. **Full Automated Test Suite Status:** **200 passed in 25.15s** (11 new Phase 6 UI tests in `tests/test_ui_phase6.py`, 10 existing UI tests in `tests/test_ui.py` passing, 0 failures, 0 errors, 0 skips).
10. **Git Discipline:** Created 4 focused Phase 6 commits (`8f1a8f5`, `5e7859b`, `9de1a1b`, `9b6f003`).

---

## 2. Tab & Control Implementation

The UI architecture is organized under `src/ui/` with clear separation of concerns:

```
src/ui/
├── __init__.py           # UI module declaration
├── app.py                # Main Streamlit assembly & page configuration
├── sidebar.py            # Sidebar controls, masked API key, model selector, sync trigger
├── chat_tab.py           # Tab 1: 'Ask the Brain' primary conversation interface
├── pr_brief_tab.py       # Tab 2: 'PR Brief' deterministic investigation & ownership drift
├── explorer_tab.py       # Tab 3: 'Graph Explorer' interactive Vis.js neighborhood canvas
├── feed_tab.py           # Tab 4: 'Change Feed' live sync runs & audit change records
├── compare_tab.py        # Tab 5: 'Compare' fair 3-way evaluation (ON vs Vector vs OFF)
├── benchmark_tab.py      # Tab 6: 'Benchmark' audited metrics & live 10-question test runner
└── health_tab.py         # Tab 7: 'Health' live telemetry, node/edge counts, stale docs
```

### Sidebar Controls
- **API Key Security:** OpenRouter API Key input has `type="password"`. Value is stored only in ephemeral `st.session_state["openrouter_api_key"]`. Never logged, written to disk, or serialized.
- **Model Selector:** Configurable dropdown defaulted to `os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")` with custom model slug input support.
- **Demo Control:** Radio buttons switching between:
  - `Graph ON (Company Brain Agent)`
  - `Plain Retrieval (TF-IDF Vector)`
  - `Graph OFF (Direct Model Alone)`
- **Temporal Cutoff:** Checkbox toggles date and time selectors generating UTC ISO 8601 strings (e.g., `2024-01-01T00:00:00Z`).
- **Sync Trigger:** Dedicated "🔄 Sync Now" button invoking `SyncEngine.run_once(dry_run=False)` with live execution status.
- **Connection Diagnostics:** Dynamic badge displaying connection state, latency (ms), node count (298), edge count (531), and sync cursor age.

---

## 3. Graph ON, Plain Retrieval & Graph OFF Separation

The **Compare** tab (`src/ui/compare_tab.py`) and sidebar demo switch enforce strict isolation among the three architectures:

1. **Graph ON (Company Brain Agent):**
   - Executes through `AgentExecutionLoop(client=client)`.
   - Has access to all 14 typed graph tools (`find_entity`, `get_entity`, `neighbors`, `who_owns`, `who_knows`, `trace_decision`, `find_stale_docs`, `explain_path`, `pr_brief`, `sync_status`, etc.).
   - Gated by `AgentEvidenceVerifier`.
   - Results in `[VERIFIED]` evidence-backed claims or explicit `[REFUSED]` outcomes.

2. **Plain Retrieval (TF-IDF Vector Baseline):**
   - Executes through `LocalVectorBaseline` in `src/evaluation/vector_baseline.py`.
   - Indexes identical repository text documents (PR bodies, issue descriptions, file paths).
   - Zero graph traversal, zero knowledge graph tools.
   - Computes cosine similarity over TF-IDF vectors respecting `as_of` cutoffs.
   - Lacks entity relationships, CODEOWNERS precedence, and verifier gating.

3. **Graph OFF (Direct Model Alone):**
   - Direct LLM prompt without repository context or graph tools.
   - Zero database reads, zero graph access.
   - In zero-key environments, explicitly reports `[UNAVAILABLE]` without fabricating model responses.

---

## 4. Citation and Evidence-Path Rendering

The chat and investigation interfaces render authentic, verified sources:
- **In-Text Citation Anchors:** Uses standard `[S1]`, `[S2]` markers corresponding to the structured source list.
- **Clickable Source Links:** Every citation resolves to an authentic GitHub URL (e.g., `https://github.com/FalkorDB/FalkorDB/pull/3339`, `https://github.com/FalkorDB/FalkorDB/blob/main/CODEOWNERS`).
- **Claim Categorization:** Explains the derivation of each statement:
  - **Facts:** Direct assertions supported by active FalkorDB nodes and relationships.
  - **Inferences:** Derived reasoning (such as decayed KNOWS scores or bus-factor calculations).
  - **Unresolved / Refusal:** Gaps where evidence is absent or unverifiable.
- **Multi-Hop Graph Paths:** Evidence paths computed via `find_shortest_path` or `find_explanation_path` render sequential relationship hops: `(src) -> [:REL] -> (dst)`.

---

## 5. Live Change Feed and Health Checks

### Change Feed Tab
- Queries `MATCH (s:SyncRun) OPTIONAL MATCH (s)-[c:CHANGED]->(target) ...` via `FalkorDBClient.ro_query`.
- Surfaces:
  - Run ID, Status (`SUCCESS`, `PARTIAL`, `FAILED`), Duration, Event Count.
  - Execution mode: `[REAL SYNC]` vs `[DRY-RUN]`.
  - Detailed mutation audit: Operation (`upsert_node`, `upsert_edge`, `close_edge`, `tombstone_node`), Target ID, Before state, After state.
  - Repository scope (`FalkorDB/FalkorDB`) and cursor advance state.

### Health Tab
- **Database Telemetry:** Confirms FalkorDB 1.8.0 connection status, query latency (1.1ms), total nodes (298), and total edges (531).
- **Label Breakdown:** Node counts per label (`File: 110`, `Person: 67`, `PullRequest: 63`, `Issue: 27`, `Team: 15`, `Document: 8`, `Decision: 8`).
- **Relationship Breakdown:** Edge counts per type (`MODIFIES`, `AUTHORED`, `REVIEWED`, `RESOLVES`, `ON`, `REFERENCES`, `DECIDED_IN`, `OWNS`).
- **Knowledge Integrity Audit:** Runs `audit_repository_documentation_staleness(client)`, reporting 0 stale documents and 0 unresolved timestamps against active code files.
- **Runtime Dependencies:** Reports Python 3.14, Streamlit 1.66.0, read-only query mode (`ro_query`), and GraphWriter mutation gating.

---

## 6. Actual Benchmark Data Sources

The **Benchmark** tab displays authentic evaluation metrics:
- Primary data source: [`project_context/evaluation_raw_results.json`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/project_context/evaluation_raw_results.json).
- Audited results:
  - **Graph ON:** 20/20 correct (100.0% accuracy), 0 unsupported claims, 4.01ms avg latency.
  - **Vector Baseline:** 15/20 correct (75.0% accuracy), 14.46ms avg latency.
  - **Graph OFF:** 2/20 correct (10.0% accuracy).
- Includes an interactive "▶️ Run Live 10-Question Benchmark" button that runs the 10 canonical Phase 5 test cases live against `repo_kg` and displays individual verdicts without altering sealed holdout artifacts.

---

## 7. Offline and No-Key Handling

RepoBrain is engineered to remain fully operational across degraded environments:
1. **No OpenRouter API Key:**
   - Sidebar displays `Mode: Zero-Key Deterministic Fallback (Offline Safe)`.
   - Agent automatically engages the deterministic fallback planner (`_execute_deterministic_fallback`).
   - Answers are grounded directly in FalkorDB graph evidence and validated by `AgentEvidenceVerifier`.
   - Never fabricates LLM output; reports engine honestly.
2. **Offline FalkorDB (`localhost:6379` unreachable):**
   - Sidebar displays `[OFFLINE] FalkorDB Offline`.
   - Main body renders clean error card: `[ERROR] Database Connection Failed` with instructions to verify Docker container `falkordb`.
   - Does not crash or raise unhandled exceptions (verified by `test_ui_database_unavailability_handling`).
3. **Empty Graph / Missing Entities:**
   - When a requested entity does not exist (e.g. PR #9999 or `fake_file.py`), the agent and UI issue explicit `[REFUSED]` cards explaining the lack of ground-truth evidence.

---

## 8. Test Suite Verification

Full test suite execution:
```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q
```

**Result:**
```
........................................................................ [ 36%]
........................................................................ [ 72%]
........................................................                 [100%]
200 passed in 25.15s
```

Breakdown:
- **UI Tests (`tests/test_ui.py` & `tests/test_ui_phase6.py`):** 21/21 passed in 7.20s.
- **Agent Tests (`tests/test_agent.py`):** 16/16 passed.
- **Decision & Knowledge Tests (`tests/test_decision_tracing.py`, `tests/test_knowledge_*.py`):** 23/23 passed.
- **Sync Engine Tests (`tests/test_sync.py`):** 11/11 passed.
- **GraphWriter & Audit Tests (`tests/test_graph_writer.py`):** 12/12 passed.
- **Phase 0 Baseline Defect Tests (`tests/test_phase0_defects.py`):** 10/10 passed.
- **Total:** **200 passed, 0 failed, 0 errors, 0 skipped.**

---

## 9. Git Commits Created

Four focused, atomic commits created on branch `main`:
1. `8f1a8f5`: `feat: add Company Brain sidebar, multi-tab layout, and chat interface`
2. `5e7859b`: `feat: add interactive graph explorer and change feed tabs`
3. `9de1a1b`: `feat: add fair 3-way architecture comparison and live benchmark tabs`
4. `9b6f003`: `test: cover Phase 6 multi-tab UI, masked key, and mode separation`

Pre-existing 48 staged files and all unstaged working tree files were preserved.

---

## 10. Phase 7 Readiness & Next Steps

Phase 6 is complete. RepoBrain now features a complete, multi-tabbed, evidence-gated user interface exposing every capability of the Company Brain architecture.

### Readiness for Phase 7 (Evaluation & Benchmark Hardening)
- Streamlit UI is verified and running on `http://localhost:8501`.
- The 3-way evaluation harness (`compare_tab.py` and `benchmark_tab.py`) provides the foundational interface for running formal holdout evaluations in Phase 7.
- Grounded metrics and raw export paths are verified and intact.
