"""RepoBrain — Compare Tab.

Implements fair 3-way evaluation comparing:
1. Graph ON (Company Brain Agent with typed graph tools and evidence verifier)
2. Plain Retrieval (TF-IDF vector baseline over raw repository text corpus)
3. Graph OFF (Model alone with zero repository context and zero graph tools)
"""

import time
from typing import Any, Dict, Optional
import streamlit as st

from src.db import FalkorDBClient
from src.agent.models import AgentRequest, AgentAnswer
from src.agent.loop import AgentExecutionLoop
from src.evaluation.vector_baseline import LocalVectorBaseline


def render_compare_tab(client: Optional[FalkorDBClient], config: Dict[str, Any]) -> None:
    """Render fair 3-way comparison interface."""
    st.subheader("⚖️ Fair 3-Way Architecture Comparison")
    st.markdown(
        "Demonstrates the measurable difference between **Graph ON** (Company Brain), "
        "**Plain Retrieval** (TF-IDF Vector Baseline), and **Graph OFF** (Direct LLM without context)."
    )

    if not client:
        st.error("[OFFLINE] Cannot run comparison: FalkorDB is offline on `localhost:6379`.")
        return

    # Presets & Input
    compare_presets = [
        "Who owns src/module.c?",
        "Who knows about src/module.c?",
        "What was decided about graph limits?",
        "Are there any stale documentation files?",
        "What is the brief for PR #3339?",
        "Suggest reviewers for PR #3339",
        "Who owns nonexistent/fake_file.py?",
    ]

    selected_q = st.selectbox(
        "Choose a benchmark question or type custom question:",
        options=compare_presets + ["Custom..."],
        index=0,
    )

    if selected_q == "Custom...":
        q_text = st.text_input("Custom question:", value="Who owns src/module.c?").strip()
    else:
        q_text = selected_q

    run_comp = st.button("🚀 Run Fair 3-Way Comparison", use_container_width=True)

    if run_comp and q_text:
        api_key = config.get("openrouter_api_key") or None
        model = config.get("model") or "anthropic/claude-3.5-sonnet"
        as_of = config.get("as_of")

        col_on, col_vec, col_off = st.columns(3)

        # ------------------------------------------------------------------
        # Column 1: Graph ON (Company Brain Agent)
        # ------------------------------------------------------------------
        with col_on:
            st.markdown("### 🧠 1. Graph ON (Company Brain)")
            st.caption("Typed graph tools, freshness check, and ground-truth evidence verifier gate.")

            t0 = time.perf_counter()
            try:
                from src.agent.client import OpenRouterClient
                llm = OpenRouterClient(api_key=api_key, model=model)
                loop = AgentExecutionLoop(client=client, llm_client=llm)
                req = AgentRequest(
                    question=q_text,
                    as_of=as_of,
                    openrouter_key=api_key,
                    model=model,
                )
                answer_on: AgentAnswer = loop.run(req)
                lat_on = (time.perf_counter() - t0) * 1000

                # Status Badge
                if answer_on.status == "VERIFIED":
                    st.success(f"**[VERIFIED]** Evidence Gate Passed ({lat_on:.1f}ms)")
                elif answer_on.status == "REFUSED":
                    st.warning(f"**[REFUSED]** Speculation Rejected ({lat_on:.1f}ms)")
                else:
                    st.error(f"**[{answer_on.status}]** Rejected ({lat_on:.1f}ms)")

                st.markdown(f"**Engine:** `{'Live LLM' if api_key else 'Deterministic Fallback'}`")
                st.markdown(answer_on.answer)

                st.markdown("---")
                st.markdown(f"**Verified Sources ({len(answer_on.sources)}):**")
                for s in answer_on.sources:
                    st.caption(f"- [{s.source_id}] {s.entity_type} `{s.entity_id}`")

                st.markdown(f"**Claims:** `{len(answer_on.claims)}` verified | **Unresolved:** `{len(answer_on.unresolved)}`")

            except Exception as exc:
                st.error(f"Graph ON error: {exc}")

        # ------------------------------------------------------------------
        # Column 2: Plain Retrieval (TF-IDF Vector Baseline)
        # ------------------------------------------------------------------
        with col_vec:
            st.markdown("### 📄 2. Plain Retrieval (TF-IDF)")
            st.caption("Keyword & TF-IDF similarity over raw text corpus without graph topology.")

            t0 = time.perf_counter()
            try:
                vector_engine = LocalVectorBaseline()
                # Run search over corpus
                scored_docs = vector_engine.search(q_text, cutoff_timestamp=as_of, top_k=3)
                lat_vec = (time.perf_counter() - t0) * 1000

                st.info(f"**[UNVERIFIED]** Text-Search Retrieval ({lat_vec:.1f}ms)")
                st.markdown(f"**Engine:** `LocalVectorBaseline (TF-IDF)`")

                if scored_docs:
                    top_doc, top_score = scored_docs[0]
                    st.markdown(
                        f"**Top Matched Document:** [{top_doc.doc_id}]({top_doc.url})  \n"
                        f"*Type:* `{top_doc.doc_type}` | *Cosine Score:* `{top_score:.3f}`  \n\n"
                        f"**Text Snippet:** {top_doc.body[:220]}..."
                    )
                else:
                    st.caption("No relevant documents retrieved above similarity threshold.")

                st.markdown("---")
                st.markdown(f"**Retrieved Sources ({len(scored_docs)}):**")
                for d, score in scored_docs:
                    st.caption(f"- [{d.doc_id}] {d.title[:35]}... (score: {score:.2f})")

                st.caption("⚠️ Limitation: Lacks entity relationships, CODEOWNERS precedence, and verifier gating.")

            except Exception as exc:
                st.error(f"Vector search error: {exc}")

        # ------------------------------------------------------------------
        # Column 3: Graph OFF (Model Alone / Direct Prompt)
        # ------------------------------------------------------------------
        with col_off:
            st.markdown("### ❌ 3. Graph OFF (Model Alone)")
            st.caption("Direct LLM response with zero repository context and zero graph tools.")

            t0 = time.perf_counter()
            if api_key:
                try:
                    from src.agent.client import OpenRouterClient
                    client_llm = OpenRouterClient(api_key=api_key, model=model)
                    messages = [
                        {"role": "system", "content": "You are a software assistant. Answer the user question based only on your pre-trained knowledge without access to external repository databases."},
                        {"role": "user", "content": q_text},
                    ]
                    resp = client_llm.chat(messages=messages, temperature=0.0)
                    lat_off = (time.perf_counter() - t0) * 1000
                    st.warning(f"**[UNVERIFIED]** Zero-Context Model Response ({lat_off:.1f}ms)")
                    st.markdown(f"**Engine:** `Live LLM ({model})`")
                    st.markdown(resp.get("content", "No response."))
                    st.caption("⚠️ Warning: Hallucination risk is high without repository grounding.")
                except Exception as exc:
                    st.error(f"Live LLM error: {exc}")
            else:
                lat_off = (time.perf_counter() - t0) * 1000
                st.info(f"**[UNAVAILABLE]** No OpenRouter API Key ({lat_off:.1f}ms)")
                st.markdown("**Engine:** `Direct LLM Unavailable`")
                st.markdown(
                    "> *No OPENROUTER_API_KEY provided.* In accordance with benchmark integrity rules, "
                    "Graph OFF responses are not fabricated when credentials are unavailable. "
                    "Provide an API key in the sidebar to test raw model performance."
                )
                st.caption("Honest Evaluation Rule: Never simulate or fabricate live API responses.")
