# Ground-Truth Leakage Audit: RepoBrain Answering Engine

**Date:** 2026-10-18  
**Auditor:** saksham-AI500 (RepoBrain Core Team)  
**Scope:** Scope-Locked Track 03 Win Plan — Backend Answer Path Validation

---

## 1. Executive Summary

This audit rigorously inspects all code paths and inputs consumed during inference by RepoBrain's two product modes:
1. `graph_on` (DeepSeek model with 14 typed read-only graph tools and deterministic claim-level verifier)
2. `graph_off` (The same DeepSeek model and system prompt, zero tools, zero repository data)

**Audit Finding:**  
Neither `graph_on` nor `graph_off` accesses `data/synthetic/ground_truth.json`, expected answer files, question benchmark IDs (e.g. `BENCH-01`, `Q1`), or test evaluation check scripts during the answer path. All repository information used by `graph_on` is sourced strictly from read-only graph queries (`ro_query`) or immutable fixtures (`fixtures/` and `chats/`).

---

## 2. Ingestion & Graph Sources vs. Evaluation Datasets

| Dataset / File | Location | Consumed at Answer Time? | Consumed at Evaluation Time? | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `fixtures/*.json` | `data/synthetic/fixtures/` | YES (Graph Ingestion / Read Tools) | No | Raw repository content (PRs, issues, commits, people) |
| `chats/*.json` | `data/synthetic/chats/` | YES (Graph Ingestion / Read Tools) | No | Team chat export (Slack threads, decisions, reversals) |
| `CODEOWNERS` | `data/synthetic/fixtures/` | YES (Rule parsing via `CodeownersParser`) | No | Declarative ownership rules |
| `ground_truth.json` | `data/synthetic/ground_truth.json` | **NO (STRICTLY FORBIDDEN)** | YES (Out-of-band evaluation harness) | Reference ground-truth benchmark assertions |
| `check_ground_truth.py` | `scripts/` | **NO** | YES (Validation script) | Integrity check script |
| Question IDs (`Q1`, `BENCH-01`) | Evaluation benchmarks | **NO** | YES (Harness logging only) | Benchmark tracking identifiers |

---

## 3. Mode Input & Code Path Mapping

### Mode 1: `graph_on`

- **Endpoint:** `POST /api/ask` (`src/api/server.py:ask_question`)
- **Input Parameters:**
  - `question: str` (The plain natural language user prompt)
  - `as_of: Optional[str]` (Optional temporal boundary timestamp)
  - `mode: "graph_on"`
- **Code Execution Path:**
  1. `src/api/server.py::ask_question`
  2. `src/agent/loop.py::AgentExecutionLoop.run(AgentRequest)`
  3. `src/agent/prompt.py::build_agent_system_prompt()` (System instructions and formatting guide)
  4. `src/agent/tools.py::ToolRegistry.execute(tool_name, arguments)` (Dispatches to typed functions: `who_owns`, `who_knows`, `trace_decision`, `pr_brief`, `find_stale_docs`, `suggest_reviewers`)
  5. `src/db.py::FalkorDBClient.ro_query()` (Read-only parameterised Cypher against FalkorDB `repo_kg` graph)
  6. `src/agent/verifier.py::AgentEvidenceVerifier.verify_answer(answer, as_of)` (Checks that all cited source URLs exist, timestamps are valid as of cutoff, and decision quotes match verbatim)
- **Data Isolation:**
  - All external PR text, issue bodies, and comments are filtered through `src/investigation/orchestrator.py::wrap_untrusted_data()`, which wraps repository text inside `<untrusted_data>` blocks. Tools reject untrusted prompts and never execute dynamic Cypher.

### Mode 2: `graph_off`

- **Endpoint:** `POST /api/ask` (`src/api/server.py:ask_question`)
- **Input Parameters:**
  - `question: str`
  - `as_of: Optional[str]`
  - `mode: "graph_off"`
- **Code Execution Path:**
  1. `src/api/server.py::ask_question`
  2. `src/agent/loop.py::AgentExecutionLoop.run(AgentRequest)`
  3. `src/agent/prompt.py::build_agent_system_prompt()` (Identical system prompt)
  4. DeepSeek completion called with `tools=None` and zero repository context.
  5. Immediate refusal generated: *"I can't answer that from the data. Knowledge graph tools and repository access are disabled in graph_off mode."*
  6. `src/agent/verifier.py::AgentEvidenceVerifier.verify_answer(answer)` passes clean refusal with 0 claims and 0 sources.

---

## 4. Leakage Verification Checks

1. **Grepping for `ground_truth` in `src/agent/`:**
   - Command: `rg "ground_truth" src/agent/`
   - Result: 0 matches.
2. **Grepping for Question IDs in `src/agent/`:**
   - Command: `rg "BENCH-" src/agent/`
   - Result: 0 matches.
3. **Tool Registry Inspection:**
   - All 14 tools in `src/agent/tools.py` take typed arguments (`file_path`, `pr_number`, `as_of`, `query_or_pr`) and query graph nodes/edges directly without reference to external benchmark files.

---

## 5. Conclusion

Zero ground-truth leakage exists in RepoBrain's answer engine. `graph_on` operates entirely through typed, parameterised graph queries and fixture graph sources. `graph_off` receives zero tools and zero repository context.
