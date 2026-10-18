# RepoBrain — Phase 4: Knowledge Logic, Ownership Intelligence & Temporal Reasoning Report

**Date / Timestamp:** 2026-10-17 14:02 IST  
**Git Branch:** `main`  
**Phase 4 Commits:** `b221dd9`, `fc3de68`, `c8da75e`, `9eb1262`, `a1b8873`, `c1fc5ac`  
**Test Suite Status:** 173 passed in 15.14s (100% passing, 0 failed, 0 errors, 0 skips)  
**Active Graph (`repo_kg`):** 293 nodes, 531 edges (Healthy, 0.82ms latency)

---

## 1. Executive Summary

Phase 4 of the RepoBrain project establishes mathematically sound, evidence-grounded knowledge logic, ownership intelligence, and temporal reasoning on top of the Phase 1 GraphWriter, Phase 2 incremental sync engine, and Phase 3 unified knowledge sources.

In strict compliance with `AGENT_BRIEF.md`:
1. **Declared vs. Observed Ownership:** Cleanly separates CODEOWNERS rule precedence from observed contributor activity. Reports all overlapping matching rules in definition order without collapsing multi-owner structures.
2. **KNOWS Knowledge Score:** Implements the exact formula $\sum (\text{weight} \times \exp(-\text{age} / \text{half\_life}))$ with explicit activity weights (Authored = 3, Reviewed = 2, Commented = 1), a 90.0-day half-life, strict bot exclusion, and complete per-contributor evidence traces.
3. **Bus Factor & Ownership Risk:** Preserves the core definition (fewest people whose decayed contributions cover >50% of relevant activity), retains its documented 180.0-day half-life, applies deterministic tie-breaking, and outputs structured explainability reports (`BusFactorReport`).
4. **Grounded Stale-Document Detection:** Audits repository markdown documentation against linked files through grounded graph edges (`REFERENCES`, `DECIDED_IN` + `AFFECTS`). Flags documents where referenced code files were modified strictly after the document edit timestamp before the `as_of` cutoff.
5. **Orphaned Ownership Detection:** Discovers declared CODEOWNERS maintainers with zero observed human activity within a configurable inactivity window (default 90.0 days) prior to `as_of`, without mutating or fabricating ownership rules.
6. **Graph Algorithm Verification:** Validated FalkorDB 42201 Cypher capabilities for PageRank (excluding bots by default) and shortest paths (using supported bounded-hop patterns returning sequential nodes and relationship provenance).
7. **Strict Temporal Queries:** Enforces `as_of` cutoffs and interval filters across all metrics, ensuring historical queries exclude future modifications and closed edges/tombstones remain queryable for their active windows.

---

## 2. Mathematical Formulas and Core Logic

### 2.1 KNOWS Scoring Formula

The KNOWS score evaluates an engineer's current, decaying expertise in a file or module based exclusively on graph-grounded evidence:

$$\text{KNOWS.score}(p, f, t_{\text{as\_of}}) = \sum_{a \in \text{Activity}(p, f, t \le t_{\text{as\_of}})} \text{weight}(a) \times \exp\left(-\frac{\text{age}(a, t_{\text{as\_of}})}{\tau_{\text{KNOWS}}}\right)$$

- **Activity Weights:**
  - `AUTHORED` (merged Pull Request authoring): **3.0**
  - `REVIEWED` (submitted Pull Request review): **2.0**
  - `COMMENTED` (Discussion/PR comment referencing file or code context): **1.0**
- **Half-Life:** $\tau_{\text{KNOWS}} = 90.0 \text{ days}$.
- **Decay Formula:** $\exp(-\Delta t / 90.0)$, where $\Delta t = \max(0.0, (t_{\text{as\_of}} - t_a) / 86400.0)$.
- **Bot Policy:** Accounts ending in `[bot]`, `github-actions`, `dependabot`, etc., are strictly excluded from human scoring.
- **Explainability:** Each score returns an array of `ActivityContribution` items detailing the activity type, source PR/Comment ID, raw weight, age in days, decayed value, and public source URL.

### 2.2 Bus Factor Calculation & Risk Semantics

$$\text{Bus Factor} = \min \left\{ k : \sum_{i=1}^k D_i > 0.5 \times \sum_{j=1}^N D_j \right\}$$

- **Decayed Activity ($D_i$):** Uses half-life $\tau_{\text{BF}} = 180.0 \text{ days}$ with exponential decay $0.5^{\Delta t / 180.0}$.
- **Sorting & Tie-Breaking:** Contributors are sorted deterministically by `(-decayed_score, login_asc)` to ensure zero non-deterministic churn across queries.
- **Risk Level Thresholds:**
  - `HIGH`: Bus factor $\le 1$ (single individual concentration or zero contributors).
  - `MEDIUM`: Bus factor $= 2$.
  - `LOW`: Bus factor $\ge 3$ (well-distributed engineering knowledge).
- **Edge Case Policy:**
  - Zero activity returns `bus_factor = 0`, `is_insufficient_evidence = True`, and `risk_level = HIGH`.
  - Tied contributions are deterministically resolved via lexicographical username ordering.

### 2.3 Stale Document Detection

A document $d$ referencing file $f$ is evaluated relative to $t_{\text{as\_of}}$:
1. $t_d = \text{coalesce}(d.\text{observed\_at}, d.\text{created\_at}, d.\text{valid\_from})$
2. $t_f = \max(\{ \text{pr}.\text{merged\_at} \mid \text{pr} \xrightarrow{\text{MODIFIES}} f, \text{pr}.\text{merged\_at} \le t_{\text{as\_of}} \})$
3. **Status Determination:**
   - If $t_d$ is missing or invalid: `UNRESOLVED_TIMESTAMPS` (avoids false-positive staleness claims).
   - If no modifying PR exists prior to $t_{\text{as\_of}}$: `UP_TO_DATE`.
   - If $t_f > t_d$: `POTENTIALLY_STALE` with diff days $= (t_f - t_d) / 86400.0$ and itemized list of intervening PRs.
   - If $t_f \le t_d$: `UP_TO_DATE`.

### 2.4 Orphaned Ownership Detection

An ownership rule in CODEOWNERS declaring owner $p$ (person or team) is flagged as orphaned if:
$$\forall a \in \text{ObservedActivity}(p, t \le t_{\text{as\_of}}), \quad (t_{\text{as\_of}} - t_a) > T_{\text{inactivity}}$$
- **Default Inactivity Threshold:** $T_{\text{inactivity}} = 90.0 \text{ days}$ (configurable via parameter).
- **Rule Preservation:** The CODEOWNERS pattern and edge remain 100% intact in the graph; no declared rules are mutated or deleted.
- **Resolution:** If $p$ has never contributed any activity across the graph, status is classified as `NO_RECORDED_ACTIVITY`.

---

## 3. FalkorDB Algorithm & Syntax Verification

FalkorDB version 42201 was queried and verified for graph algorithm capabilities:
1. **PageRank:**
   - Excludes automated bots by default from the projection.
   - Calculates relative centrality across `Person`, `PullRequest`, `File`, and `Document` nodes.
2. **Shortest Paths:**
   - FalkorDB 42201 does not support the Neo4j-style undirected syntax `shortestPath((a)-[*]-(b))`.
   - Instead, FalkorDB requires bounded Cypher path matching:
     ```cypher
     MATCH path = (src)-[*1..4]-(dst)
     WHERE src.login = $src AND dst.path = $dst
     RETURN path
     ORDER BY length(path) ASC
     LIMIT 1
     ```
   - RepoBrain wraps this in `src/graph/algorithms.py` and returns structured, auditable node sequences with relationship types and edge provenance URLs.

---

## 4. Summary of Files Changed & Created

| File | Status | Description |
|------|--------|-------------|
| `src/knowledge/temporal.py` | New | Unified temporal reasoning, UTC ISO normalization, and validity filter generator. |
| `src/knowledge/scoring.py` | New | KNOWS score implementation with 90d exponential decay, bot exclusion, and contribution itemization. |
| `src/knowledge/stale_docs.py` | New | Grounded documentation staleness engine with PR diff auditing and multi-hop link traversal. |
| `src/ownership/orphaned.py` | New | Orphaned ownership detector with configurable inactivity threshold and CODEOWNERS preservation. |
| `src/ownership/codeowners.py` | Modified | Added `match_all` method to capture overlapping rules in definition order. |
| `src/ownership/discrepancy.py` | Modified | Added `overlapping_rules` field to `OwnershipDiscrepancyReport`. |
| `src/ownership/metrics.py` | Modified | Added `BusFactorReport`, `calculate_bus_factor_detailed`, and deterministic tie-breaking. |
| `src/graph/writer.py` | Modified | Updated provenance construction in `upsert_node` and `upsert_edge` to preserve explicit caller timestamps. |
| `tests/test_knowledge_logic.py` | New | 8 comprehensive end-to-end integration tests covering all Phase 4 requirements. |
| `project_context/PROGRESS.md` | Modified | Updated with Phase 4 completion entry and verification metrics. |

---

## 5. Test Suite Verification & Execution Results

All 173 tests across the entire RepoBrain test suite passed cleanly with 0 failures:

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\grraph Hackathon\grraph Hackathon\RepoBrain
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 173 items

tests/test_db.py .                                                       [  0%]
tests/test_decision_tracing.py ........                                  [  5%]
tests/test_edge_cases_and_security.py .                                  [  5%]
tests/test_evaluation.py .                                               [  6%]
tests/test_graph_algorithms.py .                                         [  6%]
tests/test_graph_ownership.py .                                          [  7%]
tests/test_graph_queries.py .                                            [  8%]
tests/test_graph_writer.py ........................................       [ 31%]
tests/test_ingestion.py .                                                [ 31%]
tests/test_investigation.py ....................                         [ 43%]
tests/test_knowledge_logic.py ........                                   [ 47%]
tests/test_knowledge_sources.py .......                                  [ 52%]
tests/test_milestone_1.py .....                                          [ 54%]
tests/test_ownership_drift.py ...........                                [ 61%]
tests/test_phase0_defects.py .........                                   [ 66%]
tests/test_prompt_injection.py ........                                  [ 71%]
tests/test_sync.py ...........                                           [ 77%]
tests/test_ui.py ..........                                              [ 83%]
tests/test_url_auditor.py ......                                         [ 86%]
tests/test_verifier_mutations.py .......................                 [100%]

============================ 173 passed in 15.14s =============================
```

### New Phase 4 Tests Breakdown (`tests/test_knowledge_logic.py`):
1. `test_declared_vs_observed_ownership_and_overlapping_rules`: Verifies CODEOWNERS precedence, multi-owner matching, and overlapping rule exposure.
2. `test_knows_scoring_weights_and_exponential_decay`: Tests weights (3, 2, 1), 90-day decay ($e^{-\Delta t / 90}$), and verified mathematically against manual calculation.
3. `test_bot_exclusion_in_knows_scores`: Asserts bot activity produces 0.0 KNOWS score while human contributions remain intact.
4. `test_bus_factor_calculations_and_edge_cases`: Tests single-owner concentration, balanced distributions, zero-activity edge case, and deterministic tie-breaking.
5. `test_stale_document_detection_with_grounded_links`: Verifies document staleness against modifying PRs before and after the `as_of` cutoff.
6. `test_orphaned_owner_detection_threshold`: Verifies inactive CODEOWNERS detection with configurable threshold (60d vs 180d) and non-destructive rule preservation.
7. `test_temporal_as_of_boundary_conditions`: Tests boundary behavior at $T-1$, $T$, and $T+1$ seconds with future-event exclusion.
8. `test_pagerank_and_shortest_path_algorithms`: Validates FalkorDB Cypher syntax for shortest paths and bot-excluded PageRank.

---

## 6. Git Commit Log

```
c1fc5ac test: cover temporal knowledge logic, stale docs, and ownership metrics
a1b8873 feat: report inactive declared owners with configurable inactivity threshold
9eb1262 feat: detect stale documents from temporal file changes
c8da75e feat: align bus-factor explainability and overlapping CODEOWNERS precedence
fc3de68 feat: calculate evidence-weighted knowledge scores with exponential decay
b221dd9 feat: implement unified temporal reasoning and validity utilities
```

---

## 7. Limitations & Phase 5 Readiness

### Current Limitations:
1. **GitHub API Auth Token:** Live remote diffing against GitHub remains gated pending human token authorization; local offline fixtures provide 100% deterministic testing.
2. **Document Modification Timestamps:** Git commit histories for documentation files are ingested via file observation timestamps; where commit timestamps are omitted, documents gracefully default to `UNRESOLVED_TIMESTAMPS` rather than asserting incorrect staleness.

### Phase 5 Readiness:
- All required knowledge tools (`knows_score`, `stale_docs`, `orphaned_owners`, `bus_factor`, `temporal_query`) are ready for exposure as typed, read-only tools to the Phase 5 investigation agent.
- Zero mock dependencies; all functions operate directly against FalkorDB.
- Phase 4 is fully complete and verified. Ready for Phase 5.
