"""Core SyncEngine coordinating fetching, state, reconciliation, and GraphWriter."""

import logging
import time
from typing import List, Optional

from src.db import FalkorDBClient
from src.graph.writer import GraphWriter, current_utc_iso
from src.sync.fetcher import GitHubFetcher
from src.sync.models import (
    GitHubChangeEvent,
    ReconciliationResult,
    SyncState,
)
from src.sync.reconciler import EventReconciler
from src.sync.state import SyncLockError, SyncStateManager

logger = logging.getLogger(__name__)


class SyncEngine:
    """Orchestrates reliable incremental synchronization for FalkorDB `repo_kg`."""

    def __init__(
        self,
        client: Optional[FalkorDBClient] = None,
        writer: Optional[GraphWriter] = None,
        fetcher: Optional[GitHubFetcher] = None,
        state_manager: Optional[SyncStateManager] = None,
    ):
        self.client = client or FalkorDBClient()
        self.writer = writer or GraphWriter(client=self.client)
        self.fetcher = fetcher or GitHubFetcher()
        self.state_manager = state_manager or SyncStateManager(client=self.client)

    def run_once(
        self,
        repo: str = "FalkorDB/FalkorDB",
        dry_run: bool = False,
        replay_fixture: Optional[str] = None,
        events_override: Optional[List[GitHubChangeEvent]] = None,
    ) -> ReconciliationResult:
        """Perform a single synchronization cycle.

        Args:
            repo: Target repository slug (e.g. "FalkorDB/FalkorDB").
            dry_run: If True, calculates and logs mutations without altering the graph or cursor.
            replay_fixture: Optional path to local events JSON/JSONL fixture.
            events_override: In-memory events list for direct unit/integration testing.
        """
        run_id = f"sync_{int(time.time())}"
        self.writer.run_id = run_id
        result = ReconciliationResult(run_id=run_id, repo=repo, dry_run=dry_run)

        # 1. Acquire execution lock (unless dry-run)
        if not dry_run:
            try:
                self.state_manager.acquire_lock(repo=repo, run_id=run_id)
            except SyncLockError as err:
                result.errors.append(str(err))
                result.failures += 1
                return result

        try:
            state = self.state_manager.get_state(repo)

            # 2. Collect events from replay fixture, override, or live fetcher
            if events_override is not None:
                events = events_override
                new_state = state
            elif replay_fixture:
                events = self.fetcher.load_replay_events(replay_fixture)
                new_state = state
            else:
                events, new_state = self.fetcher.fetch_incremental_events(repo, state)

            result.events_processed = len(events)

            # 3. Reconcile events
            reconciler = EventReconciler(writer=self.writer, dry_run=dry_run)
            for ev in events:
                # Incremental cursor check: skip events already processed in prior sync
                if state.last_sync_at and ev.timestamp <= state.last_sync_at:
                    result.no_ops += 1
                    continue

                try:
                    applied, changed, _ = reconciler.reconcile_event(ev)
                    if applied:
                        if changed:
                            result.mutations_applied += 1
                        else:
                            result.no_ops += 1
                    else:
                        result.failures += 1
                except Exception as ex:
                    logger.error(f"Failed to reconcile event {ev.event_id}: {ex}")
                    result.failures += 1
                    result.errors.append(f"Event {ev.event_id}: {str(ex)}")

            # 4. Advance cursor only if successful and not dry-run
            if not dry_run and result.failures == 0:
                new_state.last_sync_at = current_utc_iso()
                new_state.last_run_id = run_id
                self.state_manager.save_state(new_state)
                result.cursor_advanced = True

        except Exception as exc:
            logger.error(f"SyncEngine execution failed: {exc}")
            result.errors.append(str(exc))
            result.failures += 1
        finally:
            if not dry_run:
                self.state_manager.release_lock(repo, status="idle" if result.failures == 0 else "failed")

        return result

    def run_watch(
        self,
        repo: str = "FalkorDB/FalkorDB",
        interval: int = 30,
        dry_run: bool = False,
        max_iterations: Optional[int] = None,
    ) -> None:
        """Poll repository periodically at `interval` seconds."""
        iterations = 0
        logger.info(f"Starting SyncEngine watch mode for '{repo}' (interval={interval}s, dry_run={dry_run})")
        while max_iterations is None or iterations < max_iterations:
            try:
                res = self.run_once(repo=repo, dry_run=dry_run)
                logger.info(
                    f"[Run {res.run_id}] Processed {res.events_processed} events, "
                    f"{res.mutations_applied} mutations applied, {res.no_ops} no-ops, {res.failures} failures."
                )
            except Exception as e:
                logger.error(f"Error in watch cycle: {e}")

            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break
            time.sleep(interval)
