"""RepoBrain — Company Brain Streamlit Application.

Track 03: Company Brain (Target: M6 Mac Mini Prize).
Exposes the knowledge graph, live sync engine, evidence-gated agent,
interactive graph visualizer, 3-way comparative evaluation, and live health diagnostics.
"""

import sys
from pathlib import Path
from typing import Optional

# Ensure workspace root is in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

import streamlit as st
from src.db import FalkorDBClient
from src.investigation.orchestrator import PROrchestrator
from src.investigation.models import PRBrief

# UI Tabs and Components
from src.ui.sidebar import render_sidebar
from src.ui.chat_tab import render_chat_tab
from src.ui.explorer_tab import render_explorer_tab
from src.ui.feed_tab import render_feed_tab
from src.ui.compare_tab import render_compare_tab
from src.ui.benchmark_tab import render_benchmark_tab
from src.ui.health_tab import render_health_tab
from src.ui.pr_brief_tab import render_pr_brief_tab, render_brief


st.set_page_config(
    page_title="RepoBrain — Company Brain & Evidence Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_db_client() -> Optional[FalkorDBClient]:
    """Retrieve singleton FalkorDB client handle."""
    try:
        client = FalkorDBClient()
        client.ping()
        return client
    except Exception:
        return None


@st.cache_resource
def get_orchestrator(_client: Optional[FalkorDBClient] = None) -> PROrchestrator:
    """Retrieve singleton investigation orchestrator."""
    return PROrchestrator(client=_client)


def main() -> None:
    """Main Streamlit execution routine."""
    client = get_db_client()

    # 1. Render Sidebar Configuration & Controls
    config = render_sidebar(client)

    # 2. Application Title & Header
    st.title("🧠 RepoBrain — Company Brain")
    st.markdown(
        "Institutional memory, decision tracing, and governance intelligence for engineering repositories. "
        "Every claim is verified against **FalkorDB** ground truth with tamper-proof source citations."
    )

    if not client:
        st.error(
            "[ERROR] Database Connection Failed: FalkorDB is not reachable on `localhost:6379`. "
            "Please ensure the FalkorDB Docker container is running."
        )
        return

    # 3. Main Multi-Tab Interface (All 6 core tabs + preserved PR Brief)
    (
        tab_chat,
        tab_brief,
        tab_explorer,
        tab_feed,
        tab_compare,
        tab_benchmark,
        tab_health,
    ) = st.tabs([
        "🧠 Ask the Brain",
        "📋 PR Brief",
        "🔍 Graph Explorer",
        "🔄 Change Feed",
        "⚖️ Compare",
        "📊 Benchmark",
        "🩺 Health",
    ])

    with tab_chat:
        render_chat_tab(client, config)

    with tab_brief:
        render_pr_brief_tab(client, config)

    with tab_explorer:
        render_explorer_tab(client, config)

    with tab_feed:
        render_feed_tab(client, config)

    with tab_compare:
        render_compare_tab(client, config)

    with tab_benchmark:
        render_benchmark_tab(client, config)

    with tab_health:
        render_health_tab(client, config)


if __name__ == "__main__":
    main()
