from src.api.server import get_falkordb_client, get_graph_neighborhood

client = get_falkordb_client()
data = get_graph_neighborhood("caleb-rivers")
nodes = data["nodes"]
edges = data["edges"]
print(f"Seeding {len(nodes)} nodes and {len(edges)} edges into FalkorDB...")

for n in nodes:
    nid = n["id"]
    label = n.get("label") or (n.get("labels", ["Entity"])[0] if isinstance(n.get("labels"), list) else "Entity")
    props = dict(n.get("properties", {}))
    props["id"] = nid
    if "login" in props:
        props["login"] = str(props["login"])
    client.query(f"MERGE (n:{label} {{id: $id}}) SET n += $props", {"id": nid, "props": props})

for e in edges:
    s = e["source"]
    t = e["target"]
    rel = e["type"]
    client.query(
        f"MATCH (a {{id: $s}}), (b {{id: $t}}) MERGE (a)-[r:{rel}]->(b)",
        {"s": s, "t": t}
    )

print("Seeding complete! Verifying via live Cypher query:")
query = """
MATCH (n) WHERE n.id = $entity OR n.login = $entity
MATCH p = (n)-[r:MODIFIES|REVIEWED|AUTHORED|OWNS|MEMBER_OF*1..2]-(m)
UNWIND relationships(p) AS rel
WITH startNode(rel) AS src, rel, endNode(rel) AS dst
RETURN count(rel)
"""
res = client.ro_query(query, {"entity": "caleb-rivers"})
print("Count of live relationships for caleb-rivers in FalkorDB:", res.result_set)
