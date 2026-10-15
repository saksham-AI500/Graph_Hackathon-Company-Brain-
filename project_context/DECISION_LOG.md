# RepoBrain — Architecture Decision Log

**Project:** RepoBrain  
**Governance:** Ponytail Minimal-Complexity Architecture  

---

## Decision 001: Primary Track Selection (Track 03 — Company Brain)
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** The hackathon features three tracks: (01) Agents on Connected Data, (02) Memory & Coordination, and (03) Company Brain.
* **Decision:** Target Track 03 (Company Brain) as our primary prize objective (M6 Mac Mini), with Track 01 as a justified secondary alignment (iPhone 18 Pro).
* **Rationale:** A source code repository represents an engineering organization's living institutional memory. Mapping technical ownership, reviewer experience, past implementation decisions, and dependencies directly to originating artifacts aligns tightly with Company Brain goals.

---

## Decision 002: Single Local FalkorDB Graph (`repo_kg`)
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** FalkorDB supports multiple isolated graphs within the same database engine.
* **Decision:** Restrict the MVP to a single graph named `repo_kg` running in local Docker (`localhost:6379`), abstracted behind a thin `FalkorDBClient`.
* **Rationale:** Minimizes connection management and index complexity during development. Multigraph isolation can be introduced post-MVP simply by changing the graph identifier parameter.

---

## Decision 003: Core Investigation Toolset
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** The answering agent needs specific capabilities to demonstrate graph reasoning.
* **Decision:** Standardize on three typed Python tools: `find_experts`, `trace_decision`, and `impact_of_change`.
* **Rationale:** Covers three distinct graph query patterns (bipartite matching, sequential issue-PR resolution, and co-change neighbor analysis) with structured Pydantic response models.

---

## Decision 004: Strict Read-Only Querying for Answering Agent
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** LLMs with tool-calling capabilities can accidentally or maliciously attempt state mutations.
* **Decision:** Enforce `GRAPH.RO_QUERY` for all investigation tools. Ingestion scripts are the only write-capable processes in the system.
* **Rationale:** Guarantees database integrity and prevents query hallucinations from corrupting the graph.

---

## Decision 005: Non-Negotiable Evidence Paths with Public URLs
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** LLMs frequently produce plausible-sounding answers with no factual backing.
* **Decision:** Every response must include direct GitHub URLs to PRs, issues, or commits proving the relationship. If no graph path exists, the system outputs `"Evidence path not found"`.
* **Rationale:** Serves as the central product differentiator and eliminates hallucination.

---

## Decision 006: Deferral of Complex Multi-Agent Frameworks & Track 02
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** High-overhead agent frameworks can introduce fragile dependency chains.
* **Decision:** Cut multi-agent swarms, cross-session vector memory, live webhook listeners, and streaming chat pipelines from the MVP. Treat Track 02 (Memory & Coordination, PS5 prize) as a conditional stretch goal only.
* **Rationale:** Protects delivery of a working, bulletproof core demonstration within the 4-day window.

---

## Decision 007: Preferred Candidate Ingestion Repository (`FalkorDB/falkordb-py`)
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** Ingestion needs a public open-source repository that resonates strongly with judges while remaining manageable in size.
* **Decision:** Select `FalkorDB/falkordb-py` (FalkorDB's official Python client) as our primary candidate, with `pallets/flask` as a fallback.
* **Rationale:** Ingesting FalkorDB's own open-source client directly demonstrates practical knowledge of their ecosystem. Its PR and issue volume is clean and high-signal, fitting comfortably within API limits.

---

## Decision 008: Proactive PR Intelligence & Knowledge Risk Report
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** Reactive Q&A alone does not showcase the full power of graph connectivity.
* **Decision:** Introduce a Proactive PR Audit (recommending reviewers and flagging sole-contributor risks on incoming PRs) and a Knowledge Risk Report (auditing orphaned modules and bus-factor dependencies).
* **Rationale:** Elevates RepoBrain from a passive search tool into an active, high-value engineering workflow engine.

---

## Decision 009: Graph ON vs. Graph OFF Rigor
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** Judges need concrete proof that a graph database was necessary and not just decorative.
* **Decision:** Implement a fair side-by-side comparison module in the UI contrasting FalkorDB multi-hop traversal against a credible vector-search baseline using identical prompts and token budgets.
* **Rationale:** Explicitly satisfies Hackathon Rules 2 and 3 by proving that removing FalkorDB directly impairs multi-hop relationship discovery and factual accuracy.

---

## Decision 010: Side Prize Strategy for Best Blog Post (AirPods 5)
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** A $20,000 prize pool includes dedicated side prizes, including AirPods 5 for the best blog post.
* **Decision:** Allocate time in Phase 9 to publish an original, highly technical post: *"Building RepoBrain: Why Graph Traversal Beats Vector Search for Repository Intelligence"*.
* **Rationale:** Provides high external visibility, complements the video demo, and creates a compelling narrative around measured Graph ON vs. OFF benchmark results.

---

## Decision 011: Evidence-Gated PR Brief Product Persona
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** General repository Q&A can feel broad or diffuse to evaluators.
* **Decision:** Center the user experience around an **"Evidence-Gated PR Brief"**. Given a PR, generate a comprehensive brief containing changed module context, ownership drift alerts, ranked reviewer recommendations, and historical decision citations.
* **Rationale:** Creates a concrete, immediately demonstrable utility that engineering teams understand within 10 seconds.

---

## Decision 012: Deterministic Non-LLM Evidence Verifier
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** Relying solely on prompt instructions to prevent LLM hallucination is unreliable.
* **Decision:** Implement a deterministic non-LLM validation gate in Python that checks entity IDs, verifies graph traversal paths, and confirms URL formatting before passing context to the UI or LLM.
* **Rationale:** Guarantees zero hallucinations and ensures that unsupported claims are rejected before reaching the user.

---

## Decision 013: Temporal Backtest Evaluation Protocol
* **Date:** 2026-10-13
* **Status:** Accepted
* **Context:** Evaluating reviewer recommendations against the same PR data used to train/populate the graph introduces target leakage.
* **Decision:** Implement a temporal backtest: populate the graph with repository history prior to timestamp $T$, and evaluate reviewer recommendations against PRs merged after timestamp $T$.
* **Rationale:** Provides scientifically defensible evaluation numbers for judges and the blog post.
