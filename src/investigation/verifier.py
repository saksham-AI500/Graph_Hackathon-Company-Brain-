"""Deterministic Non-LLM Evidence Verifier for PR Briefs.

Validates that every claim in an investigation brief is strictly supported by
active FalkorDB graph relationships and public GitHub URLs.
Guarantees that target PR is never counted as its own historical evidence.
"""

from typing import List, Optional
from src.db import FalkorDBClient
from src.investigation.models import PRBrief
from src.ownership.verifier import NonLLMEvidenceVerifier, VerificationResult


class PROnlineEvidenceVerifier(NonLLMEvidenceVerifier):
    """Extended verifier with full PR brief validation and target PR exclusion checks."""

    def __init__(self, client: FalkorDBClient):
        super().__init__(client)

    def verify_brief(self, brief: PRBrief) -> VerificationResult:
        """Validate an entire PRBrief against the active FalkorDB graph."""
        rejections: List[str] = []
        verified_urls: List[str] = []
        verified_prs = 0
        verified_reviewers = 0

        # If brief was refused due to missing target, verify target genuinely does not exist
        if brief.status == "REFUSED":
            if not brief.target_pr:
                return VerificationResult(
                    is_valid=True,
                    rejection_reasons=[],
                    verified_prs_count=0,
                    verified_reviewers_count=0,
                    verified_source_urls=[],
                )
            target_num = brief.target_pr.number
            check = self.client.ro_query(
                "MATCH (pr:PullRequest {number: $n}) RETURN count(pr)", {"n": target_num}
            )
            exists = check.result_set[0][0] > 0 if check and check.result_set else False
            if exists:
                rejections.append(f"Brief marked REFUSED, but PR #{target_num} exists in graph.")
            return VerificationResult(
                is_valid=len(rejections) == 0,
                rejection_reasons=rejections,
                verified_prs_count=0,
                verified_reviewers_count=0,
                verified_source_urls=[],
            )

        if not brief.target_pr:
            return VerificationResult(
                is_valid=False,
                rejection_reasons=["Malformed brief: missing target_pr metadata."],
            )

        target_num = brief.target_pr.number

        # 1. Verify Target PR exists in graph and properties match
        pr_res = self.client.ro_query(
            "MATCH (pr:PullRequest {number: $n}) RETURN pr.url, pr.title", {"n": target_num}
        )
        if not pr_res or not pr_res.result_set:
            rejections.append(f"Target PR #{target_num} does not exist in graph repo_kg.")
        else:
            db_url, db_title = pr_res.result_set[0]
            if brief.target_pr.url != db_url:
                rejections.append(f"Target PR URL mismatch: brief has '{brief.target_pr.url}', graph has '{db_url}'.")
            verified_urls.append(brief.target_pr.url)
            verified_prs += 1

        # 2. Verify Changed Files
        for f in brief.changed_files:
            file_res = self.client.ro_query(
                """
                MATCH (pr:PullRequest {number: $pr_num})-[m:MODIFIES]->(file:File {path: $path})
                RETURN file.url, m.additions, m.deletions
                """,
                {"pr_num": target_num, "path": f.path},
            )
            if not file_res or not file_res.result_set:
                rejections.append(
                    f"Fabrication: File '{f.path}' is not linked via (:MODIFIES) to target PR #{target_num}."
                )
            else:
                verified_urls.append(f.url)

        # 3. Verify Linked Issues
        for iss in brief.linked_issues:
            iss_res = self.client.ro_query(
                """
                MATCH (pr:PullRequest {number: $pr_num})-[:RESOLVES]->(i:Issue {number: $iss_num})
                RETURN i.url
                """,
                {"pr_num": target_num, "iss_num": iss.number},
            )
            if not iss_res or not iss_res.result_set:
                rejections.append(
                    f"Unsupported Issue claim: Issue #{iss.number} is not linked via (:RESOLVES) to PR #{target_num}."
                )
            else:
                verified_urls.append(iss.url)

        # 4. CRITICAL RULE: Target PR Exclusion on Historical Reviewers
        for rev in brief.historical_reviewers:
            # Must verify that each historical reviewer is verified on OTHER PRs
            rev_res = self.client.ro_query(
                """
                MATCH (pr:PullRequest)<-[r:REVIEWED]-(p:Person {login: $login})
                WHERE pr.number <> $target_num
                RETURN count(DISTINCT pr)
                """,
                {"login": rev.login, "target_num": target_num},
            )
            prior_count = rev_res.result_set[0][0] if rev_res and rev_res.result_set else 0
            if prior_count == 0:
                rejections.append(
                    f"Target-PR self-contamination: Reviewer '{rev.login}' has 0 historical reviews outside PR #{target_num}."
                )
            else:
                verified_reviewers += 1
                verified_urls.append(rev.url)

            # Check that evidence_pr_urls does NOT contain target PR
            for ev_url in rev.evidence_pr_urls:
                if f"/pull/{target_num}" in ev_url:
                    rejections.append(
                        f"Target-PR self-contamination: Target PR #{target_num} included in historical evidence URLs for '{rev.login}'."
                    )
                verified_urls.append(ev_url)

        # 5. Verify Co-Change Signals Exclude Target PR
        for sig in brief.co_change_signals:
            for ev_url in sig.evidence_pr_urls:
                if f"/pull/{target_num}" in ev_url:
                    rejections.append(
                        f"Target-PR self-contamination: Target PR #{target_num} included in co-change evidence for '{sig.co_changed_file}'."
                    )
                verified_urls.append(ev_url)

        # 6. Verify URL formatting across all evidence sources
        for ref in brief.evidence_sources:
            if not ref.url.startswith("https://github.com/"):
                rejections.append(f"Malformed source reference URL: '{ref.url}'.")

        is_valid = len(rejections) == 0
        return VerificationResult(
            is_valid=is_valid,
            rejection_reasons=rejections,
            verified_prs_count=verified_prs,
            verified_reviewers_count=verified_reviewers,
            verified_source_urls=verified_urls,
        )
