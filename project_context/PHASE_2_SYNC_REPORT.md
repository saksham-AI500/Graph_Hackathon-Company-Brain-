# RepoBrain — Phase 2: Incremental GitHub Sync Engine & Live Graph Updates Report

**Date & Time:** October 17, 2026, 12:45 IST  
**Git Branch:** `main`  
**Phase Status:** COMPLETED & VERIFIED  
**Overall Test Suite Status:** **150 passed / 150 total** (0 failures, 0 errors, 0 skips in 14.79s)  
**Database Health:** FalkorDB `repo_kg` ONLINE (270 nodes, 508 edges verified intact)  

---

## 1. Executive Summary

Phase 2 implements the incremental synchronization engine for RepoBrain under `src/sync/`, completing Track 03 requirements for live and replayable graph updates. The engine detects repository changes and applies atomic, non-destructive graph mutations to FalkorDB strictly through the Phase 1 `GraphWriter` mutation interface.

Key accomplishments:
1. **Decoupled Architecture (`src/sync/`):** Clean separation between event definitions (`models.py`), cursor and concurrency management (`state.py`), GitHub API fetching and fixture replay (`fetcher.py`), mutation mapping (`reconciler.py`), sync pipeline execution (`engine.py`), and command-line execution (`cli.py`).
2. **Four Operational Modes:** Fully supported `--once`, `--watch --interval <sec>`, `--dry-run`, and `--replay <fixture.jsonl>`.
3. **Reconciles All 7 Mandated Change Categories:** Pull request lifecycle transitions, PR file additions/deletions/renames with edge superseding, review submission/dismissal keyed by review ID, issue lifecycle and PR resolution links, comment additions with provenance, CODEOWNERS rule updates and owner removals, and document additions and tombstoning.
4. **Reliable Cursors & Concurrency Protection:** Synchronizes state via `(:SyncState)` graph nodes (and local disk cache fallback), tracks `last_sync_at` and per-resource ETags/timestamps, guards runs with a 300s distributed mutex lock, and guarantees that cursors never advance on failed or dry-run executions.
5. **Idempotent Replay & Zero Graph Regressions:** Deterministic fixture replay verified; repeated executions produce 0 duplicate nodes, 0 duplicate edges, and 0 spurious change events.
6. **Integrity Preserved:** Production graph `repo_kg` verified intact with 270 nodes and 508 edges.

---

## 2. Architecture & CLI Usage

### Component Structure

```
src/sync/
├── __init__.py           # Package exports
├── models.py             # EventType enum, GitHubChangeEvent, SyncState, PlannedAction, ReconciliationResult
├── state.py              # SyncStateManager: FalkorDB (:SyncState) persistence, disk cache, distributed lock
├── fetcher.py            # GitHubFetcher: ETags, since cursors, retry backoff, JSON/JSONL offline replay
├── reconciler.py         # EventReconciler: Maps normalized events to Phase 1 GraphWriter primitives
├── engine.py             # SyncEngine: Run coordination, cursor advance policy, error aggregation
└── cli.py                # CLI entrypoint with argparse support
```

### CLI Command Reference

The sync engine is invoked via Python module execution:

```bash
# Perform a single incremental synchronization run against GitHub:
python -m src.sync.cli --once --repo FalkorDB/FalkorDB

# Run in watch mode, polling every 30 seconds:
python -m src.sync.cli --watch --interval 30 --repo FalkorDB/FalkorDB

# Calculate and report planned actions without modifying graph data or advancing cursors:
python -m src.sync.cli --dry-run --replay tests/fixtures/sync_events_replay.jsonl

# Deterministically replay normalized events from a local fixture without live GitHub access:
python -m src.sync.cli --replay tests/fixtures/sync_events_replay.jsonl

# Verbose logging with step-by-step audit details:
python -m src.sync.cli --replay tests/fixtures/sync_events_replay.jsonl --verbose
```

---

## 3. Supported Event Types & Reconciliation Semantics

Every change category is reconciled via `EventReconciler` using Phase 1 `GraphWriter` primitives (`upsert_node`, `upsert_edge`, `close_edge`, `tombstone_node`). No raw Cypher queries bypass `GraphWriter`.

| Category | Normalized Event Type | Target Entities & Rel Types | Reconciliation Semantics |
| :--- | :--- | :--- | :--- |
| **PR Lifecycle** | `pr_opened`, `pr_merged`, `pr_closed`, `pr_reopened` | `PullRequest`, `[:AUTHORED]` | `pr_opened`: upserts PR node and author edge.<br>`pr_closed` / `pr_merged`: updates `state`, `merged_at`, `closed_at`.<br>`pr_reopened`: restores `state='open'`, clears `closed_at`, preserves history without deletion. |
| **PR Files** | `pr_file_added`, `pr_file_removed`, `pr_file_renamed` | `File`, `[:MODIFIES]` | `pr_file_added`: upserts `File` node, creates active `[:MODIFIES]` edge.<br>`pr_file_removed`: closes active `[:MODIFIES]` edge by setting `valid_to=timestamp`.<br>`pr_file_renamed`: closes prior `[:MODIFIES]` edge for `old_path` with `valid_to`, upserts new `File` node, creates active `[:MODIFIES]` edge for new path. |
| **Reviews** | `review_submitted`, `review_dismissed` | `Person`, `PullRequest`, `[:REVIEWED]` | `review_submitted`: upserts `[:REVIEWED {id: review_id, state: state, submitted_at: ts}]`. Multiple reviews on same PR remain distinct because they are keyed by review ID.<br>`review_dismissed`: updates `state='DISMISSED'` on the specific review relationship identified by `review_id`. |
| **Issues** | `issue_opened`, `issue_edited`, `issue_closed`, `issue_reopened`, `issue_resolves_pr` | `Issue`, `Person`, `PullRequest`, `[:REPORTED]`, `[:RESOLVES]` | `issue_opened`: upserts Issue node and reporter edge.<br>`issue_closed`: sets `state='closed'`, `closed_at`.<br>`issue_reopened`: restores `state='open'`, clears `closed_at`.<br>`issue_resolves_pr`: creates explicit `[:RESOLVES]` relationship from PR to Issue with authentic source URL. |
| **Comments** | `comment_created` | `Person`, `PullRequest` / `Issue`, `[:COMMENTED]` | Upserts commenter `Person`, upserts `[:COMMENTED]` edge with `observed_at`, `source_url`, and comment metadata. |
| **CODEOWNERS** | `codeowners_rule_added`, `codeowners_rule_changed`, `codeowners_owner_removed` | `OwnershipRule`, `Person`, `Team`, `File`, `[:DECLARES_OWNER]`, `[:COVERS]` | `codeowners_rule_added`: upserts `OwnershipRule`, links `[:DECLARES_OWNER]` to owners and `[:COVERS]` to matched files.<br>`codeowners_owner_removed`: closes `[:DECLARES_OWNER]` edge between rule and removed owner with `valid_to`. |
| **Documents** | `document_added`, `document_edited`, `document_deleted` | `File` | `document_added`: upserts `File` node with `file_type='documentation'`.<br>`document_edited`: updates `observed_at` and document metadata.<br>`document_deleted`: calls `GraphWriter.tombstone_node(File, path)` setting `status='tombstoned'`, `tombstoned_at`, and `valid_to`. Node is never hard-deleted. |

---

## 4. Cursor Strategy, Retries & Concurrency

### Distributed Concurrency Mutex
- `SyncStateManager.acquire_lock(repo, lock_timeout=300.0)` sets a distributed lock on `(:SyncState {repo})` in FalkorDB (and mirrors to `.cache/sync_state_<repo>.json`).
- If another sync job holds the lock and the TTL has not expired, execution raises `RuntimeError("Sync lock currently held...")` and halts cleanly.
- `release_lock()` ensures the lock is freed in a `finally:` block upon completion or failure.

### Incremental Cursors & Safe Advancement
- `SyncState` tracks `last_sync_at` (ISO timestamp), `etags: Dict[str, str]` (per-resource endpoint ETags), and `resource_cursors: Dict[str, str]` (per-resource pagination tokens or commit SHAs).
- **Safe Advancement Policy:** The cursor is advanced to `max(event.timestamp)` **only if all events succeed** and **the run is not a dry-run**. If any event fails, the cursor remains at the previous successful state, ensuring all unprocessed work remains discoverable for subsequent retry runs.
- **Idempotency on Replay:** If an event has a timestamp `<= last_sync_at`, the engine evaluates the event as a no-op, prevents redundant graph writes, and does not regress the cursor.

### Bounded Retries with Exponential Backoff
- `GitHubFetcher` wraps API calls with retry logic: transient network failures, timeouts, and HTTP 403 rate limits trigger exponential backoff up to 3 attempts with jitter.
- Authentication tokens and credentials are never included in log outputs.

---

## 5. Regression Test Results

The full test suite was executed in the local virtual environment (`.venv\Scripts\python.exe -m pytest -v`), running all 150 tests across 16 test suites.

```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\grraph Hackathon\grraph Hackathon\RepoBrain
configfile: pyproject.toml
collected 150 items

tests/test_db.py::test_db_ping PASSED                                    [  0%]
tests/test_db.py::test_db_custom_query PASSED                            [  1%]
tests/test_edge_cases_and_security.py::test_missing_author_person_handled PASSED [  2%]
...
tests/test_graph_writer.py::test_upsert_node_and_edge_with_provenance PASSED [ 23%]
tests/test_graph_writer.py::test_idempotent_writes_suppress_change_events PASSED [ 24%]
tests/test_graph_writer.py::test_close_edge_sets_valid_to PASSED         [ 24%]
tests/test_graph_writer.py::test_temporal_as_of_filtering PASSED         [ 25%]
tests/test_graph_writer.py::test_tombstone_node_preserves_history PASSED  [ 26%]
tests/test_graph_writer.py::test_audit_records_traceable_to_sync_run PASSED [ 26%]
tests/test_graph_writer.py::test_input_validation_and_schema_enforcement PASSED [ 27%]
tests/test_graph_writer.py::test_missing_evidence_rejection PASSED       [ 28%]
tests/test_graph_writer.py::test_read_only_boundary_enforcement PASSED   [ 28%]
tests/test_graph_writer.py::test_null_timestamps_do_not_leak_into_temporal_ranges PASSED [ 29%]
tests/test_graph_writer.py::test_non_destructive_updates PASSED          [ 30%]
tests/test_graph_writer.py::test_error_handling_leaves_graph_unmodified PASSED [ 30%]
...
tests/test_phase0_defects.py::test_defect1_missing_timestamps_stored_as_real_nulls PASSED [ 60%]
tests/test_phase0_defects.py::test_defect2_distinct_reviews_keyed_by_id_do_not_collapse PASSED [ 62%]
tests/test_phase0_defects.py::test_defect3_bus_factor_calculation_fewest_people_covering_over_50_percent PASSED [ 62%]
...
tests/test_sync.py::test_initial_sync_replay PASSED                      [ 72%]
tests/test_sync.py::test_idempotent_second_run PASSED                    [ 73%]
tests/test_sync.py::test_pr_lifecycle_transitions PASSED                 [ 74%]
tests/test_sync.py::test_pr_file_renaming PASSED                         [ 74%]
tests/test_sync.py::test_distinct_reviews_keyed_by_id PASSED             [ 75%]
tests/test_sync.py::test_issue_lifecycle_and_resolution PASSED           [ 76%]
tests/test_sync.py::test_codeowners_changes PASSED                       [ 76%]
tests/test_sync.py::test_document_addition_and_tombstone PASSED          [ 77%]
tests/test_sync.py::test_dry_run_produces_no_graph_mutations PASSED      [ 78%]
tests/test_sync.py::test_concurrency_lock_protection PASSED              [ 78%]
tests/test_sync.py::test_rate_limit_handling PASSED                      [ 79%]
...
tests/test_verifier_mutations.py::test_mutation_file_url_parity_mismatch PASSED [100%]

============================ 150 passed in 14.79s =============================
```

### Dedicated Sync Test Coverage (`tests/test_sync.py`)
1. `test_initial_sync_replay`: Verifies that a 12-event replay fixture successfully creates and updates PRs, Files, Issues, Reviews, CODEOWNERS rules, and Documents.
2. `test_idempotent_second_run`: Verifies that replaying the identical fixture on an already-synced database executes as 100% no-ops without duplicate nodes or edges.
3. `test_pr_lifecycle_transitions`: Verifies `pr_opened` -> `pr_closed` -> `pr_reopened` lifecycle preserving audit records and clearing `closed_at`.
4. `test_pr_file_renaming`: Verifies that renaming a file closes the `[:MODIFIES]` relationship to the old path with `valid_to` and creates an active edge to the new path.
5. `test_distinct_reviews_keyed_by_id`: Verifies that multiple reviews on the same PR submitted by different reviewers remain distinct by review ID, and `review_dismissed` updates only the targeted review.
6. `test_issue_lifecycle_and_resolution`: Verifies issue open, close, and explicit `[:RESOLVES]` relationship generation linking PR to Issue.
7. `test_codeowners_changes`: Verifies adding a CODEOWNERS rule and removing an owner by closing the `[:DECLARES_OWNER]` relationship with `valid_to`.
8. `test_document_addition_and_tombstone`: Verifies document creation and tombstoning via `tombstone_node` without hard deletion.
9. `test_dry_run_produces_no_graph_mutations`: Verifies that `--dry-run` calculates planned actions without writing to FalkorDB or advancing cursors.
10. `test_concurrency_lock_protection`: Verifies distributed lock acquisition and blocking of concurrent sync runs.
11. `test_rate_limit_handling`: Verifies retry backoff behavior on simulated HTTP 403 rate-limiting headers.

---

## 6. Sandbox Live-Diff Gate Status

**Status:** EXPLICITLY BLOCKED (Offline Replay Engine 100% Operational).

In accordance with Step 7 of the user prompt and project constraints:
- "Identify the exact public or explicitly owned sandbox repository to use for live-diff testing. If none exists or access is unavailable, stop before creating or modifying a remote repository and report the blocker."
- "Before a live test, confirm the target repository and the intended changes. Do not create, edit or delete remote repository content without explicit human authorization."
- "If no authorized sandbox is available, complete offline replay tests and report the live-diff gate as blocked. Do not pretend an offline test is a live GitHub test."

**Audit Finding:**
- `os.getenv("GITHUB_TOKEN")` is not configured in the active environment.
- No public or explicitly owned remote sandbox repository has been authorized by the user for automated mutation testing.
- Consequently, the remote live-diff test was **not executed against a live GitHub repository**, avoiding unauthorized remote modifications.
- Local fixture replay (`tests/fixtures/sync_events_replay.jsonl`) and dry-run execution were executed and passed all verification criteria.

---

## 7. Graph Counts & Database Health

Health check executed against FalkorDB:

```
============================================================
RepoBrain - FalkorDB Health Check
============================================================
Status:      HEALTHY
Host:        localhost:6379
Graph:       repo_kg
Latency:     1.12 ms
Nodes:       270
Edges:       508
============================================================
Health Check PASSED.
```

- Production graph counts remain exactly at **270 nodes and 508 edges**, demonstrating that test fixtures and dry-run executions operate in strict isolation without polluting the primary repository graph.

---

## 8. Files Changed & Git Commit Discipline

### Phase 2 Git Commits

Four focused, granular commits were created on `main` for Phase 2 milestones, strictly preserving the 48 pre-existing staged files in the index:

1. `259d201`: `feat: add sync state, event models and cursor management`
   - Added `src/sync/models.py`
   - Added `src/sync/state.py`
2. `36eebb3`: `feat: implement idempotent GitHub event reconciliation with GraphWriter`
   - Added `src/sync/reconciler.py`
   - Fixed property validator in `src/graph/writer.py` (preventing false positive on `'state'` property)
3. `aa50ce9`: `feat: implement sync engine, fetcher, and command-line execution interface`
   - Added `src/sync/fetcher.py`
   - Added `src/sync/engine.py`
   - Added `src/sync/cli.py`
   - Added `src/sync/__init__.py`
4. `9684281`: `test: cover sync replay, idempotency, lifecycle transitions, and lock recovery`
   - Added `tests/fixtures/sync_events_replay.jsonl`
   - Added `tests/test_sync.py`

### Staged Files Preservation
All 48 pre-existing staged files from prior phases remain untouched in the git index.

---

## 9. Remaining Limitations & Phase 3 Readiness

### Limitations
1. **Live Remote Sandbox Diff Gate:** Requires an authorized user sandbox repository and `GITHUB_TOKEN` credentials to test live GitHub REST API webhooks/polling against remote infrastructure.
2. **Transaction Rollback in FalkorDB Client:** FalkorDB Python client v1.8.0 does not support multi-query transactional `BEGIN/ROLLBACK` blocks across individual Cypher queries. To mitigate this, `EventReconciler` performs validation upfront, isolates entity operations, records failures in `ReconciliationResult.errors`, and halts cursor advancement so unapplied changes are retried cleanly on the next sync run.

### Phase 3 Readiness
The sync engine architecture (`src/sync/`) is complete, robust, and fully integrated with Phase 1 `GraphWriter`. It provides the operational foundation for any subsequent live investigation or drift workflows without requiring any refactoring of core graph storage. Phase 2 is complete.
