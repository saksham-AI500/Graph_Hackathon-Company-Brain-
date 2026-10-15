# RepoBrain — UI Requirements Backlog

This backlog records concrete user interface and user experience requirements discovered during the implementation, backtesting, and evaluation of RepoBrain for Graph Hacks 2026 Track 03 (Company Brain).

These items document functional UI requirements for future visual design passes (e.g. dedicated Google AI Studio/Gemini UI-design workflow), while keeping the current Streamlit application functional and stable.

---

## 1. Requirements Matrix

| ID | Feature Area | Description & Rationale | Priority | Current Status | Acceptance Criteria |
|---|---|---|---|---|---|
| **REQ-UI-01** | **Evidence Source URLs** | Direct, clickable markdown links for all cited entities (PRs, Issues, Profiles, CODEOWNERS rules). | **P0 (Critical)** | **Implemented** | Every evidence claim renders an authentic GitHub URL (`https://github.com/...`) terminating at the source record. |
| **REQ-UI-02** | **Verified vs. Inferred Sections** | Visual hierarchy separating deterministic verified facts from probabilistic inferences and unresolved questions. | **P0 (Critical)** | **Implemented** | Three distinct sections: "1. Verified Facts", "2. Evidence-Supported Inferences", "3. Unresolved Questions". |
| **REQ-UI-03** | **Honest Refusal & Gate States** | Clear visual callouts when a PR is refused due to nonexistent graph records or rejected by deterministic verifier. | **P0 (Critical)** | **Implemented** | Displays warning banner with refusal reason when target PR does not exist (e.g. PR #9999); prevents speculation. |
| **REQ-UI-04** | **Ownership Drift Diagnostics** | Visual breakdown of declared CODEOWNERS vs observed maintainers, HHI reviewer concentration, and bus factor risks. | **P0 (Critical)** | **Implemented** | Expandable card per modified file detailing discrepancy category, bus factor score, and top maintainer distribution. |
| **REQ-UI-05** | **Live Graph Diagnostics** | Sidebar status indicator showing real-time FalkorDB host, port, active graph name, latency, node, and edge counts. | **P1 (High)** | **Implemented** | Automatically queries `GRAPH.RO_QUERY` on load; shows green status badge and live counts (266 nodes, 482 edges). |
| **REQ-UI-06** | **Visible Temporal Cutoff Indicator** | Explicit badge or timeline tag showing the point-in-time cutoff ($T = \text{target\_pr.created\_at}$) and evidence eligibility. | **P1 (High)** | **Partial / Backlog** | Display exact ISO timestamp cutoff in the PR header; explicitly flag that future PRs/reviews post-cutoff are excluded. |
| **REQ-UI-07** | **Interactive Benchmark Comparison Tab** | Dedicated tab or dashboard view displaying the tri-mode evaluation comparison (Graph ON vs Vector Baseline vs Graph OFF). | **P1 (High)** | **Backlog** | Render summary comparison table showing overall accuracy, refusal rate, unsupported claim rate, and latency from `evaluation_raw_results.json`. |
| **REQ-UI-08** | **Inspectable Graph Traversal Paths** | Expandable graph query path viewer showing Cypher query template, input parameters, and matched node hops. | **P2 (Medium)** | **Partial / Backlog** | Expandable accordion under evidence tabs allowing technical judges to view the exact parameterized Cypher query and execution latency. |
| **REQ-UI-09** | **Empty & Failure Graceful Degradation** | Structured handling for database disconnects, rate limits, or empty co-change sets without uncaught Python exceptions. | **P1 (High)** | **Implemented** | Fallback alert boxes for database offline (`localhost:6379`), zero linked issues, and zero historical reviewer touches. |
| **REQ-UI-10** | **Clickable Quick-Preset Selector** | One-click demo presets for signature demonstration PRs (PR #3339, #3342, #3176, #3161, #9999). | **P1 (High)** | **Implemented** | Sidebar preset buttons pre-populate target input and trigger investigation without manual URL copy-pasting. |
| **REQ-UI-11** | **Track Capability Workflow Distinction** | Visual selector or badges explicitly distinguishing the three mapped competition capabilities: (A) Company Brain (Core), (B) Graph-Driven Tool Reasoning, and (C) Memory/State Status. | **P1 (High)** | **Backlog** | Dedicated header badge or toggle identifying which capability workflow is active, showing honest implementation status (`IMPLEMENTED` vs `PARTIAL` vs `OUT OF SCOPE`). |

---

## 2. Requirement Details & Design Guidance

### REQ-UI-06: Visible Temporal Cutoff & Evidence Eligibility
- **Source:** Phase 5 and Phase 6 temporal backtesting audit.
- **Problem:** Users and judges need immediate visual confidence that the investigation engine is not "cheating" by using knowledge from the future.
- **Specification:**
  - When investigating PR #3339, render a timeline banner:
    `⏱️ Temporal Precedent Cutoff: 2026-10-14 09:03:20 UTC (Target PR Creation)`
    `Strict Isolation: Excluded PR #3342 (merged 9h later) and post-cutoff reviews.`
  - Color badge: Blue/Indigo temporal isolation badge.

### REQ-UI-07: Interactive Benchmark Comparison View
- **Source:** Phase 6 evaluation integrity audit.
- **Problem:** Benchmarks are currently executed via pytest and stored in JSON, but live demo judges benefit from seeing the 20-question tri-mode comparison in the UI.
- **Specification:**
  - Add an "Evaluation Benchmark" expander or tab in `app.py`.
  - Load `project_context/evaluation_raw_results.json` directly.
  - Render the comparison table:
    - Mode A (Graph ON): 100.0% Accuracy, 100% Refusal Accuracy, 0% Unsupported claims, 4.0ms latency.
    - Mode B (Vector Baseline): 75.0% Accuracy, 100% Refusal Accuracy, 0% Unsupported claims, 14.5ms latency.
    - Mode C (Graph OFF): 10.0% Accuracy, 0% Refusal Accuracy, 30% Unsupported claims, 1.5ms latency.

### REQ-UI-08: Inspectable Graph Traversal Path Accordion
- **Source:** Hackathon judging transparency requirement (Track 03 — Company Brain).
- **Problem:** Judges need to verify that FalkorDB graph relationships are genuinely queried rather than generated by a stochastic LLM prompt.
- **Specification:**
  - For each historical reviewer or linked issue, provide an expandable `View Cypher Relationship Path` toggle.
  - Display syntax-highlighted Cypher snippet:
    `MATCH (f:File)<-[:MODIFIES]-(pr:PullRequest)<-[r:REVIEWED]-(p:Person)`
    `WHERE f.path IN $files AND pr.merged_at < $cutoff`
  - Show query execution time in milliseconds (e.g. `2.8ms via GRAPH.RO_QUERY`).

---

## 3. Governance & Scope Boundary
- **Do Not Redesign UI Now:** The current Streamlit interface satisfies all P0 functional and verification requirements for Hackathon Phase 6.
- **Deferred Implementation:** Visual skinning, Tailwind/CSS themes, dynamic animations, and dedicated Gemini UI components will be addressed in the separate UI design phase if time permits, preserving the core engine's stability.
