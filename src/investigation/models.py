"""Investigation contracts and structured PR brief schemas."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class InvestigationInput(BaseModel):
    """Input specification for PR investigation, accepting a PR number or GitHub URL."""
    target: Union[int, str]

    @field_validator("target")
    @classmethod
    def validate_target(cls, v: Union[int, str]) -> int:
        if isinstance(v, int):
            if v <= 0:
                raise ValueError("PR number must be positive.")
            return v
        if isinstance(v, str):
            v_clean = v.strip()
            # If plain numeric string
            if v_clean.isdigit():
                num = int(v_clean)
                if num <= 0:
                    raise ValueError("PR number must be positive.")
                return num
            # If GitHub URL (strictly validated without injected syntax)
            match = re.fullmatch(r"https?://github\.com/[a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+/pull/(\d+)/?", v_clean)
            if match:
                return int(match.group(1))
            raise ValueError(f"Invalid PR identifier or URL format: '{v}'")
        raise TypeError("Target must be an integer PR number or GitHub PR URL string.")


class PRBriefMetadata(BaseModel):
    """Metadata describing the target pull request."""
    number: int
    title: str
    url: str
    author: str
    author_url: str
    state: str = "closed"
    created_at: Optional[str] = None
    merged_at: Optional[str] = None


class LinkedIssueFinding(BaseModel):
    """An issue resolved by the pull request with resolution evidence."""
    number: int
    title: str
    url: str
    reporter: Optional[str] = None
    reporter_url: Optional[str] = None
    resolution_evidence: str


class ChangedFileFinding(BaseModel):
    """A file touched by the pull request with declared ownership."""
    path: str
    url: str
    additions: int = 0
    deletions: int = 0
    declared_owners: List[str] = Field(default_factory=list)
    is_team_ownership: bool = False
    rule_pattern: Optional[str] = None


class HistoricalReviewerFinding(BaseModel):
    """A recommended or historical reviewer with audit citations."""
    login: str
    url: str
    is_bot: bool = False
    prior_touches: int = 0
    evidence_pr_urls: List[str] = Field(default_factory=list)
    review_states: List[str] = Field(default_factory=list)


class CoChangeSignal(BaseModel):
    """Files historically modified in tandem with changed files."""
    primary_file: str
    co_changed_file: str
    co_change_count: int
    evidence_pr_urls: List[str] = Field(default_factory=list)


class OwnershipDriftFinding(BaseModel):
    """Ownership alignment or drift summary for changed modules."""
    file_path: str
    declared_owners: List[str]
    observed_human_reviewers: List[str]
    drift_score: float
    bus_factor: int
    risk_level: str
    discrepancy_category: str
    finding: str


class EvidenceReference(BaseModel):
    """An explicit auditable source record reference."""
    entity_type: str
    entity_id: Union[int, str]
    url: str
    description: str


class PRBrief(BaseModel):
    """The Evidence-Gated PR Brief for engineering teams."""
    target_pr: Optional[PRBriefMetadata] = None
    status: str = "PENDING"  # VERIFIED, REJECTED, REFUSED

    # Strict separation of findings
    verified_facts: List[str] = Field(default_factory=list)
    evidence_inferences: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)

    # Detailed structured findings
    changed_files: List[ChangedFileFinding] = Field(default_factory=list)
    linked_issues: List[LinkedIssueFinding] = Field(default_factory=list)
    historical_reviewers: List[HistoricalReviewerFinding] = Field(default_factory=list)
    co_change_signals: List[CoChangeSignal] = Field(default_factory=list)
    ownership_drift: List[OwnershipDriftFinding] = Field(default_factory=list)

    # Verifiable evidence paths
    evidence_sources: List[EvidenceReference] = Field(default_factory=list)
    refusal_message: Optional[str] = None
    verification_errors: List[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the PR Brief as a structured, evidence-auditable markdown report."""
        if self.refusal_message:
            return f"# REPOBRAIN INVESTIGATION REFUSAL\n\n**Status:** {self.status}\n\n**Reason:** {self.refusal_message}\n"

        target = self.target_pr
        lines = [
            f"# REPOBRAIN PR BRIEF - PR #{target.number if target else 'UNKNOWN'}",
            f"**Title:** {target.title if target else 'N/A'}  ",
            f"**Author:** [{target.author}]({target.author_url}) | **State:** `{target.state}` | **Verification:** `{self.status}`  ",
            f"**Source PR:** {target.url if target else 'N/A'}\n",
            "---",
            "## 1. Verified Facts",
        ]
        for fact in self.verified_facts:
            lines.append(f"- {fact}")
        if not self.verified_facts:
            lines.append("- *No verified facts recorded.*")

        lines.append("\n## 2. Evidence-Supported Inferences")
        for inf in self.evidence_inferences:
            lines.append(f"- {inf}")
        if not self.evidence_inferences:
            lines.append("- *No inferences generated.*")

        lines.append("\n## 3. Unresolved Questions")
        for q in self.unresolved_questions:
            lines.append(f"- {q}")
        if not self.unresolved_questions:
            lines.append("- *No unresolved questions.*")

        if self.changed_files:
            lines.append("\n## 4. Changed Files & Declared Ownership")
            lines.append("| File | Changes | Declared CODEOWNERS |")
            lines.append("|---|---|---|")
            for f in self.changed_files:
                owners = ", ".join(f.declared_owners) if f.declared_owners else "*None (Unowned)*"
                lines.append(f"| [`{f.path}`]({f.url}) | +{f.additions} / -{f.deletions} | {owners} |")

        if self.historical_reviewers:
            lines.append("\n## 5. Historical Domain Reviewers (Target PR Excluded)")
            lines.append("| Reviewer | Type | Prior File Touches | Sample Evidence PRs |")
            lines.append("|---|---|---|---|")
            for r in self.historical_reviewers:
                rtype = "Bot" if r.is_bot else "Human"
                sample_prs = ", ".join(f"[PR #{u.split('/')[-1]}]({u})" for u in r.evidence_pr_urls[:3])
                lines.append(f"| [{r.login}]({r.url}) | {rtype} | {r.prior_touches} | {sample_prs} |")

        if self.ownership_drift:
            lines.append("\n## 6. Ownership Discrepancy & Drift Signals")
            for d in self.ownership_drift:
                lines.append(f"- **`{d.file_path}`** ({d.discrepancy_category}, Risk: `{d.risk_level}`, Drift Score: {d.drift_score:.2f}, Bus Factor: {d.bus_factor})")
                lines.append(f"  - *Finding:* {d.finding}")

        if self.co_change_signals:
            lines.append("\n## 7. Significant File Co-Change Precedents")
            for c in self.co_change_signals:
                pr_links = ", ".join(f"[PR #{u.split('/')[-1]}]({u})" for u in c.evidence_pr_urls[:2])
                lines.append(f"- `{c.primary_file}` co-changed with `{c.co_changed_file}` {c.co_change_count}x in: {pr_links}")

        if self.evidence_sources:
            lines.append("\n## 8. Audit Evidence Traceability")
            for ev in self.evidence_sources:
                lines.append(f"- [{ev.entity_type} {ev.entity_id}]({ev.url}): {ev.description}")

        if self.verification_errors:
            lines.append("\n## ⚠️ Verification Errors")
            for err in self.verification_errors:
                lines.append(f"- ❌ {err}")

        return "\n".join(lines)
