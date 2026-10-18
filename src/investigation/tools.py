"""Typed, read-only FalkorDB investigation tools for PR analysis.

All queries use strictly parameterized Cypher and allowlisted templates.
Target PR is explicitly excluded from historical precedent lookups.
"""

from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient
from src.ownership.codeowners import CodeownersParser
from src.ownership.discrepancy import evaluate_ownership_discrepancy


def lookup_pr_details(
    client: FalkorDBClient, pr_number: int
) -> Optional[Dict[str, Any]]:
    """Fetch core metadata and author for a target PR."""
    query = """
    MATCH (pr:PullRequest {number: $pr_number})
    OPTIONAL MATCH (pr)<-[:AUTHORED]-(a:Person)
    RETURN pr.number AS number,
           pr.title AS title,
           pr.url AS url,
           pr.state AS state,
           pr.created_at AS created_at,
           pr.merged_at AS merged_at,
           a.login AS author_login,
           a.url AS author_url
    """
    res = client.ro_query(query, {"pr_number": pr_number})
    if not res or not res.result_set:
        return None

    row = res.result_set[0]
    return {
        "number": row[0],
        "title": row[1],
        "url": row[2],
        "state": row[3],
        "created_at": row[4],
        "merged_at": row[5],
        "author_login": row[6] or "unknown",
        "author_url": row[7] or f"https://github.com/{row[6]}",
    }


def lookup_linked_issues(
    client: FalkorDBClient, pr_number: int
) -> List[Dict[str, Any]]:
    """Fetch issues explicitly linked via (:RESOLVES) to the PR with reporter details."""
    query = """
    MATCH (pr:PullRequest {number: $pr_number})-[:RESOLVES]->(i:Issue)
    OPTIONAL MATCH (reporter:Person)-[:REPORTED]->(i)
    RETURN i.number AS issue_number,
           i.title AS issue_title,
           i.url AS issue_url,
           reporter.login AS reporter_login,
           reporter.url AS reporter_url
    ORDER BY i.number ASC
    """
    res = client.ro_query(query, {"pr_number": pr_number})
    issues = []
    if res and res.result_set:
        for row in res.result_set:
            issues.append(
                {
                    "number": row[0],
                    "title": row[1],
                    "url": row[2],
                    "reporter": row[3],
                    "reporter_url": row[4],
                }
            )
    return issues


def lookup_changed_files(
    client: FalkorDBClient, pr_number: int
) -> List[Dict[str, Any]]:
    """Fetch all files modified by the target PR with addition/deletion metrics."""
    query = """
    MATCH (pr:PullRequest {number: $pr_number})-[m:MODIFIES]->(f:File)
    RETURN f.path AS path,
           f.url AS url,
           m.additions AS additions,
           m.deletions AS deletions
    ORDER BY f.path ASC
    """
    res = client.ro_query(query, {"pr_number": pr_number})
    files = []
    if res and res.result_set:
        for row in res.result_set:
            files.append(
                {
                    "path": row[0],
                    "url": row[1],
                    "additions": row[2] or 0,
                    "deletions": row[3] or 0,
                }
            )
    return files


def find_historical_reviewers(
    client: FalkorDBClient,
    file_paths: List[str],
    exclude_pr_number: int,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Find historical reviewers for changed files across OTHER PRs (excluding target PR)."""
    if not file_paths:
        return []

    query = """
    MATCH (f:File)<-[:MODIFIES]-(prior_pr:PullRequest)<-[r:REVIEWED]-(p:Person)
    WHERE f.path IN $file_paths AND prior_pr.number <> $exclude_pr
    RETURN p.login AS reviewer,
           p.url AS reviewer_url,
           count(DISTINCT prior_pr) AS prior_pr_count,
           collect(DISTINCT prior_pr.url)[0..5] AS evidence_pr_urls,
           collect(DISTINCT r.state) AS review_states
    ORDER BY prior_pr_count DESC, p.login ASC
    LIMIT $limit
    """
    res = client.ro_query(
        query,
        {
            "file_paths": file_paths,
            "exclude_pr": exclude_pr_number,
            "limit": limit,
        },
    )
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


def find_related_co_changes(
    client: FalkorDBClient,
    file_paths: List[str],
    exclude_pr_number: int,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Identify files historically co-modified with touched files in prior PRs."""
    if not file_paths:
        return []

    query = """
    MATCH (f1:File)<-[:MODIFIES]-(prior_pr:PullRequest)-[:MODIFIES]->(f2:File)
    WHERE f1.path IN $file_paths
      AND NOT f2.path IN $file_paths
      AND prior_pr.number <> $exclude_pr
    RETURN f1.path AS primary_file,
           f2.path AS co_changed_file,
           count(DISTINCT prior_pr) AS co_change_count,
           collect(DISTINCT prior_pr.url)[0..5] AS evidence_pr_urls
    ORDER BY co_change_count DESC, f2.path ASC
    LIMIT $limit
    """
    res = client.ro_query(
        query,
        {
            "file_paths": file_paths,
            "exclude_pr": exclude_pr_number,
            "limit": limit,
        },
    )
    signals = []
    if res and res.result_set:
        for row in res.result_set:
            signals.append(
                {
                    "primary_file": row[0],
                    "co_changed_file": row[1],
                    "co_change_count": row[2],
                    "evidence_pr_urls": row[3] or [],
                }
            )
    return signals


def audit_ownership_for_files(
    client: FalkorDBClient,
    file_paths: List[str],
    codeowners: Optional[CodeownersParser] = None,
    cutoff_timestamp: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Evaluate declared CODEOWNERS and ownership drift for all changed files."""
    parser = codeowners or CodeownersParser.from_cache_or_default()
    audits = []
    for fp in file_paths:
        rep = evaluate_ownership_discrepancy(
            client, fp, parser, cutoff_timestamp=cutoff_timestamp
        )
        audits.append(rep.to_dict())
    return audits


class ToolPermissionError(PermissionError):
    """Raised when an unrecognized tool or prohibited write operation is attempted."""
    pass


ALLOWED_INVESTIGATION_TOOLS = {
    "lookup_pr_details": lookup_pr_details,
    "lookup_linked_issues": lookup_linked_issues,
    "lookup_changed_files": lookup_changed_files,
    "find_historical_reviewers": find_historical_reviewers,
    "find_related_co_changes": find_related_co_changes,
    "audit_ownership_for_files": audit_ownership_for_files,
}


def validate_and_invoke_tool(
    client: FalkorDBClient,
    tool_name: str,
    arguments: Dict[str, Any],
) -> Any:
    """Validate tool name and arguments against strict schema before invocation.

    Protection Boundary:
    - Rejects any unknown or unlisted tool.
    - Explicitly blocks any graph-writing, cypher-execution, or mutation operations.
    - Ensures all executed investigation tools are strictly read-only allowlisted functions.
    """
    if tool_name not in ALLOWED_INVESTIGATION_TOOLS:
        raise ToolPermissionError(
            f"Unauthorized tool execution rejected: '{tool_name}'. "
            f"Only read-only investigation tools are permitted. Write operations are strictly disallowed."
        )

    # Argument validation against strict schemas
    if tool_name in ("lookup_pr_details", "lookup_linked_issues", "lookup_changed_files"):
        if "pr_number" not in arguments or not isinstance(arguments["pr_number"], int):
            raise ValueError(f"Tool '{tool_name}' requires integer 'pr_number' argument.")
        return ALLOWED_INVESTIGATION_TOOLS[tool_name](client, arguments["pr_number"])

    if tool_name in ("find_historical_reviewers", "find_related_co_changes"):
        if "file_paths" not in arguments or not isinstance(arguments["file_paths"], list):
            raise ValueError(f"Tool '{tool_name}' requires list of strings 'file_paths'.")
        if "exclude_pr_number" not in arguments or not isinstance(arguments["exclude_pr_number"], int):
            raise ValueError(f"Tool '{tool_name}' requires integer 'exclude_pr_number'.")
        limit = int(arguments.get("limit", 5))
        return ALLOWED_INVESTIGATION_TOOLS[tool_name](
            client,
            file_paths=arguments["file_paths"],
            exclude_pr_number=arguments["exclude_pr_number"],
            limit=limit,
        )

    if tool_name == "audit_ownership_for_files":
        if "file_paths" not in arguments or not isinstance(arguments["file_paths"], list):
            raise ValueError("Tool 'audit_ownership_for_files' requires list 'file_paths'.")
        return audit_ownership_for_files(
            client,
            file_paths=arguments["file_paths"],
            codeowners=arguments.get("codeowners"),
            cutoff_timestamp=arguments.get("cutoff_timestamp"),
        )

