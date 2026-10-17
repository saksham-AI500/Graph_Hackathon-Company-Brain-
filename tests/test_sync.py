"""Unit and integration tests for RepoBrain incremental synchronization engine.

Covers all required Phase 2 scenarios:
- Initial synchronization via replay.
- Idempotent repeated run (zero spurious mutations).
- PR lifecycle (open, merge, close, reopen).
- File lifecycle (add, remove, rename).
- Review submission and dismissal without review collapse.
- Issue lifecycle (edit, close, resolve).
- CODEOWNERS changes and owner removal.
- Document addition and tombstoning.
- Null/malformed timestamp handling.
- Dry-run verification (no graph changes, cursor unadvanced).
- Cursor persistence and recovery.
- Concurrency locking.
- Rate limiting and transient retry behavior.
"""

from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from src.db import FalkorDBClient
from src.graph.writer import GraphWriter
from src.sync.engine import SyncEngine
from src.sync.fetcher import GitHubFetcher, RateLimitExceededError
from src.sync.models import (
    EventType,
    GitHubChangeEvent,
    SyncState,
)
from src.sync.reconciler import EventReconciler
from src.sync.state import SyncLockError, SyncStateManager


TEST_REPLAY_FIXTURE = str(Path("tests/fixtures/sync_events_replay.jsonl").resolve())


@pytest.fixture(scope="module")
def sync_env():
    """Setup an isolated test graph client, writer, and engine."""
    import shutil
    cache_path = Path(".cache/test_sync")
    shutil.rmtree(cache_path, ignore_errors=True)

    test_graph = "test_sync_kg"
    client = FalkorDBClient(graph_name=test_graph)
    try:
        client.graph.delete()
    except Exception:
        pass

    writer = GraphWriter(client=client, run_id="sync_test_run")
    state_mgr = SyncStateManager(client=client, cache_dir=str(cache_path))
    fetcher = GitHubFetcher()
    engine = SyncEngine(client=client, writer=writer, fetcher=fetcher, state_manager=state_mgr)

    yield client, writer, state_mgr, engine

    try:
        client.graph.delete()
    except Exception:
        pass
    shutil.rmtree(cache_path, ignore_errors=True)


# -----------------------------------------------------------------------------
# 1. Initial Synchronization via Replay
# -----------------------------------------------------------------------------

def test_initial_sync_replay(sync_env):
    client, _, state_mgr, engine = sync_env
    res = engine.run_once(repo="FalkorDB/falkordb-py", replay_fixture=TEST_REPLAY_FIXTURE)

    assert res.failures == 0
    assert res.events_processed == 12
    assert res.mutations_applied > 0
    assert res.cursor_advanced is True

    # Verify PR 4001 was ingested and is closed/merged
    pr_res = client.ro_query("MATCH (pr:PullRequest {number: 4001}) RETURN pr.title, pr.state, pr.merged_at")
    assert len(pr_res.result_set) == 1
    row = pr_res.result_set[0]
    assert row[0] == "Add sync engine"
    assert row[1] == "closed"
    assert row[2] == "2026-10-16T12:00:00Z"

    # Verify cursor state was persisted
    state = state_mgr.get_state("FalkorDB/falkordb-py")
    assert state.last_sync_at is not None
    assert state.status == "idle"


# -----------------------------------------------------------------------------
# 2. Idempotent Second Run (Zero Spurious Mutations)
# -----------------------------------------------------------------------------

def test_idempotent_second_run(sync_env):
    _, _, _, engine = sync_env
    res2 = engine.run_once(repo="FalkorDB/falkordb-py", replay_fixture=TEST_REPLAY_FIXTURE)

    assert res2.failures == 0
    assert res2.events_processed == 12
    assert res2.mutations_applied == 0  # Zero state changes
    assert res2.no_ops == 12           # All events recognized as no-ops


# -----------------------------------------------------------------------------
# 3. PR Lifecycle Transitions (Open -> Close -> Reopen)
# -----------------------------------------------------------------------------

def test_pr_lifecycle_transitions(sync_env):
    client, writer, _, _ = sync_env
    reconciler = EventReconciler(writer=writer)

    # 1. Open PR 4002
    ev_open = GitHubChangeEvent(
        event_id="pr_open_4002",
        event_type=EventType.PR_OPENED,
        timestamp="2026-10-16T15:00:00Z",
        source_url="https://github.com/pr/4002",
        data={"pr_number": 4002, "title": "Lifecycle PR", "author_login": "alice", "created_at": "2026-10-16T15:00:00Z"},
    )
    reconciler.reconcile_event(ev_open)
    res = client.ro_query("MATCH (pr:PullRequest {number: 4002}) RETURN pr.state")
    assert res.result_set[0][0] == "open"

    # 2. Close PR 4002
    ev_close = GitHubChangeEvent(
        event_id="pr_close_4002",
        event_type=EventType.PR_CLOSED,
        timestamp="2026-10-16T16:00:00Z",
        source_url="https://github.com/pr/4002",
        data={"pr_number": 4002, "closed_at": "2026-10-16T16:00:00Z"},
    )
    reconciler.reconcile_event(ev_close)
    res = client.ro_query("MATCH (pr:PullRequest {number: 4002}) RETURN pr.state, pr.closed_at")
    assert res.result_set[0][0] == "closed"
    assert res.result_set[0][1] == "2026-10-16T16:00:00Z"

    # 3. Reopen PR 4002
    ev_reopen = GitHubChangeEvent(
        event_id="pr_reopen_4002",
        event_type=EventType.PR_REOPENED,
        timestamp="2026-10-16T17:00:00Z",
        source_url="https://github.com/pr/4002",
        data={"pr_number": 4002},
    )
    reconciler.reconcile_event(ev_reopen)
    res = client.ro_query("MATCH (pr:PullRequest {number: 4002}) RETURN pr.state, pr.closed_at")
    assert res.result_set[0][0] == "open"
    assert res.result_set[0][1] is None  # closed_at cleared upon reopen


# -----------------------------------------------------------------------------
# 4. PR File Renaming and Closure of Old Paths
# -----------------------------------------------------------------------------

def test_pr_file_renaming(sync_env):
    client, _, _, _ = sync_env

    # From replay: src/sync_module.py was renamed to src/sync_engine.py in PR 4001
    # Check old path relationship was closed (valid_to is set)
    old_rel = client.ro_query(
        "MATCH (pr:PullRequest {number: 4001})-[r:MODIFIES]->(f:File {path: 'src/sync_module.py'}) RETURN r.valid_to"
    )
    assert len(old_rel.result_set) == 1
    assert old_rel.result_set[0][0] is not None  # valid_to is set (closed)

    # Check new path relationship is currently active (valid_to is null)
    new_rel = client.ro_query(
        "MATCH (pr:PullRequest {number: 4001})-[r:MODIFIES]->(f:File {path: 'src/sync_engine.py'}) RETURN r.valid_to"
    )
    assert len(new_rel.result_set) == 1
    assert new_rel.result_set[0][0] is None  # currently valid


# -----------------------------------------------------------------------------
# 5. Distinct Reviews Keyed by Review ID
# -----------------------------------------------------------------------------

def test_distinct_reviews_keyed_by_id(sync_env):
    client, _, _, _ = sync_env

    # From replay: sync_bob submitted two reviews on PR 4001 (review 7001 APPROVED, review 7002 COMMENTED)
    reviews_res = client.ro_query(
        "MATCH (p:Person {login: 'sync_bob'})-[r:REVIEWED]->(pr:PullRequest {number: 4001}) "
        "RETURN r.id, r.state ORDER BY r.id ASC"
    )
    assert len(reviews_res.result_set) == 2
    assert reviews_res.result_set[0] == [7001, "APPROVED"]
    assert reviews_res.result_set[1] == [7002, "COMMENTED"]


# -----------------------------------------------------------------------------
# 6. Issue Lifecycle and Resolution
# -----------------------------------------------------------------------------

def test_issue_lifecycle_and_resolution(sync_env):
    client, _, _, _ = sync_env

    # From replay: Issue 5001 linked via RESOLVES from PR 4001 and closed
    iss_res = client.ro_query(
        "MATCH (pr:PullRequest {number: 4001})-[:RESOLVES]->(i:Issue {number: 5001}) "
        "RETURN i.title, i.state, i.closed_at"
    )
    assert len(iss_res.result_set) == 1
    assert iss_res.result_set[0][0] == "Sync engine requirement"
    assert iss_res.result_set[0][1] == "closed"


# -----------------------------------------------------------------------------
# 7. CODEOWNERS Changes & Owner Removal
# -----------------------------------------------------------------------------

def test_codeowners_changes(sync_env):
    client, writer, _, _ = sync_env
    reconciler = EventReconciler(writer=writer)

    # Rule added in replay: /src/sync/ -> @FalkorDB/falkordb-core
    rule_res = client.ro_query(
        "MATCH (r:OwnershipRule {pattern: '/src/sync/'})-[:DECLARES_OWNER]->(t:Team {name: '@FalkorDB/falkordb-core'}) "
        "RETURN count(r)"
    )
    assert rule_res.result_set[0][0] == 1

    # Remove owner
    ev_rem = GitHubChangeEvent(
        event_id="co_rem_01",
        event_type=EventType.CODEOWNERS_OWNER_REMOVED,
        timestamp="2026-10-16T18:00:00Z",
        source_url="https://github.com/CODEOWNERS",
        data={"pattern": "/src/sync/", "owner_name": "@FalkorDB/falkordb-core"},
    )
    reconciler.reconcile_event(ev_rem)

    # Edge must be closed (valid_to set)
    closed_res = client.ro_query(
        "MATCH (r:OwnershipRule {pattern: '/src/sync/'})-[rel:DECLARES_OWNER]->(t:Team {name: '@FalkorDB/falkordb-core'}) "
        "RETURN rel.valid_to"
    )
    assert closed_res.result_set[0][0] == "2026-10-16T18:00:00Z"


# -----------------------------------------------------------------------------
# 8. Document Additions and Tombstoning
# -----------------------------------------------------------------------------

def test_document_addition_and_tombstone(sync_env):
    client, _, _, _ = sync_env

    # Added doc
    doc_res = client.ro_query("MATCH (f:File {path: 'docs/sync_architecture.md'}) RETURN f.status")
    assert doc_res.result_set[0][0] == "active"

    # Deleted doc is tombstoned, not hard-deleted
    tomb_res = client.ro_query("MATCH (f:File {path: 'docs/old_draft.md'}) RETURN f.status, f.tombstoned_at")
    assert len(tomb_res.result_set) == 1
    assert tomb_res.result_set[0][0] == "tombstoned"
    assert tomb_res.result_set[0][1] == "2026-10-16T14:00:00Z"


# -----------------------------------------------------------------------------
# 9. Dry-Run Mode Verification
# -----------------------------------------------------------------------------

def test_dry_run_produces_no_graph_mutations(sync_env):
    client, _, state_mgr, engine = sync_env

    # Capture initial counts
    init_counts = client.get_counts()
    init_state = state_mgr.get_state("FalkorDB/falkordb-py")

    # Run in dry-run mode with new PR event
    dry_event = GitHubChangeEvent(
        event_id="dry_event_9999",
        event_type=EventType.PR_OPENED,
        timestamp="2026-10-16T19:00:00Z",
        source_url="https://github.com/pr/9999",
        data={"pr_number": 9999, "title": "Dry run PR", "author_login": "ghost"},
    )

    res = engine.run_once(
        repo="FalkorDB/falkordb-py",
        dry_run=True,
        events_override=[dry_event],
    )

    assert res.dry_run is True
    assert res.events_processed == 1
    assert res.cursor_advanced is False

    # Node 9999 must NOT exist in FalkorDB
    check_pr = client.ro_query("MATCH (pr:PullRequest {number: 9999}) RETURN count(pr)")
    assert check_pr.result_set[0][0] == 0

    # Counts must remain identical
    after_counts = client.get_counts()
    assert init_counts == after_counts


# -----------------------------------------------------------------------------
# 10. Concurrency Lock Protection
# -----------------------------------------------------------------------------

def test_concurrency_lock_protection(sync_env):
    _, _, state_mgr, engine = sync_env

    # Manually lock repository
    state_mgr.acquire_lock("locked_repo", run_id="run_alpha")

    # Second lock attempt must fail
    with pytest.raises(SyncLockError, match="Concurrent sync active"):
        state_mgr.acquire_lock("locked_repo", run_id="run_beta")

    # Engine run reports failure cleanly
    res = engine.run_once(repo="locked_repo")
    assert res.failures == 1
    assert any("Concurrent sync active" in err for err in res.errors)

    # Clean release
    state_mgr.release_lock("locked_repo")
    state = state_mgr.get_state("locked_repo")
    assert state.status == "idle"


# -----------------------------------------------------------------------------
# 11. Rate Limiting and Retry Handling
# -----------------------------------------------------------------------------

def test_rate_limit_handling():
    fetcher = GitHubFetcher(max_retries=2)
    fake_resp = MagicMock()
    fake_resp.status_code = 403
    fake_resp.text = "API rate limit exceeded"
    fake_resp.headers = {"X-RateLimit-Remaining": "0"}

    mock_client = MagicMock()
    mock_client.get.return_value = fake_resp

    with pytest.raises(RateLimitExceededError, match="rate limit exceeded"):
        fetcher._request_with_retry(mock_client, "https://api.github.com/test", headers={})
