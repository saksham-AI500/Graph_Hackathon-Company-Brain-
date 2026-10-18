"""Pydantic and data models for the RepoBrain Company Brain agent."""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class ToolCall(BaseModel):
    """Structured representation of a tool call invocation."""
    name: str = Field(description="Name of the allowlisted tool")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Typed arguments for the tool")
    call_id: Optional[str] = Field(default=None, description="Unique call ID for request tracing")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Tool name cannot be empty")
        return clean


class ToolResult(BaseModel):
    """Structured output returned by an executed tool."""
    name: str
    call_id: Optional[str] = None
    success: bool
    data: Any = None
    error: Optional[str] = None
    evidence_urls: List[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "call_id": self.call_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "evidence_urls": self.evidence_urls,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }


class SourceItem(BaseModel):
    """An auditable, graph-grounded source evidence record."""
    id: str = Field(description="Citation identifier, e.g., 'S1', 'S2'")
    entity_type: str = Field(description="Graph label or entity type, e.g., 'PullRequest', 'File', 'Decision'")
    identifier: Union[str, int] = Field(description="Unique identity key, e.g., PR number or file path")
    url: str = Field(description="Public GitHub or documentation URL")
    title_or_desc: Optional[str] = None
    snippet: Optional[str] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    span_text: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    source_id: Optional[str] = None
    entity_id: Optional[str] = None
    description: Optional[str] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        clean = v.strip().upper()
        if not (clean.startswith("S") and len(clean) >= 2):
            raise ValueError(f"Source ID must follow 'S1', 'S2' format, got '{v}'")
        return clean

    def model_post_init(self, __context: Any) -> None:
        if not self.source_id:
            self.source_id = self.id
        if not self.entity_id:
            self.entity_id = str(self.identifier)
        if not self.description:
            self.description = self.title_or_desc or ""
        if not self.span_text and self.snippet:
            self.span_text = self.snippet

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "identifier": self.identifier,
            "url": self.url,
            "title_or_desc": self.title_or_desc,
            "snippet": self.snippet,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "span_text": self.span_text,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "source_id": self.source_id,
            "entity_id": self.entity_id,
            "description": self.description,
        }


class Claim(BaseModel):
    """A discrete verifiable factual assertion derived from tool evidence."""
    claim_id: str = Field(description="Unique claim identifier, e.g., 'C1', 'C2'")
    text: str = Field(description="The factual proposition")
    claim_type: str = Field(
        default="GENERAL",
        description="Category: 'OWNERSHIP', 'DECISION', 'KNOWLEDGE', 'STALENESS', 'PR_INVESTIGATION', 'GENERAL'",
    )
    source_ids: List[str] = Field(default_factory=list, description="Associated source item IDs, e.g. ['S1']")
    verified: bool = False
    unresolved_reason: Optional[str] = None
    statement: Optional[str] = None
    verification_path: Optional[str] = None  # "structured" or "nli_prose"
    score: Optional[float] = None
    post_hoc: bool = False
    supporting_span: Optional[str] = None
    citation_correction: Optional[Dict[str, Any]] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.statement:
            self.statement = self.text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "claim_type": self.claim_type,
            "source_ids": self.source_ids,
            "verified": self.verified,
            "unresolved_reason": self.unresolved_reason,
            "statement": self.statement,
            "verification_path": self.verification_path,
            "score": self.score,
            "post_hoc": self.post_hoc,
            "supporting_span": self.supporting_span,
            "citation_correction": self.citation_correction,
        }


class RankingItem(BaseModel):
    """Reviewer recommendation candidate ranking entry."""
    rank: int = Field(description="1-based rank position")
    login: str = Field(description="GitHub username / login")
    score: float = Field(description="Composite expertise score")
    reasons: List[str] = Field(default_factory=list, description="Evidence-backed reasons for recommendation")
    source_ids: List[str] = Field(default_factory=list, description="Citing source identifiers, e.g. ['S1']")
    tied: bool = Field(default=False, description="Whether candidate shares identical score with adjacent rank")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "login": self.login,
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "source_ids": self.source_ids,
            "tied": self.tied,
        }


class ExcludedItem(BaseModel):
    """Excluded reviewer candidate record."""
    login: str = Field(description="Candidate username / login")
    reason: str = Field(description="Exclusion reason, e.g. departed employee, bot account")
    end_date: Optional[str] = Field(default=None, description="Departure or inactive cutoff date if applicable")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "login": self.login,
            "reason": self.reason,
            "end_date": self.end_date,
        }


class AgentRequest(BaseModel):
    """Validated input question and parameters for the Company Brain agent."""
    question: str
    as_of: Optional[str] = None
    max_steps: int = Field(default=8, ge=1, le=12)
    model: Optional[str] = None
    api_key: Optional[str] = None
    openrouter_key: Optional[str] = None
    mode: str = Field(default="graph_on", description="'graph_on' or 'graph_off'")
    previous_answer: Optional[str] = Field(default=None, description="Previous answer text for computing what_changed diff")
    require_fresh: bool = True
    dry_run_sync: bool = True

    def model_post_init(self, __context: Any) -> None:
        if not self.api_key and self.openrouter_key:
            self.api_key = self.openrouter_key
        elif not self.openrouter_key and self.api_key:
            self.openrouter_key = self.api_key

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Question cannot be empty or whitespace only.")
        return clean


class AgentAnswer(BaseModel):
    """Verified, structured response from the Company Brain agent adhering to AGENT_BRIEF schema."""
    answer: str = Field(description="Markdown explanation with [S1], [S2] source citations")
    claims: List[Claim] = Field(default_factory=list, description="Itemized factual claims")
    sources: List[SourceItem] = Field(default_factory=list, description="Itemized supporting evidence sources")
    unresolved: List[str] = Field(default_factory=list, description="Questions or gaps that could not be resolved")
    as_of: Optional[str] = None
    fresh_checked: bool = True
    status: str = Field(default="VERIFIED", description="'VERIFIED', 'PARTIALLY_VERIFIED', 'ANSWERED_UNCERTAIN', or 'REFUSED'")
    step_count: int = 0
    tools_used: List[str] = Field(default_factory=list)
    execution_log: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    model_used: str = "deterministic_fallback"

    context: str = ""
    ranking: List[Union[RankingItem, Dict[str, Any]]] = Field(default_factory=list)
    reasoning: str = ""
    excluded: List[Union[ExcludedItem, Dict[str, Any]]] = Field(default_factory=list)
    mode: str = "graph_on"
    synced_at: Optional[str] = None
    model: Optional[str] = None
    verifier: Dict[str, Any] = Field(default_factory=lambda: {"claims_total": 0, "claims_passed": 0, "sources_valid": 0, "sources_total": 0})
    what_changed: Optional[Dict[str, Any]] = None

    refusal_reason: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.tool_calls and self.execution_log:
            self.tool_calls = self.execution_log
        elif not self.execution_log and self.tool_calls:
            self.execution_log = self.tool_calls
        if not self.model or self.model == "deepseek/deepseek-chat":
            if self.model_used and self.model_used != "deterministic_fallback":
                self.model = self.model_used
            else:
                self.model = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")
        if self.refusal_reason is None and self.status == "REFUSED":
            if self.unresolved:
                self.refusal_reason = "; ".join(self.unresolved)
            else:
                self.refusal_reason = self.answer

    def to_api_response(self) -> Dict[str, Any]:
        """Convert AgentAnswer into the exact Part 3 Answer Object specified for Track 03 API."""
        claims_fmt = []
        for c in self.claims:
            ctype = c.claim_type.lower() if c.claim_type else "fact"
            if ctype not in ("fact", "inference", "unresolved"):
                ctype = "fact"
            claims_fmt.append({
                "id": c.claim_id,
                "text": c.text,
                "type": ctype,
                "source_ids": c.source_ids,
                "verified": bool(c.verified),
                "verification_path": c.verification_path or "exact_lookup",
            })

        sources_fmt = []
        for s in self.sources:
            sources_fmt.append({
                "id": s.id,
                "entity": str(s.identifier),
                "entity_type": s.entity_type or "Entity",
                "url": s.url,
                "date": s.valid_from or "",
                "quote": s.snippet or "",
            })

        ranking_fmt = []
        for r in self.ranking:
            if isinstance(r, RankingItem):
                ranking_fmt.append(r.to_dict())
            elif isinstance(r, dict):
                ranking_fmt.append({
                    "rank": int(r.get("rank", len(ranking_fmt) + 1)),
                    "login": str(r.get("login", "")),
                    "score": round(float(r.get("score") if r.get("score") is not None else r.get("total_score", 0.0)), 3),
                    "reasons": list(r.get("reasons") or r.get("evidence") or []),
                    "source_ids": list(r.get("source_ids", [])),
                    "tied": bool(r.get("tied", False)),
                })

        excluded_fmt = []
        for e in self.excluded:
            if isinstance(e, ExcludedItem):
                excluded_fmt.append(e.to_dict())
            elif isinstance(e, dict):
                excluded_fmt.append({
                    "login": str(e.get("login", "")),
                    "reason": str(e.get("reason", "")),
                    "end_date": e.get("end_date") or None,
                })

        tool_calls_fmt = []
        for tc in (self.tool_calls or self.execution_log or []):
            if isinstance(tc, dict) and "tool" in tc:
                tool_calls_fmt.append({
                    "tool": tc.get("tool", ""),
                    "args": tc.get("arguments", {}),
                    "result_count": 1 if tc.get("success") else 0,
                    "ms": tc.get("ms", 0),
                })
            elif isinstance(tc, dict) and "action" in tc:
                tool_calls_fmt.append({
                    "tool": tc.get("action", ""),
                    "args": tc.get("details", {}),
                    "result_count": 1,
                    "ms": 0,
                })

        verifier_fmt = dict(self.verifier) if isinstance(self.verifier, dict) else {}
        if "sentence_logs" in verifier_fmt and isinstance(verifier_fmt["sentence_logs"], list):
            clean_logs = []
            for item in verifier_fmt["sentence_logs"]:
                if isinstance(item, dict):
                    clean_item = dict(item)
                    score_val = clean_item.get("score")
                    if score_val is None:
                        clean_item["score"] = 1.0 if clean_item.get("passed") else 0.0
                    else:
                        try:
                            clean_item["score"] = float(score_val)
                        except (ValueError, TypeError):
                            clean_item["score"] = 0.0
                    clean_logs.append(clean_item)
            verifier_fmt["sentence_logs"] = clean_logs

        resp = {
            "answer": self.answer,
            "status": self.status,
            "context": self.context or (f"As of {self.as_of}" if self.as_of else "As of latest synchronized data"),
            "ranking": ranking_fmt,
            "reasoning": self.reasoning,
            "claims": claims_fmt,
            "excluded": excluded_fmt,
            "unresolved": self.unresolved,
            "sources": sources_fmt,
            "mode": self.mode,
            "as_of": self.as_of,
            "synced_at": self.synced_at or "2026-09-30T23:59:59Z",
            "model": self.model or self.model_used or os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash"),
            "tool_calls": tool_calls_fmt,
            "verifier": verifier_fmt,
        }
        if self.what_changed:
            resp["what_changed"] = self.what_changed
        return resp

    def to_dict(self) -> Dict[str, Any]:
        d = self.to_api_response()
        d["step_count"] = self.step_count
        d["tools_used"] = self.tools_used
        d["execution_log"] = self.execution_log
        d["model_used"] = self.model_used
        d["fresh_checked"] = self.fresh_checked
        d["refusal_reason"] = self.refusal_reason
        return d
