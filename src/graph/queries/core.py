"""Core validation queries for FalkorDB repo_kg:
1. Reviewer distribution with evidence PR URLs
2. PR-to-issue tracing with authentic GitHub URLs
3. File co-change network with co-occurrence counts and PR links
"""

from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient


def get_reviewer_distribution(
    client: FalkorDBClient, limit: int = 10
) -> List[Dict[str, Any]]:
    """Query reviewer distribution, review counts, states, and evidence PR URLs."""
    query = """
    MATCH (p:Person)-[r:REVIEWED]->(pr:PullRequest)
    RETURN p.login AS reviewer,
           p.url AS reviewer_url,
           count(pr) AS review_count,
           collect(DISTINCT pr.url)[0..5] AS evidence_pr_urls,
           collect(r.state) AS review_states
    ORDER BY review_count DESC
    LIMIT $limit
    """
    res = client.ro_query(query, {"limit": limit})
    results = []
    if res and res.result_set:
        for row in res.result_set:
            results.append(
                {
                    "reviewer": row[0],
                    "reviewer_url": row[1],
                    "review_count": row[2],
                    "evidence_pr_urls": row[3],
                    "review_states": row[4],
                }
            )
    return results


def trace_pr_to_issues(
    client: FalkorDBClient,
    pr_number: Optional[int] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Trace pull requests to resolved issues and reporters with source URLs."""
    if pr_number is not None:
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
               reporter.url AS reporter_url
        """
        params = {"pr_number": pr_number}
    else:
        query = """
        MATCH (pr:PullRequest)-[:RESOLVES]->(i:Issue)
        OPTIONAL MATCH (reporter:Person)-[:REPORTED]->(i)
        RETURN pr.number AS pr_number,
               pr.title AS pr_title,
               pr.url AS pr_url,
               i.number AS issue_number,
               i.title AS issue_title,
               i.url AS issue_url,
               reporter.login AS reporter_login,
               reporter.url AS reporter_url
        ORDER BY pr.number DESC
        LIMIT $limit
        """
        params = {"limit": limit}

    res = client.ro_query(query, params)
    results = []
    if res and res.result_set:
        for row in res.result_set:
            results.append(
                {
                    "pr_number": row[0],
                    "pr_title": row[1],
                    "pr_url": row[2],
                    "issue_number": row[3],
                    "issue_title": row[4],
                    "issue_url": row[5],
                    "reporter_login": row[6],
                    "reporter_url": row[7],
                }
            )
    return results


def find_file_co_changes(
    client: FalkorDBClient,
    file_path: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Find files frequently co-modified in the same PRs with evidence PR URLs."""
    if file_path:
        query = """
        MATCH (f1:File {path: $file_path})<-[:MODIFIES]-(pr:PullRequest)-[:MODIFIES]->(f2:File)
        WHERE f1.path <> f2.path
        RETURN f1.path AS file_a,
               f2.path AS file_b,
               f2.url AS file_b_url,
               count(DISTINCT pr) AS co_change_count,
               collect(DISTINCT pr.url)[0..5] AS evidence_pr_urls
        ORDER BY co_change_count DESC
        LIMIT $limit
        """
        params = {"file_path": file_path, "limit": limit}
    else:
        query = """
        MATCH (f1:File)<-[:MODIFIES]-(pr:PullRequest)-[:MODIFIES]->(f2:File)
        WHERE f1.path < f2.path
        RETURN f1.path AS file_a,
               f1.url AS file_a_url,
               f2.path AS file_b,
               f2.url AS file_b_url,
               count(DISTINCT pr) AS co_change_count,
               collect(DISTINCT pr.url)[0..5] AS evidence_pr_urls
        ORDER BY co_change_count DESC
        LIMIT $limit
        """
        params = {"limit": limit}

    res = client.ro_query(query, params)
    results = []
    if res and res.result_set:
        for row in res.result_set:
            if file_path:
                results.append(
                    {
                        "file_a": row[0],
                        "file_b": row[1],
                        "file_b_url": row[2],
                        "co_change_count": row[3],
                        "evidence_pr_urls": row[4],
                    }
                )
            else:
                results.append(
                    {
                        "file_a": row[0],
                        "file_a_url": row[1],
                        "file_b": row[2],
                        "file_b_url": row[3],
                        "co_change_count": row[4],
                        "evidence_pr_urls": row[5],
                    }
                )
    return results


def trace_documented_decisions(
    client: FalkorDBClient,
    pr_number: Optional[int] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Query explicit engineering decisions where a merged PR resolved a documented issue."""
    if pr_number is not None:
        query = """
        MATCH (pr:PullRequest {number: $pr_num})-[:RESOLVES]->(i:Issue)
        OPTIONAL MATCH (reporter:Person)-[:REPORTED]->(i)
        RETURN pr.number AS pr_number,
               pr.title AS pr_title,
               pr.url AS pr_url,
               pr.merged_at AS decided_at,
               i.number AS issue_number,
               i.title AS issue_title,
               i.url AS issue_url,
               reporter.login AS reporter
        """
        params = {"pr_num": pr_number}
    else:
        query = """
        MATCH (pr:PullRequest)-[:RESOLVES]->(i:Issue)
        OPTIONAL MATCH (reporter:Person)-[:REPORTED]->(i)
        RETURN pr.number AS pr_number,
               pr.title AS pr_title,
               pr.url AS pr_url,
               pr.merged_at AS decided_at,
               i.number AS issue_number,
               i.title AS issue_title,
               i.url AS issue_url,
               reporter.login AS reporter
        ORDER BY pr.merged_at DESC
        LIMIT $limit
        """
        params = {"limit": limit}

    res = client.ro_query(query, params)
    decisions = []
    if res and res.result_set:
        for r in res.result_set:
            decisions.append({
                "pr_number": r[0],
                "pr_title": r[1],
                "pr_url": r[2],
                "decided_at": r[3],
                "issue_number": r[4],
                "issue_title": r[5],
                "issue_url": r[6],
                "reporter": r[7],
                "decision_type": "EXPLICIT_ISSUE_RESOLUTION",
                "evidence_basis": "Direct (:PullRequest)-[:RESOLVES]->(:Issue) relationship verified from PR description.",
            })
    return decisions


def find_source_backed_documentation(
    client: FalkorDBClient,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Query source-backed repository documentation files and their modifying PR history."""
    query = """
    MATCH (f:File)
    WHERE f.path ENDS WITH '.md' OR f.path ENDS WITH '.txt' OR f.path = 'CODEOWNERS' OR f.path CONTAINS 'docs/'
    OPTIONAL MATCH (pr:PullRequest)-[:MODIFIES]->(f)
    RETURN f.path AS doc_path,
           f.url AS doc_url,
           count(DISTINCT pr) AS modifying_prs_count,
           collect(DISTINCT pr.url)[0..5] AS evidence_pr_urls
    ORDER BY modifying_prs_count DESC
    LIMIT $limit
    """
    res = client.ro_query(query, {"limit": limit})
    docs = []
    if res and res.result_set:
        for r in res.result_set:
            docs.append({
                "path": r[0],
                "url": r[1],
                "modifying_prs_count": r[2],
                "evidence_pr_urls": r[3] or [],
            })
    return docs
