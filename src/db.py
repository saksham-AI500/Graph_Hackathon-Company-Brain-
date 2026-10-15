"""FalkorDB Client and Health-Check module for RepoBrain."""

import os
import time
from typing import Any, Dict, List, Optional
import falkordb


class FalkorDBClient:
    """FalkorDB connection manager and query runner."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        graph_name: Optional[str] = None,
    ):
        self.host = host or os.getenv("FALKORDB_HOST", "localhost")
        self.port = port or int(os.getenv("FALKORDB_PORT", "6379"))
        self.graph_name = graph_name or os.getenv("FALKORDB_GRAPH", "repo_kg")

        self._driver: Optional[falkordb.FalkorDB] = None
        self._graph: Optional[falkordb.Graph] = None
        self._connect()

    def _connect(self) -> None:
        """Initialize connection to FalkorDB and select the target graph."""
        self._driver = falkordb.FalkorDB(host=self.host, port=self.port)
        self._graph = self._driver.select_graph(self.graph_name)

    @property
    def graph(self) -> falkordb.Graph:
        """Return the active FalkorDB graph handle."""
        if self._graph is None:
            self._connect()
        return self._graph

    def ping(self) -> Dict[str, Any]:
        """Verify connection and measure round-trip latency in milliseconds."""
        start_time = time.perf_counter()
        result = self.ro_query("RETURN 1 AS ping")
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        val = result.result_set[0][0] if result and result.result_set else None
        return {
            "status": "healthy" if val == 1 else "unhealthy",
            "ping": val,
            "latency_ms": round(latency_ms, 2),
            "host": self.host,
            "port": self.port,
            "graph_name": self.graph_name,
        }

    def query(
        self, query_str: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Execute a read-write Cypher query with optional parameters."""
        return self.graph.query(query_str, params=params)

    def ro_query(
        self, query_str: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Execute a strictly read-only Cypher query with optional parameters."""
        return self.graph.ro_query(query_str, params=params)

    def get_counts(self) -> Dict[str, int]:
        """Return current node and relationship counts in the active graph."""
        node_res = self.ro_query("MATCH (n) RETURN count(n) AS node_count")
        node_count = node_res.result_set[0][0] if node_res and node_res.result_set else 0

        edge_res = self.ro_query("MATCH ()-[r]->() RETURN count(r) AS edge_count")
        edge_count = edge_res.result_set[0][0] if edge_res and edge_res.result_set else 0

        return {"nodes": int(node_count), "edges": int(edge_count)}

    def execute_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health-check and return structured report."""
        ping_info = self.ping()
        counts = self.get_counts()
        return {
            "connection": ping_info,
            "counts": counts,
        }


def main() -> None:
    """CLI entrypoint for connection and health verification."""
    print("=" * 60)
    print("RepoBrain - FalkorDB Health Check")
    print("=" * 60)
    try:
        client = FalkorDBClient()
        report = client.execute_health_check()
        conn = report["connection"]
        counts = report["counts"]
        print(f"Status:      {conn['status'].upper()}")
        print(f"Host:        {conn['host']}:{conn['port']}")
        print(f"Graph:       {conn['graph_name']}")
        print(f"Latency:     {conn['latency_ms']} ms")
        print(f"Nodes:       {counts['nodes']}")
        print(f"Edges:       {counts['edges']}")
        print("=" * 60)
        print("Health Check PASSED.")
    except Exception as exc:
        print(f"Health Check FAILED: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
