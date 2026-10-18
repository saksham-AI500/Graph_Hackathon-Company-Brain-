# RepoBrain — Phase 11: Adversarial Validation & Submission Readiness Report

**Workspace:** `D:\grraph Hackathon\RepoBrain`  
**Primary Track:** Graph Hacks 2026 — Track 03: Company Brain  
**Date:** October 15, 2026  
**Auditor:** Antigravity Autonomous Pair-Programming Agent (Ponytail Full-Level & Superpowers Verification)  
**Verification Standard:** Strict Evidence-First (Zero unverified assertions; real execution evidence only)

---

## 1. Executive Summary

Phase 11 conducted an adversarial validation and clean-clone audit of RepoBrain to expose latent defects, verify evidence grounding under adversarial attacks, validate temporal cutoffs, stress test clean-clone ingestion on empty database instances, evaluate an independent 9-question holdout dataset, and determine submission readiness.

### Key Audit Findings & Confirmed Defects
1. **Adversarial Verifier Defects (DEF-ADV-01 through 05):**
   - **Reviewer Citations Unverified:** `rev.evidence_pr_urls` verified only that the target PR was excluded, but failed to verify that the cited reviewer actually had a recorded `[:REVIEWED]` edge to the cited PR in FalkorDB. Fixed by querying `(:Person)-[:REVIEWED]->(:PullRequest)` for each cited URL.
   - **Co-Change Citations Unverified:** `sig.co_changed_file` and `sig.evidence_pr_urls` did not verify that the co-changed file exists or that the cited PRs actually co-modified both files. Fixed with Cypher co-modification validation.
   - **Entity Parity & Type Holes:** `File` and `Person` references checked existence but did not verify URL parity against graph records, and unknown entity types bypassed validation. Fixed with strict allowed entity whitelist and URL parity checks.
   - **Hostile Text Scanning Holes:** Verifier scanned only facts, inferences, and target PR title, allowing prompt injection in issue titles, resolution text, drift findings, and unresolved questions to escape. Fixed with a comprehensive multi-field scan.
2. **Clean-Clone Empty Graph Key Crash (DEF-CLEAN-01):**
   - When ingesting into a brand-new FalkorDB instance where `repo_kg` does not exist, `ping()` called `ro_query("RETURN 1 AS ping")`, triggering `ResponseError: Invalid graph operation on empty key`. Fixed by updating `ping()` to use `query()` and guarding `get_counts()` to return `{"nodes": 0, "edges": 0}` on uncreated keys.
3. **Temporal Policy Alignment:**
   - In `vector_baseline.py`, cutoff filtering used `doc.timestamp >= cutoff_timestamp` (exclusive) instead of the project's declared inclusive as-of policy (`event <= cutoff_timestamp`). Fixed by updating comparison to `> cutoff_timestamp`.
4. **Independent 9-Question Holdout:**
   - Evaluated a separate, 9-question holdout dataset covering multi-hop tracing, reviewer routing, historical cutoffs, refusals, false claims, and flat text parity:
     - **Graph ON:** **9/9 (100.0%)** overall, **5/5 (100.0%)** refusals, **59.43ms** total latency (6.6ms/query).
     - **Vector Baseline:** **3/9 (33.3%)** overall, **1/5 (20.0%)** refusals, **225.21ms** total latency (3.8x slower).
     - **Graph OFF:** **0/9 (0.0%)** overall, **0/5 (0.0%)** refusals.
5. **Full Automated Test Suite:**
   - Expanded from 108 tests to **115 passing tests** across all 15 test suites with **0 failures and 0 regressions**.

---

## 2. Actual Starting Git and Database State

### Git Version Control State
- **Current Branch:** `main` tracking `origin/main`
- **HEAD Commit:** `6474fc8 feat: RepoBrain initial submission for Graph Hacks 2026`
- **Remote URL:** `https://github.com/saksham-AI500/Graph_Hackathon-Company-Brain-.git` (Clean, zero remote divergent commits)
- **Local Working Tree:** Modified and untracked files strictly preserved. **Zero commits and zero pushes executed during Phase 11.**

### FalkorDB Live Database State (`repo_kg`)
- **Connection:** `localhost:6379`
- **Ping Status:** `HEALTHY` (round-trip latency: **1.70ms**)
- **Target Graph:** `repo_kg`
- **Total Nodes:** **270**
  - `PullRequest`: 25
  - `Issue`: 16
  - `File`: 210
  - `Person`: 15
  - `OwnershipRule`: 3
  - `Team`: 1
- **Total Relationships:** **508**
  - `MODIFIES`: 283
  - `REVIEWED`: 154
  - `RESOLVES`: 16
  - `AUTHORED`: 25
  - `REPORTED`: 6
  - `COVERS`: 23
  - `DECLARED_FOR`: 1

---

## 3. Executed Commands and Test Results

| Command | Purpose | Result |
| :--- | :--- | :--- |
| `git status --short` | Audit working tree status | Complete list of modified and untracked files verified |
| `python -c "from src.db import FalkorDBClient..."` | Live database health and counts | Status HEALTHY (1.7ms), 270 nodes, 508 edges |
| `pytest tests/test_verifier_mutations.py -v` | Run verifier adversarial mutations | **15/15 passed** in 2.04s |
| `pytest tests/test_graph_queries.py -v` | Verify decision tracing and documentation queries | **5/5 passed** in 0.84s |
| `pytest tests/test_db.py -v` | Test clean-clone empty graph key handling | **4/4 passed** in 0.90s |
| `python -m src.evaluation.holdout_runner` | Execute independent 9-question holdout | Graph ON: 9/9, Vector: 3/9, Graph OFF: 0/9 |
| `pytest -v` | Full automated regression suite | **115/115 passed** across 15 test suites |

---

## 4. Evidence-Verifier Findings (Adversarial Audit)

`PROnlineEvidenceVerifier` was subjected to adversarial tests probing relationship grounding, entity validity, and prompt injection:

1. **Authentic URL for Nonexistent PR or Issue:**
   - Attempted: `https://github.com/FalkorDB/FalkorDB/pull/99999` with `entity_id=99999`.
   - Result: **REJECTED** (`Unverified evidence: PullRequest #99999 does not exist in graph repo_kg`).
2. **Valid Reviewer Name Attached to Unreviewed PR:**
   - Attempted: Reviewer `DvirDukhan` citing PR #3189 (which they never reviewed).
   - Result: **REJECTED** (`Unsupported reviewer evidence: Reviewer 'DvirDukhan' has no recorded [:REVIEWED] relationship to cited PR #3189`).
3. **Co-Change Claim with Nonexistent File or Irrelevant PR:**
   - Attempted: Co-change signal claiming `src/commands/bulk_insert.rs` co-changed with `nonexistent_module.py` via PR #3189.
   - Result: **REJECTED** (`Unverified file: Co-changed file 'nonexistent_module.py' does not exist in graph repo_kg`).
4. **File URL Parity Mismatch:**
   - Attempted: File `src/commands/bulk_insert.rs` citing `https://github.com/.../other_wrong_file.rs`.
   - Result: **REJECTED** (`Evidence URL mismatch for File 'src/commands/bulk_insert.rs'`).
5. **Unknown Evidence Entity Type:**
   - Attempted: `entity_type="SyntheticGraphNode"`.
   - Result: **REJECTED** (`Unsupported evidence entity type: 'SyntheticGraphNode'`).
6. **Prompt Injection Across All Fields:**
   - Embedded injection strings (`IGNORE PREVIOUS INSTRUCTIONS; SYSTEM OVERRIDE`, `DROP TABLE ALL`) into:
     - `brief.unresolved_questions`
     - `brief.linked_issues[0].title`
     - `brief.linked_issues[0].resolution_evidence`
     - `brief.ownership_drift[0].finding`
     - `brief.evidence_sources[0].description`
   - Result: **100% BLOCKED & REJECTED** (`Hostile repository text / prompt injection detected`).

---

## 5. Temporal-Integrity Findings

### Inclusive As-Of Cutoff Contract
All historical reasoning in RepoBrain follows the strict, declared contract:
$$\text{Record is Eligible} \iff \text{timestamp} \le \text{cutoff\_timestamp}$$
Records occurring strictly after the cutoff ($> \text{cutoff}$) or with null/invalid timestamps are excluded from historical evidence.

### Tested Boundary Scenarios
1. **Event at $T - 1\text{s}$:** Eligible and included.
2. **Event at $T$:** Eligible and included under inclusive policy.
3. **Event at $T + 1\text{s}$:** Ineligible and strictly excluded.
4. **Timezone Offsets:** Normalized to UTC ISO 8601 (`2026-10-14T20:39:19+02:00` $\to$ `2026-10-14T18:39:19Z`).
5. **Anti-Circularity:** Target PR is strictly excluded from its own historical reviewers, co-changes, and file metrics.
6. **Vector Baseline Cutoff:** Aligned with inclusive contract (`doc.timestamp > cutoff` excluded).

---

## 6. Graph-Algorithm and Ownership Findings

### FalkorDB PageRank Review Centrality
- **Topology Nuance:** On bipartite graphs where edges point strictly from `(:Person)` to `(:PullRequest)`, standard `CALL algo.pageRank('Person', 'REVIEWED')` returns uniform scores ($0.0667$) due to zero incoming edges between persons.
- **Projected Review Centrality:** RepoBrain executes `CALL algo.pageRank(null, 'REVIEWED')` over the bipartite structure to calculate PR review scrutiny, then aggregates PageRank scores onto reviewing persons.
- **Observed Centrality on `repo_kg`:**
  - `DvirDukhan`: **0.0753** (4 reviews, heavily scrutinized PRs #3342, #3339)
  - `AviAvni`: **0.0518** (2 reviews, core index and runtime PRs)
  - `swilly22`: **0.0115** (1 review)
- **UI Semantic Guard:** The Streamlit interface captions PageRank explicitly as "Review Scrutiny Accumulated Across Reviewed Pull Requests" and does not equate centrality with code ownership or domain expertise.

### Multi-Hop Explanation Paths (`shortestPath`)
- **Verified Path:** PR #3339 $\to$ `[:RESOLVES]` $\to$ Issue #3338.
- **Edge Case Robustness:** Safely handles nonexistent start nodes, nonexistent destinations, self-loops, and disconnected entities by returning `None` without exceptions.

### Graph-Native Ownership Drift
- **Rule Matching:** Parsed from CODEOWNERS into `(:OwnershipRule)` nodes and `(:Team)` nodes connected via `[:COVERS]` and `[:DECLARED_FOR]`.
- **Query Verification:** `query_ownership_drift_graph` queries FalkorDB directly to identify unowned files (`/tests/`, `/src/`) versus owned files (`/build/` $\to$ `@FalkorDB/falkordb-core`).

---

## 7. Decision Tracing & Documentation Accuracy

RepoBrain distinguishes between:
1. **Directly Documented Facts:** Verified PR titles, Issue titles, PR URLs, Issue URLs, and author logins from raw GitHub records.
2. **Graph Relationships:** `[:RESOLVES]` relationships backed by explicit GitHub keyword closing syntax (`Closes #`, `Fixes #`).
3. **Inferences:** High-level architectural intent (e.g. why depth limits were chosen) is an inference unless supported by an Architectural Decision Record (ADR) in repository documentation.

To prevent overstating what the graph proves, `trace_documented_decisions` returns:
```json
{
  "pr_number": 3339,
  "issue_number": 3338,
  "decision_type": "EXPLICIT_ISSUE_RESOLUTION",
  "evidence_basis": "Direct (:PullRequest)-[:RESOLVES]->(:Issue) relationship verified from PR description."
}
```

---

## 8. Independent Holdout Benchmark Results

A dedicated 9-question holdout dataset was evaluated across all three comparative modes.

### Holdout Metric Summary

| Evaluation Metric | Mode A: Graph ON | Mode B: Vector Baseline | Mode C: Graph OFF |
| :--- | :---: | :---: | :---: |
| **Total Holdout Questions** | **9** | **9** | **9** |
| **Overall Accuracy** | **9/9 (100.0%)** | **3/9 (33.3%)** | **0/9 (0.0%)** |
| **Answerable Accuracy** | **4/4 (100.0%)** | **2/4 (50.0%)** | **0/4 (0.0%)** |
| **Refusal Accuracy** | **5/5 (100.0%)** | **1/5 (20.0%)** | **0/5 (0.0%)** |
| **Total Valid Evidence URLs** | **10** | **2** | **0** |
| **Unsupported Claims** | **0 (0.0%)** | **0 (0.0%)** | **0 (0.0%)** |
| **Total Evaluation Latency** | **59.43 ms** | **225.21 ms** | **24.18 ms** |
| **Average Query Latency** | **6.60 ms** | **25.02 ms** (3.8x slower) | **2.69 ms** |

### Per-Question Holdout Breakdown

| ID | Category | Question Summary | Graph ON | Vector | Graph OFF | Graph Advantage |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **HOLD-01** | MULTI_HOP | PR #3141 resolves short read decode issue #3140 | **PASS** | FAIL | FAIL | HIGH (Relational link) |
| **HOLD-02** | MULTI_HOP | PR #3179 resolves Trivy image scan issue #3178 | **PASS** | FAIL | FAIL | HIGH (Relational link) |
| **HOLD-03** | REFUSAL | Prior reviews on RDB decode before Oct 2026 cutoff | **PASS (Refused)** | FAIL | FAIL | HIGH (Temporal cutoff) |
| **HOLD-04** | OWNERSHIP | CODEOWNERS team vs author for `build/runtime/Dockerfile` | **PASS** | **PASS** | FAIL | HIGH (Graph relationships) |
| **HOLD-05** | REFUSAL | Documented history reviewing `src/commands/` before Sept cutoff | **PASS (Refused)** | FAIL | FAIL | HIGH (Temporal cutoff) |
| **HOLD-06** | REFUSAL | Issue resolved by release PR #3161 (No linked issue) | **PASS (Refused)** | **PASS (Refused)**| FAIL | HIGH (Absence of edge) |
| **HOLD-07** | REFUSAL | False claim: PR #3170 cluster replication failover | **PASS (Refused)** | FAIL | FAIL | HIGH (Factual grounding) |
| **HOLD-08** | REFUSAL | Fabricated PR #9995 approval & regression | **PASS (Refused)** | FAIL | FAIL | HIGH (Entity verification) |
| **HOLD-09** | FLAT_TEXT | Title and author of PR #3181 | **PASS** | **PASS** | FAIL | LOW (Flat text sufficient) |

*Raw results saved to:* [`project_context/holdout_raw_results.json`](file:///d:/grraph%20Hackathon/RepoBrain/project_context/holdout_raw_results.json).

---

## 9. UI & Clean-Clone Acceptance Results

### Clean-Clone Setup Verified Offline
- Executed `python -m src.ingestion.run --seed` against a newly initialized empty graph key (`clean_clone_verify_graph`).
- Ingestion loaded **25 PRs**, **16 issues**, **210 files**, and **15 persons** with **zero network calls** and **zero GitHub tokens**.
- Node count (**266**) and relationship count (**482**) were 100% idempotent across two consecutive loader passes.
- Test graph was safely deleted after verification; live `repo_kg` graph was completely untouched.

### Streamlit Application Verification
- **Header Diagnostics:** Live latency (1.7ms), status HEALTHY, graph `repo_kg`.
- **Demo Presets:** PR #3339 (linked issue #3338), PR #3342 (no linked issue), PR #3307 (index update), PR #9999 (refusal).
- **Tab 1 (Executive Brief):** Target PR metadata, verified facts, evidence inferences, unresolved questions.
- **Tab 2 (Ownership Drift):** Declared vs observed maintainers, HHI concentration, risk badges.
- **Tab 3 (Reviewers & Co-Changes):** Historical reviewers with target PR excluded, co-change signals, maintainer PageRank table.
- **Tab 4 (Evidence Paths):** Multi-hop visual graph paths rendered with clickable GitHub source links.
- **Error States:** Nonexistent PRs trigger deterministic red refusal alert; database offline state displays diagnostic recovery instructions.

---

## 10. Changes Made and Regression Tests Added

### Code Changes
1. [`src/investigation/verifier.py`](file:///d:/grraph%20Hackathon/RepoBrain/src/investigation/verifier.py):
   - Grounded reviewer citation URLs in FalkorDB (`[:REVIEWED]` edge verification).
   - Validated co-change signals (file existence and co-modification verification).
   - Enforced URL parity and entity type whitelist on evidence references.
   - Expanded prompt injection scan across all brief fields.
2. [`src/db.py`](file:///d:/grraph%20Hackathon/RepoBrain/src/db.py):
   - Updated `ping()` to use `query()` to prevent `ResponseError: Invalid graph operation on empty key` on clean clones.
   - Guarded `get_counts()` to return `{"nodes": 0, "edges": 0}` on uncreated keys.
3. [`src/evaluation/vector_baseline.py`](file:///d:/grraph%20Hackathon/RepoBrain/src/evaluation/vector_baseline.py):
   - Aligned cutoff filtering to declared inclusive as-of policy (`doc.timestamp > cutoff` excluded).
4. [`src/graph/queries/core.py`](file:///d:/grraph%20Hackathon/RepoBrain/src/graph/queries/core.py):
   - Clarified evidence basis on `trace_documented_decisions`.
5. [`src/evaluation/holdout.py`](file:///d:/grraph%20Hackathon/RepoBrain/src/evaluation/holdout.py) & [`src/evaluation/holdout_runner.py`](file:///d:/grraph%20Hackathon/RepoBrain/src/evaluation/holdout_runner.py):
   - Implemented independent 9-question holdout dataset and evaluation harness.
6. [`README.md`](file:///d:/grraph%20Hackathon/RepoBrain/README.md):
   - Updated test count to 115 passing tests and added holdout benchmark reproduction commands.

### Regression Tests Added (7 New Tests, Total: 115)
- `tests/test_verifier_mutations.py`:
  - `test_mutation_reviewer_with_unreviewed_pr_citation`
  - `test_mutation_cochange_with_unmodified_file_or_irrelevant_pr`
  - `test_mutation_prompt_injection_in_unresolved_questions_or_issue_title`
  - `test_mutation_unknown_evidence_entity_type`
  - `test_mutation_file_url_parity_mismatch`
- `tests/test_db.py`:
  - `test_falkordb_uncreated_graph_empty_key_handled_safely`
- `tests/test_evaluation.py`:
  - `test_holdout_dataset_integrity_and_execution`

---

## 11. Remaining Limitations & Risks

1. **Mutable GitHub API Text:** Current issue titles and bodies reflect the latest GitHub state. True point-in-time issue revision diffs would require scraping the GitHub timeline events API.
2. **Static CODEOWNERS Snapshot:** CODEOWNERS rules are parsed from the repository snapshot. Historical CODEOWNERS diffs at specific commit SHAs are not dynamically evaluated.
3. **Local Architecture:** RepoBrain is designed for local developer and CI investigation; it is not hosted in the cloud.

---

## 12. Final Acceptance Matrix

| Audit Task | Requirement | Status | Verification Evidence |
| :--- | :--- | :---: | :--- |
| **Task 1** | Starting State Reconciliation | **PASS** | Git `main` @ `6474fc8`, 0 commits/pushes; FalkorDB healthy (1.7ms, 270 nodes, 508 edges) |
| **Task 2** | Adversarial Evidence Verifier | **PASS** | 5 defects fixed; 15/15 mutation tests passing; citations grounded in FalkorDB edges |
| **Task 3** | Temporal Integrity Audit | **PASS** | Inclusive as-of policy enforced consistently across graph and vector baselines |
| **Task 4** | Graph Algorithms & Ownership | **PASS** | PageRank review scrutiny verified non-uniform; shortestPath edge cases handled |
| **Task 5** | Decision Tracing Accuracy | **PASS** | Documented facts distinguished from graph relationships and inferences |
| **Task 6** | Independent Holdout Benchmark | **PASS** | 9-question holdout evaluated; Graph ON 100% (9/9) vs Vector 33.3% (3/9) |
| **Task 7** | Clean-Clone & Demo Acceptance | **PASS** | Clean-clone empty key bug resolved; seed ingestion 100% offline & idempotent |
| **Task 8** | Minimal Evidence-Backed Repairs | **PASS** | Surgical fixes applied strictly to confirmed defects; zero unnecessary abstractions |
| **Task 9** | Regression Suite & Report | **PASS** | **115/115 tests passing** across 15 suites; comprehensive audit report compiled |

---

## 13. Exact Commands for Reviewer Reproduction

```bash
# 1. Activate Python virtual environment
.venv\Scripts\Activate.ps1   # Windows PowerShell
# source .venv/bin/activate  # Linux/macOS

# 2. Run complete automated test suite (115 tests)
pytest -v

# 3. Run verifier adversarial mutation tests (15 tests)
pytest tests/test_verifier_mutations.py -v

# 4. Reproduce independent 9-question holdout benchmark
python -m src.evaluation.holdout_runner

# 5. Reproduce 20-question tri-mode benchmark
python -c "from src.evaluation.evaluator import ComparativeEvaluator; ComparativeEvaluator().run_and_save_benchmark()"

# 6. Test 100% offline seed ingestion into an isolated test graph
$env:FALKORDB_GRAPH = "test_eval_graph"
python -m src.ingestion.run --seed
Remove-Item Env:\FALKORDB_GRAPH

# 7. Launch Streamlit UI
streamlit run app.py
```

---

## 14. Explicit Confirmation of Git Safety

**CONFIRMED:**
- Zero `git commit` commands were executed.
- Zero `git push` commands were executed.
- Zero Git history rewrites or resets occurred.
- The live FalkorDB graph `repo_kg` was preserved without data loss or corruption.
- All modifications are confined to the local working tree, ready for final human code freeze review.
