"""Evidence-backed ownership discrepancy analysis between declared CODEOWNERS and observed activity."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient
from src.ownership.codeowners import CodeownersMatch, CodeownersParser
from src.ownership.metrics import (
    calculate_bus_factor,
    get_file_authorship,
    get_file_review_activity,
    get_reviewer_concentration,
)

MIN_EVIDENCE_PRS_THRESHOLD = 1


@dataclass
class OwnershipDiscrepancyReport:
    """Structured evidence-backed comparison between declared CODEOWNERS and observed activity."""
    file_path: str
    has_declared_owner: bool
    declared_owners: List[str]
    declared_rule_pattern: Optional[str]
    codeowners_source_url: str
    is_team_declaration: bool

    # Observed Maintainers
    observed_human_authors: List[str]
    observed_human_reviewers: List[str]
    total_modifying_prs: int
    total_human_reviews: int

    # Concentration & Metrics
    top_reviewer: Optional[str]
    top_reviewer_share: float
    reviewer_concentration_hhi: float

    # Discrepancy Classification
    discrepancy_category: str
    confidence_level: str  # HIGH, MEDIUM, LOW, INSUFFICIENT
    summary_finding: str

    # Quantitative Ownership Drift & Risk Metrics
    drift_score: float = 0.0
    bus_factor: int = 0
    risk_level: str = "LOW"

    # Evidence Records
    supporting_prs: List[Dict[str, Any]] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    overlapping_rules: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "file_path": self.file_path,
            "has_declared_owner": self.has_declared_owner,
            "declared_owners": self.declared_owners,
            "declared_rule_pattern": self.declared_rule_pattern,
            "codeowners_source_url": self.codeowners_source_url,
            "is_team_declaration": self.is_team_declaration,
            "observed_human_authors": self.observed_human_authors,
            "observed_human_reviewers": self.observed_human_reviewers,
            "total_modifying_prs": self.total_modifying_prs,
            "total_human_reviews": self.total_human_reviews,
            "top_reviewer": self.top_reviewer,
            "top_reviewer_share": self.top_reviewer_share,
            "reviewer_concentration_hhi": self.reviewer_concentration_hhi,
            "drift_score": self.drift_score,
            "bus_factor": self.bus_factor,
            "risk_level": self.risk_level,
            "discrepancy_category": self.discrepancy_category,
            "confidence_level": self.confidence_level,
            "summary_finding": self.summary_finding,
            "supporting_prs": self.supporting_prs,
            "limitations": self.limitations,
            "overlapping_rules": self.overlapping_rules,
        }


def evaluate_ownership_discrepancy(
    client: FalkorDBClient,
    file_path: str,
    codeowners: Optional[CodeownersParser] = None,
    min_prs_threshold: int = MIN_EVIDENCE_PRS_THRESHOLD,
    cutoff_timestamp: Optional[str] = None,
) -> OwnershipDiscrepancyReport:
    """Evaluate discrepancy between declared CODEOWNERS ownership and observed repository activity."""
    parser = codeowners or CodeownersParser.from_cache_or_default()
    co_match: CodeownersMatch = parser.match(file_path)

    authorship = get_file_authorship(
        client, file_path, include_bots=False, cutoff_timestamp=cutoff_timestamp
    )
    review_activity = get_file_review_activity(
        client, file_path, include_bots=False, cutoff_timestamp=cutoff_timestamp
    )
    concentration = get_reviewer_concentration(
        client, file_path, cutoff_timestamp=cutoff_timestamp
    )

    human_authors = [a["author"] for a in authorship["authors"]]
    human_reviewers = [r["reviewer"] for r in review_activity["reviewers"]]
    total_prs = authorship["total_human_prs"]
    total_reviews = review_activity["total_human_reviews"]

    # Collect supporting PR evidence records
    supporting_prs = []
    seen_prs = set()
    for a in authorship["authors"]:
        for pr in a.get("prs", []):
            num = pr.get("number")
            if num and num not in seen_prs:
                seen_prs.add(num)
                supporting_prs.append(pr)

    limitations: List[str] = []

    overlapping_rules = [
        {"pattern": r.pattern, "owners": r.owners, "line_number": r.line_number, "is_team": r.is_team}
        for r in getattr(co_match, "overlapping_rules", [])
    ]

    # Check evidence sufficiency
    if total_prs < min_prs_threshold:
        return OwnershipDiscrepancyReport(
            file_path=file_path,
            has_declared_owner=co_match.matched,
            declared_owners=co_match.owners,
            declared_rule_pattern=co_match.rule_pattern,
            codeowners_source_url=co_match.source_url,
            is_team_declaration=co_match.is_team,
            observed_human_authors=human_authors,
            observed_human_reviewers=human_reviewers,
            total_modifying_prs=total_prs,
            total_human_reviews=total_reviews,
            top_reviewer=None,
            top_reviewer_share=0.0,
            reviewer_concentration_hhi=0.0,
            drift_score=0.0,
            bus_factor=0,
            risk_level="LOW",
            discrepancy_category="INSUFFICIENT_EVIDENCE",
            confidence_level="INSUFFICIENT",
            summary_finding="Insufficient historical PR data in graph to assess ownership alignment.",
            supporting_prs=[],
            limitations=["Dataset contains 0 merged PRs modifying this path."],
            overlapping_rules=overlapping_rules,
        )

    # Classify Discrepancy
    if co_match.matched:
        if co_match.is_team:
            limitations.append(
                f"Declared owner '{co_match.owners[0]}' is a GitHub team. GitHub API does not expose team membership without administrative organization scopes."
            )
            # If human reviewers are active, it represents team delegation
            if human_reviewers:
                category = "TEAM_DECLARED_INDIVIDUAL_ACTIVE"
                summary = (
                    f"Team '{', '.join(co_match.owners)}' declared in CODEOWNERS. "
                    f"Observed review activity handled by individual maintainers: {', '.join(human_reviewers)}."
                )
                confidence = "HIGH"
            else:
                category = "DECLARED_WITHOUT_OBSERVED_REVIEWS"
                summary = (
                    f"Team '{', '.join(co_match.owners)}' declared, but 0 human review records found in ingested history."
                )
                confidence = "MEDIUM"
        else:
            # Individual owner declared
            declared_set = set(co_match.owners)
            reviewer_set = set(human_reviewers)
            if declared_set.intersection(reviewer_set):
                category = "INDIVIDUAL_ALIGNED"
                summary = f"Declared individual owner '{', '.join(co_match.owners)}' actively reviews modifications."
                confidence = "HIGH"
            else:
                category = "OWNERSHIP_DRIFT"
                summary = (
                    f"Declared individual owner '{', '.join(co_match.owners)}' has not reviewed recent changes. "
                    f"Actual active reviewers: {', '.join(human_reviewers)}."
                )
                confidence = "HIGH"
    else:
        # File has NO declared owner in CODEOWNERS
        if human_reviewers:
            category = "UNOWNED_WITH_ACTIVE_MAINTAINERS"
            summary = (
                f"No declared owner in CODEOWNERS. Observed institutional stewardship by reviewers: "
                f"{', '.join(human_reviewers)} (Top: {concentration['top_reviewer']} at {concentration['top_reviewer_share'] * 100:.1f}% share)."
            )
            confidence = "HIGH"
        else:
            category = "UNOWNED_SPARSE_MAINTENANCE"
            summary = "No declared owner in CODEOWNERS and 0 observed human reviews in sample."
            confidence = "MEDIUM"

    if total_prs < 3:
        confidence = "MEDIUM"
        limitations.append(f"Sample size is bounded ({total_prs} PRs); metrics reflect recent sample window.")

    # Calculate Bus Factor from decayed human contributions (excluding bots)
    contributions: List[Dict[str, Any]] = []
    for a in authorship.get("authors", []):
        for pr in a.get("prs", []):
            contributions.append({
                "login": a.get("author"),
                "timestamp": pr.get("merged_at"),
                "weight": 1.0,
                "is_bot": a.get("is_bot", False),
            })
    for r in review_activity.get("reviewers", []):
        for pr_num in r.get("pr_numbers", []):
            contributions.append({
                "login": r.get("reviewer"),
                "timestamp": None,
                "weight": 0.5,
                "is_bot": r.get("is_bot", False),
            })

    bus_factor = calculate_bus_factor(contributions, cutoff_timestamp=cutoff_timestamp)

    # Calculate Drift Score according to actual divergence
    if category == "OWNERSHIP_DRIFT":
        drift_score = 1.0
        risk_level = "HIGH"
    elif category == "INDIVIDUAL_ALIGNED":
        drift_score = 0.0
        risk_level = "LOW" if bus_factor >= 2 else "MEDIUM"
    elif category == "TEAM_DECLARED_INDIVIDUAL_ACTIVE":
        drift_score = 0.0
        risk_level = "LOW" if bus_factor >= 2 else "MEDIUM"
    elif category == "DECLARED_WITHOUT_OBSERVED_REVIEWS":
        drift_score = 0.75
        risk_level = "HIGH" if bus_factor <= 1 else "MEDIUM"
    elif category == "UNOWNED_WITH_ACTIVE_MAINTAINERS":
        author_set = set(human_authors)
        reviewer_set = set(human_reviewers)
        union_set = author_set | reviewer_set
        inter_set = author_set & reviewer_set
        jaccard = len(inter_set) / len(union_set) if union_set else 1.0
        drift_score = round(1.0 - jaccard, 2)
        risk_level = "HIGH" if bus_factor <= 1 else "MEDIUM"
    elif category == "UNOWNED_SPARSE_MAINTENANCE":
        drift_score = 1.0
        risk_level = "HIGH"
    else:
        drift_score = 0.0
        risk_level = "LOW"

    return OwnershipDiscrepancyReport(
        file_path=file_path,
        has_declared_owner=co_match.matched,
        declared_owners=co_match.owners,
        declared_rule_pattern=co_match.rule_pattern,
        codeowners_source_url=co_match.source_url,
        is_team_declaration=co_match.is_team,
        observed_human_authors=human_authors,
        observed_human_reviewers=human_reviewers,
        total_modifying_prs=total_prs,
        total_human_reviews=total_reviews,
        top_reviewer=concentration["top_reviewer"],
        top_reviewer_share=concentration["top_reviewer_share"],
        reviewer_concentration_hhi=concentration["concentration_hhi"],
        drift_score=drift_score,
        bus_factor=bus_factor,
        risk_level=risk_level,
        discrepancy_category=category,
        confidence_level=confidence,
        summary_finding=summary,
        supporting_prs=supporting_prs,
        limitations=limitations,
        overlapping_rules=overlapping_rules,
    )
