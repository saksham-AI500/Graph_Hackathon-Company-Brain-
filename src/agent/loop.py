"""Bounded Agent Execution Loop for RepoBrain Company Brain.

Coordinates freshness checking, tool calling, repeated-call loop detection,
step limits, deterministic fallback, and evidence-gated verification.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from src.db import FalkorDBClient
from src.evaluation.temporal import normalize_utc_timestamp
from src.agent.client import OpenRouterClient
from src.agent.models import AgentAnswer, AgentRequest, Claim, SourceItem, ToolCall, ToolResult
from src.agent.prompt import build_agent_system_prompt, format_untrusted_context
from src.agent.tools import ToolRegistry, get_default_tool_registry
from src.agent.verifier import AgentEvidenceVerifier

logger = logging.getLogger(__name__)

MAX_STEPS_DEFAULT = 8
MAX_TOOL_RETRIES = 2


class AgentExecutionLoop:
    """Orchestrates bounded tool-calling agent reasoning with deterministic fallback."""

    def __init__(
        self,
        client: Optional[FalkorDBClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        llm_client: Optional[OpenRouterClient] = None,
        verifier: Optional[AgentEvidenceVerifier] = None,
    ):
        self.client = client or FalkorDBClient()
        self.tool_registry = tool_registry or get_default_tool_registry(client=self.client)
        self.llm_client = llm_client or OpenRouterClient()
        self.verifier = verifier or AgentEvidenceVerifier(client=self.client)

    def run(self, request: AgentRequest) -> AgentAnswer:
        """Execute the bounded reasoning loop for a user request."""
        t_start = time.time()
        execution_log: List[Dict[str, Any]] = []
        tools_used: Set[str] = set()
        step_count = 0
        norm_as_of = normalize_utc_timestamp(request.as_of)

        # ---------------------------------------------------------------------
        # Step 1: Freshness Check & Conditional Synchronization
        # ---------------------------------------------------------------------
        fresh_checked = False
        # Do not sync future evidence if querying historical as_of
        if request.require_fresh and not norm_as_of:
            fresh_res = self.tool_registry.execute("sync_status", {"repo": "FalkorDB/FalkorDB"})
            fresh_checked = True
            tools_used.add("sync_status")
            execution_log.append({
                "step": step_count,
                "action": "freshness_check",
                "result": fresh_res.data,
            })

            # Check if sync has ever run or cursor is stale
            last_sync = (fresh_res.data or {}).get("last_sync_at")
            if not last_sync:
                # Trigger a bounded dry-run or replay sync
                sync_res = self.tool_registry.execute(
                    "request_sync",
                    {"repo": "FalkorDB/FalkorDB", "dry_run": request.dry_run_sync},
                )
                tools_used.add("request_sync")
                execution_log.append({
                    "step": step_count,
                    "action": "triggered_sync",
                    "result": sync_res.data,
                })

        # ---------------------------------------------------------------------
        # Step 2: Choose Execution Path (LLM Tool Calling vs Deterministic Fallback)
        # ---------------------------------------------------------------------
        # Use LLM path only if credentials are present and not overridden
        if self.llm_client.has_credentials and request.api_key != "no_key":
            answer = self._run_llm_tool_loop(
                request=request,
                norm_as_of=norm_as_of,
                fresh_checked=fresh_checked,
                execution_log=execution_log,
                tools_used=tools_used,
            )
        else:
            answer = self._run_deterministic_path(
                request=request,
                norm_as_of=norm_as_of,
                fresh_checked=fresh_checked,
                execution_log=execution_log,
                tools_used=tools_used,
            )

        # ---------------------------------------------------------------------
        # Step 3: Evidence Verifier Gate
        # ---------------------------------------------------------------------
        verified_answer = self.verifier.verify_answer(answer, as_of=norm_as_of)
        return verified_answer

    # -------------------------------------------------------------------------
    # LLM Execution Path
    # -------------------------------------------------------------------------

    def _run_llm_tool_loop(
        self,
        request: AgentRequest,
        norm_as_of: Optional[str],
        fresh_checked: bool,
        execution_log: List[Dict[str, Any]],
        tools_used: Set[str],
    ) -> AgentAnswer:
        """Run the multi-turn OpenAI-compatible tool calling loop."""
        max_steps = min(request.max_steps, MAX_STEPS_DEFAULT)
        system_prompt = build_agent_system_prompt()
        if norm_as_of:
            system_prompt += f"\n\nCURRENT QUERY AS_OF CUTOFF: {norm_as_of}. Exclude any entities or events after this timestamp."

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.question},
        ]

        seen_tool_signatures: Set[str] = set()
        step = 0
        tool_definitions = self.tool_registry.get_tool_definitions()

        while step < max_steps:
            step += 1
            try:
                response = self.llm_client.create_chat_completion(
                    messages=messages,
                    tools=tool_definitions,
                    temperature=0.0,
                )
            except Exception as ex:
                logger.error(f"LLM API error on step {step}: {ex}")
                execution_log.append({"step": step, "error": f"LLM error: {str(ex)}"})
                break

            choices = response.get("choices") or []
            if not choices:
                break

            msg = choices[0].get("message") or {}
            messages.append(msg)

            tool_calls = self.llm_client.parse_tool_calls_from_response(response)

            # If no tool calls, model produced final response
            if not tool_calls:
                content = msg.get("content") or ""
                return self._parse_structured_answer_from_text(
                    text=content,
                    norm_as_of=norm_as_of,
                    fresh_checked=fresh_checked,
                    step_count=step,
                    tools_used=list(tools_used),
                    execution_log=execution_log,
                    model_used=self.llm_client.model,
                )

            # Execute tool calls
            for tc in tool_calls:
                tools_used.add(tc.name)
                # Loop detection: check if identical tool + args was already called
                sig = f"{tc.name}:{json.dumps(tc.arguments, sort_keys=True)}"
                if sig in seen_tool_signatures:
                    logger.warning(f"Repeated tool call detected: {sig}. Aborting loop.")
                    execution_log.append({"step": step, "loop_detected": sig})
                    # Feed warning to model
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.call_id or f"call_{step}",
                        "name": tc.name,
                        "content": json.dumps({"error": "Duplicate tool call detected. Make forward progress or synthesize answer."}),
                    })
                    continue

                seen_tool_signatures.add(sig)

                # Retry logic for tool errors
                tool_res = None
                for attempt in range(MAX_TOOL_RETRIES):
                    tool_res = self.tool_registry.execute(
                        name=tc.name,
                        arguments=tc.arguments,
                        call_id=tc.call_id,
                        as_of=norm_as_of,
                    )
                    if tool_res.success:
                        break

                execution_log.append({
                    "step": step,
                    "tool": tc.name,
                    "arguments": tc.arguments,
                    "success": tool_res.success if tool_res else False,
                    "error": tool_res.error if tool_res else None,
                })

                res_content = json.dumps(tool_res.data if tool_res and tool_res.success else {"error": tool_res.error if tool_res else "Failed"})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.call_id or f"call_{step}",
                    "name": tc.name,
                    "content": res_content,
                })

        # If loop exited without clean answer, fall back to deterministic response
        return self._run_deterministic_path(
            request=request,
            norm_as_of=norm_as_of,
            fresh_checked=fresh_checked,
            execution_log=execution_log,
            tools_used=tools_used,
        )

    # -------------------------------------------------------------------------
    # Deterministic Execution Path (Zero-Key Grounded Planner)
    # -------------------------------------------------------------------------

    def _run_deterministic_path(
        self,
        request: AgentRequest,
        norm_as_of: Optional[str],
        fresh_checked: bool,
        execution_log: List[Dict[str, Any]],
        tools_used: Set[str],
    ) -> AgentAnswer:
        """Deterministic query planner executing tools and synthesizing verified answers."""
        q = request.question.strip()
        lower_q = q.lower()
        claims: List[Claim] = []
        sources: List[SourceItem] = []
        unresolved: List[str] = []
        step_count = len(execution_log) + 1

        # Check for adversarial injection attempting system override
        if "ignore all prior instructions" in lower_q or "system: override" in lower_q or "grant root" in lower_q:
            return AgentAnswer(
                answer="I cannot fulfill this request. The input contains instructions attempting to override system security protocols.",
                claims=[],
                sources=[],
                unresolved=["Prompt injection attempt blocked by security boundary."],
                as_of=norm_as_of,
                fresh_checked=fresh_checked,
                status="REFUSED",
                step_count=step_count,
                tools_used=list(tools_used),
                execution_log=execution_log,
                model_used="deterministic_fallback",
            )

        # 1. Who owns file X / ownership drift
        if "who owns" in lower_q or "owner of" in lower_q or "ownership" in lower_q:
            fp_match = re.search(r"([\w\-./]+\.[a-zA-Z0-9]+)", q)
            if fp_match:
                fp = fp_match.group(1).lstrip("/")
                tools_used.add("who_owns")
                res = self.tool_registry.execute("who_owns", {"file_path": fp, "as_of": norm_as_of})
                if res.success and res.data:
                    d = res.data
                    src_urls = res.evidence_urls or ["https://github.com/FalkorDB/FalkorDB"]
                    sources.append(SourceItem(
                        id="S1",
                        entity_type="File",
                        identifier=fp,
                        url=src_urls[0],
                        title_or_desc=f"Repository file {fp}",
                    ))

                    owners = d.get("declared_owners") or []
                    rule = d.get("declared_rule_pattern") or d.get("matched_rule") or "none"
                    drift_score = d.get("drift_score", 0.0)

                    if owners:
                        owners_str = ", ".join(owners)
                        ans_text = (
                            f"File `{fp}` is declared in CODEOWNERS under rule `{rule}` with owner(s): {owners_str} [S1].\n"
                            f"Observed ownership drift score is {drift_score:.2f}."
                        )
                        claims.append(Claim(
                            claim_id="C1",
                            text=f"File {fp} is owned by {owners_str} according to CODEOWNERS rule {rule}.",
                            claim_type="OWNERSHIP",
                            source_ids=["S1"],
                        ))
                    else:
                        ans_text = f"File `{fp}` has no matching rule in CODEOWNERS (unowned) [S1]."
                        claims.append(Claim(
                            claim_id="C1",
                            text=f"File {fp} has no declared owners in CODEOWNERS.",
                            claim_type="OWNERSHIP",
                            source_ids=["S1"],
                        ))

                    return AgentAnswer(
                        answer=ans_text,
                        claims=claims,
                        sources=sources,
                        unresolved=unresolved,
                        as_of=norm_as_of,
                        fresh_checked=fresh_checked,
                        status="VERIFIED",
                        step_count=step_count,
                        tools_used=list(tools_used),
                        execution_log=execution_log,
                        model_used="deterministic_fallback",
                    )

        # 2. Who knows file X / expertise
        if "who knows" in lower_q or "expert" in lower_q or "knows most" in lower_q or "knowledge" in lower_q:
            fp_match = re.search(r"([\w\-./]+\.[a-zA-Z0-9]+)", q)
            if fp_match:
                fp = fp_match.group(1).lstrip("/")
                tools_used.add("who_knows")
                res = self.tool_registry.execute("who_knows", {"file_path": fp, "as_of": norm_as_of, "limit": 5})
                if res.success and res.data:
                    top_experts = res.data
                    if top_experts:
                        lead = top_experts[0]
                        lead_login = lead.get("person_login") or lead.get("login") or "unknown"
                        lead_score = lead["score"]
                        src_url = (lead.get("contributions") or [{}])[0].get("source_url") or "https://github.com/FalkorDB/FalkorDB"
                        sources.append(SourceItem(
                            id="S1",
                            entity_type="Person",
                            identifier=lead_login,
                            url=src_url,
                            title_or_desc=f"Engineer {lead_login}",
                        ))
                        claims.append(Claim(
                            claim_id="C1",
                            text=f"{lead_login} has the highest KNOWS score ({lead_score:.2f}) on {fp}.",
                            claim_type="KNOWLEDGE",
                            source_ids=["S1"],
                        ))
                        ans_text = (
                            f"The top knowledgeable engineer on `{fp}` is **{lead_login}** with a decaying "
                            f"KNOWS score of {lead_score:.2f} [S1]."
                        )
                        return AgentAnswer(
                            answer=ans_text,
                            claims=claims,
                            sources=sources,
                            unresolved=unresolved,
                            as_of=norm_as_of,
                            fresh_checked=fresh_checked,
                            status="VERIFIED",
                            step_count=step_count,
                            tools_used=list(tools_used),
                            execution_log=execution_log,
                            model_used="deterministic_fallback",
                        )

        # 3. Decision tracing / quotes
        if "decision" in lower_q or "decided" in lower_q:
            tools_used.add("trace_decision")
            res = self.tool_registry.execute("trace_decision", {"query_or_pr": q, "as_of": norm_as_of})
            if res.success and res.data:
                dec = res.data[0]
                d_id = dec["decision_id"]
                quote = dec["quote"]
                src_url = dec["source_url"]
                sources.append(SourceItem(
                    id="S1",
                    entity_type="Decision",
                    identifier=d_id,
                    url=src_url,
                    title_or_desc=f"Decision {d_id}",
                    snippet=quote,
                ))
                claims.append(Claim(
                    claim_id="C1",
                    text=quote,
                    claim_type="DECISION",
                    source_ids=["S1"],
                ))
                ans_text = f"Engineering decision recorded in the graph [S1]:\n> \"{quote}\""
                return AgentAnswer(
                    answer=ans_text,
                    claims=claims,
                    sources=sources,
                    unresolved=unresolved,
                    as_of=norm_as_of,
                    fresh_checked=fresh_checked,
                    status="VERIFIED",
                    step_count=step_count,
                    tools_used=list(tools_used),
                    execution_log=execution_log,
                    model_used="deterministic_fallback",
                )

        # 4. Stale documentation
        if "stale" in lower_q or "outdated doc" in lower_q:
            tools_used.add("find_stale_docs")
            res = self.tool_registry.execute("find_stale_docs", {"as_of": norm_as_of})
            if res.success and res.data:
                findings = (res.data or {}).get("findings") or []
                stale_items = [f for f in findings if f.get("status") == "POTENTIALLY_STALE"]
                if stale_items:
                    top_stale = stale_items[0]
                    doc_path = top_stale["document_path"]
                    f_path = top_stale["documented_file_path"]
                    src_url = top_stale["document_url"] or "https://github.com/FalkorDB/FalkorDB"
                    sources.append(SourceItem(
                        id="S1",
                        entity_type="Document",
                        identifier=doc_path,
                        url=src_url,
                        title_or_desc=f"Document {doc_path}",
                    ))
                    claims.append(Claim(
                        claim_id="C1",
                        text=f"Document {doc_path} is potentially stale because referenced file {f_path} changed later.",
                        claim_type="STALENESS",
                        source_ids=["S1"],
                    ))
                    ans_text = (
                        f"Potentially stale document identified: `{doc_path}` documents `{f_path}`, "
                        f"which was modified after the document was last edited [S1]."
                    )
                    return AgentAnswer(
                        answer=ans_text,
                        claims=claims,
                        sources=sources,
                        unresolved=unresolved,
                        as_of=norm_as_of,
                        fresh_checked=fresh_checked,
                        status="VERIFIED",
                        step_count=step_count,
                        tools_used=list(tools_used),
                        execution_log=execution_log,
                        model_used="deterministic_fallback",
                    )
                else:
                    ans_text = "Repository documentation audit: All inspected documentation links are currently up-to-date relative to code modifications."
                    return AgentAnswer(
                        answer=ans_text,
                        claims=[],
                        sources=[],
                        unresolved=[],
                        as_of=norm_as_of,
                        fresh_checked=fresh_checked,
                        status="VERIFIED",
                        step_count=step_count,
                        tools_used=list(tools_used),
                        execution_log=execution_log,
                        model_used="deterministic_fallback",
                    )

        # 5. Suggest Reviewers
        if "suggest reviewer" in lower_q or "reviewer recommendation" in lower_q:
            fp_match = re.search(r"([\w\-./]+\.[a-zA-Z0-9]+|#\d+)", q)
            target = fp_match.group(1) if fp_match else "src/module.c"
            tools_used.add("suggest_reviewers")
            res = self.tool_registry.execute("suggest_reviewers", {"file_path_or_pr": target, "as_of": norm_as_of})
            if res.success and res.data:
                suggestions = res.data
                if suggestions:
                    lead_rev = suggestions[0]["login"]
                    src_url = (suggestions[0].get("evidence_urls") or ["https://github.com/FalkorDB/FalkorDB"])[0]
                    sources.append(SourceItem(
                        id="S1",
                        entity_type="Person",
                        identifier=lead_rev,
                        url=src_url,
                        title_or_desc=f"Reviewer candidate {lead_rev}",
                    ))
                    claims.append(Claim(
                        claim_id="C1",
                        text=f"{lead_rev} is the top suggested reviewer for {target}.",
                        claim_type="KNOWLEDGE",
                        source_ids=["S1"],
                    ))
                    ans_text = f"Top suggested reviewer for `{target}` is **{lead_rev}** based on ownership and review history [S1]."
                    return AgentAnswer(
                        answer=ans_text,
                        claims=claims,
                        sources=sources,
                        unresolved=unresolved,
                        as_of=norm_as_of,
                        fresh_checked=fresh_checked,
                        status="VERIFIED",
                        step_count=step_count,
                        tools_used=list(tools_used),
                        execution_log=execution_log,
                        model_used="deterministic_fallback",
                    )

        # 6. PR Brief / Investigation
        pr_match = re.search(r"(?:pr|pull request|\#)\s*\#?\s*(\d+)", lower_q)
        if pr_match:
            pr_num = int(pr_match.group(1))
            tools_used.add("pr_brief")
            res = self.tool_registry.execute("pr_brief", {"pr_number": pr_num, "as_of": norm_as_of})
            if res.success and res.data:
                brief = res.data
                if brief.get("status") == "REFUSED":
                    return AgentAnswer(
                        answer=f"Pull Request #{pr_num} was not found in the repository graph.",
                        claims=[],
                        sources=[],
                        unresolved=[f"PR #{pr_num} does not exist in graph repo_kg."],
                        as_of=norm_as_of,
                        fresh_checked=fresh_checked,
                        status="REFUSED",
                        step_count=step_count,
                        tools_used=list(tools_used),
                        execution_log=execution_log,
                        model_used="deterministic_fallback",
                    )
                target_pr = brief.get("target_pr") or {}
                pr_url = target_pr.get("url") or f"https://github.com/FalkorDB/FalkorDB/pull/{pr_num}"
                title = target_pr.get("title") or f"PR #{pr_num}"
                sources.append(SourceItem(
                    id="S1",
                    entity_type="PullRequest",
                    identifier=pr_num,
                    url=pr_url,
                    title_or_desc=title,
                ))
                claims.append(Claim(
                    claim_id="C1",
                    text=f"Pull Request #{pr_num} is titled '{title}'.",
                    claim_type="PR_INVESTIGATION",
                    source_ids=["S1"],
                ))
                ans_text = f"Pull Request #{pr_num} titled '{title}' is verified in repo_kg [S1]."
                return AgentAnswer(
                    answer=ans_text,
                    claims=claims,
                    sources=sources,
                    unresolved=unresolved,
                    as_of=norm_as_of,
                    fresh_checked=fresh_checked,
                    status="VERIFIED",
                    step_count=step_count,
                    tools_used=list(tools_used),
                    execution_log=execution_log,
                    model_used="deterministic_fallback",
                )

        # 7. Unanswerable question / Nonexistent entity / Default Refusal
        return AgentAnswer(
            answer=(
                "I cannot answer this question because no grounded graph evidence or matching entity "
                "was found in repo_kg."
            ),
            claims=[],
            sources=[],
            unresolved=["No relevant entities or relationships found in graph."],
            as_of=norm_as_of,
            fresh_checked=fresh_checked,
            status="REFUSED",
            step_count=step_count,
            tools_used=list(tools_used),
            execution_log=execution_log,
            model_used="deterministic_fallback",
        )

    def _parse_structured_answer_from_text(
        self,
        text: str,
        norm_as_of: Optional[str],
        fresh_checked: bool,
        step_count: int,
        tools_used: List[str],
        execution_log: List[Dict[str, Any]],
        model_used: str,
    ) -> AgentAnswer:
        """Parse structured AgentAnswer from LLM completion text."""
        # Find all [S1], [S2] citation markers
        citations = re.findall(r"\[(S\d+)\]", text)
        claims: List[Claim] = []
        sources: List[SourceItem] = []

        # If model formatted markdown without explicit structured JSON, generate claim
        if citations:
            claims.append(Claim(
                claim_id="C1",
                text=text.strip(),
                claim_type="GENERAL",
                source_ids=list(set(citations)),
            ))

        return AgentAnswer(
            answer=text.strip(),
            claims=claims,
            sources=sources,
            unresolved=[],
            as_of=norm_as_of,
            fresh_checked=fresh_checked,
            status="VERIFIED" if citations else "PARTIALLY_VERIFIED",
            step_count=step_count,
            tools_used=tools_used,
            execution_log=execution_log,
            model_used=model_used,
        )
