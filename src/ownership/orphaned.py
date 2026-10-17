"""Orphaned and inactive declared ownership detection in FalkorDB repo_kg.

Identifies CODEOWNERS rules whose declared owners have been inactive for a
configurable number of days relative to an `as_of` temporal cutoff.

Guarantees:
- Inactivity is calculated strictly relative to `as_of`.
- Excludes bot accounts from human-owner checks.
- Uses actual authorship, review, or comment evidence from graph.
- Distinguishes "INACTIVE_OWNER" from "NO_OBSERVED_ACTIVITY" and "UNRESOLVED_TIMESTAMPS".
- Non-destructive: preserves CODEOWNERS declarations and graph relationships intact.
- Configurable threshold (default: 90.0 days).
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient
from src.knowledge.scoring import is_bot_account
from src.knowledge.temporal import normalize_utc_timestamp, parse_utc_datetime


DEFAULT_INACTIVITY_THRESHOLD_DAYS = 90.0


@dataclass
class OrphanedOwnerFinding:
    """Findings for a declared owner and their covered files."""
    owner_name: str
    is_team: bool
    rule_pattern: str
    rule_line: Optional[int]
    rule_source_url: Optional[str]
    covered_files_count: int
    covered_files_sample: List[str]
    last_active: Optional[str]
    days_inactive: Optional[float]
    inactivity_threshold_days: float = DEFAULT_INACTIVITY_THRESHOLD_DAYS
    status: str = "ACTIVE"  # "ACTIVE", "INACTIVE_OWNER", "NO_OBSERVED_ACTIVITY", "UNRESOLVED_TIMESTAMPS"
    supporting_evidence_urls: List[str] = field(default_factory=list)
    as_of: Optional[str] = None
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrphanedOwnershipReport:
    """Aggregated report of declared ownership activity across the repository."""
    as_of: str
    inactivity_threshold_days: float
    total_rules_audited: int
    active_owners_count: int
    inactive_owners_count: int
    no_activity_count: int
    unresolved_count: int
    findings: List[OrphanedOwnerFinding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "inactivity_threshold_days": self.inactivity_threshold_days,
            "total_rules_audited": self.total_rules_audited,
            "active_owners_count": self.active_owners_count,
            "inactive_owners_count": self.inactive_owners_count,
            "no_activity_count": self.no_activity_count,
            "unresolved_count": self.unresolved_count,
            "findings": [f.to_dict() for f in self.findings],
        }


def get_person_last_activity(
    client: FalkorDBClient,
    login: str,
    as_of: Optional[str] = None,
) -> Tuple_Activity:
    """Retrieve the latest observed activity timestamp and source URL for a person prior to as_of."""
    norm_as_of = normalize_utc_timestamp(as_of)

    latest_ts: Optional[str] = None
    latest_url: Optional[str] = None

    # 1. Authored PRs
    author_q = """
    MATCH (p:Person {login: $login})-[:AUTHORED]->(pr:PullRequest)
    WHERE pr.merged_at IS NOT NULL AND pr.merged_at <> ''
    RETURN pr.merged_at AS ts, pr.url AS url
    ORDER BY pr.merged_at DESC
    """
    res = client.ro_query(author_q, {"login": login})
    if res and res.result_set:
        for row in res.result_set:
            ts, url = str(row[0]), row[1]
            nts = normalize_utc_timestamp(ts)
            if nts and (not norm_as_of or nts <= norm_as_of):
                if latest_ts is None or nts > latest_ts:
                    latest_ts = nts
                    latest_url = url
                break

    # 2. Reviews
    review_q = """
    MATCH (p:Person {login: $login})-[r:REVIEWED]->(pr:PullRequest)
    WHERE r.submitted_at IS NOT NULL AND r.submitted_at <> ''
    RETURN r.submitted_at AS ts, pr.url AS url
    ORDER BY r.submitted_at DESC
    """
    res = client.ro_query(review_q, {"login": login})
    if res and res.result_set:
        for row in res.result_set:
            ts, url = str(row[0]), row[1]
            nts = normalize_utc_timestamp(ts)
            if nts and (not norm_as_of or nts <= norm_as_of):
                if latest_ts is None or nts > latest_ts:
                    latest_ts = nts
                    latest_url = url
                break

    # 3. Comments
    comm_q = """
    MATCH (p:Person {login: $login})-[:AUTHORED]->(c:Comment)
    WHERE c.created_at IS NOT NULL AND c.created_at <> ''
    RETURN c.created_at AS ts, coalesce(c.url, c.source_url) AS url
    ORDER BY c.created_at DESC
    """
    res = client.ro_query(comm_q, {"login": login})
    if res and res.result_set:
        for row in res.result_set:
            ts, url = str(row[0]), row[1]
            nts = normalize_utc_timestamp(ts)
            if nts and (not norm_as_of or nts <= norm_as_of):
                if latest_ts is None or nts > latest_ts:
                    latest_ts = nts
                    latest_url = url
                break

    return latest_ts, latest_url


# Type alias for activity tuple
Tuple_Activity = tuple[Optional[str], Optional[str]]


def detect_orphaned_ownership(
    client: FalkorDBClient,
    inactivity_threshold_days: float = DEFAULT_INACTIVITY_THRESHOLD_DAYS,
    as_of: Optional[str] = None,
) -> OrphanedOwnershipReport:
    """Scan all declared CODEOWNERS rules in the graph and evaluate owner activity."""
    norm_as_of = normalize_utc_timestamp(as_of)
    ref_dt = parse_utc_datetime(norm_as_of) or datetime.now(timezone.utc)
    as_of_str = norm_as_of or ref_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fetch all OwnershipRule nodes and declared owners
    query = """
    MATCH (r:OwnershipRule)
    OPTIONAL MATCH (r)-[:DECLARES_OWNER]->(owner)
    OPTIONAL MATCH (r)-[:COVERS]->(f:File)
    RETURN r.pattern AS pattern, r.line_number AS line, r.source_url AS source_url,
           collect(DISTINCT coalesce(owner.name, owner.login)) AS owners,
           collect(DISTINCT f.path) AS covered_files
    ORDER BY r.pattern ASC
    """
    res = client.ro_query(query)
    findings: List[OrphanedOwnerFinding] = []

    active_count = 0
    inactive_count = 0
    no_activity_count = 0
    unresolved_count = 0
    total_rules = 0

    if res and res.result_set:
        for row in res.result_set:
            pattern = str(row[0])
            line = int(row[1]) if row[1] is not None else None
            source_url = row[2]
            owners = row[3] or []
            covered_files = row[4] or []
            total_rules += 1

            if not owners:
                # Rule with no declared owner in graph
                findings.append(OrphanedOwnerFinding(
                    owner_name="UNASSIGNED",
                    is_team=False,
                    rule_pattern=pattern,
                    rule_line=line,
                    rule_source_url=source_url,
                    covered_files_count=len(covered_files),
                    covered_files_sample=covered_files[:5],
                    last_active=None,
                    days_inactive=None,
                    inactivity_threshold_days=inactivity_threshold_days,
                    status="NO_OBSERVED_ACTIVITY",
                    supporting_evidence_urls=[u for u in [source_url] if u],
                    as_of=as_of_str,
                    explanation=f"Rule '{pattern}' has no declared owners linked in graph.",
                ))
                no_activity_count += 1
                continue

            for owner in owners:
                is_team = owner.startswith("@") and "/" in owner
                latest_ts: Optional[str] = None
                latest_url: Optional[str] = None

                if not is_team:
                    # Individual human owner
                    login = owner.lstrip("@")
                    if is_bot_account(login):
                        continue
                    latest_ts, latest_url = get_person_last_activity(client, login, as_of=as_of_str)
                else:
                    # Team owner: check if explicit members exist
                    member_q = """
                    MATCH (t:Team {name: $team})-[:HAS_MEMBER]->(m:Person)
                    RETURN m.login AS login
                    """
                    m_res = client.ro_query(member_q, {"team": owner})
                    team_members = [row[0] for row in m_res.result_set] if (m_res and m_res.result_set) else []

                    if team_members:
                        for tm in team_members:
                            tm_ts, tm_url = get_person_last_activity(client, tm, as_of=as_of_str)
                            if tm_ts and (latest_ts is None or tm_ts > latest_ts):
                                latest_ts = tm_ts
                                latest_url = tm_url
                    else:
                        # Team has no explicit members in graph: check observed reviewers of covered files
                        cov_q = """
                        MATCH (r:OwnershipRule {pattern: $pat})-[:COVERS]->(f:File)<-[:MODIFIES]-(pr:PullRequest)<-[rev:REVIEWED]-(p:Person)
                        WHERE rev.submitted_at IS NOT NULL AND rev.submitted_at <> ''
                        RETURN rev.submitted_at AS ts, pr.url AS url, p.login AS login
                        ORDER BY rev.submitted_at DESC
                        """
                        cov_res = client.ro_query(cov_q, {"pat": pattern})
                        if cov_res and cov_res.result_set:
                            for c_row in cov_res.result_set:
                                c_ts, c_url, c_login = str(c_row[0]), c_row[1], str(c_row[2])
                                if is_bot_account(c_login):
                                    continue
                                c_norm = normalize_utc_timestamp(c_ts)
                                if c_norm and (not norm_as_of or c_norm <= norm_as_of):
                                    latest_ts = c_norm
                                    latest_url = c_url
                                    break

                # Evaluate activity status
                if latest_ts:
                    act_dt = parse_utc_datetime(latest_ts)
                    if act_dt:
                        diff_days = round(max(0.0, (ref_dt - act_dt).total_seconds() / 86400.0), 2)
                        ev_urls = [u for u in [source_url, latest_url] if u]
                        if diff_days > inactivity_threshold_days:
                            status = "INACTIVE_OWNER"
                            explanation = (
                                f"Declared owner '{owner}' for rule '{pattern}' was last active {diff_days} days ago "
                                f"at {latest_ts} (exceeds threshold of {inactivity_threshold_days} days)."
                            )
                            inactive_count += 1
                        else:
                            status = "ACTIVE"
                            explanation = (
                                f"Declared owner '{owner}' for rule '{pattern}' is active ({diff_days} days since last activity at {latest_ts})."
                            )
                            active_count += 1

                        findings.append(OrphanedOwnerFinding(
                            owner_name=owner,
                            is_team=is_team,
                            rule_pattern=pattern,
                            rule_line=line,
                            rule_source_url=source_url,
                            covered_files_count=len(covered_files),
                            covered_files_sample=covered_files[:5],
                            last_active=latest_ts,
                            days_inactive=diff_days,
                            inactivity_threshold_days=inactivity_threshold_days,
                            status=status,
                            supporting_evidence_urls=ev_urls,
                            as_of=as_of_str,
                            explanation=explanation,
                        ))
                    else:
                        status = "UNRESOLVED_TIMESTAMPS"
                        unresolved_count += 1
                        findings.append(OrphanedOwnerFinding(
                            owner_name=owner,
                            is_team=is_team,
                            rule_pattern=pattern,
                            rule_line=line,
                            rule_source_url=source_url,
                            covered_files_count=len(covered_files),
                            covered_files_sample=covered_files[:5],
                            last_active=latest_ts,
                            days_inactive=None,
                            inactivity_threshold_days=inactivity_threshold_days,
                            status=status,
                            supporting_evidence_urls=[u for u in [source_url] if u],
                            as_of=as_of_str,
                            explanation="Invalid or unparseable activity timestamp.",
                        ))
                else:
                    status = "NO_OBSERVED_ACTIVITY"
                    no_activity_count += 1
                    findings.append(OrphanedOwnerFinding(
                        owner_name=owner,
                        is_team=is_team,
                        rule_pattern=pattern,
                        rule_line=line,
                        rule_source_url=source_url,
                        covered_files_count=len(covered_files),
                        covered_files_sample=covered_files[:5],
                        last_active=None,
                        days_inactive=None,
                        inactivity_threshold_days=inactivity_threshold_days,
                        status=status,
                        supporting_evidence_urls=[u for u in [source_url] if u],
                        as_of=as_of_str,
                        explanation=f"Declared owner '{owner}' has 0 recorded activity prior to as_of cutoff.",
                    ))

    return OrphanedOwnershipReport(
        as_of=as_of_str,
        inactivity_threshold_days=inactivity_threshold_days,
        total_rules_audited=total_rules,
        active_owners_count=active_count,
        inactive_owners_count=inactive_count,
        no_activity_count=no_activity_count,
        unresolved_count=unresolved_count,
        findings=findings,
    )
