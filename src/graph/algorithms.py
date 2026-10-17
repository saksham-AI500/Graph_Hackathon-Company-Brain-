"""Graph algorithms and explanation path generation for FalkorDB repo_kg.

Provides:
1. Maintainer Review Centrality via native FalkorDB `CALL algo.pageRank('Person', 'REVIEWED')`.
2. Multi-hop Explanation Paths via native FalkorDB `shortestPath((src)-[*..4]-(dst))`.
"""

from typing import Any, Dict, List, Optional, Union
from src.db import FalkorDBClient


def run_maintainer_pagerank(
    client: FalkorDBClient, limit: int = 10, include_bots: bool = False
) -> List[Dict[str, Any]]:
    """Execute native FalkorDB PageRank algorithm to measure maintainer review influence.

    Runs FalkorDB PageRank over REVIEWED relationships to compute Pull Request review
    depth, then projects the PageRank weights onto reviewing Person nodes.
    Reviewers who review heavily scrutinized PRs accumulate higher review influence.
    By default, automated bot accounts are excluded unless include_bots=True.
    """
    query = """
    CALL algo.pageRank(null, 'REVIEWED') YIELD node, score
    WHERE 'PullRequest' IN labels(node)
    WITH node AS pr, score
    MATCH (p:Person)-[:REVIEWED]->(pr)
    RETURN p.login AS login, p.url AS url, sum(score) AS score, count(pr) AS review_count
    ORDER BY score DESC
    """
    try:
        res = client.ro_query(query)
        if res and res.result_set:
            ranked = []
            for row in res.result_set:
                login = str(row[0])
                url = str(row[1])
                score = float(row[2])
                rev_count = int(row[3])
                is_bot = "[bot]" in login.lower() or login.lower() in ("github-actions", "dependabot")
                if not include_bots and is_bot:
                    continue
                ranked.append({
                    "login": login,
                    "score": round(score, 4),
                    "url": url,
                    "review_count": rev_count,
                    "is_bot": is_bot,
                })
            return ranked[:limit]
    except Exception:
        pass

    # Fallback to direct Person pageRank if projected join fails
    fallback_query = "CALL algo.pageRank('Person', 'REVIEWED')"
    try:
        res = client.ro_query(fallback_query)
        if res and res.result_set:
            ranked = []
            for row in res.result_set:
                node, score = row[0], float(row[1])
                login = node.properties.get("login", "unknown")
                url = node.properties.get("url", f"https://github.com/{login}")
                is_bot = "[bot]" in login.lower() or login.lower() in ("github-actions", "dependabot")
                if not include_bots and is_bot:
                    continue
                ranked.append({
                    "login": login,
                    "score": round(score, 4),
                    "url": url,
                    "review_count": 0,
                    "is_bot": is_bot,
                })
            ranked.sort(key=lambda x: x["score"], reverse=True)
            return ranked[:limit]
    except Exception:
        return []

    return []


def find_explanation_path(
    client: FalkorDBClient,
    pr_number: int,
    target_identifier: Union[int, str],
    max_depth: int = 4,
) -> Optional[Dict[str, Any]]:
    """Discover the shortest relational evidence path between target PR and any target entity.

    Connects PR to person, file, issue, or rule via FalkorDB `shortestPath(...)`.
    Returns structured, human-auditable path segments and source URLs.
    """
    # Parameterized query matching destination by login, number, or path
    depth = max(1, int(max_depth))
    # FalkorDB native shortest path query supporting multi-directional traversal
    query = f"""
    MATCH (src:PullRequest {{number: $pr_num}}), (dst)
    WHERE (dst.login = $ident OR dst.number = $ident_int OR dst.path = $ident OR dst.name = $ident)
      AND src <> dst
    MATCH path = (src)-[*1..{depth}]-(dst)
    RETURN path
    ORDER BY length(path) ASC
    LIMIT 1
    """
    ident_str = str(target_identifier)
    ident_int = int(target_identifier) if ident_str.isdigit() else -1

    try:
        res = client.ro_query(query, {"pr_num": pr_number, "ident": ident_str, "ident_int": ident_int})
    except Exception:
        return None

    if not res or not res.result_set or not res.result_set[0] or not res.result_set[0][0]:
        return None

    path_obj = res.result_set[0][0]
    nodes = path_obj.nodes()
    edges = path_obj.edges()

    parsed_nodes = []
    source_urls = []
    for n in nodes:
        labels = n.labels if hasattr(n, "labels") else ["Entity"]
        lbl = labels[0] if labels else "Entity"
        props = n.properties or {}
        name = props.get("login") or props.get("path") or props.get("title") or props.get("name") or str(props.get("number", "Unknown"))
        url = props.get("url")
        if url:
            source_urls.append(url)
        parsed_nodes.append({
            "label": lbl,
            "name": str(name),
            "properties": props,
            "url": url,
        })

    parsed_edges = []
    for e in edges:
        rel_type = e.relation if hasattr(e, "relation") else "CONNECTED_TO"
        props = e.properties or {}
        parsed_edges.append({
            "type": rel_type,
            "properties": props,
        })

    # Construct human-readable sequential hops
    hops = []
    for i in range(len(parsed_edges)):
        src = parsed_nodes[i]
        edge = parsed_edges[i]
        dst = parsed_nodes[i + 1]
        hops.append({
            "step": i + 1,
            "source": f"{src['label']}: {src['name']}",
            "relationship": edge["type"],
            "target": f"{dst['label']}: {dst['name']}",
            "source_url": src.get("url"),
            "target_url": dst.get("url"),
        })

    readable_summary = " -> ".join(
        [f"({n['label']}: {n['name']})" for n in parsed_nodes]
    )

    return {
        "start_pr": pr_number,
        "target_identifier": target_identifier,
        "hop_count": len(parsed_edges),
        "readable_summary": readable_summary,
        "hops": hops,
        "nodes": parsed_nodes,
        "relationships": parsed_edges,
        "evidence_urls": list(dict.fromkeys(source_urls)),
    }


def find_shortest_path(
    client: FalkorDBClient,
    source_label: str,
    source_id: Union[int, str],
    target_label: str,
    target_id: Union[int, str],
    max_hops: int = 4,
) -> Dict[str, Any]:
    """Discover the shortest path between any two graph entities using supported Cypher traversal."""
    depth = max(1, min(6, int(max_hops)))
    s_id_key = "number" if source_label in ("PullRequest", "Issue") else ("login" if source_label == "Person" else ("name" if source_label == "Team" else ("path" if source_label in ("File", "Document") else "id")))
    t_id_key = "number" if target_label in ("PullRequest", "Issue") else ("login" if target_label == "Person" else ("name" if target_label == "Team" else ("path" if target_label in ("File", "Document") else "id")))

    s_val = int(source_id) if source_label in ("PullRequest", "Issue") and str(source_id).isdigit() else str(source_id)
    t_val = int(target_id) if target_label in ("PullRequest", "Issue") and str(target_id).isdigit() else str(target_id)

    query = f"""
    MATCH (src:{source_label} {{{s_id_key}: $s_val}}), (dst:{target_label} {{{t_id_key}: $t_val}})
    WHERE src <> dst
    MATCH path = (src)-[*1..{depth}]-(dst)
    RETURN path
    ORDER BY length(path) ASC
    LIMIT 1
    """
    try:
        res = client.ro_query(query, {"s_val": s_val, "t_val": t_val})
        if res and res.result_set and res.result_set[0] and res.result_set[0][0]:
            path_obj = res.result_set[0][0]
            nodes = path_obj.nodes()
            edges = path_obj.edges()
            parsed_nodes = []
            source_urls = []
            for n in nodes:
                lbls = n.labels if hasattr(n, "labels") else ["Entity"]
                lbl = lbls[0] if lbls else "Entity"
                props = n.properties or {}
                name = props.get("login") or props.get("path") or props.get("title") or props.get("name") or str(props.get("number", "Unknown"))
                url = props.get("url") or props.get("source_url")
                if url:
                    source_urls.append(url)
                parsed_nodes.append({"label": lbl, "name": str(name), "url": url})
            parsed_edges = []
            for e in edges:
                rel = e.relation if hasattr(e, "relation") else "CONNECTED_TO"
                parsed_edges.append({"type": rel})
            hops = []
            for i in range(len(parsed_edges)):
                src = parsed_nodes[i]
                edge = parsed_edges[i]
                dst = parsed_nodes[i + 1]
                hops.append({
                    "step": i + 1,
                    "source": f"{src['label']}: {src['name']}",
                    "relationship": edge["type"],
                    "target": f"{dst['label']}: {dst['name']}",
                    "source_url": src.get("url"),
                    "target_url": dst.get("url"),
                })
            return {
                "source": f"{source_label}:{source_id}",
                "target": f"{target_label}:{target_id}",
                "hop_count": len(parsed_edges),
                "summary": " -> ".join([f"({n['label']}: {n['name']})" for n in parsed_nodes]),
                "hops": hops,
                "evidence_urls": list(dict.fromkeys(source_urls)),
            }
    except Exception:
        pass

    return {
        "source": f"{source_label}:{source_id}",
        "target": f"{target_label}:{target_id}",
        "hop_count": 0,
        "summary": "No path found within depth limit",
        "hops": [],
        "evidence_urls": [],
    }

