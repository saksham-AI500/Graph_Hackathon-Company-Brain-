"""Document ingestion, parsing, and graph connection engine.

Parses Markdown files (README.md, docs/*.md, ADRs) into Document entities,
extracts explicit references and decisions, and connects them via GraphWriter.
"""

import hashlib
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from src.decision.extractor import RuleBasedDecisionExtractor
from src.decision.verifier import DecisionVerifier
from src.graph.writer import GraphWriter
from src.knowledge.references import extract_explicit_references


class MarkdownDocumentRecord:
    """Structured representation of a repository Markdown document."""

    def __init__(
        self,
        path: str,
        content: str,
        source_url: str,
        observed_at: Optional[str] = None,
    ):
        self.path = path.replace("\\", "/").lstrip("/")
        self.content = content
        self.source_url = source_url
        self.observed_at = observed_at
        self.content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Extract title from first markdown heading or filename
        title_match = re.search(r"^\s*#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            self.title = title_match.group(1).strip()
        else:
            self.title = Path(path).stem.replace("_", " ").title()

        # Detect document type
        if "adr" in self.path.lower() or "decision" in self.path.lower():
            self.file_type = "adr"
        else:
            self.file_type = "documentation"


class DocumentIngestionEngine:
    """Ingests Markdown documents into FalkorDB through GraphWriter."""

    def __init__(self, writer: GraphWriter):
        self.writer = writer

    def ingest_document(
        self,
        doc: MarkdownDocumentRecord,
        run_id: str = "doc_ingest",
    ) -> Dict[str, Any]:
        """Upsert a document, link explicit references, and extract verified decisions."""
        stats = {
            "document_upserted": 0,
            "references_linked": 0,
            "decisions_extracted": 0,
        }

        # 1. Upsert Document node
        self.writer.upsert_node(
            label="Document",
            identity=doc.path,
            properties={
                "path": doc.path,
                "title": doc.title,
                "content_hash": doc.content_hash,
                "file_type": doc.file_type,
                "url": doc.source_url,
                "source_url": doc.source_url,
            },
            run_id=run_id,
        )
        stats["document_upserted"] += 1

        # 2. Extract and link explicit references
        refs = extract_explicit_references(doc.content)
        for ref in refs:
            if ref.reference_type == "issue_or_pr":
                target_num = int(ref.target_id)
                # Check if target PR or Issue exists before creating reference
                check_pr = self.writer.client.ro_query(
                    "MATCH (pr:PullRequest {number: $n}) RETURN count(pr)", {"n": target_num}
                )
                if check_pr and check_pr.result_set and check_pr.result_set[0][0] > 0:
                    self.writer.upsert_edge(
                        rel_type="REFERENCES",
                        source_label="Document",
                        source_identity=doc.path,
                        target_label="PullRequest",
                        target_identity=target_num,
                        properties={
                            "reference_text": ref.raw_text,
                            "reference_type": "pull_request",
                            "source_url": doc.source_url,
                        },
                        run_id=run_id,
                    )
                    stats["references_linked"] += 1
                    continue

                check_issue = self.writer.client.ro_query(
                    "MATCH (i:Issue {number: $n}) RETURN count(i)", {"n": target_num}
                )
                if check_issue and check_issue.result_set and check_issue.result_set[0][0] > 0:
                    self.writer.upsert_edge(
                        rel_type="REFERENCES",
                        source_label="Document",
                        source_identity=doc.path,
                        target_label="Issue",
                        target_identity=target_num,
                        properties={
                            "reference_text": ref.raw_text,
                            "reference_type": "issue",
                            "source_url": doc.source_url,
                        },
                        run_id=run_id,
                    )
                    stats["references_linked"] += 1

            elif ref.reference_type == "document_path":
                check_doc = self.writer.client.ro_query(
                    "MATCH (d:Document {path: $p}) RETURN count(d)", {"p": ref.target_id}
                )
                if check_doc and check_doc.result_set and check_doc.result_set[0][0] > 0:
                    self.writer.upsert_edge(
                        rel_type="REFERENCES",
                        source_label="Document",
                        source_identity=doc.path,
                        target_label="Document",
                        target_identity=ref.target_id,
                        properties={
                            "reference_text": ref.raw_text,
                            "reference_type": "document",
                            "source_url": doc.source_url,
                        },
                        run_id=run_id,
                    )
                    stats["references_linked"] += 1

        # 3. Extract verified decisions
        decisions = RuleBasedDecisionExtractor.extract_decisions(
            source_text=doc.content,
            source_id=doc.path,
            source_type="document",
            source_url=doc.source_url,
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
                    target_label="Document",
                    target_identity=doc.path,
                    properties={
                        "quote": dec.quote,
                        "quote_start": dec.quote_start,
                        "quote_end": dec.quote_end,
                        "source_url": dec.source_url,
                    },
                    run_id=run_id,
                )
                stats["decisions_extracted"] += 1

                # If decision affects an explicit target in the graph
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
