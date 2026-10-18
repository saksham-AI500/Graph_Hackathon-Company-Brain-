# RepoBrain — Phase 1: GraphWriter, Provenance & Temporal Validity Report

**Phase:** Phase 1 (GraphWriter, Provenance & Temporal Validity)  
**Track:** Graph Hacks 2026, Track 03: Company Brain  
**Date:** October 17, 2026 (12:30 IST)  
**Standard:** Superpowers `verification-before-completion` (Strict evidence-first methodology)  
**Current HEAD:** `5118d63` on branch `main` (Preserved pre-existing staged index intact)  

---

## 1. Executive Summary & Architecture Overview

Phase 1 establishes a secure, validated, and temporally consistent mutation gateway for RepoBrain's FalkorDB knowledge graph (`repo_kg`). Prior to this phase, graph mutations were performed via direct Cypher MERGE queries distributed across ingestion loaders and setup scripts without uniform provenance or temporal validity tracking.

`src/graph/writer.py` now provides a centralized `GraphWriter` exposing only four approved mutation primitives:
1. `upsert_node`: Idempotently creates or updates an allowlisted entity node with strict schema and property validation.
2. `upsert_edge`: Idempotently creates or updates an allowlisted relationship between existing entities with mandatory evidence grounding (`ProvenanceMetadata`).
3. `close_edge`: Temporally terminates a relationship by setting `valid_to` while preserving the historical edge for time-travel queries.
4. `tombstone_node`: Temporally marks an entity as removed (`status = 'tombstoned'`, `tombstoned_at = $ts`, `valid_to = $ts`) without hard-deleting graph nodes or edges.

All graph operations disallow caller-supplied raw Cypher and prevent query injection. Provenance (`source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`) is tracked on every derived edge and entity, and state-altering mutations produce auditable change records (`(:SyncRun)-[:CHANGED {op, target_id, before, after}]->(target)`).

---

## 2. Public API & Design Contract

### 2.1 Core Classes & Methods

```python
from src.graph.writer import (
    GraphWriter,
    ProvenanceMetadata,
    MutationResult,
    ValidationError,
    EntityNotFoundError,
)
```

#### Method Specifications
1. **`upsert_node(label: str, identity_value: Any, properties: Optional[Dict[str, Any]] = None, provenance: Optional[ProvenanceMetadata] = None) -> MutationResult`**
   - Validates `label` against `ALLOWED_NODE_LABELS`.
   - Validates properties against `ALLOWED_NODE_PROPERTIES[label]`.
   - Primary identity key cannot be overwritten.
   - Evaluates substantive property differences (ignoring execution metadata `observed_at` and `run_id`).
   - If state changed: executes parameterized Cypher update and logs a `CHANGED` audit edge from `SyncRun`.
   - If identical: returns `changed = False` without generating spurious change records.

2. **`upsert_edge(rel_type: str, source_label: str, source_identity: Any, target_label: str, target_identity: Any, properties: Optional[Dict[str, Any]] = None, provenance: Optional[ProvenanceMetadata] = None, edge_key_property: Optional[str] = None, edge_key_value: Optional[Any] = None) -> MutationResult`**
   - Requires both source and target entities to exist in FalkorDB (rejects fabricated or ungrounded endpoints with `EntityNotFoundError`).
   - Requires valid `ProvenanceMetadata` with non-empty HTTP/HTTPS `source_url`.
   - Validates `rel_type` against `ALLOWED_REL_TYPES`.
   - Merges or updates edge properties idempotently without creating duplicate relationships.

3. **`close_edge(rel_type: str, source_label: str, source_identity: Any, target_label: str, target_identity: Any, closed_at: Optional[str] = None, edge_key_property: Optional[str] = None, edge_key_value: Optional[Any] = None) -> MutationResult`**
   - Sets `valid_to = $closed_at` on the target relationship.
   - Preserves edge and historical properties in the graph.
   - Repeated calls on an already-closed relationship are deterministic no-ops (`changed = False`).

4. **`tombstone_node(label: str, identity_value: Any, tombstoned_at: Optional[str] = None) -> MutationResult`**
   - Sets `status = 'tombstoned'`, `tombstoned_at = $ts`, and `valid_to = $ts`.
   - Preserves the node and all existing connected relationships in FalkorDB for time-travel `as_of` queries.
   - Repeated calls on an already-tombstoned node return `changed = False`.

5. **`get_change_history(target_id: Optional[str] = None, run_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]`**
   - Read-only query returning audit events recorded under `SyncRun`.

### 2.2 Allowlisted Schemas
- **Allowed Node Labels:** `Person`, `PullRequest`, `Issue`, `File`, `Team`, `OwnershipRule`, `SyncRun`.
- **Allowed Relationship Types:** `AUTHORED`, `REVIEWED`, `MODIFIES`, `RESOLVES`, `REPORTED`, `DECLARES_OWNER`, `COVERS`, `OWNED_BY`, `CHANGED`.
- **Identity Keys:**
  - `Person`: `login` (str)
  - `PullRequest`: `number` (int)
  - `Issue`: `number` (int)
  - `File`: `path` (str)
  - `Team`: `name` (str)
  - `OwnershipRule`: `pattern` (str)
  - `SyncRun`: `run_id` (str)

---

## 3. Provenance & Temporal Behavior

### 3.1 Provenance Requirements
Every derived entity or edge carries:
- `source_url`: Public HTTP/HTTPS evidence URL (e.g., `https://github.com/FalkorDB/falkordb-py/pull/123`).
- `observed_at`: Normalized ISO 8601 UTC timestamp of observation.
- `run_id`: Unique identifier for the synchronization or ingestion run.
- `valid_from`: Normalized ISO 8601 UTC timestamp indicating when the relationship or entity became effective.
- `valid_to`: Normalized ISO 8601 UTC timestamp or `null` (where `null` represents currently valid).

### 3.2 Temporal Query Semantics
- **Current Active State:** `valid_to IS NULL`.
- **Historical Validity at Cutoff $T$:**
  ```cypher
  WHERE r.valid_from <= $cutoff AND (r.valid_to IS NULL OR r.valid_to > $cutoff)
  ```
- **Tombstoned Entities at Cutoff $T$:**
  If an entity was tombstoned at $T_{tomb} > T$, it is correctly evaluated as active at $T$. If queried at $T' \ge T_{tomb}$, it is evaluated as tombstoned.

---

## 4. Read/Write Boundary Audit

1. **Investigation & Read Tools:**
   All PR investigation tools (`lookup_pr_details`, `lookup_linked_issues`, `lookup_changed_files`, `find_historical_reviewers`, `find_related_co_changes`, `audit_ownership_for_files`) continue to use `FalkorDBClient.ro_query()`, which executes FalkorDB's native read-only `GRAPH.RO_QUERY` command.
2. **Permission Whitelist:**
   `validate_and_invoke_tool()` in `src/investigation/tools.py` enforces a strict whitelist of read-only tools, raising `ToolPermissionError` upon any attempt to invoke write methods (`upsert_node`, `upsert_edge`, etc.).
3. **Existing Batch Ingestion Paths (Documented Phase 2 Migration Target):**
   - `src/ingestion/loader.py` (`GraphLoader.load_pull_request`): Performs initial bulk ingestion from GitHub API caches.
   - `src/ownership/graph_ownership.py` (`load_codeowners_into_graph`): Performs initial bulk loading of CODEOWNERS rules.
   - `src/graph/schema.py` (`ensure_schema_indexes`): Executes schema index DDL.
   Per the brief's instruction, these high-volume initial seed loaders were not blindly replaced in Phase 1 to prevent instability. They remain documented targets for Phase 2 incremental sync engine integration.

---

## 5. Files Changed

| File | Status | Description |
| :--- | :--- | :--- |
| `src/graph/writer.py` | Created | Centralized `GraphWriter` implementation with validation, provenance, change logging, and temporal operations. |
| `src/graph/__init__.py` | Modified | Exported `GraphWriter`, `ProvenanceMetadata`, `MutationResult`, `ValidationError`, `EntityNotFoundError`. |
| `tests/test_graph_writer.py` | Created | 12 focused integration tests covering all Phase 1 regression requirements against isolated test graph `test_writer_kg`. |
| `project_context/PROGRESS.md` | Modified | Updated progress ledger with Phase 1 completion, timestamp in IST, test counts, and commit hashes. |

---

## 6. Regression Tests & Verification Results

The test suite in `tests/test_graph_writer.py` verifies all 12 required scenarios against real FalkorDB:

| Test ID | Test Name | Purpose / Assertion | Status |
| :--- | :--- | :--- | :--- |
| **Test 1** | `test_1_create_and_update_node` | Verifies node creation with provenance and subsequent property updates. | **PASSED** |
| **Test 2** | `test_2_create_and_update_edge_without_duplication` | Verifies edge creation and updates without creating duplicate relationships. | **PASSED** |
| **Test 3** | `test_3_idempotent_no_ops` | Asserts repeated identical node and edge upserts return `changed = False` without spurious audit logs. | **PASSED** |
| **Test 4** | `test_4_close_edge_preserves_history` | Verifies `close_edge` sets `valid_to` without deleting the edge, and repeated calls are no-ops. | **PASSED** |
| **Test 5** | `test_5_as_of_reads_before_and_after_closure` | Tests time-travel queries at $T-1\text{s}$ (active) and $T+1\text{s}$ (closed). | **PASSED** |
| **Test 6** | `test_6_tombstone_node_preserves_history` | Verifies tombstoning sets `status='tombstoned'` and `valid_to` while preserving connected edges. | **PASSED** |
| **Test 7** | `test_7_provenance_and_change_events` | Verifies `SyncRun`/`CHANGED` audit trail records `run_id`, `source_url`, `before`, and `after`. | **PASSED** |
| **Test 8** | `test_8_rejection_of_unsupported_and_malformed_inputs` | Asserts rejection of unknown labels, rel types, invalid properties, and empty IDs. | **PASSED** |
| **Test 9** | `test_9_rejection_of_missing_or_invalid_source_evidence` | Rejects missing provenance, invalid URLs (`javascript:`), and nonexistent endpoint nodes. | **PASSED** |
| **Test 10** | `test_10_read_only_tools_cannot_write` | Confirms `ro_query` blocks write Cypher and `validate_and_invoke_tool` blocks mutation tools. | **PASSED** |
| **Test 11** | `test_11_missing_timestamps_stored_as_null` | Confirms missing timestamps are stored as genuine nulls and do not leak into `<=` filters. | **PASSED** |
| **Test 12** | `test_12_failure_handling_and_safe_rejection` | Verifies clean exception raising on invalid timestamps or closing nonexistent edges. | **PASSED** |

### Complete Test Suite Execution
```powershell
$env:PYTHONUTF8 = "1"; & ".\.venv\Scripts\python.exe" -m pytest -v
```
```
============================ 139 passed in 13.72s =============================
```
- Total Tests: **139** (117 baseline + 10 Phase 0 + 12 Phase 1)
- Passed: **139 (100%)**
- Failed: **0**
- Errors: **0**
- Skipped: **0**

---

## 7. Database Integrity & Application Smoke Tests

1. **Active Graph Integrity:**
   - Database health check executed:
     ```powershell
     & ".\.venv\Scripts\python.exe" -m src.db
     ```
     - Status: `HEALTHY`
     - Host: `localhost:6379`
     - Graph: `repo_kg`
     - Nodes: **270** (Exact match with Phase 0 baseline)
     - Relationships: **508** (Exact match with Phase 0 baseline)
2. **Streamlit Application & Investigation Behavior:**
   - 23 end-to-end UI, investigation, and integrity tests executed:
     ```powershell
     & ".\.venv\Scripts\python.exe" -m pytest tests/test_integrity.py tests/test_investigation.py tests/test_ui.py -v
     ```
     - Result: **23 passed in 5.04s** (0 failures, 0 regressions).
   - Confirmed target PR exclusion rule, source URL verification, and nonexistent PR refusal remain fully functional.

---

## 8. Git Commit Log & Index Preservation

In strict adherence to the commit discipline instructions:
- Pre-existing staged changes (48 files) in the git index were **preserved intact** and not bundled into Phase 1 commits.
- Two small, independently verified commits were created targeting exclusively Phase 1 files:

```
5118d63 test: add comprehensive regression test suite for GraphWriter operations and temporal validity
fe36e3e feat: implement central GraphWriter with validated mutations, provenance and temporal semantics
```

- **Commit `fe36e3e` Diff Summary:**
  `src/graph/__init__.py`: 18 lines changed.
  `src/graph/writer.py`: 1065 lines added.
- **Commit `5118d63` Diff Summary:**
  `tests/test_graph_writer.py`: 462 lines added.
- **Zero remote pushes executed.**

---

## 9. Known Limitations & Phase 2 Readiness

1. **Known Limitations:**
   - `GraphWriter` operates synchronously per call. High-throughput bulk loading still uses parameterized batch MERGE queries in `src/ingestion/loader.py` for initial setup speed.
   - FalkorDB property graphs do not support relationship-to-relationship edges; change audit events for relationships link `(:SyncRun)-[:CHANGED]->(:SourceNode)` with edge properties stored on the change relationship.
2. **Phase 2 Readiness Checklist:**
   - [x] Central `GraphWriter` operational and tested.
   - [x] Four approved mutation operations (`upsert_node`, `upsert_edge`, `close_edge`, `tombstone_node`) fully verified.
   - [x] Provenance and change records reliably linked to `SyncRun`.
   - [x] Historical temporal validity preserved on edge closures and tombstones.
   - [x] Read tools isolated from mutation APIs.
   - [x] Graph database `repo_kg` intact with zero data loss.
   - [x] All 139 automated tests green.

**Phase 1 Exit Gate:** Complete and fully verified. Ready to proceed to Phase 2 upon user authorization.
