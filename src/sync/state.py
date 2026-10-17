"""Persistent synchronization state and cursor management for FalkorDB."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Optional

from src.db import FalkorDBClient
from src.graph.writer import current_utc_iso
from src.sync.models import SyncState


class SyncLockError(RuntimeError):
    """Raised when a concurrent synchronization run is detected."""
    pass


class SyncStateManager:
    """Manages persistent repository cursors, ETags, and concurrency locks in FalkorDB."""

    def __init__(self, client: Optional[FalkorDBClient] = None, cache_dir: Optional[str] = None):
        self.client = client or FalkorDBClient()
        self.cache_dir = Path(cache_dir or ".cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure indexes exist for SyncState."""
        try:
            self.client.query("CREATE INDEX FOR (s:SyncState) ON (s.repo)")
        except Exception:
            pass

    def _cache_path(self, repo: str) -> Path:
        slug = repo.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"sync_state_{slug}.json"

    def get_state(self, repo: str) -> SyncState:
        """Retrieve current sync state for a repository from FalkorDB (or disk cache fallback)."""
        query = """
        MATCH (s:SyncState {repo: $repo})
        RETURN s.last_sync_at AS last_sync_at,
               s.last_run_id AS last_run_id,
               s.pr_cursor AS pr_cursor,
               s.issue_cursor AS issue_cursor,
               s.commit_cursor AS commit_cursor,
               s.status AS status,
               s.locked_at AS locked_at,
               s.etag_map_json AS etag_map_json
        """
        try:
            res = self.client.ro_query(query, {"repo": repo})
            if res and res.result_set:
                row = res.result_set[0]
                etag_map = json.loads(row[7]) if row[7] else {}
                return SyncState(
                    repo=repo,
                    last_sync_at=row[0],
                    last_run_id=row[1],
                    pr_cursor=int(row[2] or 0),
                    issue_cursor=int(row[3] or 0),
                    commit_cursor=row[4],
                    status=row[5] or "idle",
                    locked_at=row[6],
                    etag_map=etag_map,
                )
        except Exception:
            pass

        # Fallback to local cache if FalkorDB does not have it yet
        cache_file = self._cache_path(repo)
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return SyncState(**data)
            except Exception:
                pass

        return SyncState(repo=repo)

    def acquire_lock(self, repo: str, run_id: str, timeout_seconds: int = 300) -> bool:
        """Attempt to acquire an exclusive execution lock for the repository."""
        state = self.get_state(repo)
        now_ts = current_utc_iso()

        if state.status == "in_progress" and state.locked_at:
            try:
                dt_locked = datetime.fromisoformat(state.locked_at.replace("Z", "+00:00"))
                dt_now = datetime.now(timezone.utc)
                age = (dt_now - dt_locked).total_seconds()
                if age < timeout_seconds:
                    raise SyncLockError(
                        f"Concurrent sync active for '{repo}'. Locked by run '{state.last_run_id}' {int(age)}s ago."
                    )
            except SyncLockError:
                raise
            except Exception:
                pass

        # Acquire lock
        state.status = "in_progress"
        state.locked_at = now_ts
        state.last_run_id = run_id
        self._save_to_graph(state)
        self._save_to_disk(state)
        return True

    def release_lock(self, repo: str, status: str = "idle") -> None:
        """Release execution lock."""
        state = self.get_state(repo)
        state.status = status
        state.locked_at = None
        self._save_to_graph(state)
        self._save_to_disk(state)

    def save_state(self, state: SyncState) -> None:
        """Persist updated sync state and cursors."""
        self._save_to_graph(state)
        self._save_to_disk(state)

    def _save_to_graph(self, state: SyncState) -> None:
        query = """
        MERGE (s:SyncState {repo: $repo})
        ON CREATE SET s.last_sync_at = $last_sync_at,
                      s.last_run_id = $last_run_id,
                      s.pr_cursor = $pr_cursor,
                      s.issue_cursor = $issue_cursor,
                      s.commit_cursor = $commit_cursor,
                      s.status = $status,
                      s.locked_at = $locked_at,
                      s.etag_map_json = $etag_map_json
        ON MATCH SET s.last_sync_at = $last_sync_at,
                     s.last_run_id = $last_run_id,
                     s.pr_cursor = $pr_cursor,
                     s.issue_cursor = $issue_cursor,
                     s.commit_cursor = $commit_cursor,
                     s.status = $status,
                     s.locked_at = $locked_at,
                     s.etag_map_json = $etag_map_json
        """
        etag_json = json.dumps(state.etag_map)
        try:
            self.client.query(
                query,
                {
                    "repo": state.repo,
                    "last_sync_at": state.last_sync_at,
                    "last_run_id": state.last_run_id,
                    "pr_cursor": state.pr_cursor,
                    "issue_cursor": state.issue_cursor,
                    "commit_cursor": state.commit_cursor,
                    "status": state.status,
                    "locked_at": state.locked_at,
                    "etag_map_json": etag_json,
                },
            )
        except Exception:
            pass

    def _save_to_disk(self, state: SyncState) -> None:
        try:
            cache_file = self._cache_path(state.repo)
            cache_file.write_text(json.dumps(state.model_dump(), indent=2), encoding="utf-8")
        except Exception:
            pass
