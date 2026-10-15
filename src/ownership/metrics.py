"""Observed repository activity metrics: authorship, reviews, and reviewer concentration."""

from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient


def get_file_authorship(
    client: FalkorDBClient,
    file_path: str,
    include_bots: bool = False,
) -> Dict[str, Any]:
    """Retrieve historical authorship by file, supporting PRs, and public source URLs."""
    query = """
    MATCH (f:File {path: $file_path})<-[m:MODIFIES]-(pr:PullRequest)<-[:AUTHORED]-(p:Person)
    RETURN p.login AS author,
           p.url AS author_url,
           count(DISTINCT pr) AS pr_count,
           collect(DISTINCT {
               number: pr.number,
               title: pr.title,
               url: pr.url,
               merged_at: pr.merged_at
           }) AS prs,
           sum(m.additions) AS total_additions,
           sum(m.deletions) AS total_deletions
    ORDER BY pr_count DESC
    """
    res = client.ro_query(query, {"file_path": file_path})
    records: List[Dict[str, Any]] = []
    total_human_prs = 0
    total_bot_prs = 0

    if res and res.result_set:
        for row in res.result_set:
            login = row[0]
            url = row[1]
            pr_cnt = row[2]
            pr_list = row[3] or []
            additions = row[4] or 0
            deletions = row[5] or 0
            is_bot = login.endswith("[bot]") or login.lower() == "github-actions[bot]"

            if is_bot:
                total_bot_prs += pr_cnt
            else:
                total_human_prs += pr_cnt

            if not include_bots and is_bot:
                continue

            records.append(
                {
                    "author": login,
                    "author_url": url,
                    "is_bot": is_bot,
                    "pr_count": pr_cnt,
                    "additions": additions,
                    "deletions": deletions,
                    "prs": pr_list,
                }
            )

    return {
        "file_path": file_path,
        "include_bots": include_bots,
        "total_human_prs": total_human_prs,
        "total_bot_prs": total_bot_prs,
        "authors": records,
    }


def get_file_review_activity(
    client: FalkorDBClient,
    file_path: str,
    include_bots: bool = False,
) -> Dict[str, Any]:
    """Retrieve historical review activity by file, review states, supporting PRs, and source URLs."""
    query = """
    MATCH (f:File {path: $file_path})<-[:MODIFIES]-(pr:PullRequest)<-[r:REVIEWED]-(p:Person)
    RETURN p.login AS reviewer,
           p.url AS reviewer_url,
           count(r) AS review_count,
           collect(DISTINCT pr.number) AS pr_numbers,
           collect(DISTINCT pr.url) AS pr_urls,
           collect(r.state) AS review_states
    ORDER BY review_count DESC
    """
    res = client.ro_query(query, {"file_path": file_path})
    records: List[Dict[str, Any]] = []
    total_human_reviews = 0
    total_bot_reviews = 0

    if res and res.result_set:
        for row in res.result_set:
            login = row[0]
            url = row[1]
            rev_cnt = row[2]
            pr_nums = row[3] or []
            pr_urls = row[4] or []
            states = row[5] or []
            is_bot = login.endswith("[bot]") or login.lower() == "github-actions[bot]"

            if is_bot:
                total_bot_reviews += rev_cnt
            else:
                total_human_reviews += rev_cnt

            if not include_bots and is_bot:
                continue

            records.append(
                {
                    "reviewer": login,
                    "reviewer_url": url,
                    "is_bot": is_bot,
                    "review_count": rev_cnt,
                    "pr_numbers": pr_nums,
                    "pr_urls": pr_urls,
                    "review_states": states,
                }
            )

    return {
        "file_path": file_path,
        "include_bots": include_bots,
        "total_human_reviews": total_human_reviews,
        "total_bot_reviews": total_bot_reviews,
        "reviewers": records,
    }


def get_reviewer_concentration(
    client: FalkorDBClient,
    file_path: str,
) -> Dict[str, Any]:
    """Calculate reviewer concentration (Herfindahl-Hirschman Index / Share) on human reviews."""
    review_data = get_file_review_activity(client, file_path, include_bots=False)
    human_reviewers = review_data["reviewers"]
    total_reviews = review_data["total_human_reviews"]

    if total_reviews == 0:
        return {
            "file_path": file_path,
            "total_human_reviews": 0,
            "concentration_hhi": 0.0,
            "top_reviewer": None,
            "top_reviewer_share": 0.0,
            "distribution": {},
        }

    distribution: Dict[str, float] = {}
    hhi = 0.0
    for rev in human_reviewers:
        share = rev["review_count"] / total_reviews
        distribution[rev["reviewer"]] = round(share, 3)
        hhi += share ** 2

    top_reviewer = human_reviewers[0]["reviewer"] if human_reviewers else None
    top_share = distribution.get(top_reviewer, 0.0) if top_reviewer else 0.0

    return {
        "file_path": file_path,
        "total_human_reviews": total_reviews,
        "concentration_hhi": round(hhi, 3),  # 1.0 = single reviewer monopoly
        "top_reviewer": top_reviewer,
        "top_reviewer_share": top_share,
        "distribution": distribution,
    }
