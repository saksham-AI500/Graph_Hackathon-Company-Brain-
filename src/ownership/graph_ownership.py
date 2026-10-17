"""Graph-Native Ownership & Drift Analysis Engine for FalkorDB repo_kg.

Transfers CODEOWNERS rules and declared owners into native FalkorDB graph entities:
- (:OwnershipRule {pattern, line_number, source_url})
- (:Team {name})
- (:OwnershipRule)-[:DECLARES_OWNER]->(:Team | :Person)
- (:OwnershipRule)-[:COVERS]->(:File)

Executes auditable ownership drift Cypher queries directly in FalkorDB.
"""

from typing import Any, Dict, List, Optional
from src.db import FalkorDBClient
from src.evaluation.temporal import normalize_utc_timestamp
from src.ownership.codeowners import CodeownersParser


OWNERSHIP_INDEXES = [
    "CREATE INDEX FOR (r:OwnershipRule) ON (r.pattern)",
    "CREATE INDEX FOR (t:Team) ON (t.name)",
]


def ensure_ownership_schema(client: FalkorDBClient) -> None:
    """Ensure indexes exist for OwnershipRule and Team nodes."""
    for stmt in OWNERSHIP_INDEXES:
        try:
            client.query(stmt)
        except Exception as exc:
            if "already indexed" in str(exc).lower() or "equivalent index already exists" in str(exc).lower():
                continue
            pass


def load_codeowners_into_graph(
    client: FalkorDBClient,
    codeowners: Optional[CodeownersParser] = None,
) -> Dict[str, int]:
    """Ingest CODEOWNERS rules, teams, and [:COVERS] relationships into FalkorDB."""
    ensure_ownership_schema(client)
    parser = codeowners or CodeownersParser.from_cache_or_default()

    stats = {
        "rules_merged": 0,
        "teams_merged": 0,
        "declares_owner_edges": 0,
        "covers_edges": 0,
        "owns_edges": 0,
    }

    # 1. Merge OwnershipRule nodes and declared owners
    for rule in parser.rules:
        client.query(
            """
            MERGE (r:OwnershipRule {pattern: $pattern})
            ON CREATE SET r.line_number = $line, r.source_url = $url
            ON MATCH SET r.line_number = $line, r.source_url = $url
            """,
            {
                "pattern": rule.pattern,
                "line": rule.line_number,
                "url": parser.source_url,
            },
        )
        stats["rules_merged"] += 1

        for owner in rule.owners:
            if owner.startswith("@") and "/" in owner:
                # Team owner (e.g. @FalkorDB/falkordb-core)
                client.query(
                    """
                    MERGE (t:Team {name: $name})
                    WITH t
                    MATCH (r:OwnershipRule {pattern: $pattern})
                    MERGE (r)-[:DECLARES_OWNER]->(t)
                    """,
                    {"name": owner, "pattern": rule.pattern},
                )
                stats["teams_merged"] += 1
                stats["declares_owner_edges"] += 1
            else:
                # Individual person owner
                login = owner.lstrip("@")
                client.query(
                    """
                    MERGE (p:Person {login: $login})
                    ON CREATE SET p.url = $url
                    WITH p
                    MATCH (r:OwnershipRule {pattern: $pattern})
                    MERGE (r)-[:DECLARES_OWNER]->(p)
                    """,
                    {
                        "login": login,
                        "url": f"https://github.com/{login}",
                        "pattern": rule.pattern,
                    },
                )
                stats["declares_owner_edges"] += 1

    # 2. Connect File nodes to their winning OwnershipRule via [:COVERS]
    files_res = client.ro_query("MATCH (f:File) RETURN f.path")
    if files_res and files_res.result_set:
        for row in files_res.result_set:
            path = row[0]
            match = parser.match(path)
            if match.matched and match.rule_pattern:
                client.query(
                    """
                    MATCH (r:OwnershipRule {pattern: $pattern}), (f:File {path: $path})
                    MERGE (r)-[:COVERS]->(f)
                    """,
                    {"pattern": match.rule_pattern, "path": path},
                )
                stats["covers_edges"] += 1

                if match.is_team:
                    for owner in match.owners:
                        if owner.startswith("@") and "/" in owner:
                            client.query(
                                """
                                MATCH (t:Team {name: $name}), (f:File {path: $path})
                                MERGE (t)-[o:OWNS]->(f)
                                ON CREATE SET o.rule_pattern = $pattern
                                ON MATCH SET o.rule_pattern = $pattern
                                """,
                                {"name": owner, "path": path, "pattern": match.rule_pattern},
                            )
                            stats["owns_edges"] += 1

    return stats


def query_ownership_drift_graph(
    client: FalkorDBClient,
    target_pr: int,
    cutoff_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute graph-native ownership drift analysis in FalkorDB for a target PR.

    Compares:
    - files touched by that PR
    - owners declared for those files via (:OwnershipRule)-[:DECLARES_OWNER]->(owner)
    - observed prior reviewer/author history via (prior_pr)-[:MODIFIES]->(f)
    - time boundary used for that activity
    """
    norm_cutoff = normalize_utc_timestamp(cutoff_timestamp) if cutoff_timestamp else None

    # Step 1: Verify target PR exists
    pr_check = client.ro_query("MATCH (p:PullRequest {number: $num}) RETURN p.url", {"num": target_pr})
    if not pr_check or not pr_check.result_set:
        return {
            "target_pr": target_pr,
            "status": "UNRESOLVED",
            "reason": f"Target PR #{target_pr} does not exist in graph.",
            "files": [],
        }

    # Step 2: Cypher query for files, declared owners, and historical activity
    if norm_cutoff:
        cypher = """
        MATCH (target_pr:PullRequest {number: $pr_num})-[m:MODIFIES]->(f:File)
        OPTIONAL MATCH (rule:OwnershipRule)-[:COVERS]->(f)
        OPTIONAL MATCH (rule)-[:DECLARES_OWNER]->(owner)
        WITH f, rule, collect(DISTINCT coalesce(owner.name, owner.login)) AS declared_owners
        OPTIONAL MATCH (f)<-[:MODIFIES]-(prior_pr:PullRequest)<-[r:REVIEWED]-(reviewer:Person)
        WHERE prior_pr.number <> $pr_num
          AND prior_pr.merged_at IS NOT NULL
          AND prior_pr.merged_at <> ''
          AND prior_pr.merged_at <= $cutoff
          AND r.submitted_at IS NOT NULL
          AND r.submitted_at <> ''
          AND r.submitted_at <= $cutoff
        RETURN f.path AS file_path,
               rule.pattern AS rule_pattern,
               declared_owners,
               collect(DISTINCT reviewer.login) AS observed_reviewers,
               count(DISTINCT prior_pr) AS prior_prs_count,
               collect(DISTINCT prior_pr.url)[0..5] AS evidence_prs
        ORDER BY prior_prs_count DESC
        """
        params = {"pr_num": target_pr, "cutoff": norm_cutoff}
    else:
        cypher = """
        MATCH (target_pr:PullRequest {number: $pr_num})-[m:MODIFIES]->(f:File)
        OPTIONAL MATCH (rule:OwnershipRule)-[:COVERS]->(f)
        OPTIONAL MATCH (rule)-[:DECLARES_OWNER]->(owner)
        WITH f, rule, collect(DISTINCT coalesce(owner.name, owner.login)) AS declared_owners
        OPTIONAL MATCH (f)<-[:MODIFIES]-(prior_pr:PullRequest)<-[r:REVIEWED]-(reviewer:Person)
        WHERE prior_pr.number <> $pr_num
        RETURN f.path AS file_path,
               rule.pattern AS rule_pattern,
               declared_owners,
               collect(DISTINCT reviewer.login) AS observed_reviewers,
               count(DISTINCT prior_pr) AS prior_prs_count,
               collect(DISTINCT prior_pr.url)[0..5] AS evidence_prs
        ORDER BY prior_prs_count DESC
        """
        params = {"pr_num": target_pr}

    res = client.ro_query(cypher, params)
    file_findings = []
    overall_drift_signals = []

    if res and res.result_set:
        for row in res.result_set:
            path, rule_pattern, declared_owners, reviewers, prs_count, evidence_prs = row
            reviewers = [r for r in (reviewers or []) if not r.endswith("[bot]")]
            declared_owners = declared_owners or []

            has_declared = len(declared_owners) > 0
            has_history = prs_count > 0

            # Classification
            if not has_declared and has_history:
                category = "UNOWNED_WITH_ACTIVE_MAINTAINERS"
                signal = (
                    f"File '{path}' has no declared CODEOWNERS in graph, "
                    f"but has {prs_count} historical PR touches reviewed by: {', '.join(reviewers[:3])}."
                )
            elif has_declared and any("/" in o for o in declared_owners) and has_history:
                category = "TEAM_DECLARATION_WITH_INDIVIDUAL_ACTIVITY"
                signal = (
                    f"File '{path}' declared for team {declared_owners}, "
                    f"routinely maintained by individual reviewers: {', '.join(reviewers[:3])}."
                )
            elif not has_history:
                category = "SPARSE_OR_UNRECORDED_HISTORY"
                signal = f"File '{path}' has sparse prior recorded reviews in repository history."
            else:
                category = "ALIGNED_OWNERSHIP"
                signal = f"File '{path}' active maintainers match declared ownership: {', '.join(declared_owners)}."

            file_findings.append({
                "file_path": path,
                "rule_pattern": rule_pattern,
                "declared_owners": declared_owners,
                "observed_reviewers": reviewers,
                "prior_prs_count": prs_count,
                "evidence_prs": evidence_prs or [],
                "discrepancy_category": category,
                "signal_summary": signal,
            })
            if category != "ALIGNED_OWNERSHIP":
                overall_drift_signals.append(signal)

    return {
        "target_pr": target_pr,
        "cutoff_applied": norm_cutoff,
        "total_files_analyzed": len(file_findings),
        "drift_signals_count": len(overall_drift_signals),
        "files": file_findings,
        "summary": (
            f"Analyzed {len(file_findings)} changed files via FalkorDB graph relationships. "
            f"Identified {len(overall_drift_signals)} ownership signals for review."
            if file_findings
            else "Target PR does not modify any recorded files."
        ),
        "note": "A mismatch is an auditable review signal — not proof of incompetence or exclusive ownership.",
    }
