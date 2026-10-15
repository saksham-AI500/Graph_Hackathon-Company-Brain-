"""Graph schema and index definitions for FalkorDB repo_kg."""

from typing import List
from src.db import FalkorDBClient

INDEX_STATEMENTS = [
    "CREATE INDEX FOR (p:Person) ON (p.login)",
    "CREATE INDEX FOR (pr:PullRequest) ON (pr.number)",
    "CREATE INDEX FOR (i:Issue) ON (i.number)",
    "CREATE INDEX FOR (f:File) ON (f.path)",
]


def ensure_schema_indexes(client: FalkorDBClient) -> List[str]:
    """Ensure all required indexes exist in the graph. Returns list of applied statements."""
    applied = []
    for stmt in INDEX_STATEMENTS:
        try:
            client.query(stmt)
            applied.append(stmt)
        except Exception as exc:
            # FalkorDB may error if index already exists
            if "already indexed" in str(exc).lower() or "equivalent index already exists" in str(exc).lower():
                continue
            # Re-raise if unexpected
            raise
    return applied


if __name__ == "__main__":
    c = FalkorDBClient()
    applied = ensure_schema_indexes(c)
    print(f"Applied indexes: {len(applied)}")
