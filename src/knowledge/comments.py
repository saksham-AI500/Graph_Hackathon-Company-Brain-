"""Comment ingestion, reference linking, and decision extraction engine.

Represents discussion comments on Pull Requests and Issues as Comment nodes,
links explicit references (#123, docs, URLs), and extracts grounded decisions.
"""

from typing import Any, Dict, List, Optional
from src.decision.extractor import RuleBasedDecisionExtractor
from src.decision.verifier import DecisionVerifier
from src.graph.writer import GraphWriter
from src.knowledge.references import extract_explicit_references


class CommentRecord:
    """Structured representation of a PR or Issue comment."""

    def __init__(
        self,
        comment_id: str,
        body: str,
        source_url: str,
        parent_type: str,  # "pull_request" or "issue"
        parent_id: int,  # PR or Issue number
        author_login: Optional[str] = None,
        created_at: Optional[str] = None,
        url: Optional[str] = None,
    ):
        self.comment_id = str(comment_id)
        self.body = body
        self.source_url = source_url
        self.parent_type = parent_type.lower()
        self.parent_id = parent_id
        self.author_login = author_login
        self.created_at = created_at
        self.url = url or source_url


class CommentIngestionEngine:
    """Ingests PR and Issue comments into FalkorDB through GraphWriter."""

    def __init__(self, writer: GraphWriter):
        self.writer = writer

    def ingest_comment(
        self,
        comment: CommentRecord,
        run_id: str = "comment_ingest",
    ) -> Dict[str, Any]:
        """Upsert a comment, connect it to parent PR/issue, link references, and extract decisions."""
        stats = {
            "comment_upserted": 0,
            "on_edges": 0,
            "authored_edges": 0,
            "references_linked": 0,
            "decisions_extracted": 0,
        }

        # 1. Upsert Comment node
        self.writer.upsert_node(
            label="Comment",
            identity=comment.comment_id,
            properties={
                "id": comment.comment_id,
                "body": comment.body,
                "url": comment.url,
                "created_at": comment.created_at,
                "author_login": comment.author_login,
                "parent_type": comment.parent_type,
                "parent_id": comment.parent_id,
                "source_url": comment.source_url,
            },
            run_id=run_id,
        )
        stats["comment_upserted"] += 1

        # 2. Connect (:Comment)-[:ON]->(:PullRequest | :Issue)
        target_label = "PullRequest" if "pr" in comment.parent_type or "pull" in comment.parent_type else "Issue"
        self.writer.upsert_edge(
            rel_type="ON",
            source_label="Comment",
            source_identity=comment.comment_id,
            target_label=target_label,
            target_identity=comment.parent_id,
            properties={"source_url": comment.source_url},
            run_id=run_id,
        )
        stats["on_edges"] += 1

        # 3. Connect Author (:Person)-[:AUTHORED]->(:Comment)
        if comment.author_login:
            self.writer.upsert_node(
                label="Person",
                identity=comment.author_login,
                properties={
                    "login": comment.author_login,
                    "url": f"https://github.com/{comment.author_login}",
                    "source_url": comment.source_url,
                },
                run_id=run_id,
            )
            self.writer.upsert_edge(
                rel_type="AUTHORED",
                source_label="Person",
                source_identity=comment.author_login,
                target_label="Comment",
                target_identity=comment.comment_id,
                properties={"source_url": comment.source_url},
                run_id=run_id,
            )
            stats["authored_edges"] += 1

        # 4. Extract and link explicit references (#123, docs, URLs)
        refs = extract_explicit_references(comment.body)
        for ref in refs:
            if ref.reference_type == "issue_or_pr":
                target_num = int(ref.target_id)
                # Check if target PR exists
                check_pr = self.writer.client.ro_query(
                    "MATCH (pr:PullRequest {number: $n}) RETURN count(pr)", {"n": target_num}
                )
                if check_pr and check_pr.result_set and check_pr.result_set[0][0] > 0:
                    self.writer.upsert_edge(
                        rel_type="REFERENCES",
                        source_label="Comment",
                        source_identity=comment.comment_id,
                        target_label="PullRequest",
                        target_identity=target_num,
                        properties={
                            "reference_text": ref.raw_text,
                            "reference_type": "pull_request",
                            "source_url": comment.source_url,
                        },
                        run_id=run_id,
                    )
                    stats["references_linked"] += 1
                    continue

                # Check if target Issue exists
                check_issue = self.writer.client.ro_query(
                    "MATCH (i:Issue {number: $n}) RETURN count(i)", {"n": target_num}
                )
                if check_issue and check_issue.result_set and check_issue.result_set[0][0] > 0:
                    self.writer.upsert_edge(
                        rel_type="REFERENCES",
                        source_label="Comment",
                        source_identity=comment.comment_id,
                        target_label="Issue",
                        target_identity=target_num,
                        properties={
                            "reference_text": ref.raw_text,
                            "reference_type": "issue",
                            "source_url": comment.source_url,
                        },
                        run_id=run_id,
                    )
                    stats["references_linked"] += 1

            elif ref.reference_type == "document_path":
                # Check if target Document exists
                check_doc = self.writer.client.ro_query(
                    "MATCH (d:Document {path: $p}) RETURN count(d)", {"p": ref.target_id}
                )
                if check_doc and check_doc.result_set and check_doc.result_set[0][0] > 0:
                    self.writer.upsert_edge(
                        rel_type="REFERENCES",
                        source_label="Comment",
                        source_identity=comment.comment_id,
                        target_label="Document",
                        target_identity=ref.target_id,
                        properties={
                            "reference_text": ref.raw_text,
                            "reference_type": "document",
                            "source_url": comment.source_url,
                        },
                        run_id=run_id,
                    )
                    stats["references_linked"] += 1

        # 5. Extract verified decisions
        decisions = RuleBasedDecisionExtractor.extract_decisions(
            source_text=comment.body,
            source_id=f"comment_{comment.comment_id}",
            source_type="comment",
            source_url=comment.source_url,
        )

        for dec in decisions:
            ver_result = DecisionVerifier.verify_decision(dec)
            if ver_result.is_valid:
                self.writer.upsert_node(
                    label="Decision",
                    identity=dec.id,
                    properties={
                        "id": dec.id,
                        "pattern": dec.pattern,
                        "quote": dec.quote,
                        "quote_start": dec.quote_start,
                        "quote_end": dec.quote_end,
                        "source_text": dec.source_text,
                        "source_id": dec.source_id,
                        "source_type": dec.source_type,
                        "status_state": dec.status_state,
                        "url": dec.source_url,
                        "source_url": dec.source_url,
                    },
                    run_id=run_id,
                )
                self.writer.upsert_edge(
                    rel_type="DECIDED_IN",
                    source_label="Decision",
                    source_identity=dec.id,
                    target_label="Comment",
                    target_identity=comment.comment_id,
                    properties={
                        "quote": dec.quote,
                        "quote_start": dec.quote_start,
                        "quote_end": dec.quote_end,
                        "source_url": dec.source_url,
                    },
                    run_id=run_id,
                )
                stats["decisions_extracted"] += 1

                if dec.affects_target:
                    target_str = dec.affects_target.strip("#")
                    if target_str.isdigit():
                        t_num = int(target_str)
                        self.writer.upsert_edge(
                            rel_type="AFFECTS",
                            source_label="Decision",
                            source_identity=dec.id,
                            target_label="Issue",
                            target_identity=t_num,
                            properties={"target_type": "issue", "source_url": dec.source_url},
                            run_id=run_id,
                        )
                    else:
                        self.writer.upsert_edge(
                            rel_type="AFFECTS",
                            source_label="Decision",
                            source_identity=dec.id,
                            target_label="File",
                            target_identity=dec.affects_target,
                            properties={"target_type": "file", "source_url": dec.source_url},
                            run_id=run_id,
                        )

                if dec.supersedes_id:
                    self.writer.upsert_edge(
                        rel_type="SUPERSEDES",
                        source_label="Decision",
                        source_identity=dec.id,
                        target_label="Decision",
                        target_identity=dec.supersedes_id,
                        properties={"source_url": dec.source_url},
                        run_id=run_id,
                    )

        return stats
