"""Evidence-based KNOWS score calculation and knowledge intelligence.

Implements the specification from AGENT_BRIEF:
    KNOWS.score = sum(weight * exp(-age / half_life))

Weights:
    - Authored activity: weight 3.0
    - Reviewed activity: weight 2.0
    - Commented activity: weight 1.0
    - Half-life: 90.0 days

Constraints:
    - Bots excluded from human expertise calculations.
    - Reference timestamp is the requested `as_of` date.
    - Valid, non-empty activity timestamps only (future events > as_of excluded).
    - Prevents double-counting by deduplicating distinct PRs, reviews, and comments.
    - Fully explainable and inspectable breakdown of contributions.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient
from src.knowledge.temporal import normalize_utc_timestamp, parse_utc_datetime


AUTHORED_WEIGHT = 3.0
REVIEWED_WEIGHT = 2.0
COMMENTED_WEIGHT = 1.0
DEFAULT_HALF_LIFE_DAYS = 90.0


def is_bot_account(login: str) -> bool:
    """Check if account is an automated bot or service account."""
    if not login or not isinstance(login, str):
        return True
    l_lower = login.lower().strip()
    return (
        l_lower.endswith("[bot]")
        or l_lower in ("github-actions", "dependabot", "github-actions[bot]", "codecov[bot]")
    )


@dataclass
class ActivityContribution:
    """A single inspectable activity contribution to a KNOWS score."""
    activity_type: str  # "authored", "reviewed", "commented"
    activity_id: str  # PR number, review ID, or comment ID
    weight: float
    timestamp: str
    age_days: float
    decay_factor: float
    decayed_score: float
    source_url: Optional[str] = None


@dataclass
class KnowledgeScore:
    """Structured, explainable knowledge score for a person on a repository entity."""
    person_login: str
    target_entity: str  # File path or module
    score: float  # sum of decayed scores
    raw_score: float  # sum of un-decayed weights
    authored_count: int
    reviewed_count: int
    commented_count: int
    total_activities: int
    last_active: Optional[str]
    as_of: str
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS
    contributions: List[ActivityContribution] = field(default_factory=list)
    evidence_urls: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert score to dictionary."""
        d = asdict(self)
        d["contributions"] = [asdict(c) for c in self.contributions]
        return d


def calculate_knows_for_file(
    client: FalkorDBClient,
    file_path: str,
    as_of: Optional[str] = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    include_bots: bool = False,
) -> List[KnowledgeScore]:
    """Calculate KNOWS scores for all contributors to a file as of a given timestamp.

    Returns ranked list of KnowledgeScore objects sorted by decayed score descending.
    """
    norm_as_of = normalize_utc_timestamp(as_of)
    ref_dt = (
        parse_utc_datetime(norm_as_of)
        if norm_as_of
        else datetime.now(timezone.utc)
    )
    as_of_str = norm_as_of or ref_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Collect authored PRs for file
    author_query = """
    MATCH (f:File {path: $file_path})<-[m:MODIFIES]-(pr:PullRequest)<-[:AUTHORED]-(p:Person)
    WHERE pr.merged_at IS NOT NULL AND pr.merged_at <> ''
    RETURN p.login AS login, pr.number AS pr_number, pr.merged_at AS timestamp, pr.url AS source_url
    """
    author_res = client.ro_query(author_query, {"file_path": file_path})

    # 2. Collect reviews for file
    review_query = """
    MATCH (f:File {path: $file_path})<-[:MODIFIES]-(pr:PullRequest)<-[r:REVIEWED]-(p:Person)
    WHERE pr.merged_at IS NOT NULL AND pr.merged_at <> ''
      AND r.submitted_at IS NOT NULL AND r.submitted_at <> ''
    RETURN p.login AS login, pr.number AS pr_number, coalesce(r.id, pr.number) AS review_id,
           r.submitted_at AS timestamp, pr.url AS source_url
    """
    review_res = client.ro_query(review_query, {"file_path": file_path})

    # 3. Collect comments on PRs modifying the file
    comment_query = """
    MATCH (f:File {path: $file_path})<-[:MODIFIES]-(pr:PullRequest)<-[:ON]-(c:Comment)<-[:AUTHORED]-(p:Person)
    WHERE c.created_at IS NOT NULL AND c.created_at <> ''
    RETURN p.login AS login, pr.number AS pr_number, c.id AS comment_id,
           c.created_at AS timestamp, coalesce(c.url, c.source_url, pr.url) AS source_url
    """
    comment_res = client.ro_query(comment_query, {"file_path": file_path})

    # Aggregator per person
    person_activities: Dict[str, Dict[str, Any]] = {}

    def _get_bucket(login: str) -> Dict[str, Any]:
        if login not in person_activities:
            person_activities[login] = {
                "authored": {},
                "reviewed": {},
                "commented": {},
            }
        return person_activities[login]

    # Process authored PRs
    if author_res and author_res.result_set:
        for row in author_res.result_set:
            login, pr_num, ts, url = row[0], int(row[1]), str(row[2]), row[3]
            if not include_bots and is_bot_account(login):
                continue
            norm_ts = normalize_utc_timestamp(ts)
            if not norm_ts or (norm_as_of and norm_ts > norm_as_of):
                continue
            bucket = _get_bucket(login)
            if pr_num not in bucket["authored"]:
                bucket["authored"][pr_num] = {"timestamp": norm_ts, "url": url}

    # Process reviews
    if review_res and review_res.result_set:
        for row in review_res.result_set:
            login, pr_num, rev_id, ts, url = row[0], int(row[1]), str(row[2]), str(row[3]), row[4]
            if not include_bots and is_bot_account(login):
                continue
            norm_ts = normalize_utc_timestamp(ts)
            if not norm_ts or (norm_as_of and norm_ts > norm_as_of):
                continue
            bucket = _get_bucket(login)
            key = f"{pr_num}_{rev_id}"
            if key not in bucket["reviewed"]:
                bucket["reviewed"][key] = {"timestamp": norm_ts, "url": url, "pr_number": pr_num}

    # Process comments
    if comment_res and comment_res.result_set:
        for row in comment_res.result_set:
            login, pr_num, comm_id, ts, url = row[0], int(row[1]), str(row[2]), str(row[3]), row[4]
            if not include_bots and is_bot_account(login):
                continue
            norm_ts = normalize_utc_timestamp(ts)
            if not norm_ts or (norm_as_of and norm_ts > norm_as_of):
                continue
            bucket = _get_bucket(login)
            if comm_id not in bucket["commented"]:
                bucket["commented"][comm_id] = {"timestamp": norm_ts, "url": url, "pr_number": pr_num}

    scores: List[KnowledgeScore] = []

    for login, acts in person_activities.items():
        contributions: List[ActivityContribution] = []
        raw_score = 0.0
        decayed_total = 0.0
        latest_ts: Optional[str] = None

        # 1. Authored contributions
        for pr_num, data in acts["authored"].items():
            ts = data["timestamp"]
            url = data["url"]
            dt = parse_utc_datetime(ts)
            if not dt:
                continue
            age_days = max(0.0, (ref_dt - dt).total_seconds() / 86400.0)
            decay = math.exp(-age_days / half_life_days)
            contrib_score = AUTHORED_WEIGHT * decay
            contributions.append(ActivityContribution(
                activity_type="authored",
                activity_id=f"pr_{pr_num}",
                weight=AUTHORED_WEIGHT,
                timestamp=ts,
                age_days=round(age_days, 2),
                decay_factor=round(decay, 6),
                decayed_score=round(contrib_score, 4),
                source_url=url,
            ))
            raw_score += AUTHORED_WEIGHT
            decayed_total += contrib_score
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts

        # 2. Reviewed contributions
        for rev_key, data in acts["reviewed"].items():
            ts = data["timestamp"]
            url = data["url"]
            dt = parse_utc_datetime(ts)
            if not dt:
                continue
            age_days = max(0.0, (ref_dt - dt).total_seconds() / 86400.0)
            decay = math.exp(-age_days / half_life_days)
            contrib_score = REVIEWED_WEIGHT * decay
            contributions.append(ActivityContribution(
                activity_type="reviewed",
                activity_id=rev_key,
                weight=REVIEWED_WEIGHT,
                timestamp=ts,
                age_days=round(age_days, 2),
                decay_factor=round(decay, 6),
                decayed_score=round(contrib_score, 4),
                source_url=url,
            ))
            raw_score += REVIEWED_WEIGHT
            decayed_total += contrib_score
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts

        # 3. Commented contributions
        for comm_id, data in acts["commented"].items():
            ts = data["timestamp"]
            url = data["url"]
            dt = parse_utc_datetime(ts)
            if not dt:
                continue
            age_days = max(0.0, (ref_dt - dt).total_seconds() / 86400.0)
            decay = math.exp(-age_days / half_life_days)
            contrib_score = COMMENTED_WEIGHT * decay
            contributions.append(ActivityContribution(
                activity_type="commented",
                activity_id=f"comment_{comm_id}",
                weight=COMMENTED_WEIGHT,
                timestamp=ts,
                age_days=round(age_days, 2),
                decay_factor=round(decay, 6),
                decayed_score=round(contrib_score, 4),
                source_url=url,
            ))
            raw_score += COMMENTED_WEIGHT
            decayed_total += contrib_score
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts

        if not contributions:
            continue

        evidence_urls = list(dict.fromkeys(c.source_url for c in contributions if c.source_url))

        scores.append(KnowledgeScore(
            person_login=login,
            target_entity=file_path,
            score=round(decayed_total, 4),
            raw_score=round(raw_score, 2),
            authored_count=len(acts["authored"]),
            reviewed_count=len(acts["reviewed"]),
            commented_count=len(acts["commented"]),
            total_activities=len(contributions),
            last_active=latest_ts,
            as_of=as_of_str,
            half_life_days=half_life_days,
            contributions=contributions,
            evidence_urls=evidence_urls,
        ))

    # Deterministic sorting: score DESC, raw_score DESC, login ASC
    scores.sort(key=lambda s: (-s.score, -s.raw_score, s.person_login))
    return scores


def calculate_knows_for_person(
    client: FalkorDBClient,
    person_login: str,
    as_of: Optional[str] = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> List[KnowledgeScore]:
    """Calculate KNOWS scores across all files modified or reviewed by a specific person."""
    if is_bot_account(person_login):
        return []

    # Find all files where this person has authored, reviewed, or commented
    query = """
    MATCH (p:Person {login: $login})-[:AUTHORED|REVIEWED]->(pr:PullRequest)-[:MODIFIES]->(f:File)
    RETURN DISTINCT f.path AS file_path
    """
    res = client.ro_query(query, {"login": person_login})
    file_scores: List[KnowledgeScore] = []
    if res and res.result_set:
        for row in res.result_set:
            file_path = str(row[0])
            scores = calculate_knows_for_file(
                client=client,
                file_path=file_path,
                as_of=as_of,
                half_life_days=half_life_days,
            )
            for sc in scores:
                if sc.person_login == person_login:
                    file_scores.append(sc)
                    break

    file_scores.sort(key=lambda s: (-s.score, s.target_entity))
    return file_scores


def get_top_experts_for_file(
    client: FalkorDBClient,
    file_path: str,
    top_k: int = 3,
    as_of: Optional[str] = None,
) -> List[KnowledgeScore]:
    """Get the top-K human experts for a specific file based on decayed KNOWS score."""
    scores = calculate_knows_for_file(client, file_path, as_of=as_of)
    return scores[:top_k]
