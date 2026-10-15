"""RepoBrain — Evidence-Gated PR Brief Streamlit Application.

Track 03: Company Brain (Target: M6 Mac Mini Prize).
Deterministic PR investigation interface with ownership discrepancy and decision tracing.
"""

import sys
from pathlib import Path
from typing import Optional

# Ensure workspace root is in path
workspace_root = Path(__file__).resolve().parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

import streamlit as st
from src.db import FalkorDBClient
from src.investigation.orchestrator import PROrchestrator
from src.investigation.models import PRBrief


st.set_page_config(
    page_title="RepoBrain — Evidence-Gated PR Investigation",
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
def get_orchestrator() -> PROrchestrator:
    """Retrieve singleton investigation orchestrator."""
    return PROrchestrator()


def render_sidebar(client: Optional[FalkorDBClient]) -> None:
    """Render system diagnostics and quick demonstration presets."""
    st.sidebar.title("🧠 RepoBrain")
    st.sidebar.caption("Graph Hacks 2026 — Track 03: Company Brain")
    st.sidebar.markdown("---")

    st.sidebar.subheader("FalkorDB Status")
    if client:
        try:
            health = client.ping()
            counts = client.get_counts()
            st.sidebar.success(f"**Connected:** `{health['graph_name']}` ({health['latency_ms']}ms)")
            st.sidebar.markdown(f"- **Host:** `{health['host']}:{health['port']}`")
            st.sidebar.markdown(f"- **Nodes:** `{counts['nodes']}`")
            st.sidebar.markdown(f"- **Relationships:** `{counts['edges']}`")
        except Exception as exc:
            st.sidebar.error(f"Error querying FalkorDB: {exc}")
    else:
        st.sidebar.error("[OFFLINE] FalkorDB Offline (`localhost:6379`)")
        st.sidebar.info("Ensure the Docker container `falkordb` is running.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Demo Presets")
    st.sidebar.caption("Click to load authentic FalkorDB pull requests:")

    presets = [
        ("3339", "PR #3339 (Resolved Issue #3338)"),
        ("3342", "PR #3342 (v4.22.1 Release / 75 Files)"),
        ("3176", "PR #3176 (Decode Fix / Issue #3175)"),
        ("3161", "PR #3161 (RDB Virtual Keys / Drift)"),
        ("9999", "PR #9999 (Nonexistent / Refusal)"),
    ]

    for pr_id, label in presets:
        if st.sidebar.button(label, key=f"btn_{pr_id}", use_container_width=True):
            st.session_state["target_input"] = pr_id


def render_brief(brief: PRBrief) -> None:
    """Render verified PR brief with auditable evidence paths."""
    if brief.status == "REFUSED":
        st.warning(f"### [REFUSED] Investigation Refused (Status: `{brief.status}`)")
        st.info(f"**Reason:** {brief.refusal_message}")
        st.markdown(
            "The deterministic gatekeeper refuses to speculate on pull requests that lack "
            "verifiable ground-truth records in the local graph."
        )
        return

    if brief.status == "REJECTED":
        st.error(f"### [REJECTED] Evidence Verification Rejected (Status: `{brief.status}`)")
        for err in brief.verification_errors:
            st.error(f"- {err}")
        return

    target = brief.target_pr
    if not target:
        st.error("No pull request metadata available in brief.")
        return

    # Header Card
    st.success("### [VERIFIED] Deterministic Evidence Gate Passed")
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(f"#### [{target.title}]({target.url})")
        st.markdown(f"**Author:** [{target.author}]({target.author_url}) | **Repository:** `FalkorDB/FalkorDB`")
    with col2:
        st.metric("Status", target.state.upper())
    with col3:
        st.metric("Files Touched", len(brief.changed_files))

    # Top Metric Banner
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Linked Issues", len(brief.linked_issues))
    m2.metric("Eligible Reviewers", len(brief.historical_reviewers))
    m3.metric("Ownership Drift Files", len(brief.ownership_drift))
    m4.metric("Co-Change Signals", len(brief.co_change_signals))

    st.markdown("---")

    # Tabbed Display
    tab_brief, tab_ownership, tab_reviewers, tab_audit = st.tabs([
        "Executive Brief",
        "Ownership Drift",
        "Reviewers & Co-Changes",
        "Auditable Evidence Paths",
    ])

    with tab_brief:
        st.subheader("1. Verified Facts")
        if brief.verified_facts:
            for fact in brief.verified_facts:
                st.markdown(f"- {fact}")
        else:
            st.caption("No explicit facts recorded.")

        st.subheader("2. Evidence-Supported Inferences")
        if brief.evidence_inferences:
            for inf in brief.evidence_inferences:
                st.markdown(f"- {inf}")
        else:
            st.caption("No inferences generated.")

        st.subheader("3. Unresolved Questions")
        if brief.unresolved_questions:
            for q in brief.unresolved_questions:
                st.markdown(f"- {q}")
        else:
            st.caption("No unresolved questions.")

        st.subheader("4. Resolved Issues Tracing")
        if brief.linked_issues:
            for iss in brief.linked_issues:
                st.markdown(
                    f"- **[Issue #{iss.number}: {iss.title}]({iss.url})**  \n"
                    f"  *Reporter:* [{iss.reporter}]({iss.reporter_url})  \n"
                    f"  *Evidence:* `{iss.resolution_evidence}`"
                )
        else:
            st.info("No linked issues were closed by this pull request.")

    with tab_ownership:
        st.subheader("Ownership Discrepancy & Drift Analysis")
        st.caption(
            "Compares declared `CODEOWNERS` rules against observed historical maintainer and reviewer activity."
        )

        if brief.ownership_drift:
            for drift in brief.ownership_drift:
                risk_color = (
                    "red" if drift.risk_level == "HIGH" else
                    "orange" if drift.risk_level == "MEDIUM" else "green"
                )
                with st.expander(f"File: {drift.file_path} - Risk: [{drift.risk_level}] (Drift: {drift.drift_score:.2f})", expanded=True):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.markdown(f"**Discrepancy:** `{drift.discrepancy_category}`")
                    col_b.markdown(f"**Bus Factor:** `{drift.bus_factor}`")
                    col_c.markdown(f"**Observed Maintainers:** {', '.join(drift.observed_human_reviewers) or 'None'}")
                    st.markdown(f"*{drift.finding}*")
        else:
            st.info("No ownership discrepancy detected for files modified in this pull request.")

    with tab_reviewers:
        st.subheader("Historical Domain Reviewers")
        st.caption("Target PR is strictly excluded from historical evidence counts per anti-circularity verification rule.")

        if brief.historical_reviewers:
            rev_data = []
            for r in brief.historical_reviewers:
                rev_type = "Bot" if r.is_bot else "Human"
                evidence_links = ", ".join(f"[PR #{u.split('/')[-1]}]({u})" for u in r.evidence_pr_urls[:3])
                rev_data.append({
                    "Reviewer": f"[{r.login}]({r.url})",
                    "Type": rev_type,
                    "Prior File Touches": r.prior_touches,
                    "Sample Precedent PRs": evidence_links,
                })
            st.markdown(
                "| Reviewer | Type | Prior Touches | Sample Precedent PRs |\n|---|---|---|---|\n" +
                "\n".join(f"| {d['Reviewer']} | {d['Type']} | {d['Prior File Touches']} | {d['Sample Precedent PRs']} |" for d in rev_data)
            )
        else:
            st.info("No historical reviewer precedence recorded for touched modules.")

        st.subheader("Co-Change Risk Signals")
        if brief.co_change_signals:
            for c in brief.co_change_signals:
                prs = ", ".join(f"[PR #{u.split('/')[-1]}]({u})" for u in c.evidence_pr_urls[:2])
                st.markdown(f"- `{c.primary_file}` co-changed with `{c.co_changed_file}` **{c.co_change_count}x** across: {prs}")
        else:
            st.info("No recurring file co-change precedents found in graph.")

    with tab_audit:
        st.subheader("Auditable Evidence Sources & Relationships")
        st.caption(
            "Every factual assertion terminates in an authentic, clickable GitHub URL and FalkorDB graph entity."
        )

        if brief.evidence_sources:
            for idx, ev in enumerate(brief.evidence_sources, 1):
                st.markdown(f"**{idx}. [{ev.entity_type} {ev.entity_id}]({ev.url})**")
                st.caption(f"Details: {ev.description}")
        else:
            st.info("No external evidence references recorded.")


def main() -> None:
    """Main Streamlit execution routine."""
    client = get_db_client()
    orchestrator = get_orchestrator()

    render_sidebar(client)

    st.title("RepoBrain — Evidence-Gated PR Brief")
    st.markdown(
        "Deterministic company brain for engineering teams. Investigates pull requests, identifies "
        "ownership drift, traces linked decisions, and verifies claims using **FalkorDB** graph analytics."
    )

    if not client:
        st.error(
            "[ERROR] Database Connection Failed: FalkorDB is not reachable on `localhost:6379`. "
            "Please ensure the FalkorDB Docker container is running."
        )
        return

    # User Input Form
    if "target_input" not in st.session_state:
        st.session_state["target_input"] = "3339"

    with st.form("investigation_form"):
        col_in, col_btn = st.columns([4, 1])
        with col_in:
            target_val = st.text_input(
                "Enter PR Number or GitHub PR URL:",
                value=st.session_state["target_input"],
                placeholder="e.g. 3339 or https://github.com/FalkorDB/FalkorDB/pull/3339",
            )
        with col_btn:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Investigate PR", use_container_width=True)

    if submitted or st.session_state.get("auto_run"):
        st.session_state["auto_run"] = False
        target_val = target_val.strip()
        if not target_val:
            st.warning("Please provide a valid PR number or GitHub pull request URL.")
            return

        with st.spinner(f"Investigating target '{target_val}' against FalkorDB graph..."):
            try:
                brief = orchestrator.investigate(target_val)
                render_brief(brief)
            except Exception as exc:
                st.error(f"Investigation execution error: {exc}")


if __name__ == "__main__":
    main()
