"""Deterministic Non-LLM Evidence Verifier.

Independently validates findings, PR records, entity identifiers, URL formats,
and count agreements against the FalkorDB graph before presenting to an LLM or user.
Rejects any claim that lacks explicit graph evidence paths.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient
from src.ownership.discrepancy import OwnershipDiscrepancyReport


@dataclass
class VerificationResult:
    """Outcome of deterministic non-LLM evidence validation."""
    is_valid: bool
    rejection_reasons: List[str] = field(default_factory=list)
    verified_prs_count: int = 0
    verified_reviewers_count: int = 0
    verified_source_urls: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "VERIFIED" if self.is_valid else "REJECTED"


class NonLLMEvidenceVerifier:
    """Non-LLM gatekeeper validating graph queries and ownership reports."""

    def __init__(self, client: FalkorDBClient):
        self.client = client

    def verify_ownership_report(
        self, report: OwnershipDiscrepancyReport
    ) -> VerificationResult:
        """Validate an OwnershipDiscrepancyReport against raw graph records."""
        rejections: List[str] = []
        verified_urls: List[str] = []

        # If report indicates insufficient evidence, verify that graph actually has < threshold
        if report.discrepancy_category == "INSUFFICIENT_EVIDENCE":
            # Check graph to ensure file indeed has 0 or insufficient PRs
            res = self.client.ro_query(
                "MATCH (f:File {path: $p})<-[:MODIFIES]-(pr:PullRequest) RETURN count(pr)",
                {"p": report.file_path},
            )
            actual_prs = res.result_set[0][0] if res and res.result_set else 0
            if actual_prs > 0 and report.total_modifying_prs == 0:
                rejections.append(f"Inconsistent state: Graph contains {actual_prs} PRs for {report.file_path}, but report has 0.")
            return VerificationResult(
                is_valid=len(rejections) == 0,
                rejection_reasons=rejections,
                verified_prs_count=0,
                verified_reviewers_count=0,
                verified_source_urls=[],
            )

        # 1. Verify file exists in graph
        file_res = self.client.ro_query(
            "MATCH (f:File {path: $p}) RETURN f.url", {"p": report.file_path}
        )
        if not file_res or not file_res.result_set:
            rejections.append(f"Entity missing: File '{report.file_path}' does not exist in repo_kg.")
        else:
            f_url = file_res.result_set[0][0]
            if not f_url or not f_url.startswith("https://github.com/"):
                rejections.append(f"Malformed URL: File url '{f_url}' is not a valid public GitHub URL.")
            else:
                verified_urls.append(f_url)

        # 2. Verify CODEOWNERS source URL
        if not report.codeowners_source_url.startswith("https://github.com/"):
            rejections.append(
                f"Invalid CODEOWNERS URL: '{report.codeowners_source_url}' is not a valid GitHub source."
            )
        else:
            verified_urls.append(report.codeowners_source_url)

        # 3. Verify supporting PRs in graph
        verified_pr_nums = set()
        for pr in report.supporting_prs:
            pr_num = pr.get("number")
            pr_url = pr.get("url", "")
            if not pr_num:
                rejections.append("Malformed PR record: missing PR number.")
                continue

            if not pr_url.startswith("https://github.com/"):
                rejections.append(f"Malformed PR URL: '{pr_url}' for PR #{pr_num}.")

            # Query database to confirm PR exists and modifies file
            pr_check = self.client.ro_query(
                """
                MATCH (f:File {path: $file_path})<-[:MODIFIES]-(pr:PullRequest {number: $pr_num})
                RETURN pr.url
                """,
                {"file_path": report.file_path, "pr_num": pr_num},
            )
            if not pr_check or not pr_check.result_set:
                rejections.append(
                    f"Fabrication detected: PR #{pr_num} has no (:MODIFIES) relationship to '{report.file_path}' in repo_kg."
                )
            else:
                verified_pr_nums.add(pr_num)
                verified_urls.append(pr_url)

        # 4. Verify observed reviewers in graph
        verified_rev_logins = set()
        for rev_login in report.observed_human_reviewers:
            rev_check = self.client.ro_query(
                """
                MATCH (f:File {path: $file_path})<-[:MODIFIES]-(pr:PullRequest)<-[r:REVIEWED]-(p:Person {login: $login})
                RETURN count(r)
                """,
                {"file_path": report.file_path, "login": rev_login},
            )
            rev_count = rev_check.result_set[0][0] if rev_check and rev_check.result_set else 0
            if rev_count == 0:
                rejections.append(
                    f"Unsupported claim: Reviewer '{rev_login}' has 0 reviews on PRs touching '{report.file_path}' in repo_kg."
                )
            else:
                verified_rev_logins.add(rev_login)

        # 5. Verify total counts agree
        if len(verified_pr_nums) != report.total_modifying_prs:
            rejections.append(
                f"Count disagreement: Report claims {report.total_modifying_prs} PRs, but verified {len(verified_pr_nums)} in graph."
            )

        is_valid = len(rejections) == 0
        return VerificationResult(
            is_valid=is_valid,
            rejection_reasons=rejections,
            verified_prs_count=len(verified_pr_nums),
            verified_reviewers_count=len(verified_rev_logins),
            verified_source_urls=verified_urls,
        )
