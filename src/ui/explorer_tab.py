"""RepoBrain — Graph Explorer Tab.

Interactive visual neighborhood explorer rendering FalkorDB nodes and relationships
via an embedded Vis.js network canvas. Color-codes entity types and highlights
active vs closed/tombstoned entities.
"""

import json
import html
from typing import Any, Dict, List, Optional
import streamlit as st
import streamlit.components.v1 as components

from src.db import FalkorDBClient


ENTITY_COLORS = {
    "Person": "#3B82F6",       # Blue
    "PullRequest": "#8B5CF6",  # Purple
    "Issue": "#F97316",        # Orange
    "File": "#10B981",         # Green
    "Team": "#F59E0B",         # Amber
    "Document": "#06B6D4",     # Cyan
    "Decision": "#EC4899",     # Pink
    "SyncRun": "#6B7280",      # Gray
}


def render_explorer_tab(client: Optional[FalkorDBClient], config: Dict[str, Any]) -> None:
    """Render the Graph Explorer interactive neighborhood visualizer."""
    st.subheader("🔍 Knowledge Graph Explorer")
    st.markdown(
        "Explore local entity neighborhoods, provenance, and relationships in FalkorDB. "
        "Drag nodes to rearrange, scroll to zoom, and select entities to inspect property records."
    )

    if not client:
        st.error("[OFFLINE] Cannot explore graph: FalkorDB is offline on `localhost:6379`.")
        return

    # Search & Filter Controls
    col_search, col_depth, col_limit = st.columns([3, 1, 1])

    with col_search:
        target_entity = st.text_input(
            "Center Entity (ID, path, login, or number):",
            value="src/module.c",
            placeholder="e.g. src/module.c, 3339, swilly22, @FalkorDB/falkordb-core",
            key="graph_explorer_entity_input",
        ).strip()

    with col_depth:
        depth = st.selectbox("Hops", [1, 2], index=0, key="graph_explorer_depth")

    with col_limit:
        limit = st.slider("Node Limit", min_value=10, max_value=50, value=25, key="graph_explorer_limit")

    # Quick Presets
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1:
        if st.button("File: src/module.c", use_container_width=True):
            target_entity = "src/module.c"
    with col_p2:
        if st.button("PR: #3339", use_container_width=True):
            target_entity = "3339"
    with col_p3:
        if st.button("Person: swilly22", use_container_width=True):
            target_entity = "swilly22"
    with col_p4:
        if st.button("Team: @falkordb-core", use_container_width=True):
            target_entity = "@FalkorDB/falkordb-core"

    if not target_entity:
        st.info("Enter an entity identifier above to explore its neighborhood.")
        return

    # Fetch neighborhood data safely using read-only query
    nodes_map: Dict[str, Dict[str, Any]] = {}
    edges_list: List[Dict[str, Any]] = []

    try:
        # Determine number vs string target
        num_target = int(target_entity) if target_entity.isdigit() else -1

        query = """
        MATCH (center)
        WHERE (center.id = $id OR center.path = $id OR center.login = $id OR center.name = $id
               OR (center.number IS NOT NULL AND center.number = $num))
        OPTIONAL MATCH (center)-[r]-(neighbor)
        RETURN center, labels(center) AS center_labels, r, type(r) AS rel_type,
               neighbor, labels(neighbor) AS neighbor_labels
        LIMIT $limit
        """
        params = {"id": target_entity, "num": num_target, "limit": limit}
        res = client.ro_query(query, params)

        if not res or not res.result_set:
            st.warning(f"No entity matching '{target_entity}' found in the graph.")
            return

        for row in res.result_set:
            c_node, c_labels, rel, rel_type, n_node, n_labels = row

            # Center Node
            if c_node:
                c_lbl = c_labels[0] if c_labels else "Entity"
                c_props = c_node.properties if hasattr(c_node, "properties") else {}
                c_id = str(c_props.get("id") or c_props.get("path") or c_props.get("login") or c_props.get("number") or "center")
                if c_id not in nodes_map:
                    nodes_map[c_id] = {
                        "id": c_id,
                        "label": c_id,
                        "type": c_lbl,
                        "status": c_props.get("status", "active"),
                        "props": c_props,
                    }

            # Neighbor Node & Edge
            if n_node and rel:
                n_lbl = n_labels[0] if n_labels else "Entity"
                n_props = n_node.properties if hasattr(n_node, "properties") else {}
                n_id = str(n_props.get("id") or n_props.get("path") or n_props.get("login") or n_props.get("number") or "neighbor")
                if n_id not in nodes_map:
                    nodes_map[n_id] = {
                        "id": n_id,
                        "label": n_id,
                        "type": n_lbl,
                        "status": n_props.get("status", "active"),
                        "props": n_props,
                    }

                rel_props = rel.properties if hasattr(rel, "properties") else {}
                edges_list.append({
                    "from": c_id,
                    "to": n_id,
                    "label": rel_type or "RELATED",
                    "valid_to": rel_props.get("valid_to"),
                })

    except Exception as exc:
        st.error(f"Error executing neighborhood query: {exc}")
        return

    if not nodes_map:
        st.warning("No neighborhood entities found.")
        return

    # Visualizer Container
    st.markdown(f"**Found {len(nodes_map)} nodes and {len(edges_list)} relationships around `{target_entity}`:**")

    # Build Vis.js network payload
    vis_nodes = []
    for nid, ndata in nodes_map.items():
        ntype = ndata["type"]
        color = ENTITY_COLORS.get(ntype, "#6B7280")
        is_tombstoned = ndata.get("status") == "tombstoned"

        vis_nodes.append({
            "id": nid,
            "label": f"{ndata['label']}\n({ntype})",
            "title": f"Type: {ntype} | Status: {ndata['status']}",
            "color": {
                "background": "#9CA3AF" if is_tombstoned else color,
                "border": "#DC2626" if is_tombstoned else "#1F2937",
                "highlight": {"background": "#FBBF24", "border": "#B45309"},
            },
            "font": {"color": "#111827", "size": 12, "face": "Inter, sans-serif"},
            "shape": "box",
            "borderWidth": 2,
        })

    vis_edges = []
    for e in edges_list:
        is_closed = bool(e.get("valid_to"))
        vis_edges.append({
            "from": e["from"],
            "to": e["to"],
            "label": e["label"],
            "color": {"color": "#9CA3AF" if is_closed else "#4B5563"},
            "dashes": is_closed,
            "arrows": "to",
            "font": {"size": 10, "align": "middle", "color": "#374151"},
        })

    # Vis.js HTML template
    vis_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
      <style>
        body {{ margin: 0; padding: 0; background: #F9FAFB; font-family: Inter, sans-serif; }}
        #network-canvas {{ width: 100%; height: 460px; border: 1px solid #E5E7EB; border-radius: 8px; }}
        #legend {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; font-size: 11px; }}
        .legend-item {{ display: flex; align-items: center; gap: 4px; }}
        .legend-badge {{ width: 12px; height: 12px; border-radius: 3px; }}
      </style>
    </head>
    <body>
      <div id="network-canvas"></div>
      <div id="legend">
        <div class="legend-item"><div class="legend-badge" style="background:#3B82F6;"></div> Person</div>
        <div class="legend-item"><div class="legend-badge" style="background:#8B5CF6;"></div> PullRequest</div>
        <div class="legend-item"><div class="legend-badge" style="background:#F97316;"></div> Issue</div>
        <div class="legend-item"><div class="legend-badge" style="background:#10B981;"></div> File</div>
        <div class="legend-item"><div class="legend-badge" style="background:#F59E0B;"></div> Team</div>
        <div class="legend-item"><div class="legend-badge" style="background:#06B6D4;"></div> Document</div>
        <div class="legend-item"><div class="legend-badge" style="background:#EC4899;"></div> Decision</div>
        <div class="legend-item"><div class="legend-badge" style="background:#9CA3AF; border: 1px dashed red;"></div> Tombstoned / Closed</div>
      </div>
      <script type="text/javascript">
        var nodes = new vis.DataSet({json.dumps(vis_nodes)});
        var edges = new vis.DataSet({json.dumps(vis_edges)});
        var container = document.getElementById('network-canvas');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
          physics: {{
            barnesHut: {{ springLength: 100, springConstant: 0.04, damping: 0.09 }},
            stabilization: {{ iterations: 100 }}
          }},
          interaction: {{ hover: true, tooltipDelay: 100, zoomView: true, dragView: true }}
        }};
        var network = new vis.Network(container, data, options);
      </script>
    </body>
    </html>
    """

    # Render embedded HTML component with fallback
    try:
        components.html(vis_html, height=520, scrolling=False)
    except Exception as exc:
        st.warning(f"Interactive visualizer could not render: {exc}. Displaying tabular neighborhood data below.")

    # Property Inspector Below Graph
    with st.expander("📋 Neighborhood Entity & Property Records", expanded=False):
        col_ntbl, col_etbl = st.columns(2)
        with col_ntbl:
            st.markdown("**Entities in Neighborhood:**")
            node_table = []
            for nid, n in nodes_map.items():
                p = n.get("props", {})
                url = p.get("source_url") or p.get("url") or "-"
                link_md = f"[{nid}]({url})" if url.startswith("http") else nid
                node_table.append({
                    "Entity": link_md,
                    "Type": n["type"],
                    "Status": n["status"],
                })
            st.markdown(
                "| Entity | Type | Status |\n|---|---|---|\n" +
                "\n".join(f"| {r['Entity']} | `{r['Type']}` | `{r['Status']}` |" for r in node_table)
            )

        with col_etbl:
            st.markdown("**Relationships in Neighborhood:**")
            edge_table = [
                f"| `{e['from']}` | &rarr; `{e['label']}` &rarr; | `{e['to']}` | {'[CLOSED]' if e.get('valid_to') else '[ACTIVE]'} |"
                for e in edges_list
            ]
            st.markdown(
                "| Source | Rel Type | Target | State |\n|---|---|---|---|\n" +
                "\n".join(edge_table)
            )
