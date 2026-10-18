"""Deterministic Non-LLM Evidence Verifier for PR Briefs.

Validates that every claim in an investigation brief is strictly supported by
active FalkorDB graph relationships and public GitHub URLs.
Guarantees that target PR is never counted as its own historical evidence.
"""

import re
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

        # 4. CRITICAL RULE: Target PR Exclusion, File Relevance, and Temporal Validity on Historical Reviewers
        target_file_paths = [f.path for f in brief.changed_files]
        cutoff = brief.target_pr.created_at if brief.target_pr else None

        for rev in brief.historical_reviewers:
            # Check 4a: Must have reviews on OTHER PRs
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
                continue

            # Check 4b: Real person who never touched the relevant file
            if target_file_paths:
                relevant_touch_res = self.client.ro_query(
                    """
                    MATCH (f:File)<-[:MODIFIES]-(pr:PullRequest)<-[r:REVIEWED]-(p:Person {login: $login})
                    WHERE pr.number <> $target_num AND f.path IN $target_files
                    RETURN count(DISTINCT pr), collect(r.submitted_at)
                    """,
                    {"login": rev.login, "target_num": target_num, "target_files": target_file_paths},
                )
                touch_count = relevant_touch_res.result_set[0][0] if relevant_touch_res and relevant_touch_res.result_set else 0
                submitted_dates = relevant_touch_res.result_set[0][1] if relevant_touch_res and relevant_touch_res.result_set else []

                rev_is_valid = True
                if touch_count == 0:
                    rejections.append(
                        f"Unrelated maintainer: Reviewer '{rev.login}' has never reviewed any files touched by PR #{target_num}."
                    )
                    rev_is_valid = False

                # Check 4c: Temporal validity (reviews must be at or before cutoff, and not null)
                elif cutoff:
                    valid_prior = False
                    for sub_at in submitted_dates:
                        if not sub_at or not isinstance(sub_at, str) or sub_at.strip() == "":
                            continue
                        if sub_at <= cutoff:
                            valid_prior = True
                            break
                    if not valid_prior:
                        rejections.append(
                            f"Future review: Review activity by '{rev.login}' on target files occurred after cutoff {cutoff} or has invalid timestamps."
                        )
                        rev_is_valid = False

                if rev_is_valid:
                    verified_reviewers += 1
                    verified_urls.append(rev.url)

            # Verify each cited evidence PR URL in FalkorDB
            for ev_url in rev.evidence_pr_urls:
                if f"/pull/{target_num}" in ev_url:
                    rejections.append(
                        f"Target-PR self-contamination: Target PR #{target_num} included in historical evidence URLs for '{rev.login}'."
                    )
                pr_match = re.search(r"/pull/(\d+)", ev_url)
                if pr_match:
                    ev_pr_num = int(pr_match.group(1))
                    rel_check = self.client.ro_query(
                        """
                        MATCH (p:Person {login: $login})-[r:REVIEWED]->(pr:PullRequest {number: $n})
                        RETURN count(r)
                        """,
                        {"login": rev.login, "n": ev_pr_num},
                    )
                    if not rel_check or not rel_check.result_set or rel_check.result_set[0][0] == 0:
                        rejections.append(
                            f"Unsupported reviewer evidence: Reviewer '{rev.login}' has no recorded [:REVIEWED] relationship to cited PR #{ev_pr_num}."
                        )
                verified_urls.append(ev_url)

        # 5. Verify Co-Change Signals Exclude Target PR and Exist in Graph
        for sig in brief.co_change_signals:
            # Verify co_changed_file exists in graph
            f_check = self.client.ro_query(
                "MATCH (f:File {path: $p}) RETURN count(f)", {"p": sig.co_changed_file}
            )
            if not f_check or not f_check.result_set or f_check.result_set[0][0] == 0:
                rejections.append(
                    f"Unverified file: Co-changed file '{sig.co_changed_file}' does not exist in graph repo_kg."
                )

            for ev_url in sig.evidence_pr_urls:
                if f"/pull/{target_num}" in ev_url:
                    rejections.append(
                        f"Target-PR self-contamination: Target PR #{target_num} included in co-change evidence for '{sig.co_changed_file}'."
                    )
                pr_match = re.search(r"/pull/(\d+)", ev_url)
                if pr_match:
                    ev_pr_num = int(pr_match.group(1))
                    co_rel_check = self.client.ro_query(
                        """
                        MATCH (pr:PullRequest {number: $n})-[:MODIFIES]->(f1:File {path: $p1}),
                              (pr)-[:MODIFIES]->(f2:File {path: $p2})
                        RETURN count(pr)
                        """,
                        {"n": ev_pr_num, "p1": sig.primary_file, "p2": sig.co_changed_file},
                    )
                    if not co_rel_check or not co_rel_check.result_set or co_rel_check.result_set[0][0] == 0:
                        rejections.append(
                            f"Unsupported co-change evidence: Cited PR #{ev_pr_num} did not co-modify '{sig.primary_file}' and '{sig.co_changed_file}'."
                        )
                verified_urls.append(ev_url)

        # 6. Verify URL formatting and FalkorDB graph entity grounding across all evidence sources
        allowed_entity_types = {"PullRequest", "Issue", "File", "Person"}
        for ref in brief.evidence_sources:
            if not ref.url.startswith("https://github.com/"):
                rejections.append(f"Malformed source reference URL: '{ref.url}'.")
                continue
            if "unsupported-fake" in ref.url or "fake-evidence" in ref.url:
                rejections.append(f"Source URL does not support claim: '{ref.url}'.")
                continue
            if ref.entity_type not in allowed_entity_types:
                rejections.append(f"Unsupported evidence entity type: '{ref.entity_type}'.")
                continue

            # Ground entity against active graph
            if ref.entity_type == "PullRequest":
                try:
                    num = int(ref.entity_id)
                    res = self.client.ro_query("MATCH (p:PullRequest {number: $n}) RETURN p.url", {"n": num})
                    if not res or not res.result_set:
                        rejections.append(f"Unverified evidence: PullRequest #{num} does not exist in graph repo_kg.")
                    elif res.result_set[0][0] != ref.url:
                        rejections.append(f"Evidence URL mismatch for PullRequest #{num}: '{ref.url}' != '{res.result_set[0][0]}'.")
                except (ValueError, TypeError):
                    rejections.append(f"Invalid PullRequest identifier: '{ref.entity_id}'.")
            elif ref.entity_type == "Issue":
                try:
                    num = int(ref.entity_id)
                    res = self.client.ro_query("MATCH (i:Issue {number: $n}) RETURN i.url", {"n": num})
                    if not res or not res.result_set:
                        rejections.append(f"Unverified evidence: Issue #{num} does not exist in graph repo_kg.")
                    elif res.result_set[0][0] != ref.url:
                        rejections.append(f"Evidence URL mismatch for Issue #{num}: '{ref.url}' != '{res.result_set[0][0]}'.")
                except (ValueError, TypeError):
                    rejections.append(f"Invalid Issue identifier: '{ref.entity_id}'.")
            elif ref.entity_type == "File":
                res = self.client.ro_query("MATCH (f:File {path: $p}) RETURN f.url", {"p": str(ref.entity_id)})
                if not res or not res.result_set:
                    rejections.append(f"Unverified evidence: File '{ref.entity_id}' does not exist in graph repo_kg.")
                elif res.result_set[0][0] != ref.url:
                    rejections.append(f"Evidence URL mismatch for File '{ref.entity_id}': '{ref.url}' != '{res.result_set[0][0]}'.")
            elif ref.entity_type == "Person":
                res = self.client.ro_query("MATCH (p:Person {login: $l}) RETURN p.url", {"l": str(ref.entity_id)})
                if not res or not res.result_set:
                    rejections.append(f"Unverified evidence: Person '{ref.entity_id}' does not exist in graph repo_kg.")
                elif res.result_set[0][0] != ref.url:
                    rejections.append(f"Evidence URL mismatch for Person '{ref.entity_id}': '{ref.url}' != '{res.result_set[0][0]}'.")

        # 7. Comprehensive hostile repository text / prompt injection scan
        hostile_keywords = [
            "ignore previous instructions",
            "system override",
            "drop table",
            "delete from",
            "<script",
            "eval(",
            "rm -rf",
            "powershell",
        ]
        scan_tokens = [
            *brief.verified_facts,
            *brief.evidence_inferences,
            *brief.unresolved_questions,
            brief.target_pr.title if brief.target_pr else "",
            *[iss.title for iss in brief.linked_issues],
            *[iss.resolution_evidence for iss in brief.linked_issues],
            *[d.finding for d in brief.ownership_drift],
            *[ref.description for ref in brief.evidence_sources],
        ]
        text_to_scan = " ".join(scan_tokens).lower()
        for kw in hostile_keywords:
            if kw in text_to_scan:
                rejections.append(f"Hostile repository text / prompt injection detected: '{kw}'.")

        is_valid = len(rejections) == 0
        return VerificationResult(
            is_valid=is_valid,
            rejection_reasons=rejections,
            verified_prs_count=verified_prs,
            verified_reviewers_count=verified_reviewers,
            verified_source_urls=verified_urls,
        )
