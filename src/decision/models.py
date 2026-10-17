"""Data models for engineering decisions and verification."""

import hashlib
from typing import List, Optional
from pydantic import BaseModel, Field
from src.graph.writer import current_utc_iso


class ExtractedDecision(BaseModel):
    """An explicit, source-quoted engineering decision extracted deterministically."""

    id: str
    pattern: str  # "we decided", "decision:", "won't fix", "going with", "status: accepted"
    quote: str
    quote_start: int
    quote_end: int
    source_text: str
    source_id: str  # "PR#3339", "Issue#5001", "Comment#7001", "docs/adr/0001.md"
    source_type: str  # "pull_request", "issue", "comment", "document"
    source_url: str
    status_state: str = "decided"  # "decided", "accepted", "wont_fix", "rejected"
    confidence: float = 1.0
    affects_target: Optional[str] = None  # target file, issue, or module if explicitly mentioned
    supersedes_id: Optional[str] = None  # id of prior decision if explicitly superseded
    observed_at: str = Field(default_factory=current_utc_iso)

    @classmethod
    def generate_id(cls, source_id: str, quote_start: int, quote_end: int) -> str:
        """Generate a deterministic decision identifier."""
        raw = f"{source_id}:{quote_start}:{quote_end}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"dec_{digest}"


class DecisionVerificationResult(BaseModel):
    """Result of deterministic decision quote and evidence verification."""

    is_valid: bool
    rejection_reasons: List[str] = Field(default_factory=list)
    decision_id: Optional[str] = None
    verified_quote: Optional[str] = None
    source_url: Optional[str] = None
