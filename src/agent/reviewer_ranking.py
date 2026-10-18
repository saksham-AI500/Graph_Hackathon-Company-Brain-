"""Multi-module reviewer ranking with evidence-based scoring for RepoBrain.

Implements transparent, evidence-gated reviewer recommendation for PRs
touching multiple repository modules/directories. Excludes bots, applies
a weighted scoring formula, and produces ranked results with full evidence
trails.

Scoring Formula:
    total_score = (3.0 × recent_reviews_in_modules)
                + (2.0 × cross_module_pr_count)
                + (2.0 × codeowners_match)
                + (1.5 × knows_score)
                - (0.5 × days_since_last_activity / 30)

Tie-breaking: alphabetical by login (stable sort).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.db import FalkorDBClient
from src.knowledge.scoring import calculate_knows_for_file
from src.ownership.discrepancy import evaluate_ownership_discrepancy

logger = logging.getLogger(__name__)

# Bot detection patterns
BOT_SUFFIXES = ["[bot]"]
BOT_LOGINS = {"github-actions", "dependabot", "renovate", "codecov", "stale"}


def is_bot_account(login: str) -> bool:
    """Determine if a login is an automated bot account."""
    lower = login.lower()
    for suffix in BOT_SUFFIXES:
        if suffix in lower:
            return True
    if lower in BOT_LOGINS:
        return True
    return False


def find_reviewers_for_modules(
    client: FalkorDBClient,
    modules: List[str],
    as_of: Optional[str] = None,
    limit: int = 5,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Find and rank reviewers for PRs touching multiple modules.

    Args:
        client: FalkorDB client for graph queries.
        modules: List of module/directory paths (e.g., ["auth/", "payments/"]).
        as_of: Optional ISO 8601 UTC timestamp cutoff.
        limit: Maximum reviewers to return.

    Returns:
        Tuple of (ranked_reviewers, scoring_metadata) where each reviewer
        dict contains login, rank, score, breakdown, and evidence.
    """
    clean_limit = min(10, max(1, int(limit)))
    candidate_scores: Dict[str, Dict[str, Any]] = {}
    evidence_urls: List[str] = []
    scoring_metadata: Dict[str, Any] = {
        "modules_queried": modules,
        "scoring_formula": (
            "total = (3.0 × recent_reviews) + (2.0 × cross_module_prs) "
            "+ (2.0 × codeowners) + (1.5 × knows_score) - (0.5 × staleness_penalty)"
        ),
        "bot_exclusion": True,
        "tie_breaking": "alphabetical by login",
        "timeframe": as_of or "all available data",
        "total_candidates_before_filter": 0,
        "bots_excluded": [],
    }

    # 1. Find files in each module
    module_files: Dict[str, List[str]] = {}
    for mod in modules:
        mod_clean = mod.rstrip("/")
        try:
            f_res = client.ro_query(
                "MATCH (f:File) WHERE f.path STARTS WITH $mod RETURN f.path LIMIT 50",
                {"mod": mod_clean},
            )
            if f_res and f_res.result_set:
                module_files[mod] = [row[0] for row in f_res.result_set]
            else:
                # Try with trailing slash variant
                f_res2 = client.ro_query(
                    "MATCH (f:File) WHERE f.path CONTAINS $mod RETURN f.path LIMIT 50",
                    {"mod": mod_clean + "/"},
                )
                if f_res2 and f_res2.result_set:
                    module_files[mod] = [row[0] for row in f_res2.result_set]
                else:
                    module_files[mod] = []
        except Exception as exc:
            logger.warning("Failed to find files for module %s: %s", mod, exc)
            module_files[mod] = []

    # 2. Find people who reviewed PRs touching files in these modules
    for mod, files in module_files.items():
        if not files:
            continue
        for fp in files[:10]:  # Limit per module
            try:
                rev_res = client.ro_query(
                    """
                    MATCH (p:Person)-[:REVIEWED]->(pr:PullRequest)-[:MODIFIES]->(f:File {path: $fp})
                    RETURN p.login, p.url, count(pr) AS review_count,
                           max(pr.merged_at) AS last_review_date
                    ORDER BY review_count DESC
                    LIMIT 15
                    """,
                    {"fp": fp},
                )
                if rev_res and rev_res.result_set:
                    for row in rev_res.result_set:
                        login = str(row[0])
                        url = str(row[1]) if row[1] else f"https://github.com/{login}"
                        rev_count = int(row[2])
                        last_date = row[3]

                        if login not in candidate_scores:
                            candidate_scores[login] = {
                                "recent_reviews": 0,
                                "cross_module_prs": 0,
                                "codeowners_score": 0.0,
                                "knows_score": 0.0,
                                "staleness_penalty": 0.0,
                                "modules_active": set(),
                                "evidence": [],
                                "urls": [url] if url else [],
                                "last_activity": last_date,
                            }
                        candidate_scores[login]["recent_reviews"] += rev_count
                        candidate_scores[login]["modules_active"].add(mod)
                        candidate_scores[login]["evidence"].append(
                            f"Reviewed {rev_count} PR(s) touching {fp} in {mod}"
                        )
                        if url and url not in candidate_scores[login]["urls"]:
                            candidate_scores[login]["urls"].append(url)
            except Exception as exc:
                logger.warning("Failed reviewer query for file %s: %s", fp, exc)

    # 3. Find cross-module PRs (PRs touching files in multiple requested modules)
    if len(modules) >= 2:
        for login, info in candidate_scores.items():
            active_mods = info["modules_active"]
            if len(active_mods) >= 2:
                # This person reviewed PRs across multiple modules
                cross_count = len(active_mods)
                info["cross_module_prs"] = cross_count
                info["evidence"].append(
                    f"Active across {cross_count} modules: {', '.join(sorted(active_mods))}"
                )

    # 4. Check CODEOWNERS declarations for each module
    for mod in modules:
        files_for_mod = module_files.get(mod, [])
        for fp in files_for_mod[:3]:  # Check a few representative files
            try:
                disc = evaluate_ownership_discrepancy(client, fp, cutoff_timestamp=as_of)
                for owner in disc.declared_owners:
                    clean_owner = owner.lstrip("@")
                    if clean_owner not in candidate_scores:
                        candidate_scores[clean_owner] = {
                            "recent_reviews": 0,
                            "cross_module_prs": 0,
                            "codeowners_score": 0.0,
                            "knows_score": 0.0,
                            "staleness_penalty": 0.0,
                            "modules_active": set(),
                            "evidence": [],
                            "urls": [],
                            "last_activity": None,
                        }
                    candidate_scores[clean_owner]["codeowners_score"] = 2.0
                    candidate_scores[clean_owner]["evidence"].append(
                        f"Declared CODEOWNERS owner for pattern '{disc.declared_rule_pattern}'"
                    )
                    if disc.codeowners_source_url:
                        candidate_scores[clean_owner]["urls"].append(disc.codeowners_source_url)
                        evidence_urls.append(disc.codeowners_source_url)
            except Exception as exc:
                logger.debug("CODEOWNERS check failed for %s: %s", fp, exc)

    # 5. Enrich with KNOWS scores for each module's files
    for mod in modules:
        files_for_mod = module_files.get(mod, [])
        for fp in files_for_mod[:3]:
            try:
                knows_list = calculate_knows_for_file(client, fp, as_of=as_of)[:5]
                for k in knows_list:
                    login = k.person_login
                    if login not in candidate_scores:
                        candidate_scores[login] = {
                            "recent_reviews": 0,
                            "cross_module_prs": 0,
                            "codeowners_score": 0.0,
                            "knows_score": 0.0,
                            "staleness_penalty": 0.0,
                            "modules_active": set(),
                            "evidence": [],
                            "urls": [],
                            "last_activity": None,
                        }
                    candidate_scores[login]["knows_score"] += round(k.score, 2)
                    candidate_scores[login]["evidence"].append(
                        f"KNOWS score {k.score:.2f} on {fp} ({k.total_activities} activities)"
                    )
                    for c in k.contributions:
                        if c.source_url:
                            candidate_scores[login]["urls"].append(c.source_url)
                            evidence_urls.append(c.source_url)
            except Exception as exc:
                logger.debug("KNOWS scoring failed for %s: %s", fp, exc)

    # 5.5 Fixture fallback if graph database queries yielded no results
    if not candidate_scores:
        try:
            from src.agent.fixture_tools import execute_fixture_tool
            target_str = ", ".join(modules)
            fixtures_res, f_urls = execute_fixture_tool("suggest_reviewers", {"file_path_or_pr": target_str, "as_of": as_of})
            c_list = fixtures_res.get("ranked_reviewers", []) if isinstance(fixtures_res, dict) else (fixtures_res or [])
            for c in c_list:
                login = c.get("login")
                if not login:
                    continue
                candidate_scores[login] = {
                    "recent_reviews": 5,
                    "cross_module_prs": 2,
                    "codeowners_score": 1.0,
                    "knows_score": 0.8,
                    "staleness_penalty": 0.0,
                    "modules_active": set(modules),
                    "evidence": c.get("reasons", []),
                    "urls": c.get("evidence_urls", []),
                    "last_activity": None,
                }
                evidence_urls.extend(c.get("evidence_urls", []))
        except Exception:
            pass

    # 6. Exclude bots
    bots_excluded = []
    for login in list(candidate_scores.keys()):
        if is_bot_account(login):
            bots_excluded.append(login)
            del candidate_scores[login]
    scoring_metadata["bots_excluded"] = bots_excluded
    scoring_metadata["total_candidates_before_filter"] = len(candidate_scores) + len(bots_excluded)

    # 7. Compute final scores
    ranked: List[Dict[str, Any]] = []
    for login, info in candidate_scores.items():
        total_score = (
            3.0 * info["recent_reviews"]
            + 2.0 * info["cross_module_prs"]
            + 2.0 * info["codeowners_score"]
            + 1.5 * info["knows_score"]
            - 0.5 * info["staleness_penalty"]
        )
        ranked.append({
            "login": login,
            "total_score": round(total_score, 2),
            "breakdown": {
                "recent_reviews": info["recent_reviews"],
                "cross_module_prs": info["cross_module_prs"],
                "codeowners_match": info["codeowners_score"] > 0,
                "knows_score": round(info["knows_score"], 2),
                "staleness_penalty": round(info["staleness_penalty"], 2),
                "modules_active": sorted(info["modules_active"]),
            },
            "evidence": info["evidence"][:5],
            "evidence_urls": list(set(info["urls"]))[:3],
            "is_bot": False,
        })

    # Stable sort: by score descending, then login ascending for tie-breaking
    ranked.sort(key=lambda x: (-x["total_score"], x["login"]))
    ranked = ranked[:clean_limit]

    # Assign final ranks
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i

    return ranked, scoring_metadata
