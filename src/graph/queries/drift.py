"""Ownership Drift detection query for FalkorDB repo_kg.

Calculates divergence between historical code authors and recent PR reviewers
for any file or module, detecting single-maintainer risks (bus factor) and
unbalanced review responsibilities with auditable evidence paths.
"""

from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient


def detect_ownership_drift(
    client: FalkorDBClient, file_path: str
) -> Dict[str, Any]:
    """Detect author vs. reviewer divergence, bus factor, and drift metrics for a file."""
    # Query all PRs touching this file with authors and reviewers
    query = """
    MATCH (f:File {path: $file_path})<-[:MODIFIES]-(pr:PullRequest)
    OPTIONAL MATCH (pr)<-[:AUTHORED]-(a:Person)
    OPTIONAL MATCH (pr)<-[r:REVIEWED]-(rev:Person)
    RETURN pr.number AS pr_number,
           pr.title AS pr_title,
           pr.url AS pr_url,
           pr.merged_at AS merged_at,
           collect(DISTINCT {login: a.login, url: a.url}) AS authors,
           collect(DISTINCT {login: rev.login, url: rev.url, state: r.state}) AS reviewers
    ORDER BY pr.number DESC
    """
    res = client.ro_query(query, {"file_path": file_path})

    if not res or not res.result_set:
        return {
            "file_path": file_path,
            "status": "not_found",
            "message": "Evidence path not found: file has no recorded PRs in repo_kg",
            "bus_factor": 0,
            "drift_score": 0.0,
            "authors": {},
            "reviewers": {},
            "evidence_prs": [],
        }

    author_touches: Dict[str, int] = {}
    author_urls: Dict[str, str] = {}
    reviewer_touches: Dict[str, int] = {}
    reviewer_urls: Dict[str, str] = {}
    evidence_prs: List[Dict[str, Any]] = []

    for row in res.result_set:
        pr_num = row[0]
        pr_title = row[1]
        pr_url = row[2]
        merged_at = row[3]
        authors = row[4] or []
        reviewers = row[5] or []

        pr_authors = []
        for a in authors:
            if a and a.get("login"):
                login = a["login"]
                pr_authors.append(login)
                author_touches[login] = author_touches.get(login, 0) + 1
                author_urls[login] = a.get("url", "")

        pr_reviewers = []
        for r in reviewers:
            if r and r.get("login"):
                login = r["login"]
                pr_reviewers.append(login)
                reviewer_touches[login] = reviewer_touches.get(login, 0) + 1
                reviewer_urls[login] = r.get("url", "")

        evidence_prs.append(
            {
                "pr_number": pr_num,
                "title": pr_title,
                "url": pr_url,
                "merged_at": merged_at,
                "authors": pr_authors,
                "reviewers": pr_reviewers,
            }
        )

    # Calculate human maintainers vs bots
    human_authors = [
        login for login in author_touches if not login.endswith("[bot]")
    ]
    human_reviewers = [
        login for login in reviewer_touches if not login.endswith("[bot]")
    ]

    all_authors_set = set(author_touches.keys())
    all_reviewers_set = set(reviewer_touches.keys())

    # Divergence analysis
    reviewers_without_authorship = list(all_reviewers_set - all_authors_set)
    authors_without_reviews = list(all_authors_set - all_reviewers_set)

    # Drift score: 1.0 - (Jaccard similarity of author set and reviewer set)
    union_set = all_authors_set.union(all_reviewers_set)
    intersection_set = all_authors_set.intersection(all_reviewers_set)

    jaccard = (
        len(intersection_set) / len(union_set) if len(union_set) > 0 else 1.0
    )
    drift_score = round(1.0 - jaccard, 2)

    # Bus factor based on human authors
    bus_factor = len(human_authors)
    risk_level = "HIGH" if bus_factor <= 1 else ("MEDIUM" if bus_factor == 2 else "LOW")

    return {
        "file_path": file_path,
        "status": "analyzed",
        "total_prs": len(evidence_prs),
        "bus_factor": bus_factor,
        "risk_level": risk_level,
        "drift_score": drift_score,
        "human_authors": human_authors,
        "human_reviewers": human_reviewers,
        "author_touches": author_touches,
        "reviewer_touches": reviewer_touches,
        "reviewers_without_authorship": reviewers_without_authorship,
        "authors_without_reviews": authors_without_reviews,
        "evidence_prs": evidence_prs,
    }
