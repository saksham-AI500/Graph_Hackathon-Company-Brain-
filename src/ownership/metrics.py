"""Observed repository activity metrics: authorship, reviews, and reviewer concentration."""

from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient


def get_file_authorship(
    client: FalkorDBClient,
    file_path: str,
    include_bots: bool = False,
    cutoff_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve historical authorship by file, supporting PRs, and public source URLs."""
    from src.evaluation.temporal import normalize_utc_timestamp
    norm_cutoff = normalize_utc_timestamp(cutoff_timestamp) if cutoff_timestamp else None

    if norm_cutoff:
        query = """
        MATCH (f:File {path: $file_path})<-[m:MODIFIES]-(pr:PullRequest)<-[:AUTHORED]-(p:Person)
        WHERE pr.merged_at IS NOT NULL AND pr.merged_at <> '' AND pr.merged_at <= $cutoff
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
        params = {"file_path": file_path, "cutoff": norm_cutoff}
    else:
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
        params = {"file_path": file_path}
    res = client.ro_query(query, params)
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
    cutoff_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve historical review activity by file, review states, supporting PRs, and source URLs."""
    from src.evaluation.temporal import normalize_utc_timestamp
    norm_cutoff = normalize_utc_timestamp(cutoff_timestamp) if cutoff_timestamp else None

    if norm_cutoff:
        query = """
        MATCH (f:File {path: $file_path})<-[:MODIFIES]-(pr:PullRequest)<-[r:REVIEWED]-(p:Person)
        WHERE pr.merged_at IS NOT NULL AND pr.merged_at <> '' AND pr.merged_at <= $cutoff
          AND r.submitted_at IS NOT NULL AND r.submitted_at <> '' AND r.submitted_at <= $cutoff
        RETURN p.login AS reviewer,
               p.url AS reviewer_url,
               count(r) AS review_count,
               collect(DISTINCT pr.number) AS pr_numbers,
               collect(DISTINCT pr.url) AS pr_urls,
               collect(r.state) AS review_states
        ORDER BY review_count DESC
        """
        params = {"file_path": file_path, "cutoff": norm_cutoff}
    else:
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
        params = {"file_path": file_path}
    res = client.ro_query(query, params)
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
    cutoff_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Calculate reviewer concentration (Herfindahl-Hirschman Index / Share) on human reviews."""
    review_data = get_file_review_activity(
        client, file_path, include_bots=False, cutoff_timestamp=cutoff_timestamp
    )
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


from dataclasses import dataclass, field


@dataclass
class BusFactorReport:
    """Detailed explainability report for bus-factor calculation."""
    bus_factor: int
    total_decayed_activity: float
    threshold_50_percent: float
    contributor_count: int
    key_contributors: List[str]
    ranked_contributors: List[Dict[str, Any]]
    risk_level: str  # HIGH, MEDIUM, LOW
    is_insufficient_evidence: bool
    half_life_days: float = 180.0
    cutoff_timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bus_factor": self.bus_factor,
            "total_decayed_activity": round(self.total_decayed_activity, 4),
            "threshold_50_percent": round(self.threshold_50_percent, 4),
            "contributor_count": self.contributor_count,
            "key_contributors": self.key_contributors,
            "ranked_contributors": self.ranked_contributors,
            "risk_level": self.risk_level,
            "is_insufficient_evidence": self.is_insufficient_evidence,
            "half_life_days": self.half_life_days,
            "cutoff_timestamp": self.cutoff_timestamp,
        }


def calculate_bus_factor_detailed(
    contributions: List[Dict[str, Any]],
    cutoff_timestamp: Optional[str] = None,
    half_life_days: float = 180.0,
) -> BusFactorReport:
    """Calculate bus factor with full explainability of contributors, scores, and risks."""
    from datetime import datetime, timezone
    from src.evaluation.temporal import normalize_utc_timestamp

    norm_cutoff = normalize_utc_timestamp(cutoff_timestamp) if cutoff_timestamp else None
    ref_dt = (
        datetime.fromisoformat(norm_cutoff.replace("Z", "+00:00"))
        if norm_cutoff
        else datetime.now(timezone.utc)
    )

    decayed_by_person: Dict[str, float] = {}

    for item in contributions:
        login = item.get("author") or item.get("login") or item.get("contributor") or ""
        if not login:
            continue

        # Exclude bot accounts
        is_bot = (
            item.get("is_bot")
            or login.endswith("[bot]")
            or login.lower() in ("github-actions", "dependabot", "github-actions[bot]", "codecov[bot]")
        )
        if is_bot:
            continue

        weight = float(item.get("weight", 1.0))
        ts_str = item.get("timestamp") or item.get("merged_at") or item.get("submitted_at")
        norm_ts = normalize_utc_timestamp(ts_str) if ts_str else None

        decay = 1.0
        if norm_ts and ref_dt:
            try:
                item_dt = datetime.fromisoformat(norm_ts.replace("Z", "+00:00"))
                if norm_cutoff and norm_ts > norm_cutoff:
                    continue
                diff_days = max(0.0, (ref_dt - item_dt).total_seconds() / 86400.0)
                decay = 0.5 ** (diff_days / half_life_days)
            except Exception:
                decay = 1.0

        decayed_val = weight * decay
        decayed_by_person[login] = decayed_by_person.get(login, 0.0) + decayed_val

    total_decayed = sum(decayed_by_person.values())
    if total_decayed <= 0.0:
        return BusFactorReport(
            bus_factor=0,
            total_decayed_activity=0.0,
            threshold_50_percent=0.0,
            contributor_count=0,
            key_contributors=[],
            ranked_contributors=[],
            risk_level="HIGH",
            is_insufficient_evidence=True,
            half_life_days=half_life_days,
            cutoff_timestamp=norm_cutoff,
        )

    threshold = 0.5 * total_decayed
    # Deterministic sorting: decayed amount DESC, login ASC
    sorted_contributors = sorted(
        decayed_by_person.items(), key=lambda kv: (-kv[1], kv[0])
    )

    ranked: List[Dict[str, Any]] = []
    cumulative = 0.0
    key_contributors: List[str] = []
    bf = len(sorted_contributors)

    for idx, (login, amount) in enumerate(sorted_contributors, start=1):
        cumulative += amount
        pct = (amount / total_decayed) * 100.0
        cum_pct = (cumulative / total_decayed) * 100.0
        ranked.append({
            "rank": idx,
            "login": login,
            "decayed_score": round(amount, 4),
            "share_percent": round(pct, 2),
            "cumulative_share_percent": round(cum_pct, 2),
        })
        if not key_contributors:
            key_contributors.append(login)
        elif cumulative - amount <= threshold:
            key_contributors.append(login)

        if cumulative > threshold and bf == len(sorted_contributors):
            bf = idx

    # Risk level semantics:
    # 0 or 1 person monopoly -> HIGH risk
    # 2 persons -> MEDIUM risk
    # 3+ persons -> LOW risk
    if bf <= 1:
        risk_level = "HIGH"
    elif bf == 2:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return BusFactorReport(
        bus_factor=bf,
        total_decayed_activity=round(total_decayed, 4),
        threshold_50_percent=round(threshold, 4),
        contributor_count=len(sorted_contributors),
        key_contributors=key_contributors,
        ranked_contributors=ranked,
        risk_level=risk_level,
        is_insufficient_evidence=False,
        half_life_days=half_life_days,
        cutoff_timestamp=norm_cutoff,
    )


def calculate_bus_factor(
    contributions: List[Dict[str, Any]],
    cutoff_timestamp: Optional[str] = None,
    half_life_days: float = 180.0,
) -> int:
    """Calculate the bus factor for a repository module or entity.

    Definition from AGENT_BRIEF: The fewest people whose contributions
    cover more than 50% of decayed contributions.
    Automated bot accounts are strictly excluded.
    """
    report = calculate_bus_factor_detailed(
        contributions=contributions,
        cutoff_timestamp=cutoff_timestamp,
        half_life_days=half_life_days,
    )
    return report.bus_factor

