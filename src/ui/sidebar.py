"""RepoBrain — Streamlit UI Sidebar and Configuration Controls.

Handles masked API key input, model selection, intelligence mode (Graph ON/OFF),
historical as-of cutoffs, sync triggers, and live system status.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import streamlit as st

from src.db import FalkorDBClient
from src.sync.state import SyncStateManager
from src.sync.engine import SyncEngine


def render_sidebar(client: Optional[FalkorDBClient]) -> Dict[str, Any]:
    """Render sidebar controls and return active configuration dictionary."""
    st.sidebar.title("🧠 RepoBrain")
    st.sidebar.caption("Graph Hacks 2026 — Track 03: Company Brain")
    st.sidebar.markdown("---")

    # 1. Connection & Health Status
    st.sidebar.subheader("System Status")
    db_status = "offline"
    node_count = 0
    edge_count = 0
    latency_ms = 0.0

    if client:
        try:
            health = client.ping()
            counts = client.get_counts()
            node_count = counts.get("nodes", 0)
            edge_count = counts.get("edges", 0)
            latency_ms = health.get("latency_ms", 0.0)
            db_status = "connected"
            st.sidebar.success(
                f"**Connected:** `{health.get('graph_name', 'repo_kg')}` ({latency_ms:.1f}ms)\n\n"
                f"Nodes: `{node_count}` | Edges: `{edge_count}`"
            )
        except Exception as exc:
            st.sidebar.error(f"FalkorDB Error: {exc}")
    else:
        st.sidebar.error("[OFFLINE] FalkorDB Offline (`localhost:6379`)")
        st.sidebar.info("Ensure Docker container `falkordb` is running.")

    # Sync Status Display
    last_sync_str = "Never"
    if client and db_status == "connected":
        try:
            state_mgr = SyncStateManager(client)
            sync_state = state_mgr.get_state("FalkorDB/FalkorDB")
            if sync_state and sync_state.last_sync_at:
                last_sync_str = sync_state.last_sync_at
                # Calculate age
                try:
                    sync_dt = datetime.fromisoformat(last_sync_str.replace("Z", "+00:00"))
                    now_dt = datetime.now(timezone.utc)
                    age_mins = int((now_dt - sync_dt).total_seconds() / 60)
                    st.sidebar.caption(f"Last Sync: {last_sync_str[:19]} ({age_mins}m ago)")
                except Exception:
                    st.sidebar.caption(f"Last Sync: {last_sync_str}")
            else:
                st.sidebar.caption("Last Sync: Initial state")
        except Exception:
            pass

    st.sidebar.markdown("---")

    # 2. OpenRouter API Configuration
    st.sidebar.subheader("LLM Configuration")

    # Masked API Key (stored strictly in session state, never written to disk or logs)
    if "openrouter_api_key" not in st.session_state:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            st.session_state["openrouter_api_key"] = ""
        else:
            st.session_state["openrouter_api_key"] = os.environ.get("OPENROUTER_API_KEY", "")

    api_key_input = st.sidebar.text_input(
        "OpenRouter API Key",
        value=st.session_state["openrouter_api_key"],
        type="password",
        placeholder="sk-or-v1-...",
        help="Kept strictly in ephemeral session memory. Never written to disk or logs.",
    )
    st.session_state["openrouter_api_key"] = api_key_input.strip()

    # Active LLM Mode Notice
    if st.session_state["openrouter_api_key"]:
        st.sidebar.success("Mode: Live OpenRouter LLM")
    else:
        st.sidebar.info("Mode: Zero-Key Deterministic Fallback (Offline Safe)")

    # Model Selector (Verified DeepSeek models)
    default_model = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat")
    preset_models = [
        default_model,
        "deepseek/deepseek-chat",
        "deepseek/deepseek-r1",
        "deepseek/deepseek-v4.1-flash",
        "deepseek/deepseek-v3.2",
        "Custom...",
    ]
    # Deduplicate while preserving order
    seen = set()
    model_options = [m for m in preset_models if not (m in seen or seen.add(m))]

    chosen_model = st.sidebar.selectbox("Model", model_options, index=0)
    if chosen_model == "Custom...":
        chosen_model = st.sidebar.text_input(
            "Custom DeepSeek Model Slug",
            value="deepseek/deepseek-chat",
            placeholder="deepseek/...",
        ).strip()
        if chosen_model and not chosen_model.startswith("deepseek/"):
            st.sidebar.warning("RepoBrain strictly requires a verified DeepSeek model.")

    st.sidebar.markdown("---")

    # 3. Intelligence Mode (Graph ON / Plain Retrieval / Graph OFF)
    st.sidebar.subheader("Intelligence Mode")
    graph_mode = st.sidebar.radio(
        "Demo Control",
        options=[
            "Graph ON (Company Brain Agent)",
            "Plain Retrieval (TF-IDF Vector)",
            "Graph OFF (Direct Model Alone)",
        ],
        index=0,
        help="Central demo switch controlling whether knowledge graph tools and verifier are active.",
    )

    st.sidebar.markdown("---")

    # 4. Historical as_of Date/Time Selector
    st.sidebar.subheader("Temporal Cutoff")
    enable_as_of = st.sidebar.checkbox(
        "Enable Historical as_of",
        value=False,
        help="Exclude all graph entities and events observed strictly after this cutoff timestamp.",
    )

    as_of_iso = None
    if enable_as_of:
        col_d, col_t = st.sidebar.columns(2)
        with col_d:
            sel_date = st.date_input("Date", value=datetime.now(timezone.utc).date())
        with col_t:
            sel_time = st.time_input("Time (UTC)", value=datetime.now(timezone.utc).time())
        if sel_date and sel_time:
            dt_combined = datetime.combine(sel_date, sel_time, tzinfo=timezone.utc)
            as_of_iso = dt_combined.strftime("%Y-%m-%dT%H:%M:%SZ")
            st.sidebar.caption(f"Cutoff: `{as_of_iso}`")

    st.sidebar.markdown("---")

    # 5. Live Incremental Sync Trigger
    st.sidebar.subheader("Data Synchronization")
    if st.sidebar.button("🔄 Sync Now", use_container_width=True):
        if not client:
            st.sidebar.error("Cannot sync: FalkorDB is offline.")
        else:
            with st.sidebar.status("Running incremental sync...", expanded=True) as sync_box:
                try:
                    engine = SyncEngine(client=client, repo="FalkorDB/FalkorDB")
                    summary = engine.run_once(dry_run=False)
                    sync_box.update(label="Sync Completed!", state="complete", expanded=False)
                    st.sidebar.success(f"Sync complete! Processed {summary.events_processed} events.")
                    st.rerun()
                except Exception as sync_err:
                    sync_box.update(label="Sync Failed", state="error")
                    st.sidebar.error(f"Sync error: {sync_err}")

    st.sidebar.markdown("---")

    # 6. Quick Demo Presets
    st.sidebar.subheader("Demo Presets")
    st.sidebar.caption("Click to load authentic questions into the active view:")

    presets = [
        ("q_reviewers_multi", "Who should review a PR touching both src/ and tests/? Rank with evidence."),
        ("q_who_owns", "Who owns src/module.c?"),
        ("q_who_knows", "Who knows about src/module.c?"),
        ("q_pr_brief", "What is the brief for PR #3339?"),
        ("q_decision", "What was decided about graph limits?"),
        ("q_stale", "Are there any stale documentation files?"),
        ("q_maintainers", "Who are the top maintainers by PageRank?"),
        ("q_sync_status", "What is the current sync status?"),
        ("q_codeowners", "Show all CODEOWNERS rules"),
    ]

    for p_key, p_text in presets:
        if st.sidebar.button(p_text, key=f"btn_{p_key}", use_container_width=True):
            st.session_state["user_question_input"] = p_text

    return {
        "db_status": db_status,
        "node_count": node_count,
        "edge_count": edge_count,
        "latency_ms": latency_ms,
        "openrouter_api_key": st.session_state["openrouter_api_key"],
        "model": chosen_model,
        "graph_mode": graph_mode,
        "as_of": as_of_iso,
    }
