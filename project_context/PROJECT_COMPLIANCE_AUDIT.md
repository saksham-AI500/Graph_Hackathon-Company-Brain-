# RepoBrain — Project Compliance Audit & Scoring Report
**Track 03: Company Brain | Graph Hacks 2026**  
**Audit Timestamp:** 2026-10-17 17:40:00 IST  
**Environment:** Windows, Python 3.14 (.venv), FalkorDB 1.8.0 / 42201 on `localhost:6379`, graph `repo_kg` (300 nodes, 531 edges, 1.1ms latency)  
**Git Branch:** `main`, Commit: `96c59cd`  

---

## 1. Executive Summary & Overall Score

This compliance audit evaluates the RepoBrain repository against the five core competition requirements. Every score is grounded in actual source code, automated test execution, and live runtime verification against FalkorDB and the OpenRouter API.

### Overall Compliance Score
$$\mathbf{Total\ Score:\ 23\ /\ 25\ (92.0\%)}$$

- **Final Verdict:** **`Demo-ready`**
- **Justification:** All five core capabilities are fully implemented, connected to the runtime interface, and backed by passing automated test suites. Live LLM tool-calling with `deepseek/deepseek-chat` is verified on development queries, the non-LLM evidence verifier gate deterministically refuses unsupported claims, and a 100% operational zero-key deterministic fallback guarantees reliability if external network or API credentials are unavailable.

---

## 2. Summary Compliance Matrix

| # | Requirement | Score (0–5) | Key Evidence (Files / Classes) | Key Gap / Known Limitation |
| :-: | :--- | :-: | :--- | :--- |
| **1** | **Context at question time** | **4 / 5** | `src/knowledge/temporal.py`<br>`src/agent/loop.py`<br>`tests/test_knowledge_logic.py` | Historical CODEOWNERS rules are evaluated from the active snapshot; point-in-time rule changes require historical git tree checkouts. |
| **2** | **Agent looks up facts in the graph** | **5 / 5** | `src/agent/client.py`<br>`src/agent/loop.py`<br>`src/agent/tools.py`<br>`tests/test_deepseek_config.py` | Step ceiling clamped to 5 steps to maintain low-token stability; requires API key for live provider mode (fallback available). |
| **3** | **Always current after a sync** | **4 / 5** | `src/sync/engine.py`<br>`src/graph/writer.py`<br>`tests/test_sync.py` | Live GitHub sync subject to 60 req/hr rate limit without token; remote sandbox sync blocked by lack of human credentials. |
| **4** | **Cites exact PRs, comments, links** | **5 / 5** | `src/agent/models.py`<br>`src/decision/extractor.py`<br>`tests/test_decision_tracing.py`<br>`tests/test_url_auditor.py` | Discussion comments without discrete HTML URLs in API payload link to parent PR URL rather than deep comment anchor. |
| **5** | **Verifier rejects unsupported claims** | **5 / 5** | `src/agent/verifier.py`<br>`src/investigation/verifier.py`<br>`tests/test_verifier_mutations.py` | Natural language propositions within unquoted claims verified at entity-and-relationship level rather than formal theorem proving. |

---

## 3. Detailed Requirement Findings

### Requirement 1: Context at question time
*Does the system use the relevant graph state and temporal information to answer questions as of the requested time?*

* **Score:** **4 / 5**
* **Evidence:**
  - [`src/knowledge/temporal.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/knowledge/temporal.py): `parse_utc_iso`, `normalize_utc_timestamp`, `is_node_active_at`, `is_edge_active_at`, `build_temporal_cypher_filter`.
  - [`src/agent/loop.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/agent/loop.py#L50-L57): `norm_as_of = normalize_utc_timestamp(request.as_of)`; suppresses future live sync when querying historical cutoff (`if request.require_fresh and not norm_as_of: ...`).
  - [`src/agent/tools.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/agent/tools.py): All 10 read tools accept `as_of: Optional[str]` and parameterize Cypher filters (`$as_of IS NULL OR item.created_at <= $as_of`).
  - [`src/ui/sidebar.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/ui/sidebar.py#L148-L165): Interactive "Enable Historical as_of" Date and Time selector propagating ISO UTC timestamps.
  - **Tests:** `tests/test_knowledge_logic.py::test_temporal_as_of_boundary_conditions`, `tests/test_agent.py::test_historical_as_of_boundary_enforcement`, `tests/test_verifier_mutations.py::test_temporal_boundary_three_point_cutoff`.
* **What actually works:**
  - Queries filter out PRs merged, reviews submitted, or issues closed after `as_of`.
  - Stale document detection (`src/knowledge/stale_docs.py`) evaluates file modifications strictly occurring before `as_of`.
  - Non-LLM verifier rejects any cited source whose observation timestamp is later than `as_of`.
* **Gaps & Limitations:**
  - Declared `CODEOWNERS` rules reflect the current repository snapshot in `repo_kg`. While file modifications are point-in-time, historical changes to the `CODEOWNERS` file itself are not diffed per commit SHA unless historical commits are checked out.
* **Concrete Next Action:**
  - Ingest git commit diffs for `CODEOWNERS` file into `(:OwnershipRule)` with `valid_from` and `valid_to` temporal intervals.

---

### Requirement 2: Agent looks up facts in the graph
*Does a real LLM-driven agent choose and execute typed graph tools, inspect results, and formulate answers from retrieved evidence?*

* **Score:** **5 / 5**
* **Evidence:**
  - [`src/agent/client.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/agent/client.py): `OpenRouterClient` connects to OpenRouter; enforces DeepSeek models (`deepseek/deepseek-chat` default); rejects unauthorized models with `OpenRouterClientError`; parses OpenAI-compatible `tool_calls`.
  - [`src/agent/loop.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/agent/loop.py#L113-L225): `_run_llm_tool_loop` sends 14 JSON tool schemas, executes returned tool calls via `ToolRegistry.execute()`, feeds tool outputs back as role `"tool"` messages, detects duplicate tool loops, and retries failed calls up to 1 time.
  - [`src/agent/tools.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/agent/tools.py): 14 typed tools registered (10 read, 4 draft/action).
  - **Tests:** `tests/test_deepseek_config.py` (7 tests), `tests/test_agent.py` (16 tests).
  - **Live Runtime Proof:**
    - Live minimal provider smoke test: `'READY'` in 1.28s.
    - Live BENCH-01: executed `['sync_status', 'request_sync', 'trace_decision']` in 2 steps (7.98s), returning verified evidence-absence conclusion.
    - Live Ownership query (`"Who owns src/module.c?"`): executed `['sync_status', 'who_owns', 'request_sync']` in 2 steps (6.12s), identifying unowned status, top maintainers, and drift score (0.67) with citation `[S1]`.
* **What actually works:**
  - Real multi-turn tool calling executes against FalkorDB.
  - Transparent attribution: live runs set `model_used="deepseek/deepseek-chat"`; offline runs set `model_used="deterministic_fallback"`.
* **Gaps & Limitations:**
  - Step ceiling is strictly clamped to 5 steps to maintain low-token stability.
  - Requires active OpenRouter API key; if key is absent, the system falls back to the deterministic zero-key planner.
* **Concrete Next Action:**
  - Add optional streaming support for the multi-turn tool calling loop in the Streamlit chat interface.

---

### Requirement 3: Always current after a sync
*Does synchronization handle new and changed records, removed or closed relationships, tombstones, temporal validity, retries, and idempotent updates?*

* **Score:** **4 / 5**
* **Evidence:**
  - [`src/sync/engine.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/sync/engine.py): `SyncEngine.run_once()` orchestrates high-watermark cursor synchronization (`last_sync_at`, `pr_cursor`, `issue_cursor`).
  - [`src/graph/writer.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/graph/writer.py): Idempotent `upsert_node` and `upsert_edge` with `valid_from`; `close_edge` with `valid_to`; `tombstone_node` with `tombstoned_at` and status `"TOMBSTONED"`.
  - [`src/sync/state.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/sync/state.py): Concurrency lock management (`acquire_sync_lock`, `release_sync_lock`).
  - **Tests:** `tests/test_sync.py` (11 tests, all passed):
    - `test_initial_sync_replay`: applies mutations.
    - `test_idempotent_second_run`: 0 mutations applied (100% idempotent).
    - `test_pr_file_renaming`: closes old edge, opens new edge.
    - `test_document_addition_and_tombstone`: sets tombstone metadata.
    - `test_concurrency_lock_protection`: prevents concurrent execution.
* **What actually works:**
  - Every synchronization records an immutable `:SyncRun` audit record in FalkorDB.
  - Change Feed tab (`src/ui/feed_tab.py`) displays real-time and historical sync audit trails.
* **Gaps & Limitations:**
  - Live GitHub API sync is subject to unauthenticated rate limits (60 req/hr) unless a `GITHUB_TOKEN` is supplied.
  - Remote sandbox repository live-diff testing was blocked due to lack of human-provided sandbox credentials; verified via deterministic local fixture replay.
* **Concrete Next Action:**
  - Configure GitHub Webhook receiver endpoint to trigger event-driven sync alongside polling.

---

### Requirement 4: Cites exact PRs, comments, links
*Are answers supported by exact source records and URLs, including PRs, issues, comments, documents, and relevant links?*

* **Score:** **5 / 5**
* **Evidence:**
  - [`src/agent/models.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/agent/models.py): `SourceItem` model enforces `id`, `entity_type`, `identifier`, `url`, `title_or_desc`, `snippet`, `valid_from`, `valid_to`.
  - [`src/decision/extractor.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/decision/extractor.py): Exact character-slice offsets (`source_text[quote_start:quote_end] == quote`).
  - [`src/decision/verifier.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/decision/verifier.py): Rejects decision claims if quote does not match exact slice substring.
  - [`src/agent/loop.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/agent/loop.py#L650-L740): Maps tool execution evidence URLs to bracketed markers (`[S1]`, `[S2]`).
  - **Tests:** `tests/test_decision_tracing.py` (7 tests), `tests/test_url_auditor.py` (6 tests).
* **What actually works:**
  - PRs, issues, files, decisions, and documents are cited with public GitHub URLs (`https://github.com/FalkorDB/FalkorDB/...`).
  - Streamlit UI renders sources in an interactive citation ledger with clickable URLs.
* **Gaps & Limitations:**
  - Discussion comments without discrete HTML URLs in API payloads link to parent PR URL rather than a deep comment anchor (`#issuecomment-...`).
* **Concrete Next Action:**
  - Ingest GitHub comment node IDs to generate direct anchor links (`#issuecomment-{id}`).

---

### Requirement 5: Verifier rejects unsupported claims
*Does the verifier check each material claim against retrieved evidence, validate citations, detect unsupported statements, and reject or qualify claims that cannot be verified?*

* **Score:** **5 / 5**
* **Evidence:**
  - [`src/agent/verifier.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/agent/verifier.py): Non-LLM deterministic `AgentEvidenceVerifier`.
    1. Verifies sources: validates URL protocol, checks entity existence in FalkorDB by primary key, checks temporal validity (`is_node_active_at`).
    2. Verifies claims: ensures claim cites verified sources; checks quote exactness for `DECISION` claims and file existence for `OWNERSHIP` claims.
    3. Gatekeeper decision: if zero claims verified or primary claim fails, converts answer to explicit refusal (`status="REFUSED"`).
  - [`src/investigation/verifier.py`](file:///d:/grraph%20Hackathon/grraph%20Hackathon/RepoBrain/src/investigation/verifier.py): `PROnlineEvidenceVerifier` enforces target PR anti-circularity and validates reviewer touches.
  - **Tests:** `tests/test_agent.py::test_unsupported_claim_refused` (synthetic fake engineer refused); `tests/test_verifier_mutations.py` (14 mutation tests passing: fake PRs, unrelated maintainers, future reviews, fake issues, invalid URLs).
* **What actually works:**
  - Fabricated entities, hallucinated PR numbers, and prompt-injection overrides are rejected deterministically before reaching the user.
* **Gaps & Limitations:**
  - Natural language assertions within unquoted claims are validated by entity and relationship support rather than formal logical theorem proving.
* **Concrete Next Action:**
  - Add fine-grained relation-tuple extraction for claims (e.g. `(Person)-[REVIEWED]->(PR)`) to enable granular per-relation verifier checks.

---

## 4. Test Commands and Actual Results

### Focused Compliance Audit Test Run
Executed via:
```powershell
& "D:\grraph Hackathon\grraph Hackathon\RepoBrain\.venv\Scripts\python.exe" -m pytest tests/test_knowledge_logic.py tests/test_deepseek_config.py tests/test_sync.py tests/test_decision_tracing.py tests/test_verifier_mutations.py tests/test_agent.py -v
```

* **Result:** **65 passed in 12.43s** (0 failures, 0 skips, 0 errors).

### Full Repository Test Suite Run
Executed via:
```powershell
& "D:\grraph Hackathon\grraph Hackathon\RepoBrain\.venv\Scripts\python.exe" -m pytest tests/ -v
```

* **Result:** **217 passed in 28.24s** across all 18 test suites (0 failures, 0 skips, 0 errors).

---

## 5. Distinction: Live DeepSeek Execution vs. Deterministic Fallback

| Dimension | Live DeepSeek Execution (`deepseek/deepseek-chat`) | Zero-Key Deterministic Fallback (`deterministic_fallback`) |
| :--- | :--- | :--- |
| **Activation Condition** | Valid OpenRouter API key present in `.env` or Streamlit sidebar. | No API key provided, placeholder key used, or `api_key="no_key"`. |
| **Model Identifier** | `deepseek/deepseek-chat` (or allowlisted DeepSeek slug) | `deterministic_fallback` |
| **Tool Calling Method** | Dynamic OpenAI-compatible function calling loop via OpenRouter API. | Rule-based query planner executing allowlisted tools. |
| **Step Ceiling** | Up to 5 steps (`MAX_STEPS_DEFAULT = 5`). | Bounded 1–3 steps. |
| **Token Usage** | Actual prompt & completion tokens billed by OpenRouter. | 0 tokens (strictly null in reports). |
| **Latency** | ~6.0s – 8.0s (network + generation). | ~5ms – 400ms (database Cypher execution). |
| **Verifier Gate** | Non-LLM `AgentEvidenceVerifier` validates claims & sources. | Non-LLM `AgentEvidenceVerifier` validates claims & sources. |
| **UI Attribution Badge** | `Mode: Live OpenRouter LLM` (green badge in sidebar). | `Mode: Zero-Key Deterministic Fallback (Offline Safe)` (info badge). |

---

## 6. Three Highest-Priority Improvements

| Rank | Improvement | Expected Impact | Implementation Effort |
| :-: | :--- | :--- | :--- |
| **1** | **Historical CODEOWNERS Git Tree Diff Ingestion** | Full point-in-time temporal accuracy for CODEOWNERS rule evaluations across multi-year repository histories. | Medium (Parse git commit tree history for CODEOWNERS file). |
| **2** | **Deep Comment Anchor URLs** | Precision source navigation directly to specific discussion comments (`#issuecomment-{id}`). | Low (Extract comment ID in GitHub fetcher and format URL). |
| **3** | **Streaming Tool Execution in Streamlit UI** | Enhanced interactive user experience showing tool thoughts and interim results as they stream. | Low (Leverage Streamlit `st.chat_message` with streaming callback). |

---

## 7. Final Verdict & Certification

$$\mathbf{Verdict:\ Demo-Ready}$$

**Justification:**  
RepoBrain achieves **23 / 25 (92.0%)** on the compliance scoring rubric. Every core requirement—temporal question context, live DeepSeek tool calling, incremental synchronization, exact URL citations, and deterministic claim verification—is fully implemented and backed by passing automated test suites (217/217 passed). The system operates seamlessly both online with live DeepSeek models and 100% offline via its grounded deterministic fallback.
