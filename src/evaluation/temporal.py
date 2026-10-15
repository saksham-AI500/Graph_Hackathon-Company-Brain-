"""Temporal Backtesting Engine for RepoBrain.

Enforces historical validity at target_pr.created_at:
- Excludes target PR from its own historical evidence.
- Excludes PRs merged at or after the cutoff timestamp.
- Excludes future review activities and co-changes.
"""

from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient
from src.ownership.codeowners import CodeownersParser
from src.ownership.discrepancy import evaluate_ownership_discrepancy, OwnershipDiscrepancyReport


def get_pr_creation_cutoff(client: FalkorDBClient, pr_number: int) -> Optional[str]:
    """Retrieve the exact created_at timestamp for a pull request."""
    query = """
    MATCH (pr:PullRequest {number: $pr_number})
    RETURN pr.created_at AS created_at
    """
    res = client.ro_query(query, {"pr_number": pr_number})
    if res and res.result_set:
        return res.result_set[0][0]
    return None


def find_historical_reviewers_temporal(
    client: FalkorDBClient,
    file_paths: List[str],
    exclude_pr_number: int,
    cutoff_timestamp: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Query historical reviewers strictly before the cutoff timestamp."""
    if not file_paths:
        return []

    if cutoff_timestamp:
        query = """
        MATCH (f:File)<-[:MODIFIES]-(prior_pr:PullRequest)<-[r:REVIEWED]-(p:Person)
        WHERE f.path IN $file_paths
          AND prior_pr.number <> $exclude_pr
          AND prior_pr.merged_at IS NOT NULL
          AND prior_pr.merged_at < $cutoff
          AND (r.submitted_at IS NULL OR r.submitted_at < $cutoff)
        RETURN p.login AS reviewer,
               p.url AS reviewer_url,
               count(DISTINCT prior_pr) AS prior_pr_count,
               collect(DISTINCT prior_pr.url)[0..5] AS evidence_pr_urls,
               collect(DISTINCT r.state) AS review_states
        ORDER BY prior_pr_count DESC
        LIMIT $limit
        """
        params = {
            "file_paths": file_paths,
            "exclude_pr": exclude_pr_number,
            "cutoff": cutoff_timestamp,
            "limit": limit,
        }
    else:
        query = """
        MATCH (f:File)<-[:MODIFIES]-(prior_pr:PullRequest)<-[r:REVIEWED]-(p:Person)
        WHERE f.path IN $file_paths AND prior_pr.number <> $exclude_pr
        RETURN p.login AS reviewer,
               p.url AS reviewer_url,
               count(DISTINCT prior_pr) AS prior_pr_count,
               collect(DISTINCT prior_pr.url)[0..5] AS evidence_pr_urls,
               collect(DISTINCT r.state) AS review_states
        ORDER BY prior_pr_count DESC
        LIMIT $limit
        """
        params = {
            "file_paths": file_paths,
            "exclude_pr": exclude_pr_number,
            "limit": limit,
        }

    res = client.ro_query(query, params)
    reviewers = []
    if res and res.result_set:
        for row in res.result_set:
            login = row[0]
            is_bot = login.endswith("[bot]") or login.lower() == "github-actions[bot]"
            reviewers.append(
                {
                    "login": login,
                    "url": row[1],
                    "is_bot": is_bot,
                    "prior_touches": row[2],
                    "evidence_pr_urls": row[3] or [],
                    "review_states": row[4] or [],
                }
            )
    return reviewers


def find_related_co_changes_temporal(
    client: FalkorDBClient,
    file_paths: List[str],
    exclude_pr_number: int,
    cutoff_timestamp: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Identify file co-changes strictly merged before cutoff timestamp."""
    if not file_paths:
        return []

    if cutoff_timestamp:
        query = """
        MATCH (f1:File)<-[:MODIFIES]-(prior_pr:PullRequest)-[:MODIFIES]->(f2:File)
        WHERE f1.path IN $file_paths
          AND NOT f2.path IN $file_paths
          AND prior_pr.number <> $exclude_pr
          AND prior_pr.merged_at IS NOT NULL
          AND prior_pr.merged_at < $cutoff
        RETURN f1.path AS primary_file,
               f2.path AS co_changed_file,
               count(DISTINCT prior_pr) AS co_change_count,
               collect(DISTINCT prior_pr.url)[0..3] AS evidence_pr_urls
        ORDER BY co_change_count DESC
        LIMIT $limit
        """
        params = {
            "file_paths": file_paths,
            "exclude_pr": exclude_pr_number,
            "cutoff": cutoff_timestamp,
            "limit": limit,
        }
    else:
        query = """
        MATCH (f1:File)<-[:MODIFIES]-(prior_pr:PullRequest)-[:MODIFIES]->(f2:File)
        WHERE f1.path IN $file_paths
          AND NOT f2.path IN $file_paths
          AND prior_pr.number <> $exclude_pr
        RETURN f1.path AS primary_file,
               f2.path AS co_changed_file,
               count(DISTINCT prior_pr) AS co_change_count,
               collect(DISTINCT prior_pr.url)[0..3] AS evidence_pr_urls
        ORDER BY co_change_count DESC
        LIMIT $limit
        """
        params = {
            "file_paths": file_paths,
            "exclude_pr": exclude_pr_number,
            "limit": limit,
        }

    res = client.ro_query(query, params)
    co_changes = []
    if res and res.result_set:
        for row in res.result_set:
            co_changes.append(
                {
                    "primary_file": row[0],
                    "co_changed_file": row[1],
                    "co_change_count": row[2],
                    "evidence_pr_urls": row[3] or [],
                }
            )
    return co_changes


def trace_pr_to_issues_temporal(
    client: FalkorDBClient,
    pr_number: int,
    cutoff_timestamp: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Trace PR to resolved issues ensuring issue was created at or before cutoff."""
    if cutoff_timestamp:
        query = """
        MATCH (pr:PullRequest {number: $pr_number})-[:RESOLVES]->(i:Issue)
        WHERE (i.created_at IS NOT NULL AND i.created_at <= $cutoff)
        OPTIONAL MATCH (reporter:Person)-[:REPORTED]->(i)
        RETURN pr.number AS pr_number,
               pr.title AS pr_title,
               pr.url AS pr_url,
               i.number AS issue_number,
               i.title AS issue_title,
               i.url AS issue_url,
               reporter.login AS reporter_login,
               reporter.url AS reporter_url,
               i.created_at AS issue_created_at
        """
        params = {"pr_number": pr_number, "cutoff": cutoff_timestamp}
    else:
        query = """
        MATCH (pr:PullRequest {number: $pr_number})-[:RESOLVES]->(i:Issue)
        OPTIONAL MATCH (reporter:Person)-[:REPORTED]->(i)
        RETURN pr.number AS pr_number,
               pr.title AS pr_title,
               pr.url AS pr_url,
               i.number AS issue_number,
               i.title AS issue_title,
               i.url AS issue_url,
               reporter.login AS reporter_login,
               reporter.url AS reporter_url,
               i.created_at AS issue_created_at
        """
        params = {"pr_number": pr_number}

    res = client.ro_query(query, params)
    issues = []
    if res and res.result_set:
        for row in res.result_set:
            issues.append(
                {
                    "pr_number": row[0],
                    "pr_title": row[1],
                    "pr_url": row[2],
                    "issue_number": row[3],
                    "issue_title": row[4],
                    "issue_url": row[5],
                    "reporter_login": row[6],
                    "reporter_url": row[7],
                    "issue_created_at": row[8],
                }
            )
    return issues
