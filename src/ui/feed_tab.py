"""RepoBrain — Change Feed Tab.

Exposes live synchronization activity and audit change records from (:SyncRun)
and (:SyncRun)-[:CHANGED]->(target) records stored in FalkorDB.
"""

from typing import Any, Dict, List, Optional
import streamlit as st

from src.db import FalkorDBClient
from src.sync.state import SyncStateManager


def render_feed_tab(client: Optional[FalkorDBClient], config: Dict[str, Any]) -> None:
    """Render the Change Feed tab displaying live sync runs and audit logs."""
    st.subheader("🔄 Live Change Feed & Audit Log")
    st.markdown(
        "Displays real synchronization activity, incremental update runs, and tamper-proof "
        "audit change records captured by the Phase 1 GraphWriter and Phase 2 Sync Engine."
    )

    if not client:
        st.error("[OFFLINE] Cannot query change feed: FalkorDB is offline on `localhost:6379`.")
        return

    # 1. Overall Sync State Card
    state_mgr = SyncStateManager(client)
    try:
        current_state = state_mgr.get_state("FalkorDB/FalkorDB")
    except Exception as exc:
        st.error(f"Error reading sync state: {exc}")
        current_state = None

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric("Target Repository", "FalkorDB/FalkorDB")
    with col_s2:
        last_sync = current_state.last_sync_at[:19] if current_state and current_state.last_sync_at else "Initial"
        st.metric("Latest Cursor", last_sync)
    with col_s3:
        lock_status = "LOCKED" if current_state and current_state.locked_at else "IDLE / READY"
        st.metric("Sync Engine State", lock_status)
    with col_s4:
        etag_count = len(current_state.etag_map) if current_state and current_state.etag_map else 0
        st.metric("Cached ETags", f"{etag_count} cached")

    st.markdown("---")

    # 2. Query Recent SyncRuns from FalkorDB
    query = """
    MATCH (s:SyncRun)
    OPTIONAL MATCH (s)-[c:CHANGED]->(target)
    RETURN s.run_id AS run_id,
           s.started_at AS started_at,
           s.completed_at AS completed_at,
           s.status AS status,
           s.events_processed AS events_processed,
           s.dry_run AS dry_run,
           s.error AS error,
           collect({
               op: c.op,
               target_id: c.target_id,
               before: c.before,
               after: c.after
           }) AS changes
    ORDER BY s.started_at DESC
    LIMIT 20
    """

    runs = []
    try:
        res = client.ro_query(query)
        if res and res.result_set:
            for row in res.result_set:
                run_id, started, completed, status, ev_count, dry_run, err, changes = row
                # Filter out empty collected maps
                valid_changes = [ch for ch in (changes or []) if ch.get("op")]
                runs.append({
                    "run_id": run_id or "unknown",
                    "started_at": started or "unknown",
                    "completed_at": completed or "-",
                    "status": status or "SUCCESS",
                    "events_processed": ev_count or 0,
                    "dry_run": bool(dry_run),
                    "error": err,
                    "changes": valid_changes,
                })
    except Exception as exc:
        st.error(f"Error querying sync runs: {exc}")

    if not runs:
        st.info(
            "No synchronization runs recorded in `repo_kg` yet.\n\n"
            "Click **🔄 Sync Now** in the sidebar to execute an incremental synchronization run."
        )
        return

    st.markdown(f"### Recent Synchronization Runs ({len(runs)} recorded):")

    for idx, r in enumerate(runs):
        run_status = r["status"]
        dry_badge = "[DRY-RUN]" if r["dry_run"] else "[REAL SYNC]"
        status_color = "🟢" if run_status == "SUCCESS" else "🔴" if run_status == "FAILED" else "🟡"

        with st.expander(
            f"{status_color} Run `{r['run_id'][:8]}...` — {dry_badge} {run_status} ({r['events_processed']} events) — {r['started_at'][:19]}",
            expanded=(idx == 0),
        ):
            c_meta1, c_meta2, c_meta3 = st.columns(3)
            with c_meta1:
                st.markdown(f"**Run ID:** `{r['run_id']}`")
                st.markdown(f"**Execution Mode:** `{dry_badge}`")
            with c_meta2:
                st.markdown(f"**Started:** `{r['started_at']}`")
                st.markdown(f"**Completed:** `{r['completed_at']}`")
            with c_meta3:
                st.markdown(f"**Status:** `{run_status}`")
                st.markdown(f"**Events Processed:** `{r['events_processed']}`")

            if r.get("error"):
                st.error(f"**Error Details:** {r['error']}")

            # Change Records Breakdown
            changes = r.get("changes", [])
            st.markdown(f"**Graph Mutations & Audit Records ({len(changes)}):**")
            if changes:
                change_rows = []
                for ch in changes:
                    op = ch.get("op", "-")
                    target = ch.get("target_id", "-")
                    before_val = str(ch.get("before") or "-")
                    after_val = str(ch.get("after") or "-")
                    change_rows.append(f"| `{op}` | `{target}` | `{before_val[:30]}` | `{after_val[:30]}` |")

                st.markdown(
                    "| Operation | Target Entity | Before State | After State |\n|---|---|---|---|\n" +
                    "\n".join(change_rows)
                )
            else:
                st.caption("No entity mutations applied (idempotent run or dry-run).")
