# RepoBrain — Master Project Context & Strategy

**Document Status:** Governing Project Context  
**Last Updated:** October 13, 2026  
**Target Event:** FalkorDB Graph Hacks 2026 (Organized by WeMakeDevs & FalkorDB)  
**Workspace Root:** `D:\grraph Hackathon\RepoBrain`  

---

## 1. Project Mission & Core Definition

* **Project Name:** RepoBrain
* **Core Definition:** An **Evidence-Gated PR Brief for engineering teams** that enables developers and AI agents to investigate software repositories by reasoning over connected relationships among contributors, pull requests, issues, files, historical changes, and architectural decisions.
* **The Core Problem:** AI coding assistants and PR reviewers often operate with isolated file search or unstructured vector chunks. They recommend the wrong reviewer, miss historical rationales in closed issues, overlook files historically co-changed together, and hallucinate plausible-sounding explanations when context is incomplete.
* **The Solution:** RepoBrain structures repository history into an explicit knowledge graph inside FalkorDB (`repo_kg`), exposing typed investigation tools guarded by a **deterministic non-LLM evidence verifier**. Every finding in the PR Brief is backed by an auditable graph path and public GitHub source URLs.

---

## 2. Prize Targets & Track Positioning

| Track / Category | Target Priority | Advertised Official Prize | Strategic Alignment in RepoBrain |
| :--- | :--- | :--- | :--- |
| **Track 03: Company Brain** | **PRIMARY TARGET** | **M6 Mac Mini** | Core repository knowledge engine: institutional memory, ownership drift, reviewer expertise, and decision history grounded in FalkorDB. |
| **Track 01: Connected Data** | **SECONDARY TARGET** | **iPhone 18 Pro** | Multi-hop Cypher queries as typed tools, Proactive PR Intelligence, and Knowledge Risk Reports that actively drive agent actions. |
| **Track 02: Memory & Coordination** | **CONDITIONAL STRETCH** | **PS5 with GTA VI** | *Pursued only if core MVP is stable.* Demonstrated persistent memory, fact correction superseding outdated facts, and memory-diff view. |
| **Best Blog Post** | **SIDE PRIZE TARGET** | **AirPods 5** | Original, technically rigorous write-up detailing FalkorDB architecture, temporal backtesting, measured Graph ON vs. OFF benchmarks, and lessons learned. |
| **Top 50 Submissions** | **RECOGNITION** | **T-Shirt** | Polished, reproducible, completely documented project with verified setup. |

*Rule:* We never compromise the core MVP to chase stretch prizes. We only declare tracks whose capabilities are genuinely built, tested, and demonstrated.

---

## 3. Core Milestones & Release Acceptance Criteria

### Milestone 1 Gate (First Major Deliverable — Kickoff Hours 1–12):
1. A cached public repository dataset stored in `.cache/`.
2. A working FalkorDB graph named `repo_kg` loaded with verified node/edge counts.
3. One correct `ownership_drift` Cypher query manually validated against 3 specific modules in git history.
4. Zero fabricated ownership, relationships, or decision rationales.

### Pre-Release Gates (Before Final Submission):
1. **Evidence Gating:** Every PR Brief finding is traceable to graph records and public evidence URLs.
2. **Non-LLM Verification:** A deterministic validator validates supporting records before LLM output.
3. **Refusal Protocol:** The agent cleanly refuses unsupported claims (`"Evidence path not found"`).
4. **Temporal Backtesting:** Evaluation uses an independent historical train/test split.
5. **Fair Comparison:** Graph ON is evaluated against a credible, fair vector baseline under equal token budgets.
6. **Submission Assets:** All 7 required assets (public repo, README, Cypher catalog, video demo, local/live run guide, track declaration, AI disclosure) are complete.

---

## 4. Required Standout Features (Ranked by Priority)

1. **Real Data & Working Graph Investigations (MVP Foundation):**
   * Real ingestion from a public GitHub repository into local FalkorDB (`repo_kg`). Candidate preference: `FalkorDB/falkordb-py` (official client), fallback `pallets/flask`.
2. **Evidence-Path Visualization (Core Differentiator):**
   * Interactive UI element allowing judges to inspect exact multi-hop graph nodes, edges, and public GitHub source URLs.
3. **Proactive PR Intelligence:**
   * Given an active PR URL, automatically identifies touched modules, flags ownership drift, recommends reviewers based on historical depth, and uncovers related historical decisions.
4. **Knowledge Risk Report:**
   * Graph-derived risk audit: Single-person dependency (bus factor), orphaned modules (zero recent activity), and stale ownership.
5. **Graph ON vs. Graph OFF Rigor:**
   * Fair benchmark comparing FalkorDB multi-hop traversal against a credible vector-search baseline using identical prompts and token budgets.
6. **Malicious-Input Safety Demonstration:**
   * Demonstrates resilience against adversarial PR comments or prompt injection attempts in repository content. Parameterized Cypher and read-only query isolation.
7. **Measured Evaluation Suite:**
   * Temporal backtest and hand-verified benchmark across multi-hop and unanswerable questions measuring accuracy, citation validity, and latency.
8. **Memory Correction & MCP Integrations (Stretch Deliverables):**
   * Storing updated repository conventions that explicitly alter subsequent agent responses.

---

## 5. Scope Control (Ponytail Strict YAGNI)

### In-Scope for Hackathon MVP:
* Single local FalkorDB instance (`falkordb/falkordb:latest`, port `6379`).
* Single graph: `repo_kg`.
* Single public GitHub repository.
* Core entities: `Person`, `PullRequest`, `Issue`, `File`.
* Core relations: `[:AUTHORED]`, `[:REVIEWED]`, `[:REPORTED]`, `[:MODIFIES]`, `[:RESOLVES]`.
* Read-only agent tool access (`GRAPH.RO_QUERY`).
* Minimal Streamlit UI with Evidence Path Visualizer.

### Strictly Deferred Post-MVP:
* Multi-agent orchestration frameworks (LangGraph, CrewAI).
* User-memory graphs or multi-tenant isolation.
* Graph clustering, sharding, or replica routing.
* Multi-repository switching.
* Live GitHub webhooks.
* Elaborate animated graph visualization libraries.
