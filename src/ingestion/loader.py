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
                          pr.created_at = CASE WHEN $created_at = '' THEN null ELSE $created_at END,
                          pr.merged_at = CASE WHEN $merged_at = '' THEN null ELSE $merged_at END
            ON MATCH SET pr.title = $title, pr.url = $url, pr.state = $state,
                         pr.created_at = CASE WHEN $created_at = '' THEN null ELSE $created_at END,
                         pr.merged_at = CASE WHEN $merged_at = '' THEN null ELSE $merged_at END
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
            if rev.id is not None:
                self.client.query(
                    """
                    MATCH (p:Person {login: $login}), (pr:PullRequest {number: $number})
                    MERGE (p)-[r:REVIEWED {id: $review_id}]->(pr)
                    ON CREATE SET r.state = $state,
                                  r.submitted_at = CASE WHEN $submitted_at = '' THEN null ELSE $submitted_at END
                    ON MATCH SET r.state = $state,
                                 r.submitted_at = CASE WHEN $submitted_at = '' THEN null ELSE $submitted_at END
                    """,
                    {
                        "login": rev.author_login,
                        "number": pr.number,
                        "review_id": rev.id,
                        "state": rev.state,
                        "submitted_at": rev.submitted_at or "",
                    },
                )
            else:
                self.client.query(
                    """
                    MATCH (p:Person {login: $login}), (pr:PullRequest {number: $number})
                    MERGE (p)-[r:REVIEWED {state: $state}]->(pr)
                    ON CREATE SET r.submitted_at = CASE WHEN $submitted_at = '' THEN null ELSE $submitted_at END
                    ON MATCH SET r.submitted_at = CASE WHEN $submitted_at = '' THEN null ELSE $submitted_at END
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
                              i.created_at = CASE WHEN $created_at = '' THEN null ELSE $created_at END,
                              i.closed_at = CASE WHEN $closed_at = '' THEN null ELSE $closed_at END
                ON MATCH SET i.title = $title, i.url = $url, i.state = $state,
                             i.created_at = CASE WHEN $created_at = '' THEN null ELSE $created_at END,
                             i.closed_at = CASE WHEN $closed_at = '' THEN null ELSE $closed_at END
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

    def load_chats(self, chat_threads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ingest synthetic Slack chat threads into graph as Comment and Decision nodes."""
        stats = {
            "threads_processed": 0,
            "comments_created": 0,
            "decisions_created": 0,
        }
        for thread in chat_threads:
            t_id = thread.get("thread_id")
            channel = thread.get("channel")
            thread_url = thread.get("thread_url")
            has_decision = thread.get("has_decision", False)
            decision_quote = thread.get("decision_quote")
            linked_entity = thread.get("linked_entity")

            for msg in thread.get("messages", []):
                m_id = msg.get("message_id")
                author = msg.get("author")
                text = msg.get("text", "")
                ts = msg.get("timestamp")

                # Ingest author and comment
                self.client.query(
                    """
                    MERGE (p:Person {login: $author})
                    ON CREATE SET p.url = $author_url
                    MERGE (c:Comment {id: $m_id})
                    ON CREATE SET c.channel = $channel,
                                  c.author = $author,
                                  c.text = $text,
                                  c.timestamp = CASE WHEN $ts = '' THEN null ELSE $ts END,
                                  c.url = $thread_url
                    MERGE (p)-[:POSTED]->(c)
                    """,
                    {
                        "author": author,
                        "author_url": f"https://github.com/{author}",
                        "m_id": m_id,
                        "channel": channel,
                        "text": text,
                        "ts": ts or "",
                        "thread_url": thread_url or "",
                    },
                )
                stats["comments_created"] += 1

                # If message contains the decision quote, link decision node
                if has_decision and decision_quote and (decision_quote in text or "Decision:" in text or "Reversal:" in text):
                    dec_id = f"dec_{t_id}"
                    self.client.query(
                        """
                        MATCH (c:Comment {id: $m_id})
                        MERGE (d:Decision {id: $dec_id})
                        ON CREATE SET d.quote = $quote,
                                      d.channel = $channel,
                                      d.source_url = $source_url,
                                      d.timestamp = CASE WHEN $ts = '' THEN null ELSE $ts END,
                                      d.is_reversal = $is_reversal
                        MERGE (c)-[:CONTAINS_DECISION]->(d)
                        """,
                        {
                            "m_id": m_id,
                            "dec_id": dec_id,
                            "quote": decision_quote,
                            "channel": channel,
                            "source_url": thread_url or "",
                            "ts": ts or "",
                            "is_reversal": thread.get("is_reversal", False),
                        },
                    )
                    stats["decisions_created"] += 1

            stats["threads_processed"] += 1

        return stats

    def load_pull_requests(self, prs: List[PullRequestRecord]) -> Dict[str, Any]:
        """Ingest a collection of pull requests into the graph."""
        total_stats = {
            "prs": 0,
            "authored_edges": 0,
            "reviews": 0,
            "files": 0,
            "modifies_edges": 0,
            "issues": 0,
            "resolves_edges": 0,
        }
        for pr in prs:
            st = self.load_pull_request(pr)
            for k in total_stats:
                total_stats[k] += st.get(k, 0)
        total_stats["final_counts"] = self.client.get_counts()
        return total_stats

