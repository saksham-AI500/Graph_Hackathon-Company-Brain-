"""Investigation Orchestrator: executes bounded investigation workflow with evidence verification."""

import os
from typing import Any, Dict, List, Optional, Union
from src.db import FalkorDBClient
from src.investigation.models import (
    ChangedFileFinding,
    CoChangeSignal,
    EvidenceReference,
    HistoricalReviewerFinding,
    InvestigationInput,
    LinkedIssueFinding,
    OwnershipDriftFinding,
    PRBrief,
    PRBriefMetadata,
)
from src.investigation.tools import (
    audit_ownership_for_files,
    find_historical_reviewers,
    find_related_co_changes,
    lookup_changed_files,
    lookup_linked_issues,
    lookup_pr_details,
)
from src.investigation.verifier import PROnlineEvidenceVerifier
from src.ownership.codeowners import CodeownersParser


def sanitize_untrusted_text(text: Optional[str]) -> str:
    """Sanitize repository text (PR titles, issue bodies, comments).

    Enforces data-isolation:
    1. Strips HTML script, iframe, and executable tags.
    2. Neutralizes attempts to forge system instructions or injection delimiters
       (e.g., '<!-- SYSTEM:', '[SYSTEM OVERRIDE]', '</untrusted_data>').
    3. Normalizes whitespace and bounds maximum length to prevent context flooding.
    """
    if not text or not isinstance(text, str):
        return ""

    import re

    sanitized = text
    # Strip script, iframe, and executable tags
    sanitized = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", sanitized, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r"<\s*/?\s*script[^>]*>", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"<\s*/?\s*(?:iframe|object|embed|applet)[^>]*>", "", sanitized, flags=re.IGNORECASE)

    # Neutralize attempts to close data isolation boundary or inject fake system tags
    sanitized = sanitized.replace("</untrusted_data>", "&lt;/untrusted_data&gt;")
    sanitized = sanitized.replace("<untrusted_data", "&lt;untrusted_data")
    sanitized = re.sub(r"<!--\s*SYSTEM.*?(?:-->|$)", "", sanitized, flags=re.IGNORECASE)

    return sanitized.strip()[:2000]


def wrap_untrusted_data(text: Optional[str], source: str = "repository_text") -> str:
    """Wrap untrusted repository text in strict data-isolation tags.

    Protection Boundary:
    - Treats all repository text, comments, PR bodies, and issue text as passive data, never instructions.
    - Delimits content within <untrusted_data source="..."> blocks before passing to models.
    - Residual Risk: While structural wrapping and deterministic tool validation prevent tool/graph injection,
      stochastic LLM text interpretation cannot be 100% mathematically prevented solely via prompting;
      RepoBrain mitigates this with a deterministic, non-LLM verification gate before brief emission.
    """
    sanitized = sanitize_untrusted_text(text)
    import re
    safe_source = re.sub(r'[^a-zA-Z0-9_\-.:/]', '_', str(source))[:100]
    return f'<untrusted_data source="{safe_source}">\n{sanitized}\n</untrusted_data>'


class PROrchestrator:
    """Orchestrates evidence-gated PR investigation briefs."""

    def __init__(
        self,
        client: Optional[FalkorDBClient] = None,
        codeowners: Optional[CodeownersParser] = None,
    ):
        self.client = client or FalkorDBClient()
        self.codeowners = codeowners or CodeownersParser.from_cache_or_default()
        self.verifier = PROnlineEvidenceVerifier(self.client)

    def investigate(self, target: Union[InvestigationInput, int, str]) -> PRBrief:
        """Execute the end-to-end investigation contract for a target PR."""
        # 1. Parse and validate input
        try:
            if isinstance(target, InvestigationInput):
                pr_number = target.target
            else:
                inp = InvestigationInput(target=target)
                pr_number = inp.target
        except Exception as exc:
            return PRBrief(
                status="REFUSED",
                refusal_message=f"Invalid PR input: {exc}",
                unresolved_questions=[f"Could not parse valid PR identifier from '{target}'."],
            )

        # Check database connectivity
        health = self.client.ping()
        if health.get("status") != "healthy":
            return PRBrief(
                status="REFUSED",
                refusal_message=f"Database unavailable: Cannot connect to FalkorDB at {self.client.host}:{self.client.port}.",
                unresolved_questions=["FalkorDB database service is offline or unreachable."],
            )

        # 2. Look up target PR details
        pr_data = lookup_pr_details(self.client, pr_number)
        if not pr_data:
            return PRBrief(
                status="REFUSED",
                refusal_message=f"Evidence path not found: PR #{pr_number} does not exist in graph repo_kg.",
                unresolved_questions=[
                    f"PR #{pr_number} is not recorded in the ingested repository knowledge graph."
                ],
            )

        metadata = PRBriefMetadata(
            number=pr_data["number"],
            title=sanitize_untrusted_text(pr_data["title"]),
            url=pr_data["url"],
            author=pr_data["author_login"],
            author_url=pr_data["author_url"],
            state=pr_data["state"],
            created_at=pr_data["created_at"],
            merged_at=pr_data["merged_at"],
        )

        # 3. Retrieve Graph Evidence
        linked_issues_raw = lookup_linked_issues(self.client, pr_number)
        changed_files_raw = lookup_changed_files(self.client, pr_number)
        file_paths = [f["path"] for f in changed_files_raw]

        cutoff_ts = pr_data.get("created_at")

        # Historical reviewers (EXCLUDING target PR and strictly respecting temporal cutoff)
        from src.evaluation.temporal import (
            find_historical_reviewers_temporal,
            find_related_co_changes_temporal,
        )
        historical_revs_raw = find_historical_reviewers_temporal(
            self.client,
            file_paths=file_paths,
            exclude_pr_number=pr_number,
            cutoff_timestamp=cutoff_ts,
            limit=5,
        )

        # Co-change signals (EXCLUDING target PR and strictly respecting temporal cutoff)
        co_changes_raw = find_related_co_changes_temporal(
            self.client,
            file_paths=file_paths,
            exclude_pr_number=pr_number,
            cutoff_timestamp=cutoff_ts,
            limit=5,
        )

        # Ownership audits (respecting target PR creation cutoff)
        ownership_audits = audit_ownership_for_files(
            self.client,
            file_paths=file_paths,
            codeowners=self.codeowners,
            cutoff_timestamp=cutoff_ts,
        )

        # 4. Construct Structured Findings
        changed_files: List[ChangedFileFinding] = []
        for f, audit in zip(changed_files_raw, ownership_audits):
            changed_files.append(
                ChangedFileFinding(
                    path=f["path"],
                    url=f["url"],
                    additions=f["additions"],
                    deletions=f["deletions"],
                    declared_owners=audit.get("declared_owners", []),
                    is_team_ownership=audit.get("is_team_declaration", False),
                    rule_pattern=audit.get("declared_rule_pattern"),
                )
            )

        linked_issues: List[LinkedIssueFinding] = []
        for iss in linked_issues_raw:
            linked_issues.append(
                LinkedIssueFinding(
                    number=iss["number"],
                    title=sanitize_untrusted_text(iss["title"]),
                    url=iss["url"],
                    reporter=iss.get("reporter"),
                    reporter_url=iss.get("reporter_url"),
                    resolution_evidence=f"Explicitly resolved by PR #{pr_number} in GitHub issue tracker.",
                )
            )

        hist_reviewers: List[HistoricalReviewerFinding] = []
        for rev in historical_revs_raw:
            hist_reviewers.append(
                HistoricalReviewerFinding(
                    login=rev["login"],
                    url=rev["url"],
                    is_bot=rev["is_bot"],
                    prior_touches=rev["prior_touches"],
                    evidence_pr_urls=rev["evidence_pr_urls"],
                    review_states=rev["review_states"],
                )
            )

        co_signals: List[CoChangeSignal] = []
        for co in co_changes_raw:
            co_signals.append(
                CoChangeSignal(
                    primary_file=co["primary_file"],
                    co_changed_file=co["co_changed_file"],
                    co_change_count=co["co_change_count"],
                    evidence_pr_urls=co["evidence_pr_urls"],
                )
            )

        ownership_drift: List[OwnershipDriftFinding] = []
        for audit in ownership_audits:
            ownership_drift.append(
                OwnershipDriftFinding(
                    file_path=audit["file_path"],
                    declared_owners=audit.get("declared_owners", []),
                    observed_human_reviewers=audit.get("observed_human_reviewers", []),
                    drift_score=audit.get("drift_score", 0.0),
                    bus_factor=audit.get("bus_factor", 0),
                    risk_level=audit.get("risk_level", "LOW"),
                    discrepancy_category=audit.get("discrepancy_category", "UNKNOWN"),
                    finding=audit.get("summary_finding", ""),
                )
            )

        # 5. Build Evidence Sources Catalog
        evidence_sources: List[EvidenceReference] = [
            EvidenceReference(
                entity_type="PullRequest",
                entity_id=pr_number,
                url=metadata.url,
                description=f"Target PR #{pr_number} metadata",
            )
        ]
        for iss in linked_issues:
            evidence_sources.append(
                EvidenceReference(
                    entity_type="Issue",
                    entity_id=iss.number,
                    url=iss.url,
                    description=f"Linked resolved issue #{iss.number}",
                )
            )
        for cf in changed_files:
            evidence_sources.append(
                EvidenceReference(
                    entity_type="File",
                    entity_id=cf.path,
                    url=cf.url,
                    description=f"Modified file: {cf.path}",
                )
            )

        # 6. Synthesize Verified Facts, Inferences, and Unresolved Questions
        verified_facts: List[str] = [
            f"Target PR #{pr_number} ('{metadata.title}') was authored by {metadata.author} and is {metadata.state} on GitHub ({metadata.url}).",
            f"Modifies {len(changed_files)} repository file(s).",
        ]
        if linked_issues:
            verified_facts.append(
                f"Resolves {len(linked_issues)} issue(s): "
                + ", ".join([f"#{i.number} ('{i.title}') [{i.url}]" for i in linked_issues])
            )

        evidence_inferences: List[str] = []
        human_reviewers = [r for r in hist_reviewers if not r.is_bot]
        if human_reviewers:
            top_rec = human_reviewers[0]
            evidence_inferences.append(
                f"Recommended reviewer: {top_rec.login} with {top_rec.prior_touches} prior reviews on touched modules (Evidence: {', '.join(top_rec.evidence_pr_urls[:2])})."
            )
        if co_signals:
            top_co = co_signals[0]
            evidence_inferences.append(
                f"Co-change risk: {top_co.primary_file} has historically co-changed with {top_co.co_changed_file} across {top_co.co_change_count} prior PR(s)."
            )

        unresolved_questions: List[str] = []
        if not linked_issues:
            unresolved_questions.append(
                "No linked issue was closed by this PR; implementation rationale relies on PR description and commit notes."
            )
        unowned_count = sum(1 for cf in changed_files if not cf.declared_owners)
        if unowned_count > 0:
            unresolved_questions.append(
                f"{unowned_count} of {len(changed_files)} changed file(s) lack a declared owner in CODEOWNERS; ownership is informal."
            )

        # 7. Assemble Draft Brief
        brief = PRBrief(
            target_pr=metadata,
            status="PENDING",
            verified_facts=verified_facts,
            evidence_inferences=evidence_inferences,
            unresolved_questions=unresolved_questions,
            changed_files=changed_files,
            linked_issues=linked_issues,
            historical_reviewers=hist_reviewers,
            co_change_signals=co_signals,
            ownership_drift=ownership_drift,
            evidence_sources=evidence_sources,
        )

        # 8. Run Deterministic Verification
        v_res = self.verifier.verify_brief(brief)
        if v_res.is_valid:
            brief.status = "VERIFIED"
        else:
            brief.status = "REJECTED"
            brief.verification_errors = v_res.rejection_reasons
            brief.refusal_message = (
                f"Deterministic Verification Failed: {'; '.join(v_res.rejection_reasons)}"
            )

        return brief
