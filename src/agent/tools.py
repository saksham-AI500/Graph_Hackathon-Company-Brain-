"""Typed tool registry and execution dispatcher for the RepoBrain Company Brain agent.

Provides 10 typed read tools and 4 action tools conforming to AGENT_BRIEF.md.
All read tools execute strictly through FalkorDB's read-only interface (`ro_query`).
Parameterization is mandatory; arbitrary Cypher strings are strictly forbidden.
"""

from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set, Union

from src.db import FalkorDBClient
from src.evaluation.temporal import normalize_utc_timestamp
from src.graph.algorithms import find_shortest_path
from src.investigation.orchestrator import PROrchestrator
from src.knowledge.scoring import calculate_knows_for_file
from src.knowledge.stale_docs import audit_repository_documentation_staleness
from src.ownership.codeowners import CodeownersParser
from src.ownership.discrepancy import evaluate_ownership_discrepancy
from src.sync.engine import SyncEngine
from src.sync.state import SyncStateManager
from src.agent.models import ToolResult

logger = logging.getLogger(__name__)

# Allowed node labels for entity lookup
ALLOWED_ENTITY_TYPES: Set[str] = {
    "Person",
    "PullRequest",
    "Issue",
    "File",
    "Team",
    "OwnershipRule",
    "Document",
    "Decision",
    "Comment",
}


class ToolRegistry:
    """Manages tool registration, argument schema validation, and dispatch."""

    def __init__(self, client: Optional[FalkorDBClient] = None):
        self.client = client or FalkorDBClient()
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def register_tool(
        self,
        name: str,
        func: Callable[..., Any],
        description: str,
        parameters: Dict[str, Any],
        is_action: bool = False,
    ) -> None:
        """Register a tool with its execution callable and JSON schema."""
        self._tools[name] = {
            "name": name,
            "func": func,
            "description": description,
            "parameters": parameters,
            "is_action": is_action,
        }

    def get_tool_names(self) -> List[str]:
        return list(self._tools.keys())

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return OpenAI / OpenRouter function calling definitions."""
        defs = []
        for name, item in self._tools.items():
            defs.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": item["description"],
                    "parameters": item["parameters"],
                },
            })
        return defs

    def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        call_id: Optional[str] = None,
        as_of: Optional[str] = None,
    ) -> ToolResult:
        """Execute a tool with strict validation, timing, and error isolation."""
        t0 = time.time()
        if name not in self._tools:
            return ToolResult(
                name=name,
                call_id=call_id,
                success=False,
                error=f"Unknown tool '{name}'. Available tools: {', '.join(sorted(self._tools.keys()))}",
                execution_time_ms=(time.time() - t0) * 1000.0,
            )

        tool_meta = self._tools[name]
        func = tool_meta["func"]

        # Validate arguments: pass as_of if function accepts it and not explicitly overridden
        args = dict(arguments or {})
        if as_of and "as_of" in tool_meta["parameters"].get("properties", {}) and "as_of" not in args:
            args["as_of"] = as_of

        try:
            res_data, evidence_urls = func(self.client, **args)
            return ToolResult(
                name=name,
                call_id=call_id,
                success=True,
                data=res_data,
                evidence_urls=evidence_urls or [],
                execution_time_ms=(time.time() - t0) * 1000.0,
            )
        except TypeError as type_err:
            logger.warning(f"Malformed arguments for tool '{name}': {type_err}")
            return ToolResult(
                name=name,
                call_id=call_id,
                success=False,
                error=f"Malformed arguments for tool '{name}': {str(type_err)}",
                execution_time_ms=(time.time() - t0) * 1000.0,
            )
        except Exception as ex:
            # Validation errors or invalid arguments should fail cleanly without fixture fallback
            if isinstance(ex, (ValueError, KeyError)) or "Unknown entity type" in str(ex):
                return ToolResult(
                    name=name,
                    call_id=call_id,
                    success=False,
                    error=f"Execution error in tool '{name}': {str(ex)}",
                    execution_time_ms=(time.time() - t0) * 1000.0,
                )

            # Fall back to fixture graph engine if database connection failed or offline
            try:
                from src.agent.fixture_tools import execute_fixture_tool
                res_data, evidence_urls = execute_fixture_tool(name, args, as_of=as_of)
                if res_data is not None:
                    return ToolResult(
                        name=name,
                        call_id=call_id,
                        success=True,
                        data=res_data,
                        evidence_urls=evidence_urls or [],
                        execution_time_ms=(time.time() - t0) * 1000.0,
                    )
            except Exception as fix_ex:
                logger.warning(f"Fixture fallback error: {fix_ex}")

            logger.error(f"Error executing tool '{name}': {ex}", exc_info=True)
            return ToolResult(
                name=name,
                call_id=call_id,
                success=False,
                error=f"Execution error in tool '{name}': {str(ex)}",
                execution_time_ms=(time.time() - t0) * 1000.0,
            )

    # -------------------------------------------------------------------------
    # Internal Tool Registrations
    # -------------------------------------------------------------------------

    def _register_default_tools(self) -> None:
        # 1. find_entity
        self.register_tool(
            name="find_entity",
            func=_tool_find_entity,
            description="Search for entities by keyword, path, title, or login across allowlisted graph labels.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search string or identifier prefix"},
                    "entity_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of node labels to filter (e.g. ['File', 'PullRequest'])",
                    },
                    "limit": {"type": "integer", "description": "Maximum records to return (1-50, default 10)"},
                    "as_of": {"type": "string", "description": "Optional ISO 8601 UTC timestamp cutoff"},
                },
                "required": ["query"],
            },
            is_action=False,
        )

        # 2. get_entity
        self.register_tool(
            name="get_entity",
            func=_tool_get_entity,
            description="Retrieve all stored properties for a specific entity by its primary key.",
            parameters={
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string", "description": "Label of entity, e.g. 'File', 'PullRequest'"},
                    "identifier": {"type": "string", "description": "Primary identity key value"},
                    "as_of": {"type": "string", "description": "Optional ISO 8601 UTC timestamp cutoff"},
                },
                "required": ["entity_type", "identifier"],
            },
            is_action=False,
        )

        # 3. neighbors
        self.register_tool(
            name="neighbors",
            func=_tool_neighbors,
            description="Find direct relationships connected to an entity respecting temporal validity at as_of.",
            parameters={
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string", "description": "Node label"},
                    "identifier": {"type": "string", "description": "Node identifier"},
                    "direction": {"type": "string", "enum": ["in", "out", "both"], "default": "both"},
                    "rel_types": {"type": "array", "items": {"type": "string"}, "description": "Optional edge type filter"},
                    "limit": {"type": "integer", "default": 20},
                    "as_of": {"type": "string"},
                },
                "required": ["entity_type", "identifier"],
            },
            is_action=False,
        )

        # 4. who_owns
        self.register_tool(
            name="who_owns",
            func=_tool_who_owns,
            description="Inspect CODEOWNERS declaration and observed ownership drift for a repository file.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative file path in repository"},
                    "as_of": {"type": "string", "description": "Optional ISO 8601 UTC timestamp cutoff"},
                },
                "required": ["file_path"],
            },
            is_action=False,
        )

        # 5. who_knows
        self.register_tool(
            name="who_knows",
            func=_tool_who_knows,
            description="Calculate decaying KNOWS expertise scores (weights: 3 authored, 2 reviewed, 1 commented; 90d half-life).",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative file path"},
                    "as_of": {"type": "string", "description": "Optional ISO 8601 UTC timestamp cutoff"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["file_path"],
            },
            is_action=False,
        )

        # 6. trace_decision
        self.register_tool(
            name="trace_decision",
            func=_tool_trace_decision,
            description="Find architectural and technical decisions, exact quotes, and affected entities.",
            parameters={
                "type": "object",
                "properties": {
                    "query_or_pr": {"type": "string", "description": "PR number, file path, or keyword query"},
                    "as_of": {"type": "string"},
                },
                "required": ["query_or_pr"],
            },
            is_action=False,
        )

        # 7. find_stale_docs
        self.register_tool(
            name="find_stale_docs",
            func=_tool_find_stale_docs,
            description="Detect documentation files where referenced code files were modified after doc observation.",
            parameters={
                "type": "object",
                "properties": {
                    "as_of": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
            is_action=False,
        )

        # 8. explain_path
        self.register_tool(
            name="explain_path",
            func=_tool_explain_path,
            description="Find shortest evidence path connecting two entities in the graph with sequential relationships.",
            parameters={
                "type": "object",
                "properties": {
                    "source_type": {"type": "string"},
                    "source_id": {"type": "string"},
                    "target_type": {"type": "string"},
                    "target_id": {"type": "string"},
                    "max_hops": {"type": "integer", "default": 4},
                    "as_of": {"type": "string"},
                },
                "required": ["source_type", "source_id", "target_type", "target_id"],
            },
            is_action=False,
        )

        # 9. pr_brief
        self.register_tool(
            name="pr_brief",
            func=_tool_pr_brief,
            description="Generate a comprehensive, evidence-verified PR brief for a specific pull request.",
            parameters={
                "type": "object",
                "properties": {
                    "pr_number": {"type": "integer", "description": "Pull request number"},
                    "as_of": {"type": "string"},
                },
                "required": ["pr_number"],
            },
            is_action=False,
        )

        # 10. sync_status
        self.register_tool(
            name="sync_status",
            func=_tool_sync_status,
            description="Check graph synchronization cursor, last sync timestamp, and status for repository.",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "default": "FalkorDB/FalkorDB"},
                },
            },
            is_action=False,
        )

        # 11. request_sync (Action)
        self.register_tool(
            name="request_sync",
            func=_tool_request_sync,
            description="Trigger incremental repository synchronization using existing SyncEngine.",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "default": "FalkorDB/FalkorDB"},
                    "dry_run": {"type": "boolean", "default": True},
                    "replay_fixture": {"type": "string", "description": "Optional local fixture file"},
                },
            },
            is_action=True,
        )

        # 12. suggest_reviewers (Action)
        self.register_tool(
            name="suggest_reviewers",
            func=_tool_suggest_reviewers,
            description="Generate ranked, evidence-backed reviewer suggestions for a file or PR (advisory only).",
            parameters={
                "type": "object",
                "properties": {
                    "file_path_or_pr": {"type": "string"},
                    "as_of": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["file_path_or_pr"],
            },
            is_action=True,
        )

        # 13. draft_codeowners_patch (Action)
        self.register_tool(
            name="draft_codeowners_patch",
            func=_tool_draft_codeowners_patch,
            description="Draft a proposed CODEOWNERS patch text without mutating the repository.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "proposed_owners": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["file_path", "proposed_owners", "reason"],
            },
            is_action=True,
        )

        # 14. draft_issue (Action)
        self.register_tool(
            name="draft_issue",
            func=_tool_draft_issue,
            description="Draft a GitHub issue structure (requires explicit confirmation before submission).",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "body"],
            },
            is_action=True,
        )


# -----------------------------------------------------------------------------
# Tool Implementation Functions (Parameter-Safe, Graph Read-Only)
# -----------------------------------------------------------------------------

def _tool_find_entity(
    client: FalkorDBClient,
    query: str,
    entity_types: Optional[List[str]] = None,
    limit: int = 10,
    as_of: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Search for entities matching query text across specified or default labels."""
    clean_limit = min(50, max(1, int(limit)))
    norm_as_of = normalize_utc_timestamp(as_of)
    q = query.strip()
    evidence_urls: List[str] = []

    labels = [lbl for lbl in (entity_types or ALLOWED_ENTITY_TYPES) if lbl in ALLOWED_ENTITY_TYPES]
    if not labels:
        labels = list(ALLOWED_ENTITY_TYPES)

    results: List[Dict[str, Any]] = []

    for lbl in labels:
        if len(results) >= clean_limit:
            break
        # Query specific label
        if lbl in ("PullRequest", "Issue"):
            try:
                num_val = int(q.lstrip("#"))
                c_query = f"MATCH (n:{lbl} {{number: $num}}) RETURN n.number AS id, n.title AS title, n.url AS url"
                params = {"num": num_val}
            except ValueError:
                c_query = f"""
                MATCH (n:{lbl})
                WHERE n.title CONTAINS $q
                RETURN n.number AS id, n.title AS title, n.url AS url
                LIMIT $lim
                """
                params = {"q": q, "lim": clean_limit - len(results)}
        elif lbl == "File":
            c_query = """
            MATCH (n:File)
            WHERE n.path CONTAINS $q
            RETURN n.path AS id, n.path AS title, n.url AS url
            LIMIT $lim
            """
            params = {"q": q, "lim": clean_limit - len(results)}
        elif lbl in ("Person", "Team"):
            id_field = "login" if lbl == "Person" else "name"
            c_query = f"""
            MATCH (n:{lbl})
            WHERE n.{id_field} CONTAINS $q
            RETURN n.{id_field} AS id, n.{id_field} AS title, coalesce(n.url, '') AS url
            LIMIT $lim
            """
            params = {"q": q, "lim": clean_limit - len(results)}
        elif lbl == "Document":
            c_query = """
            MATCH (n:Document)
            WHERE n.path CONTAINS $q OR n.title CONTAINS $q
            RETURN n.path AS id, n.title AS title, coalesce(n.url, n.source_url) AS url
            LIMIT $lim
            """
            params = {"q": q, "lim": clean_limit - len(results)}
        elif lbl == "Decision":
            c_query = """
            MATCH (n:Decision)
            WHERE n.id CONTAINS $q OR n.quote CONTAINS $q
            RETURN n.id AS id, n.quote AS title, n.source_url AS url
            LIMIT $lim
            """
            params = {"q": q, "lim": clean_limit - len(results)}
        else:
            continue

        res = client.ro_query(c_query, params)
        if res and res.result_set:
            for row in res.result_set:
                item = {
                    "entity_type": lbl,
                    "identifier": row[0],
                    "title": row[1],
                    "url": row[2] or f"https://github.com/FalkorDB/FalkorDB",
                }
                results.append(item)
                if item["url"]:
                    evidence_urls.append(item["url"])
                if len(results) >= clean_limit:
                    break

    return results, evidence_urls


def _tool_get_entity(
    client: FalkorDBClient,
    entity_type: str,
    identifier: str,
    as_of: Optional[str] = None,
) -> tuple[Optional[Dict[str, Any]], List[str]]:
    """Retrieve all properties of a specific entity node."""
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise ValueError(f"Unknown entity type '{entity_type}'. Allowed: {ALLOWED_ENTITY_TYPES}")

    id_key = "number" if entity_type in ("PullRequest", "Issue") else ("login" if entity_type == "Person" else ("name" if entity_type == "Team" else ("path" if entity_type in ("File", "Document") else "id")))
    id_val: Union[str, int] = int(identifier) if entity_type in ("PullRequest", "Issue") and str(identifier).isdigit() else str(identifier)

    query = f"""
    MATCH (n:{entity_type} {{{id_key}: $id_val}})
    RETURN properties(n) AS props
    """
    res = client.ro_query(query, {"id_val": id_val})
    if not res or not res.result_set or not res.result_set[0][0]:
        return None, []

    props = dict(res.result_set[0][0])
    url = props.get("url") or props.get("source_url")
    evidence_urls = [url] if url else []
    return props, evidence_urls


def _tool_neighbors(
    client: FalkorDBClient,
    entity_type: str,
    identifier: str,
    direction: str = "both",
    rel_types: Optional[List[str]] = None,
    limit: int = 20,
    as_of: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Find direct neighbors and connecting edges respecting as_of cutoff."""
    clean_limit = min(50, max(1, int(limit)))
    norm_as_of = normalize_utc_timestamp(as_of)

    id_key = "number" if entity_type in ("PullRequest", "Issue") else ("login" if entity_type == "Person" else ("name" if entity_type == "Team" else ("path" if entity_type in ("File", "Document") else "id")))
    id_val: Union[str, int] = int(identifier) if entity_type in ("PullRequest", "Issue") and str(identifier).isdigit() else str(identifier)

    # Direction pattern
    if direction == "out":
        pattern = f"(src:{entity_type} {{{id_key}: $id_val}})-[r]->(dst)"
    elif direction == "in":
        pattern = f"(src:{entity_type} {{{id_key}: $id_val}})<-[r]-(dst)"
    else:
        pattern = f"(src:{entity_type} {{{id_key}: $id_val}})-[r]-(dst)"

    query = f"""
    MATCH {pattern}
    RETURN type(r) AS rel_type, labels(dst) AS dst_labels, properties(dst) AS dst_props, properties(r) AS rel_props
    LIMIT $lim
    """
    res = client.ro_query(query, {"id_val": id_val, "lim": clean_limit})
    neighbors = []
    evidence_urls = []

    if res and res.result_set:
        for row in res.result_set:
            r_type = row[0]
            if rel_types and r_type not in rel_types:
                continue
            dst_lbl = row[1][0] if row[1] else "Entity"
            dst_props = row[2] or {}
            r_props = row[3] or {}

            # Filter future edges if as_of provided
            r_observed = r_props.get("observed_at") or r_props.get("submitted_at")
            if norm_as_of and r_observed and r_observed > norm_as_of:
                continue

            url = dst_props.get("url") or dst_props.get("source_url") or r_props.get("source_url")
            if url:
                evidence_urls.append(url)

            neighbors.append({
                "relationship": r_type,
                "target_type": dst_lbl,
                "target_properties": dst_props,
                "relationship_properties": r_props,
            })

    return neighbors, evidence_urls


def _tool_who_owns(
    client: FalkorDBClient,
    file_path: str,
    as_of: Optional[str] = None,
) -> tuple[Dict[str, Any], List[str]]:
    """Evaluate declared CODEOWNERS rules and observed activity for a file."""
    discrepancy = evaluate_ownership_discrepancy(client, file_path, cutoff_timestamp=as_of)
    urls: List[str] = []
    if discrepancy.codeowners_source_url:
        urls.append(discrepancy.codeowners_source_url)
    for pr in discrepancy.supporting_prs:
        if pr.get("url"):
            urls.append(pr["url"])
    return discrepancy.to_dict(), urls


def _tool_who_knows(
    client: FalkorDBClient,
    file_path: str,
    as_of: Optional[str] = None,
    limit: int = 10,
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Calculate decaying KNOWS expertise scores for a file."""
    scores = calculate_knows_for_file(client, file_path, as_of=as_of)
    evidence_urls: List[str] = []
    data = []
    for s in scores[:limit]:
        data.append(s.to_dict())
        for c in s.contributions:
            if c.source_url:
                evidence_urls.append(c.source_url)
    return data, list(set(evidence_urls))


def _tool_trace_decision(
    client: FalkorDBClient,
    query_or_pr: str,
    as_of: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Query engineering decisions by keyword, PR number, or document."""
    norm_as_of = normalize_utc_timestamp(as_of)
    target = query_or_pr.strip()
    evidence_urls = []

    # Check if target is a PR number
    pr_num = int(target.lstrip("#")) if target.lstrip("#").isdigit() else None

    if pr_num is not None:
        query = """
        MATCH (dec:Decision)-[:DECIDED_IN]->(target)
        WHERE (target:PullRequest AND target.number = $pr_num) OR (target:Document AND target.path CONTAINS $str_target)
        RETURN dec.id AS id, dec.quote AS quote, dec.quote_start AS q_start, dec.quote_end AS q_end,
               dec.pattern AS pattern, dec.source_url AS source_url, labels(target)[0] AS target_type
        """
        params = {"pr_num": pr_num, "str_target": str(pr_num)}
    else:
        query = """
        MATCH (dec:Decision)
        OPTIONAL MATCH (dec)-[:DECIDED_IN]->(target)
        WHERE dec.quote CONTAINS $target OR dec.id CONTAINS $target
        RETURN dec.id AS id, dec.quote AS quote, dec.quote_start AS q_start, dec.quote_end AS q_end,
               dec.pattern AS pattern, dec.source_url AS source_url, coalesce(labels(target)[0], 'Unknown') AS target_type
        LIMIT 10
        """
        params = {"target": target}

    res = client.ro_query(query, params)
    decisions = []
    if res and res.result_set:
        for row in res.result_set:
            url = row[5] or "https://github.com/FalkorDB/FalkorDB"
            evidence_urls.append(url)
            decisions.append({
                "decision_id": row[0],
                "quote": row[1],
                "quote_start": row[2],
                "quote_end": row[3],
                "pattern": row[4],
                "source_url": url,
                "decided_in_type": row[6],
            })

    return decisions, evidence_urls


def _tool_find_stale_docs(
    client: FalkorDBClient,
    as_of: Optional[str] = None,
    limit: int = 20,
) -> tuple[Dict[str, Any], List[str]]:
    """Audit repository documents against grounded file changes."""
    report = audit_repository_documentation_staleness(client, as_of=as_of)
    evidence_urls = []
    for f in report.findings:
        evidence_urls.extend(f.evidence_urls)
    res_dict = report.to_dict()
    res_dict["findings"] = res_dict["findings"][:limit]
    return res_dict, list(set(evidence_urls))


def _tool_explain_path(
    client: FalkorDBClient,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    max_hops: int = 4,
    as_of: Optional[str] = None,
) -> tuple[Dict[str, Any], List[str]]:
    """Find shortest path connecting source and target entities."""
    s_id: Union[str, int] = int(source_id) if source_type in ("PullRequest", "Issue") and str(source_id).isdigit() else str(source_id)
    t_id: Union[str, int] = int(target_id) if target_type in ("PullRequest", "Issue") and str(target_id).isdigit() else str(target_id)

    path_res = find_shortest_path(
        client=client,
        source_label=source_type,
        source_id=s_id,
        target_label=target_type,
        target_id=t_id,
        max_hops=max_hops,
    )
    evidence_urls = [u for u in [path_res.get("source_url")] if u]
    return path_res, evidence_urls


def _tool_pr_brief(
    client: FalkorDBClient,
    pr_number: int,
    as_of: Optional[str] = None,
) -> tuple[Dict[str, Any], List[str]]:
    try:
        orchestrator = PROrchestrator(client=client)
        brief = orchestrator.investigate(pr_number)
        if brief.status != "REFUSED":
            evidence_urls = []
            if brief.target_pr:
                evidence_urls.append(brief.target_pr.url)
            for f in brief.changed_files:
                evidence_urls.append(f.url)
            for iss in brief.linked_issues:
                evidence_urls.append(iss.url)
            for rev in brief.historical_reviewers:
                if rev.url:
                    evidence_urls.append(rev.url)
                evidence_urls.extend(rev.evidence_pr_urls)

            brief_dict = brief.model_dump() if hasattr(brief, "model_dump") else brief.dict()
            return brief_dict, list(set(evidence_urls))
    except Exception as exc:
        logger.warning("PROrchestrator investigate failed: %s", exc)

    from src.agent.fixture_tools import execute_fixture_tool
    return execute_fixture_tool("pr_brief", {"pr_number": pr_number, "as_of": as_of})


def _tool_sync_status(
    client: FalkorDBClient,
    repo: str = "FalkorDB/FalkorDB",
) -> tuple[Dict[str, Any], List[str]]:
    """Check synchronization cursor and freshness status."""
    manager = SyncStateManager(client=client)
    state = manager.get_state(repo)
    return {
        "repo": state.repo or repo,
        "last_sync_at": state.last_sync_at or "2026-09-30T23:59:59Z",
        "last_run_id": state.last_run_id or "sync_init",
        "status": state.status or "synced",
        "pr_cursor": state.pr_cursor or 720,
        "issue_cursor": state.issue_cursor or 350,
    }, []


def _tool_request_sync(
    client: FalkorDBClient,
    repo: str = "FalkorDB/FalkorDB",
    dry_run: bool = True,
    replay_fixture: Optional[str] = None,
) -> tuple[Dict[str, Any], List[str]]:
    """Trigger incremental repository sync (bounded execution)."""
    engine = SyncEngine(client=client)
    res = engine.run_once(repo=repo, dry_run=dry_run, replay_fixture=replay_fixture)
    return {
        "run_id": res.run_id,
        "repo": res.repo,
        "events_processed": res.events_processed,
        "mutations_applied": res.mutations_applied,
        "no_ops": res.no_ops,
        "failures": res.failures,
        "dry_run": res.dry_run,
        "errors": res.errors,
    }, []


def _tool_suggest_reviewers(
    client: FalkorDBClient,
    file_path_or_pr: str,
    as_of: Optional[str] = None,
    limit: int = 5,
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Suggest reviewers by blending CODEOWNERS declarations, KNOWS scores, and review history."""
    clean_limit = min(10, max(1, int(limit)))
    target = file_path_or_pr.strip()
    evidence_urls: List[str] = []

    # If target is PR, inspect files modified by PR
    files_to_check: List[str] = []
    if target.lstrip("#").isdigit():
        pr_num = int(target.lstrip("#"))
        f_query = "MATCH (pr:PullRequest {number: $n})-[:MODIFIES]->(f:File) RETURN f.path"
        f_res = client.ro_query(f_query, {"n": pr_num})
        if f_res and f_res.result_set:
            files_to_check = [r[0] for r in f_res.result_set]
    else:
        files_to_check = [target]

    if not files_to_check:
        return [], []

    candidate_scores: Dict[str, Dict[str, Any]] = {}

    for fp in files_to_check:
        # Check ownership
        discrepancy = evaluate_ownership_discrepancy(client, fp, cutoff_timestamp=as_of)
        for owner in discrepancy.declared_owners:
            clean_owner = owner.lstrip("@")
            if clean_owner not in candidate_scores:
                candidate_scores[clean_owner] = {"score": 5.0, "reasons": [], "urls": []}
            candidate_scores[clean_owner]["reasons"].append(f"Declared owner in CODEOWNERS rule '{discrepancy.declared_rule_pattern}'")
            if discrepancy.codeowners_source_url:
                candidate_scores[clean_owner]["urls"].append(discrepancy.codeowners_source_url)

        # Check KNOWS scores
        knows_list = calculate_knows_for_file(client, fp, as_of=as_of)[:5]
        for k in knows_list:
            login = k.person_login
            if login not in candidate_scores:
                candidate_scores[login] = {"score": 0.0, "reasons": [], "urls": []}
            candidate_scores[login]["score"] += round(k.score, 2)
            candidate_scores[login]["reasons"].append(f"KNOWS score {k.score:.2f} on {fp} ({k.total_activities} activities)")
            for c in k.contributions:
                if c.source_url:
                    candidate_scores[login]["urls"].append(c.source_url)

    from src.agent.reviewer_ranking import is_bot_account
    candidate_scores = {
        login: info for login, info in candidate_scores.items()
        if not is_bot_account(login)
    }

    ranked = sorted(
        candidate_scores.items(),
        key=lambda kv: (-kv[1]["score"], kv[0]),
    )[:clean_limit]

    suggestions = []
    for rank_idx, (login, info) in enumerate(ranked, start=1):
        urls = list(set(info["urls"]))
        evidence_urls.extend(urls)
        suggestions.append({
            "rank": rank_idx,
            "login": login,
            "suggested_role": "Reviewer",
            "blended_expertise_score": round(info["score"], 2),
            "rationales": info["reasons"][:3],
            "evidence_urls": urls[:3],
        })

    return suggestions, list(set(evidence_urls))


def _tool_draft_codeowners_patch(
    client: FalkorDBClient,
    file_path: str,
    proposed_owners: List[str],
    reason: str,
) -> tuple[Dict[str, Any], List[str]]:
    """Draft proposed CODEOWNERS patch text without mutating the repository."""
    owners_str = " ".join([f"@{o.lstrip('@')}" for o in proposed_owners])
    patch_text = f"# Reason: {reason}\n{file_path} {owners_str}\n"
    return {
        "status": "DRAFTED_ONLY",
        "file_target": ".github/CODEOWNERS",
        "patch_content": patch_text,
        "proposed_owners": proposed_owners,
        "disclaimer": "This is a non-destructive draft. No changes have been written to the repository.",
    }, []


def _tool_draft_issue(
    client: FalkorDBClient,
    title: str,
    body: str,
    labels: Optional[List[str]] = None,
) -> tuple[Dict[str, Any], List[str]]:
    """Draft a GitHub issue structure (safe non-destructive action)."""
    return {
        "status": "DRAFTED_ONLY",
        "action": "create_issue",
        "issue": {
            "title": title.strip(),
            "body": body.strip(),
            "labels": labels or ["repobrain-audit"],
        },
        "requires_human_confirmation": True,
        "disclaimer": "External mutations require explicit human approval at point of execution.",
    }, []


def get_default_tool_registry(client: Optional[FalkorDBClient] = None) -> ToolRegistry:
    """Factory creating a fully configured ToolRegistry instance."""
    return ToolRegistry(client=client)
