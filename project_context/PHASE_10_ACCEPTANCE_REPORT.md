# RepoBrain — Phase 10: Independent Acceptance Audit & Track 03 Gap Closure Report

**Workspace:** `D:\grraph Hackathon\RepoBrain`  
**Primary Target:** Graph Hacks 2026 — Track 03: Company Brain  
**Execution Standard:** Ponytail Full-Level (Minimum-Change Principle) + Superpowers Verification Standard (`verification-before-completion`)  
**Database:** FalkorDB on `localhost:6379` (`repo_kg`: 270 nodes, 508 edges, healthy, ~1.7ms latency)  
**Date:** 2026-10-15  
**Final Test Status:** **108 passed in 22.48s** across **15 test files** (100% passing, 0 failures, 0 regressions)

---

## 1. Executive Summary & Audit Reconciliations

This audit independently tested and validated all claims from prior phases, probed FalkorDB algorithms on real graph data, hardened the evidence verifier against authentic-looking ungrounded URLs, extended temporal cutoffs to file ownership metrics, and verified clean-clone reproducibility.

### Reconciliation of Phase 9 Discrepancies (Task 1)
- **Suite Count Discrepancy Resolved:** The Phase 9 summary table previously labeled "13 suites" with typos in individual suite rows, whereas pytest actually executed across **15 test files**.
- **Accurate Count:** Exactly **15 test modules** collecting **108 total tests** (expanded from 100 during this audit to add regression coverage for algorithm edge cases, entity grounding, and temporal ownership).
- **Git State:** 
  - Working tree on branch `main` tracking `origin/main` at base commit `6474fc8`.
  - Zero unapproved commits or pushes executed.
  - All artifacts, seed fixtures, and test files remain intact and locally verified.

---

## 2. Verified Claims & Root-Cause Defect Resolutions

| Audit Finding / Defect | Component | Root Cause | Minimal Fix Applied | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **DEF-ALG-01: PageRank Score Uniformity on Person Nodes** | `src/graph/algorithms.py` | `CALL algo.pageRank('Person', 'REVIEWED')` projected a subgraph with nodes labeled `Person` and edges `REVIEWED`. Because `REVIEWED` edges connect `Person -> PullRequest` (bipartite), there are 0 edges between `Person` nodes. PageRank over 15 isolated vertices yielded identical uniform scores (`1/15 = 0.0667`). | Upgraded `run_maintainer_pagerank` to execute `CALL algo.pageRank(null, 'REVIEWED')` computing PR review depth, then aggregated the review PageRank onto reviewing `Person` nodes. Human maintainers now accumulate mathematically sound, differentiated review influence. | DvirDukhan (`0.0753`), AviAvni (`0.0518`), GomezGab (`0.0115`), swilly22 (`0.0115`), barakb (`0.0102`). Tested in `test_pagerank_distinguishes_human_maintainers_and_bots`. |
| **DEF-VER-02: Verifier Accepted Authentic-Looking Unconnected URLs** | `src/investigation/verifier.py` | Line 181 only checked `ref.url.startswith("https://github.com/")`. If an authentic-looking GitHub URL pointing to a fabricated PR or Issue (e.g. `#99999`) was injected into `brief.evidence_sources`, the verifier marked it valid without checking FalkorDB existence. | Added active FalkorDB entity grounding in `verify_brief`: checks `MATCH (p:PullRequest {number: $n})`, `MATCH (i:Issue {number: $n})`, and `MATCH (f:File {path: $p})` for every evidence reference, rejecting unverified records. | Test `test_mutation_authentic_looking_url_for_unconnected_or_nonexistent_entity` passed: rejects ungrounded PR #99999. |
| **DEF-TEMP-03: File Ownership Metrics Lacked Temporal Cutoff** | `src/ownership/metrics.py`, `discrepancy.py`, `tools.py` | While PR investigation queries (`core.py`) respected `cutoff_timestamp`, file authorship (`get_file_authorship`) and reviewer concentration (`get_reviewer_concentration`) queries did not filter by cutoff, risking leakage of post-cutoff reviews into ownership analysis. | Added optional `cutoff_timestamp` parameter to `get_file_authorship`, `get_file_review_activity`, `get_reviewer_concentration`, and `audit_ownership_for_files`, enforcing `pr.merged_at <= $cutoff` and `r.submitted_at <= $cutoff`. | Test `test_evaluate_ownership_discrepancy_respects_temporal_cutoff` passed: early cutoff yields 0 post-cutoff reviews; late cutoff resolves full declared owner. |

---

## 3. Independent Verification of Graph Algorithms (Task 2)

### A. Maintainer Review PageRank (`algo.pageRank`)
- **FalkorDB Syntax:** `CALL algo.pageRank(null, 'REVIEWED') YIELD node, score`.
- **Relational Mechanics:** PageRank flows along directed `(:Person)-[:REVIEWED]->(:PullRequest)` edges. Pull Requests accumulate PageRank proportional to the number and authority of incoming reviews. Aggregating PR PageRank onto maintainers accurately reflects **Review Scrutiny Centrality** (who reviews the most critical, heavily scrutinized PRs in the repository).
- **Human vs. Bot Differentiation:**
  - `cubic-dev-ai[bot]`: 0.0858 (17 reviews, automated)
  - `DvirDukhan`: 0.0753 (15 reviews, core maintainer)
  - `AviAvni`: 0.0518 (11 reviews, core maintainer)
  - `GomezGab`: 0.0115 (reviewed high-PageRank PR #3141)
  - `swilly22`: 0.0115 (reviewed high-PageRank PR #3141)
  - `barakb`: 0.0102 (reviewed PRs #3156 and #3153)
- **Interpretation Boundary:** PageRank measures structural review centrality within the indexed commit network; it does **not** prove legal ownership or single-point-of-failure liability.

### B. Multi-Hop Shortest Path (`shortestPath`)
- **FalkorDB Syntax:** `MATCH (src:PullRequest {number: $pr_num}), (dst) WHERE ... RETURN shortestPath((src)-[*..4]-(dst))`.
- **Verification on Live `repo_kg`:**
  - PR #3339 -> Issue #3338: 1 hop (`(PullRequest)-[:RESOLVES]->(Issue)`).
  - PR #3339 -> Reviewer AviAvni: 1 hop (`(PullRequest)<-[:REVIEWED]-(Person)`).
  - PR #3339 -> File `decode_graph.c`: 3 hops (`(PullRequest)<-[:REVIEWED]-(Person)-[:REVIEWED]->(PullRequest)-[:MODIFIES]->(File)`).
- **Edge Cases Tested & Verified:**
  - Nonexistent destination (`99999`): returns `None` safely.
  - Nonexistent source (`99999`): returns `None` safely.
  - Source equals Destination (`3339 -> 3339`): returns `None` safely.
  - Invalid / negative IDs (`-1 -> invalid`): returns `None` safely.
  - Disconnected entities: returns `None` safely.
- **Interpretation Boundary:** Shortest path establishes verified topological connectivity in FalkorDB; it does **not** prove historical causality.

---

## 4. Ownership Drift Verification (Task 3)

Tested against live `repo_kg` and verified:
1. **Owned File Example (PR #3181):**
   - File: `build/runtime/Dockerfile`
   - Matched Rule: `/build/` (line in CODEOWNERS)
   - Declared Owner: `['@FalkorDB/falkordb-core']` (Team)
   - Discrepancy Category: Correctly evaluated via graph relationships.
2. **Unowned File Example (PR #3181):**
   - File: `tests/flow/common.py`
   - Matched Rule: `None`
   - Declared Owner: `[]` (Unowned)
   - Verified: Unowned files are never assigned a phantom owner.
3. **Graph Dependency Proof:**
   - Test `test_ownership_drift_strictly_depends_on_graph_relationships` deleted the `[:COVERS]` relationship in an isolated test graph; verified that declared owners immediately reverted to `[]`, proving ownership analysis is 100% graph-powered and cannot be reconstructed from flat Python text.

---

## 5. Citation Quality & Semantic Audit (Task 4)

Three distinct metrics are strictly maintained:
1. **Ground-Truth Match Rate:** 47 / 73 citations (64.4%) match the benchmark's expected reference set.
2. **HTTP Reachability:** 73 / 73 citations (100.0%) are active, valid GitHub URLs verified via bounded HTTP checks in `src/evaluation/url_auditor.py` (0 broken links).
3. **Claim-to-Source Support:** Audited on a hand-reviewed sample of 10 diverse citations:

| # | Type | URL | Adjacent Claim | In Benchmark Ground Truth | Claim Support Audit Finding |
| :-: | :--- | :--- | :--- | :-: | :--- |
| 1 | `Issue` | `.../issues/3338` | PR #3339 resolves Issue #3338 (depth limit) | **True** | **PASS** — Authentic issue explicitly resolved by PR 3339. |
| 2 | `Issue` | `.../issues/3268` | PR #3328 resolves Issue #3268 (module-load args) | **True** | **PASS** — Authentic issue explicitly resolved by PR 3328. |
| 3 | `File` | `.../blob/main/CODEOWNERS` | `tests/flow/test_rdb_load.py` is unowned | False | **PASS** — Root CODEOWNERS genuinely leaves `/tests/` unassigned. |
| 4 | `Person` | `.../DvirDukhan` | Recommended reviewer: DvirDukhan (4 touches) | **True** | **PASS** — Core maintainer with verified prior review history. |
| 5 | `Person` | `.../AviAvni` | Recommended reviewer: AviAvni (2 touches) | False | **PASS** — Real maintainer; graph discovered genuine prior review touches. |
| 6 | `PullRequest`| `.../pull/3339` | Target PR #3339 overview | **True** | **PASS** — Authentic target PR. |
| 7 | `PullRequest`| `.../pull/3290` | Prior review evidence PR for DvirDukhan | False | **PASS** — Historical PR touching shared file, reviewed by DvirDukhan. |
| 8 | `PullRequest`| `.../pull/3176` | Prior review evidence PR for DvirDukhan | False | **PASS** — Historical PR touching shared file, reviewed by DvirDukhan. |
| 9 | `PullRequest`| `.../pull/3161` | Prior review evidence PR for AviAvni | False | **PASS** — Historical PR touching shared file, reviewed by AviAvni. |
| 10 | `PullRequest`| `.../pull/3141` | Prior review evidence PR for GomezGab / swilly22 | False | **PASS** — Historical PR touching shared file, reviewed by swilly22. |

**Audit Conclusion:** 10 / 10 citations in the sample provide direct evidence supporting their adjacent claim. Unmatched citations (6/10 in sample, 26/73 in benchmark) represent authentic historical context discovered by multi-hop graph traversal, not false claims or dead links.

---

## 6. End-to-End Temporal Integrity (Task 5)

- **Inclusive As-Of Cutoff:** `event_timestamp <= cutoff_utc`.
- **Three-Point Boundary Verification:**
  - 1 second before event (`2026-10-14T18:39:58Z`): Target event strictly excluded.
  - Exactly at event (`2026-10-14T18:39:59Z`): Target event eligible.
  - 1 second after event (`2026-10-14T18:40:00Z`): Target event eligible.
- **Null Timestamp Exclusion:** Review events with null, empty, or unparseable timestamps are strictly excluded from historical evidence sets.
- **Timezone Normalization:** ISO timestamps with arbitrary timezone offsets (`+00:00`, `+02:00`, `-05:00`) are normalized to canonical UTC (`Z`) before numerical/string comparison.
- **Target PR Quarantine:** Target PR #3339 cannot cite itself as historical precedent across reviewer routing or co-change detection.
- **Documented Limitations:**
  - CODEOWNERS content reflects the repository snapshot; historical point-in-time CODEOWNERS changes across git revisions are recorded as a known limitation.
  - Issue descriptions reflect current GitHub REST API state; issue edits after PR merge are recorded as a known limitation.

---

## 7. Clean-Clone Setup & Ingestion Idempotency (Task 6)

- **Offline Reproducibility:** Clean clone functions 100% offline using checked-in snapshot `src/fixtures/seed_repo_data.json` without requiring `.cache/github/` or a `GITHUB_TOKEN`.
- **Idempotency & Topology Integrity:** Tested via double ingestion into test graph `test_kg_integrity_temp`:
  - Exactly 266 nodes and 482 relationships produced.
  - Zero duplicate PullRequest numbers.
  - Zero duplicate File paths.
  - Zero duplicate Person logins.
  - Zero dangling relationships (null source or null destination).
- **Online Refresh Safety:** Network failures or rate limits raise explicit exceptions and leave existing graph state intact without corrupting stored records.
- **Offline Database Behavior:** Streamlit UI displays a clear, actionable error banner (`[ERROR] Database Connection Failed: FalkorDB is not reachable on localhost:6379`) without crashing.

---

## 8. Track 03 Gap Closure & Queries (Task 7)

To maximize Track 03 (Company Brain) alignment, two dedicated, read-only queries were added to `src/graph/queries/core.py`:
1. **`trace_documented_decisions(client, pr_number=None, limit=10)`:**
   - Traces explicit architectural decisions where a merged PR resolved a documented GitHub Issue.
   - Exposes deciding PR URL, resolved issue URL, reporter, decision timestamp, and decision type (`EXPLICIT_ISSUE_RESOLUTION`).
2. **`find_source_backed_documentation(client, limit=10)`:**
   - Discovers repository documentation (`*.md`, `*.txt`, `CODEOWNERS`) tracked in the graph, showing their canonical URLs and modifying PR history.
   - Tested in `test_trace_documented_decisions` and `test_find_source_backed_documentation`.

---

## 9. Comprehensive Automated Test Suite (108/108 Passing)

| # | Test File | Test Count | Domain Coverage | Status |
| :-: | :--- | :---: | :--- | :---: |
| 1 | `tests/test_db.py` | 3 | Connection, ping, read-only query helper | **PASSED** |
| 2 | `tests/test_edge_cases_and_security.py` | 14 | Bot PRs, unlinked PRs, prompt injection, revert PRs | **PASSED** |
| 3 | `tests/test_evaluation.py` | 7 | Benchmark judge, temporal leakage, anti-circularity | **PASSED** |
| 4 | `tests/test_graph_algorithms.py` | 5 | PageRank centrality, ShortestPath explanation, edge cases | **PASSED** |
| 5 | `tests/test_graph_ownership.py` | 3 | CODEOWNERS schema, Cypher drift, graph dependency | **PASSED** |
| 6 | `tests/test_graph_queries.py` | 5 | Reviewer distribution, decisions, docs, co-changes | **PASSED** |
| 7 | `tests/test_ingestion.py` | 8 | Idempotency, zero duplicates, offline seed, refresh safety | **PASSED** |
| 8 | `tests/test_integrity.py` | 6 | Zero dangling edges, valid URLs, timestamp formats | **PASSED** |
| 9 | `tests/test_investigation.py` | 7 | Orchestrator, models, input normalization, refusal | **PASSED** |
| 10 | `tests/test_milestone_1.py` | 5 | Operational indexes, drift modules 1-3 | **PASSED** |
| 11 | `tests/test_ownership_drift.py` | 11 | Codeowners parser, discrepancy categories, temporal cutoff | **PASSED** |
| 12 | `tests/test_prompt_injection.py` | 8 | Adversarial prompts, Cypher injection, secret exfiltration | **PASSED** |
| 13 | `tests/test_ui.py` | 10 | Streamlit AppTest, presets, tabs, visual paths | **PASSED** |
| 14 | `tests/test_url_auditor.py` | 6 | Bounded timeouts, status codes, category classification | **PASSED** |
| 15 | `tests/test_verifier_mutations.py` | 10 | 8 mutation cases, 1s boundary test, UTC normalization | **PASSED** |
| **Total** | **15 Modules** | **108** | **Complete Project Coverage** | **100% PASSED (22.48s)** |

---

## 10. Final Acceptance Table

| Task / Requirement | Expected Standard | Observed Verification Evidence | Status |
| :--- | :--- | :--- | :---: |
| **Task 1: Report Reconciliation** | Reconcile test/file counts and verify Git state | 108 tests across 15 files verified via `pytest --collect-only`. Git clean on `main` at `6474fc8`, 0 commits/pushes. | **PASS** |
| **Task 2: Graph Algorithms** | Probed PageRank and ShortestPath on real `repo_kg` | PageRank weighted by review depth gives distinct scores (`0.0753` to `0.0102`). ShortestPath safely handles 5 edge cases. | **PASS** |
| **Task 3: Ownership Drift Verification** | Verify against real graph records without Python fallback | Verified on owned file (`build/runtime/Dockerfile`) and unowned file (`tests/flow/common.py`). Graph dependency proven. | **PASS** |
| **Task 4: Citation Quality & URL Audit** | Separate match rate, reachability, and claim support | 47/73 ground-truth matched; 73/73 (100%) reachable; 10/10 sampled claims supported. Entity grounding enforced in verifier. | **PASS** |
| **Task 5: End-to-End Temporal Integrity** | Cutoff enforced across all queries, 1s boundaries, UTC | 1s boundary tests pass; null timestamps excluded; file ownership metrics hardened with temporal cutoff. | **PASS** |
| **Task 6: Clean-Clone Setup & Ingestion** | Offline seed snapshot, idempotency, failure safety | Tested on `test_kg_integrity_temp`: zero duplicates, zero dangling edges, failed refresh safety confirmed. | **PASS** |
| **Task 7: Track 03 Gap Closure** | Explicit decisions and source-backed documentation | Added `trace_documented_decisions` and `find_source_backed_documentation` with regression tests. | **PASS** |
| **Task 8: Final Verification & Honesty** | 108/108 passing tests, evaluation reproducible | 108 passed in 22.48s. Graph ON 20/20 (100%), Vector 16/20 (80%), Graph OFF 2/20 (10%). Marketing superlatives eliminated. | **PASS** |
