"""Idempotent graph ingestion loader for FalkorDB repo_kg."""

from typing import Any, Dict, List
from src.db import FalkorDBClient
from src.graph.schema import ensure_schema_indexes
from src.ingestion.models import PullRequestRecord


class GraphLoader:
    """Loads validated GitHub records into FalkorDB idempotently using MERGE."""

    def __init__(self, client: FalkorDBClient):
        self.client = client
        ensure_schema_indexes(self.client)

    def load_pull_request(self, pr: PullRequestRecord) -> Dict[str, int]:
        """Idempotently ingest a single PullRequestRecord and its linked entities."""
        stats = {
            "persons": 0,
            "prs": 0,
            "files": 0,
            "issues": 0,
            "authored_edges": 0,
            "reviewed_edges": 0,
            "modifies_edges": 0,
            "resolves_edges": 0,
            "reported_edges": 0,
        }

        # 1. Merge PR Author (Person)
        self.client.query(
            """
            MERGE (p:Person {login: $login})
            ON CREATE SET p.url = $url, p.created_at = timestamp()
            ON MATCH SET p.url = $url
            """,
            {"login": pr.author_login, "url": pr.author_url},
        )
        stats["persons"] += 1

        # 2. Merge PullRequest
        self.client.query(
            """
            MERGE (pr:PullRequest {number: $number})
            ON CREATE SET pr.title = $title, pr.url = $url, pr.state = $state,
                          pr.created_at = $created_at, pr.merged_at = $merged_at
            ON MATCH SET pr.title = $title, pr.url = $url, pr.state = $state,
                         pr.created_at = $created_at, pr.merged_at = $merged_at
            """,
            {
                "number": pr.number,
                "title": pr.title,
                "url": pr.url,
                "state": pr.state,
                "created_at": pr.created_at or "",
                "merged_at": pr.merged_at or "",
            },
        )
        stats["prs"] += 1

        # 3. Merge (:Person)-[:AUTHORED]->(:PullRequest)
        self.client.query(
            """
            MATCH (p:Person {login: $login}), (pr:PullRequest {number: $number})
            MERGE (p)-[:AUTHORED]->(pr)
            """,
            {"login": pr.author_login, "number": pr.number},
        )
        stats["authored_edges"] += 1

        # 4. Merge Reviews and Reviewers
        for rev in pr.reviews:
            self.client.query(
                """
                MERGE (p:Person {login: $login})
                ON CREATE SET p.url = $url, p.created_at = timestamp()
                ON MATCH SET p.url = $url
                """,
                {"login": rev.author_login, "url": rev.author_url},
            )
            self.client.query(
                """
                MATCH (p:Person {login: $login}), (pr:PullRequest {number: $number})
                MERGE (p)-[r:REVIEWED {state: $state}]->(pr)
                ON CREATE SET r.submitted_at = $submitted_at
                ON MATCH SET r.submitted_at = $submitted_at
                """,
                {
                    "login": rev.author_login,
                    "number": pr.number,
                    "state": rev.state,
                    "submitted_at": rev.submitted_at or "",
                },
            )
            stats["reviewed_edges"] += 1

        # 5. Merge Files and (:PullRequest)-[:MODIFIES]->(:File)
        for f in pr.files:
            self.client.query(
                """
                MERGE (file:File {path: $path})
                ON CREATE SET file.url = $url
                ON MATCH SET file.url = $url
                """,
                {"path": f.path, "url": f.url},
            )
            stats["files"] += 1

            self.client.query(
                """
                MATCH (pr:PullRequest {number: $number}), (file:File {path: $path})
                MERGE (pr)-[r:MODIFIES]->(file)
                ON CREATE SET r.additions = $additions, r.deletions = $deletions
                ON MATCH SET r.additions = $additions, r.deletions = $deletions
                """,
                {
                    "number": pr.number,
                    "path": f.path,
                    "additions": f.additions,
                    "deletions": f.deletions,
                },
            )
            stats["modifies_edges"] += 1

        # 6. Merge Resolved Issues and (:PullRequest)-[:RESOLVES]->(:Issue)
        for iss in pr.resolved_issues:
            self.client.query(
                """
                MERGE (i:Issue {number: $number})
                ON CREATE SET i.title = $title, i.url = $url, i.state = $state,
                              i.created_at = $created_at, i.closed_at = $closed_at
                ON MATCH SET i.title = $title, i.url = $url, i.state = $state,
                             i.created_at = $created_at, i.closed_at = $closed_at
                """,
                {
                    "number": iss.number,
                    "title": iss.title,
                    "url": iss.url,
                    "state": iss.state,
                    "created_at": iss.created_at or "",
                    "closed_at": iss.closed_at or "",
                },
            )
            stats["issues"] += 1

            self.client.query(
                """
                MATCH (pr:PullRequest {number: $pr_number}), (i:Issue {number: $issue_number})
                MERGE (pr)-[:RESOLVES]->(i)
                """,
                {"pr_number": pr.number, "issue_number": iss.number},
            )
            stats["resolves_edges"] += 1

            if iss.author_login and iss.author_url:
                self.client.query(
                    """
                    MERGE (p:Person {login: $login})
                    ON CREATE SET p.url = $url
                    ON MATCH SET p.url = $url
                    """,
                    {"login": iss.author_login, "url": iss.author_url},
                )
                self.client.query(
                    """
                    MATCH (p:Person {login: $login}), (i:Issue {number: $number})
                    MERGE (p)-[:REPORTED]->(i)
                    """,
                    {"login": iss.author_login, "number": iss.number},
                )
                stats["reported_edges"] += 1

        return stats

    def load_pull_requests(self, prs: List[PullRequestRecord]) -> Dict[str, Any]:
        """Ingest multiple pull request records and return aggregate summary."""
        total_processed = 0
        for pr in prs:
            self.load_pull_request(pr)
            total_processed += 1

        counts = self.client.get_counts()
        return {
            "prs_processed": total_processed,
            "final_counts": counts,
        }
