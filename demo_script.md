# RepoBrain — 90-Second Video Demo Script
**Track 03 — Company Brain | Graph Hacks 2026**

---

## Production Overview
- **Total Duration:** 90 Seconds (01:30)
- **Target Interface:** Streamlit UI running locally at `http://localhost:8501` (`streamlit run app.py`)
- **Key Real PR Used:** PR #3339 (`FalkorDB/FalkorDB` merged pull request)
- **Refusal Target Used:** Non-existent PR #9999
- **Narration Pace:** ~130-140 words per minute (crisp, professional, authoritative)
- **Total Script Word Count:** ~200 words

---

## Timeline & Scene Breakdown

### [00:00 – 00:10] The Problem: Context is Scattered
* **Visual Action:**
  - Screen opens on the RepoBrain Streamlit Dashboard (`http://localhost:8501`).
  - The hero header *"RepoBrain: Institutional Memory for Pull Requests"* is visible, along with the sidebar showing FalkorDB connection status (*"Connected: localhost:6379 (Graph: repo_kg)"*).
  - Cursor hovers over the PR input box.
* **Narration:**
  > *"When reviewing pull requests, critical context is scattered: Git blame tells you who touched a line, but not why. CODEOWNERS files drift, and historical rationale gets lost in forgotten issues."*
* **Verification Note:**
  - Header and sidebar connection badge verified against `src/ui/dashboard.py`.

---

### [00:10 – 00:35] Live Investigation: PR #3339
* **Visual Action:**
  - User enters `3339` into the PR input field and clicks **"Generate Brief"**.
  - Loading spinner executes briefly (<100ms backend latency).
  - The **Evidence-Gated PR Brief** renders with sections:
    - Target PR metadata: Title, Author, Merge date, and GitHub link (`https://github.com/FalkorDB/FalkorDB/pull/3339`).
    - Modified Files table listing changed paths (e.g., `tests/pytest/test_graph.py`).
* **Narration:**
  > *"Meet RepoBrain, powered by FalkorDB. Entering PR 3339 instantly retrieves its full topological history. In just four milliseconds, FalkorDB traverses files, historical co-changes, and past reviewers."*
* **Verification Note:**
  - PR #3339 is indexed in `repo_kg` with verified files and merged status.

---

### [00:35 – 00:52] Ownership Drift & Historical Reality
* **Visual Action:**
  - Scroll down to the **"Ownership & Reviewer Analysis"** panel.
  - Highlight the discrepancy card:
    - Shows modified paths that have *No Declared Codeowner* in the root `CODEOWNERS` file.
    - Displays the **Observed Historical Maintainers** chart/list identified by FalkorDB (e.g., maintainers with frequent past reviews on these exact paths).
* **Narration:**
  > *"Notice the ownership discrepancy: static CODEOWNERS rules leave this subsystem unassigned. But FalkorDB's graph reveals the actual domain experts who actively review these files, highlighting organizational drift."*
* **Verification Note:**
  - Path unassigned in CODEOWNERS and active maintainers match the output of `OwnershipDriftAnalyzer` on PR #3339.

---

### [00:52 – 01:08] Linked Decision Tracing & Grounded Citations
* **Visual Action:**
  - Scroll to the **"Historical Context & Evidence Citations"** section.
  - Click on the linked issue citation (`https://github.com/FalkorDB/FalkorDB/issues/...`).
  - Expand the **"Evidence Verification Ledger"**: shows green badges for 100% verified URLs adhering to the domain whitelist, strictly filtered before the target PR's creation date.
* **Narration:**
  > *"Every insight is evidence-gated. RepoBrain traces linked issues and prior co-changing PRs, enforcing strict temporal filtering so no future knowledge leaks. Every cited URL is deterministically verified."*
* **Verification Note:**
  - Temporal filtering and URL domain verification verified by `PROnlineEvidenceVerifier` and `NonLLMEvidenceVerifier`.

---

### [01:08 – 01:18] Refusal Demonstration: Non-Existent PR #9999
* **Visual Action:**
  - In the search bar, type `9999` and click **"Generate Brief"**.
  - A prominent amber/red refusal banner appears:
    - *"Investigation Refused: Target PR #9999 not found in repository knowledge graph. RepoBrain refuses to hallucinate claims without graph evidence."*
* **Narration:**
  > *"When a query lacks graph evidence—like non-existent PR 9999—RepoBrain refuses to guess. Zero hallucinations, zero fabricated claims."*
* **Verification Note:**
  - Refusal logic verified in test `test_refusal_on_missing_pr` in `tests/test_pr_brief_engine.py`.

---

### [01:18 – 01:30] FalkorDB Advantage & Audited Benchmark
* **Visual Action:**
  - Switch tab to the **"Evaluation & Benchmarks"** view or display the benchmark summary card:
    - Graph ON: 20/20 (100%) vs Vector TF-IDF: 15/20 (75%) vs Graph OFF: 2/20 (10%).
    - Latency: 4.01ms vs 14.46ms.
    - Notice on screen: *"20-question audited temporal backtesting benchmark on FalkorDB/FalkorDB"*.
* **Narration:**
  > *"In our audited 20-question backtesting benchmark, FalkorDB delivered 100% accuracy and 4-millisecond queries—outperforming vector search while guaranteeing auditable proof. RepoBrain: institutional memory you can trust."*
* **Verification Note:**
  - Metrics match Phase 6 audited evaluation results in `project_context/evaluation_raw_results.json`.

---

## Recording Checklist for Presenter
- [ ] Ensure Docker container `falkordb` is running on port `6379`.
- [ ] Launch application in terminal: `streamlit run app.py`.
- [ ] Set browser window to 1080p (1920x1080) with 100% zoom for optimal legibility.
- [ ] Test PR `3339` and PR `9999` once prior to final recording to cache browser rendering.
- [ ] Deliver narration at a steady, confident cadence matching the 90-second markers.
