"""RepoBrain — Health and Live Diagnostics Tab.

Displays database connectivity, node/relationship counts broken down by type,
synchronization state, stale documentation audits, and LLM runtime status.
"""

import sys
from typing import Any, Dict, List, Optional
import streamlit as st

from src.db import FalkorDBClient
from src.knowledge.stale_docs import audit_repository_documentation_staleness


def render_health_tab(client: Optional[FalkorDBClient], config: Dict[str, Any]) -> None:
    """Render the Health & Diagnostics tab."""
    st.subheader("🩺 System Health & Graph Telemetry")
    st.markdown(
        "Real-time operational diagnostics for FalkorDB graph storage, synchronization status, "
        "stale-document integrity audits, and LLM execution runtime."
    )

    # 1. FalkorDB Database Telemetry
    st.markdown("### 1. FalkorDB Connection & Topology")
    if client:
        try:
            ping_res = client.ping()
            counts = client.get_counts()

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("FalkorDB Status", "ONLINE", delta="Healthy")
            with c2:
                st.metric("Graph Latency", f"{ping_res.get('latency_ms', 0):.2f} ms")
            with c3:
                st.metric("Total Nodes", counts.get("nodes", 0))
            with c4:
                st.metric("Total Relationships", counts.get("edges", 0))

            st.caption(f"Host: `{ping_res.get('host', 'localhost')}:{ping_res.get('port', 6379)}` | Graph: `{ping_res.get('graph_name', 'repo_kg')}`")

            # Entity Label Breakdown
            st.markdown("#### Entity Breakdown by Node Label")
            query_labels = """
            MATCH (n)
            RETURN labels(n)[0] AS label, count(n) AS count
            ORDER BY count DESC
            """
            lbl_res = client.ro_query(query_labels)
            if lbl_res and lbl_res.result_set:
                lbl_rows = [f"| `{row[0] or 'Unknown'}` | **{row[1]}** |" for row in lbl_res.result_set]
                st.markdown("| Node Label | Entity Count |\n|---|---|\n" + "\n".join(lbl_rows))

            # Relationship Type Breakdown
            st.markdown("#### Relationship Breakdown by Type")
            query_rels = """
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(r) AS count
            ORDER BY count DESC
            """
            rel_res = client.ro_query(query_rels)
            if rel_res and rel_res.result_set:
                rel_rows = [f"| `:{row[0] or 'RELATED'}` | **{row[1]}** |" for row in rel_res.result_set]
                st.markdown("| Relationship Type | Edge Count |\n|---|---|\n" + "\n".join(rel_rows))

        except Exception as exc:
            st.error(f"Error querying FalkorDB telemetry: {exc}")
    else:
        st.error(
            "🔴 **FalkorDB Offline:** Unable to connect to `localhost:6379`. "
            "Ensure the Docker container `falkordb` is running."
        )

    st.markdown("---")

    # 2. Knowledge Graph Stale-Document & Timestamp Audit
    st.markdown("### 2. Knowledge Integrity & Freshness Audit")
    if client:
        try:
            stale_report = audit_repository_documentation_staleness(client)
            col_k1, col_k2, col_k3 = st.columns(3)
            with col_k1:
                st.metric("Total Audited Documents", stale_report.total_documents_checked)
            with col_k2:
                st.metric("Potentially Stale Docs", stale_report.potentially_stale_count)
            with col_k3:
                st.metric("Unresolved Timestamps", stale_report.unresolved_count)

            stale_findings = [f for f in stale_report.findings if f.status == "POTENTIALLY_STALE"]
            if stale_findings:
                for sf in stale_findings:
                    st.warning(f"📄 Stale Document: `{sf.document_path}` — Modified code referenced: {sf.documented_file_path}")
            else:
                st.success("✅ All documented references are up to date with active code files.")
        except Exception as exc:
            st.error(f"Error running stale-document audit: {exc}")
    else:
        st.info("FalkorDB is offline; knowledge integrity audit unavailable.")

    st.markdown("---")

    # 3. Agent & LLM Execution Status
    st.markdown("### 3. Agent Execution Engine & Runtime")
    api_key_configured = bool(config.get("openrouter_api_key"))

    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        st.metric("OpenRouter Key", "Configured" if api_key_configured else "Not Provided")
    with col_a2:
        st.metric("Configured Model", config.get("model", "anthropic/claude-3.5-sonnet"))
    with col_a3:
        st.metric("Fallback Status", "Live LLM" if api_key_configured else "Deterministic Fallback")

    st.markdown("#### System & Runtime Dependencies")
    st.markdown(
        f"- **Python Version:** `{sys.version.split()[0]}`\n"
        f"- **Streamlit Version:** `{st.__version__}`\n"
        f"- **Query Execution Mode:** Read-Only (`FalkorDBClient.ro_query` enforced)\n"
        f"- **Graph Mutation Isolation:** Enforced (`GraphWriter` & `SyncEngine` gated)"
    )
