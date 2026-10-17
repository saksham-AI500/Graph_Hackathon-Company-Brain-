"""RepoBrain — PR Brief & Investigation Tab.

Preserves the deterministic PR investigation workflow, ownership discrepancy analysis,
PageRank reviewer centrality, and shortest-path visual evidence paths.
"""

from typing import Any, Dict, Optional
import streamlit as st

from src.db import FalkorDBClient
from src.investigation.orchestrator import PROrchestrator
from src.investigation.models import PRBrief


def render_brief(brief: PRBrief, client: Optional[FalkorDBClient] = None) -> None:
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

        # FalkorDB Native Graph Algorithm: Maintainer Centrality
        st.subheader("FalkorDB Graph Algorithm: Maintainer Review Centrality")
        st.caption("Calculated via FalkorDB `CALL algo.pageRank(null, 'REVIEWED')` projected onto maintainers. Excludes automated bot accounts by default.")
        if client:
            from src.graph.algorithms import run_maintainer_pagerank
            include_bots = st.checkbox("Include automated bot accounts in PageRank", value=False, key="pagerank_include_bots")
            ranks = run_maintainer_pagerank(client, limit=6, include_bots=include_bots)
            if ranks:
                rank_rows = "\n".join(
                    f"| [{r['login']}]({r['url']}) | {'Bot' if r.get('is_bot') else 'Human'} | `{r['score']}` | {r.get('review_count', '-')} | {'High Scrutiny Reviewer' if r['score'] > 0.03 else 'Contributor Reviewer'} |"
                    for r in ranks
                )
                st.markdown(
                    "| Maintainer | Type | PageRank Score | Reviews Conducted | Interpretation |\n|---|---|---|---|---|\n" + rank_rows
                )

    with tab_audit:
        st.subheader("FalkorDB Visual Evidence Paths")
        st.caption(
            "Every claim is backed by a verified graph path computed via FalkorDB `shortestPath(...)`."
        )

        if client and brief.target_pr:
            from src.graph.algorithms import find_explanation_path
            t_num = brief.target_pr.number

            # 1. Path to Linked Issues
            for iss in brief.linked_issues:
                path = find_explanation_path(client, t_num, iss.number)
                if path:
                    with st.expander(f"Evidence Path to Issue #{iss.number}: {path['readable_summary']}", expanded=True):
                        for h in path["hops"]:
                            src_md = f"[{h['source']}]({h['source_url']})" if h.get("source_url") else h["source"]
                            dst_md = f"[{h['target']}]({h['target_url']})" if h.get("target_url") else h["target"]
                            st.markdown(f"- **Step {h['step']}:** {src_md} &rarr; `{h['relationship']}` &rarr; {dst_md}")

            # 2. Path to Historical Reviewers
            for rev in brief.historical_reviewers[:2]:
                path = find_explanation_path(client, t_num, rev.login)
                if path:
                    with st.expander(f"Evidence Path to Reviewer '{rev.login}': {path['readable_summary']}"):
                        for h in path["hops"]:
                            src_md = f"[{h['source']}]({h['source_url']})" if h.get("source_url") else h["source"]
                            dst_md = f"[{h['target']}]({h['target_url']})" if h.get("target_url") else h["target"]
                            st.markdown(f"- **Step {h['step']}:** {src_md} &rarr; `{h['relationship']}` &rarr; {dst_md}")

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


def render_pr_brief_tab(client: Optional[FalkorDBClient], config: Dict[str, Any]) -> None:
    """Render the PR Investigation form and brief."""
    st.subheader("📋 Pull Request Investigation & Brief")
    st.markdown(
        "Deterministic PR investigation interface with ownership discrepancy, decision tracing, "
        "and FalkorDB shortest-path evidence verification."
    )

    if not client:
        st.error(
            "[ERROR] Database Connection Failed: FalkorDB is not reachable on `localhost:6379`. "
            "Please ensure the FalkorDB Docker container is running."
        )
        return

    orchestrator = PROrchestrator(client=client)

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
                render_brief(brief, client=client)
            except Exception as exc:
                st.error(f"Investigation execution error: {exc}")
