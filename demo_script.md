# RepoBrain — 2-to-3 Minute Live Submission Demo Script
**Track 03: Company Brain | Graph Hacks 2026**

---

## Production Overview
- **Total Duration:** 2 minutes 30 seconds (~150 seconds)
- **Target Interface:** Streamlit UI running locally at `http://localhost:8501` (`streamlit run app.py`)
- **Backend Stack:** FalkorDB 1.8.0 / 42201 on `localhost:6379`, graph `repo_kg` (300 nodes, 531 edges, ~1.1ms query latency)
- **AI Model Stack:** DeepSeek via OpenRouter (`deepseek/deepseek-chat` default) with Zero-Key Deterministic Fallback
- **Narration Pace:** ~135 words per minute (crisp, professional, authoritative)
- **Key Artifacts Demonstrated:**
  1. Real evidence-backed question with citations and deterministic verification gate.
  2. Interactive Graph Explorer neighborhood exploration.
  3. Incremental Change Feed with `:SyncRun` audit records.
  4. Tri-architecture comparison (Graph ON, Plain Retrieval, Graph OFF) with honest availability badges.
  5. Benchmark v2 auditable transparency and contamination disclosures.

---

## Timeline & Scene Breakdown

### [00:00 – 00:25] Scene 1: The Problem & System Architecture
* **Visual Action:**
  - Screen opens on the RepoBrain Streamlit Dashboard (`http://localhost:8501`).
  - Point to the sidebar:
    - Connection Status: `Connected: repo_kg (1.1ms) | Nodes: 300 | Edges: 531`.
    - LLM Configuration: Model selected is `deepseek/deepseek-chat` (or `Zero-Key Deterministic Fallback`).
  - Show the 7 dedicated tabs: **Ask the Brain**, **PR Brief**, **Graph Explorer**, **Change Feed**, **Compare**, **Benchmark**, **Health**.
* **Narration:**
  > *"When engineering teams scale, institutional memory fragments across CODEOWNERS, pull requests, decisions, and chat. Git blame tells you who touched a line, but not why, while static CODEOWNERS files silently drift.*
  >
  > *Meet RepoBrain, built for Graph Hacks Track 03: Company Brain. Powered by FalkorDB graph database and DeepSeek reasoning, RepoBrain turns repository history into an auditable, temporal property graph with sub-2-millisecond latency."*

---

### [00:25 – 00:55] Scene 2: Real Evidence-Backed Question & Deterministic Verifier Gate
* **Visual Action:**
  - Navigate to **"Ask the Brain"** tab.
  - Click the demo preset button in the sidebar: *"Who owns src/module.c?"* (or type it into the question box) and click **"Ask Company Brain"**.
  - Show the response rendering in real time:
    - Synthesized markdown explaining ownership status, Codeowners rule match, observed review activity, and drift score (0.67).
    - Prominent green **VERIFIED** badge.
    - Factual assertion cards with bracketed citations like `[S1]`.
    - Supporting Evidence Sources table with verified GitHub URL (`https://github.com/FalkorDB/FalkorDB`).
    - Expand the **"Tool Execution Trace & Verifier Gate"** ledger: shows the exact read tools called (`who_owns`, `who_knows`), step count (2 of 5 ceiling), and non-LLM graph assertion check.
* **Narration:**
  > *"Let's ask: 'Who owns src/module.c?'. The agent calls typed graph read tools, evaluates ownership drift, and cites its sources with bracketed markers.*
  >
  > *Crucially, every single claim must pass our Non-LLM Evidence Verifier before reaching the user. If an entity doesn't exist in FalkorDB or a timestamp violates temporal bounds, the claim is dropped or converted to an honest refusal. Zero hallucinations, 100% verified graph proof."*

---

### [00:55 – 01:25] Scene 3: Interactive Graph Explorer & Neighborhood Inspection
* **Visual Action:**
  - Click on the **"Graph Explorer"** tab.
  - Select Entity Type: `File`, Entity Identifier: `src/module.c`, and Depth: `1-hop`.
  - Click **"Explore Neighborhood"**.
  - Show the dynamic interactive network visualization:
    - Center file node `src/module.c` connected to Pull Requests (`#3342`, `#3141`), Teams, and Engineers (`DvirDukhan`, `GomezGab`, `swilly22`).
    - Hover over an edge to display properties (`MODIFIES`, `REVIEWED`, `valid_from` timestamps).
    - Show the tabular neighborhood relationships breakdown below the canvas.
* **Narration:**
  > *"In the Graph Explorer, developers can visually inspect real repository topology. Selecting 'src/module.c' exposes its immediate graph neighborhood: which PRs modified it, which engineers reviewed it, and which engineering decisions link to it.*
  >
  > *FalkorDB's native Cypher engine computes these multi-hop relationships instantly, allowing teams to explore institutional context intuitively without writing complex database queries."*

---

### [00:25 – 01:50] Scene 4: Live Incremental Synchronization & Change Feed
* **Visual Action:**
  - Click on the **"Change Feed"** tab.
  - Show the **Repository Sync Health** metric cards:
    - Repository: `FalkorDB/FalkorDB`, Status: `IDLE`, Last Sync timestamp, Total Historical Mutations.
  - Scroll down to the **Audit Ledger of Sync Runs**:
    - Display records of recent `:SyncRun` nodes showing `run_id`, timestamp, `events_processed`, and `mutations_applied`.
  - Click the sidebar button **"🔄 Sync Now"**.
  - Watch the status indicator run an incremental check against the GitHub API and report clean synchronization without corrupting graph state.
* **Narration:**
  > *"Static graphs become obsolete quickly. RepoBrain features an incremental sync engine under `src/sync`. It polls the GitHub API using high-watermark cursors and writes transactional mutations into FalkorDB via the Phase 1 GraphWriter.*
  >
  > *Every synchronization event creates an immutable `SyncRun` node in the graph, providing a tamper-proof audit log of repository updates and documentation state."*

---

### [01:50 – 02:15] Scene 5: Comparison Fairness & Tri-Architecture Separation
* **Visual Action:**
  - Click on the **"Compare"** tab.
  - Select question: *"Who knows the most about src/module.c?"*.
  - Show the three side-by-side columns:
    1. **Graph ON (Company Brain Agent):** 100% verified, cites engineer `DvirDukhan` with decaying KNOWS score and PR links.
    2. **Plain Retrieval (TF-IDF Vector Baseline):** Retrieves raw text documents without graph topology; shows partial context with lower precision.
    3. **Graph OFF (Model Alone):** Displays honest `[UNAVAILABLE]` status if no external model key is passed, or general pre-training response without repository tools.
* **Narration:**
  > *"To validate comparative advantage, our 'Compare' tab tests the three architectures side by side under identical conditions.*
  >
  > *Graph ON leverages FalkorDB tools and the verifier gate. Plain Retrieval relies purely on TF-IDF lexical search over permitted repository text without topology. And Graph OFF receives zero graph context or tools. If an architecture cannot run, RepoBrain honestly marks it unavailable rather than fabricating scores."*

---

### [02:15 – 02:30] Scene 6: Audited Benchmark v2 & Transparency Disclosures
* **Visual Action:**
  - Switch to the **"Benchmark"** tab.
  - Toggle between **Development Split (12 questions)** and **Sealed Holdout Split (8 questions)**.
  - Show the audited metrics table:
    - Graph ON: 100% accuracy, 0.0% unsupported claims, ~424ms latency.
    - Plain Retrieval: 66.7% accuracy, 33.3% unsupported claim rate.
    - Point to the **Split Integrity & Contamination Disclosure** banner at the top of the tab.
* **Narration:**
  > *"In our versioned Benchmark v2, Graph ON achieved 100% accuracy and zero unsupported claims across 108 evaluated runs. In the interest of total scientific honesty, we explicitly disclose prior exposure of benchmark questions in early phases, and publish all raw JSON artifacts openly.*
  >
  > *RepoBrain delivers institutional memory you can actually trust. Thank you!"*

---

## Presenter Checklist Before Recording
- [x] Docker container running FalkorDB on `localhost:6379`.
- [x] Streamlit running on `http://localhost:8501` (`streamlit run app.py`).
- [x] Masked API key set in sidebar or `.env` using verified DeepSeek model (`deepseek/deepseek-chat`).
- [x] Full test suite passing (217/217 passed).
- [x] Browser zoomed to 100% at 1080p (1920x1080).
- [x] Keep pace steady (~135 wpm) to finish within the 2:30 target.
