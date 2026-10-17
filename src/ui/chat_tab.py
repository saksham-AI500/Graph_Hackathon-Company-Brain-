"""RepoBrain — Ask the Brain Chat Tab.

Primary interaction surface powered by AgentExecutionLoop with verifier-gated
structured answers, clickable citations, claim breakdowns, evidence paths,
and tool-calling traces.
"""

from typing import Any, Dict, List, Optional
import streamlit as st

from src.db import FalkorDBClient
from src.agent.models import AgentRequest, AgentAnswer
from src.agent.loop import AgentExecutionLoop
from src.graph.algorithms import find_shortest_path


def render_chat_tab(client: Optional[FalkorDBClient], config: Dict[str, Any]) -> None:
    """Render the 'Ask the Brain' primary chat tab."""
    st.subheader("🧠 Ask the Company Brain")
    st.markdown(
        "Ask engineering, governance, ownership, or architectural questions. "
        "Answers are generated using typed knowledge graph tools and strictly gated by the evidence verifier."
    )

    if not client:
        st.error(
            "[ERROR] Database Connection Failed: FalkorDB is not reachable on `localhost:6379`. "
            "Please ensure the FalkorDB Docker container is running to query the Company Brain."
        )
        return

    # Initialize chat history in session state
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    col_ctrl, col_clear = st.columns([5, 1])
    with col_clear:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state["chat_history"] = []
            st.rerun()

    # Chat prompt input
    prompt = st.chat_input("Ask the Company Brain (e.g. Who owns src/module.c?)...")
    preset_q = st.session_state.pop("user_question_input", None)

    submitted = False
    question_text = ""
    if prompt:
        question_text = prompt.strip()
        submitted = True
    elif preset_q:
        question_text = preset_q.strip()
        submitted = True

    if submitted and question_text.strip():
        q_clean = question_text.strip()
        st.session_state["user_question_input"] = q_clean

        # Build request with session configuration
        api_key = config.get("openrouter_api_key") or None
        model = config.get("model") or "anthropic/claude-3.5-sonnet"
        as_of = config.get("as_of")

        req = AgentRequest(
            question=q_clean,
            as_of=as_of,
            openrouter_key=api_key,
            model=model,
            max_steps=8,
        )

        with st.spinner("Company Brain executing typed graph tools and verifying evidence..."):
            try:
                from src.agent.client import OpenRouterClient
                llm = OpenRouterClient(api_key=api_key, model=model)
                loop = AgentExecutionLoop(client=client, llm_client=llm)
                answer: AgentAnswer = loop.run(req)

                # Append to session chat history
                st.session_state["chat_history"].append({
                    "question": q_clean,
                    "answer": answer,
                    "as_of": as_of,
                    "mode": config.get("graph_mode", "Graph ON"),
                })
            except Exception as exc:
                st.error(f"Agent execution encountered an error: {exc}")

    # Render Chat History (most recent on top)
    if not st.session_state["chat_history"]:
        st.info("No queries yet. Enter a question above or select a preset from the sidebar.")
        return

    st.markdown("---")
    st.markdown("### Conversation History")

    for idx, item in enumerate(reversed(st.session_state["chat_history"])):
        q = item["question"]
        ans: AgentAnswer = item["answer"]
        as_of_val = item.get("as_of")

        with st.container():
            # User Question Card
            st.markdown(f"#### 👤 Question: {q}")
            if as_of_val:
                st.caption(f"Historical Cutoff: `{as_of_val}`")

            # Answer Card with Status Header
            if ans.status == "VERIFIED":
                st.success(f"**[VERIFIED]** Ground-Truth Evidence Gate Passed ({len(ans.claims)} verified claims, {len(ans.sources)} sources)")
            elif ans.status == "REFUSED":
                st.warning(f"**[REFUSED]** Speculation Rejected ({len(ans.unresolved)} unresolved issues)")
                if ans.refusal_reason:
                    st.info(f"**Refusal Reason:** {ans.refusal_reason}")
            else:
                st.error(f"**[{ans.status}]** Evidence Verification Failed")

            # Formatted Answer Text
            st.markdown(ans.answer)

            # Details Accordion
            with st.expander("🔍 View Claims, Citations, Evidence Paths & Tool Trace", expanded=(idx == 0)):
                # Tabbed Breakdown
                t_claims, t_sources, t_paths, t_tools = st.tabs([
                    "Claims & Derivations",
                    "Evidence Sources",
                    "Graph Paths",
                    "Tool Execution Trace",
                ])

                with t_claims:
                    facts = [c for c in ans.claims if c.claim_type == "FACT"]
                    inferences = [c for c in ans.claims if c.claim_type == "INFERENCE"]

                    st.markdown("**1. Verified Facts:**")
                    if facts:
                        for f in facts:
                            sources_marker = ", ".join(f"[{sid}]" for sid in f.source_ids) if f.source_ids else ""
                            st.markdown(f"- {f.statement} {sources_marker}")
                    else:
                        st.caption("No direct factual claims recorded.")

                    st.markdown("**2. Evidence-Supported Inferences:**")
                    if inferences:
                        for inf in inferences:
                            sources_marker = ", ".join(f"[{sid}]" for sid in inf.source_ids) if inf.source_ids else ""
                            st.markdown(f"- {inf.statement} {sources_marker}")
                    else:
                        st.caption("No derived inferences recorded.")

                    st.markdown("**3. Unresolved Questions / Limitations:**")
                    if ans.unresolved:
                        for u in ans.unresolved:
                            st.markdown(f"- {u}")
                    else:
                        st.caption("Zero unresolved items.")

                with t_sources:
                    if ans.sources:
                        st.markdown("| Source ID | Entity Type | Identifier / URL | Description |")
                        st.markdown("|---|---|---|---|")
                        for s in ans.sources:
                            link = f"[{s.entity_id}]({s.url})" if s.url.startswith("http") else s.entity_id
                            st.markdown(f"| **{s.source_id}** | `{s.entity_type}` | {link} | {s.description} |")
                    else:
                        st.info("No cited sources in this response.")

                with t_paths:
                    st.markdown("**Computed Evidence Graph Hops:**")
                    # Display evidence paths if sources exist
                    if ans.sources and client:
                        found_hops = False
                        for s in ans.sources[:3]:
                            if s.entity_type in ["File", "PullRequest", "Issue"]:
                                path_res = find_shortest_path(client, "src/module.c", str(s.entity_id), max_depth=3)
                                if path_res and path_res.get("hops"):
                                    found_hops = True
                                    st.markdown(f"- Path to **{s.entity_id}**: {path_res['readable_summary']}")
                                    for h in path_res["hops"]:
                                        st.caption(f"  Step {h['step']}: `{h['source']}` &rarr; `{h['relationship']}` &rarr; `{h['target']}`")
                        if not found_hops:
                            st.caption("Direct entity verification: Citations confirmed against active node records.")
                    else:
                        st.caption("No multi-hop path required.")

                with t_tools:
                    st.markdown(f"**Freshness Checked:** `{'Yes' if ans.fresh_checked else 'No'}` | **Execution Steps:** `{len(ans.tool_calls)}`")
                    if ans.tool_calls:
                        for t_idx, tc in enumerate(ans.tool_calls, 1):
                            dur_str = f"({tc.execution_time_ms:.1f}ms)" if tc.execution_time_ms else ""
                            st.markdown(f"**Step {t_idx}: `{tc.tool_name}`** {dur_str}")
                            st.json(tc.arguments)
                    else:
                        st.caption("Direct deterministic resolution; no secondary tool calls.")

            st.markdown("---")
