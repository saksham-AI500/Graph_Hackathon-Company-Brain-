"""Pydantic and data models for the RepoBrain Company Brain agent."""

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
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        clean = v.strip().upper()
        if not (clean.startswith("S") and len(clean) >= 2):
            raise ValueError(f"Source ID must follow 'S1', 'S2' format, got '{v}'")
        return clean

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "identifier": self.identifier,
            "url": self.url,
            "title_or_desc": self.title_or_desc,
            "snippet": self.snippet,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "claim_type": self.claim_type,
            "source_ids": self.source_ids,
            "verified": self.verified,
            "unresolved_reason": self.unresolved_reason,
        }


class AgentRequest(BaseModel):
    """Validated input question and parameters for the Company Brain agent."""
    question: str
    as_of: Optional[str] = None
    max_steps: int = Field(default=8, ge=1, le=12)
    model: Optional[str] = None
    api_key: Optional[str] = None
    require_fresh: bool = True
    dry_run_sync: bool = True

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
    status: str = Field(default="VERIFIED", description="'VERIFIED', 'PARTIALLY_VERIFIED', or 'REFUSED'")
    step_count: int = 0
    tools_used: List[str] = Field(default_factory=list)
    execution_log: List[Dict[str, Any]] = Field(default_factory=list)
    model_used: str = "deterministic_fallback"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "claims": [c.to_dict() for c in self.claims],
            "sources": [s.to_dict() for s in self.sources],
            "unresolved": self.unresolved,
            "as_of": self.as_of,
            "fresh_checked": self.fresh_checked,
            "status": self.status,
            "step_count": self.step_count,
            "tools_used": self.tools_used,
            "execution_log": self.execution_log,
            "model_used": self.model_used,
        }
