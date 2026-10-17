import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.decision.extractor import RuleBasedDecisionExtractor
from src.decision.verifier import DecisionVerifier
from src.graph.writer import (
    GraphWriter,
    ProvenanceMetadata,
    current_utc_iso,
    EntityNotFoundError,
)
from src.knowledge.references import extract_explicit_references
from src.sync.models import (
    EventType,
    GitHubChangeEvent,
    PlannedAction,
)

logger = logging.getLogger(__name__)


class EventReconciler:
    """Reconciles normalized GitHub change events against FalkorDB via GraphWriter."""

    def __init__(self, writer: GraphWriter, dry_run: bool = False):
        self.writer = writer
        self.dry_run = dry_run

    def reconcile_event(self, event: GitHubChangeEvent) -> Tuple[bool, bool, List[PlannedAction]]:
        """Reconcile a single GitHubChangeEvent.

        Returns:
            (applied: bool, changed: bool, actions: List[PlannedAction])
        """
        actions = self.plan_event(event)

        if self.dry_run:
            logger.info(f"[DRY-RUN] Planned {len(actions)} actions for {event.event_type.value} ({event.event_id})")
            return True, False, actions

        changed_any = False
        run_id = self.writer.run_id
        prov = ProvenanceMetadata(
            source_url=event.source_url,
            observed_at=event.timestamp,
            run_id=run_id,
            valid_from=event.timestamp,
        )

        for act in actions:
            op = act.op
            details = act.details

            if op == "upsert_node":
                res = self.writer.upsert_node(
                    label=details["label"],
                    identity_value=details["identity"],
                    properties=details.get("properties"),
                    provenance=prov,
                )
                if res.changed:
                    changed_any = True

            elif op == "upsert_edge":
                res = self.writer.upsert_edge(
                    rel_type=details["rel_type"],
                    source_label=details["source_label"],
                    source_identity=details["source_identity"],
                    target_label=details["target_label"],
                    target_identity=details["target_identity"],
                    properties=details.get("properties"),
                    provenance=prov,
                    edge_key_property=details.get("edge_key_property"),
                    edge_key_value=details.get("edge_key_value"),
                )
                if res.changed:
                    changed_any = True

            elif op == "close_edge":
                try:
                    res = self.writer.close_edge(
                        rel_type=details["rel_type"],
                        source_label=details["source_label"],
                        source_identity=details["source_identity"],
                        target_label=details["target_label"],
                        target_identity=details["target_identity"],
                        closed_at=details.get("closed_at", event.timestamp),
                        edge_key_property=details.get("edge_key_property"),
                        edge_key_value=details.get("edge_key_value"),
                    )
                    if res.changed:
                        changed_any = True
                except EntityNotFoundError:
                    # Closing nonexistent edge is safely handled as a no-op during sync
                    pass

            elif op == "tombstone_node":
                try:
                    res = self.writer.tombstone_node(
                        label=details["label"],
                        identity_value=details["identity"],
                        tombstoned_at=details.get("tombstoned_at", event.timestamp),
                    )
                    if res.changed:
                        changed_any = True
                except EntityNotFoundError:
                    # Tombstoning nonexistent node is safely handled
                    pass

        return True, changed_any, actions

    def plan_event(self, event: GitHubChangeEvent) -> List[PlannedAction]:
        """Translate event into concrete planned GraphWriter actions."""
        actions: List[PlannedAction] = []
        d = event.data
        etype = event.event_type

        # 1. PR Lifecycle
        if etype == EventType.PR_OPENED:
            author_login = d.get("author_login", event.actor or "unknown")
            author_url = d.get("author_url", f"https://github.com/{author_login}")
            pr_num = int(d["pr_number"])
            pr_url = d.get("url", event.source_url)
            title = d.get("title", f"PR #{pr_num}")
            created_at = d.get("created_at", event.timestamp)

            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Person",
                target_id=author_login,
                details={"label": "Person", "identity": author_login, "properties": {"url": author_url}},
            ))
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="PullRequest",
                target_id=str(pr_num),
                details={
                    "label": "PullRequest",
                    "identity": pr_num,
                    "properties": {
                        "title": title,
                        "url": pr_url,
                        "state": "open",
                        "created_at": created_at,
                    },
                },
            ))
            actions.append(PlannedAction(
                op="upsert_edge",
                entity_or_rel="AUTHORED",
                target_id=f"{author_login}->{pr_num}",
                details={
                    "rel_type": "AUTHORED",
                    "source_label": "Person",
                    "source_identity": author_login,
                    "target_label": "PullRequest",
                    "target_identity": pr_num,
                },
            ))

        elif etype == EventType.PR_CLOSED:
            pr_num = int(d["pr_number"])
            closed_at = d.get("closed_at", event.timestamp)
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="PullRequest",
                target_id=str(pr_num),
                details={
                    "label": "PullRequest",
                    "identity": pr_num,
                    "properties": {"state": "closed", "closed_at": closed_at},
                },
            ))

        elif etype == EventType.PR_MERGED:
            pr_num = int(d["pr_number"])
            merged_at = d.get("merged_at", event.timestamp)
            closed_at = d.get("closed_at", merged_at)
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="PullRequest",
                target_id=str(pr_num),
                details={
                    "label": "PullRequest",
                    "identity": pr_num,
                    "properties": {"state": "closed", "merged_at": merged_at, "closed_at": closed_at},
                },
            ))

        elif etype == EventType.PR_REOPENED:
            pr_num = int(d["pr_number"])
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="PullRequest",
                target_id=str(pr_num),
                details={
                    "label": "PullRequest",
                    "identity": pr_num,
                    "properties": {"state": "open", "closed_at": None, "merged_at": None},
                },
            ))

        # 2. PR Files
        elif etype == EventType.PR_FILE_ADDED:
            pr_num = int(d["pr_number"])
            fpath = d["path"]
            furl = d.get("url", f"{event.source_url}#{fpath}")
            adds = int(d.get("additions", 0))
            dels = int(d.get("deletions", 0))

            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="File",
                target_id=fpath,
                details={"label": "File", "identity": fpath, "properties": {"url": furl}},
            ))
            actions.append(PlannedAction(
                op="upsert_edge",
                entity_or_rel="MODIFIES",
                target_id=f"{pr_num}->{fpath}",
                details={
                    "rel_type": "MODIFIES",
                    "source_label": "PullRequest",
                    "source_identity": pr_num,
                    "target_label": "File",
                    "target_identity": fpath,
                    "properties": {"additions": adds, "deletions": dels},
                },
            ))

        elif etype == EventType.PR_FILE_REMOVED:
            pr_num = int(d["pr_number"])
            fpath = d["path"]
            actions.append(PlannedAction(
                op="close_edge",
                entity_or_rel="MODIFIES",
                target_id=f"{pr_num}->{fpath}",
                details={
                    "rel_type": "MODIFIES",
                    "source_label": "PullRequest",
                    "source_identity": pr_num,
                    "target_label": "File",
                    "target_identity": fpath,
                    "closed_at": event.timestamp,
                },
            ))

        elif etype == EventType.PR_FILE_RENAMED:
            pr_num = int(d["pr_number"])
            old_path = d["old_path"]
            new_path = d["new_path"]
            new_url = d.get("url", f"{event.source_url}#{new_path}")
            adds = int(d.get("additions", 0))
            dels = int(d.get("deletions", 0))

            # Close old path relationship
            actions.append(PlannedAction(
                op="close_edge",
                entity_or_rel="MODIFIES",
                target_id=f"{pr_num}->{old_path}",
                details={
                    "rel_type": "MODIFIES",
                    "source_label": "PullRequest",
                    "source_identity": pr_num,
                    "target_label": "File",
                    "target_identity": old_path,
                    "closed_at": event.timestamp,
                },
            ))
            # Upsert new path node & relationship
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="File",
                target_id=new_path,
                details={"label": "File", "identity": new_path, "properties": {"url": new_url}},
            ))
            actions.append(PlannedAction(
                op="upsert_edge",
                entity_or_rel="MODIFIES",
                target_id=f"{pr_num}->{new_path}",
                details={
                    "rel_type": "MODIFIES",
                    "source_label": "PullRequest",
                    "source_identity": pr_num,
                    "target_label": "File",
                    "target_identity": new_path,
                    "properties": {"additions": adds, "deletions": dels},
                },
            ))

        # 3. Reviews
        elif etype == EventType.REVIEW_SUBMITTED:
            review_id = int(d["review_id"])
            pr_num = int(d["pr_number"])
            rev_login = d.get("author_login", event.actor or "reviewer")
            rev_url = d.get("author_url", f"https://github.com/{rev_login}")
            state = d.get("state", "COMMENTED")
            sub_at = d.get("submitted_at", event.timestamp)

            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Person",
                target_id=rev_login,
                details={"label": "Person", "identity": rev_login, "properties": {"url": rev_url}},
            ))
            actions.append(PlannedAction(
                op="upsert_edge",
                entity_or_rel="REVIEWED",
                target_id=f"{rev_login}->{pr_num}#{review_id}",
                details={
                    "rel_type": "REVIEWED",
                    "source_label": "Person",
                    "source_identity": rev_login,
                    "target_label": "PullRequest",
                    "target_identity": pr_num,
                    "properties": {"id": review_id, "state": state, "submitted_at": sub_at},
                    "edge_key_property": "id",
                    "edge_key_value": review_id,
                },
            ))

        elif etype == EventType.REVIEW_DISMISSED:
            review_id = int(d["review_id"])
            pr_num = int(d["pr_number"])
            rev_login = d.get("author_login", event.actor or "reviewer")
            actions.append(PlannedAction(
                op="close_edge",
                entity_or_rel="REVIEWED",
                target_id=f"{rev_login}->{pr_num}#{review_id}",
                details={
                    "rel_type": "REVIEWED",
                    "source_label": "Person",
                    "source_identity": rev_login,
                    "target_label": "PullRequest",
                    "target_identity": pr_num,
                    "closed_at": event.timestamp,
                    "edge_key_property": "id",
                    "edge_key_value": review_id,
                },
            ))

        # 4. Issues
        elif etype == EventType.ISSUE_OPENED:
            iss_num = int(d["issue_number"])
            iss_url = d.get("url", event.source_url)
            title = d.get("title", f"Issue #{iss_num}")
            created_at = d.get("created_at", event.timestamp)
            author_login = d.get("author_login", event.actor)

            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Issue",
                target_id=str(iss_num),
                details={
                    "label": "Issue",
                    "identity": iss_num,
                    "properties": {"title": title, "url": iss_url, "state": "open", "created_at": created_at},
                },
            ))
            if author_login:
                actions.append(PlannedAction(
                    op="upsert_node",
                    entity_or_rel="Person",
                    target_id=author_login,
                    details={"label": "Person", "identity": author_login, "properties": {"url": f"https://github.com/{author_login}"}},
                ))
                actions.append(PlannedAction(
                    op="upsert_edge",
                    entity_or_rel="REPORTED",
                    target_id=f"{author_login}->{iss_num}",
                    details={
                        "rel_type": "REPORTED",
                        "source_label": "Person",
                        "source_identity": author_login,
                        "target_label": "Issue",
                        "target_identity": iss_num,
                    },
                ))

        elif etype == EventType.ISSUE_EDITED:
            iss_num = int(d["issue_number"])
            props: Dict[str, Any] = {}
            if "title" in d:
                props["title"] = d["title"]
            if "state" in d:
                props["state"] = d["state"]
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Issue",
                target_id=str(iss_num),
                details={"label": "Issue", "identity": iss_num, "properties": props},
            ))

        elif etype == EventType.ISSUE_CLOSED:
            iss_num = int(d["issue_number"])
            closed_at = d.get("closed_at", event.timestamp)
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Issue",
                target_id=str(iss_num),
                details={"label": "Issue", "identity": iss_num, "properties": {"state": "closed", "closed_at": closed_at}},
            ))

        elif etype == EventType.ISSUE_REOPENED:
            iss_num = int(d["issue_number"])
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Issue",
                target_id=str(iss_num),
                details={"label": "Issue", "identity": iss_num, "properties": {"state": "open", "closed_at": None}},
            ))

        elif etype == EventType.ISSUE_RESOLVED_BY_PR:
            pr_num = int(d["pr_number"])
            iss_num = int(d["issue_number"])
            actions.append(PlannedAction(
                op="upsert_edge",
                entity_or_rel="RESOLVES",
                target_id=f"{pr_num}->{iss_num}",
                details={
                    "rel_type": "RESOLVES",
                    "source_label": "PullRequest",
                    "source_identity": pr_num,
                    "target_label": "Issue",
                    "target_identity": iss_num,
                },
            ))

        # 5. Comments
        elif etype == EventType.COMMENT_CREATED:
            actor = event.actor or d.get("author_login")
            cid = str(d.get("comment_id", d.get("id", f"comment_{event.event_id}")))
            body = d.get("body", "")
            url = d.get("url", event.source_url)
            parent_type = d.get("parent_type", "pull_request" if "pr_number" in d else "issue")
            parent_id = int(d.get("parent_id", d.get("pr_number", d.get("issue_number", 0))))

            if actor:
                actions.append(PlannedAction(
                    op="upsert_node",
                    entity_or_rel="Person",
                    target_id=actor,
                    details={"label": "Person", "identity": actor, "properties": {"url": f"https://github.com/{actor}"}},
                ))

            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Comment",
                target_id=cid,
                details={
                    "label": "Comment",
                    "identity": cid,
                    "properties": {
                        "id": cid,
                        "body": body,
                        "url": url,
                        "created_at": d.get("created_at", event.timestamp),
                        "author_login": actor,
                        "parent_type": parent_type,
                        "parent_id": parent_id,
                        "source_url": event.source_url,
                    },
                },
            ))

            if parent_id:
                target_label = "PullRequest" if ("pr" in parent_type.lower() or "pull" in parent_type.lower()) else "Issue"
                actions.append(PlannedAction(
                    op="upsert_edge",
                    entity_or_rel="ON",
                    target_id=f"{cid}->{parent_id}",
                    details={
                        "rel_type": "ON",
                        "source_label": "Comment",
                        "source_identity": cid,
                        "target_label": target_label,
                        "target_identity": parent_id,
                    },
                ))

            if actor:
                actions.append(PlannedAction(
                    op="upsert_edge",
                    entity_or_rel="AUTHORED",
                    target_id=f"{actor}->{cid}",
                    details={
                        "rel_type": "AUTHORED",
                        "source_label": "Person",
                        "source_identity": actor,
                        "target_label": "Comment",
                        "target_identity": cid,
                    },
                ))

            # Explicit references
            refs = extract_explicit_references(body)
            for ref in refs:
                if ref.reference_type == "issue_or_pr":
                    t_num = int(ref.target_id)
                    actions.append(PlannedAction(
                        op="upsert_edge",
                        entity_or_rel="REFERENCES",
                        target_id=f"{cid}->{t_num}",
                        details={
                            "rel_type": "REFERENCES",
                            "source_label": "Comment",
                            "source_identity": cid,
                            "target_label": "Issue",
                            "target_identity": t_num,
                            "properties": {"reference_text": ref.raw_text, "reference_type": "issue"},
                        },
                    ))
                elif ref.reference_type == "document_path":
                    actions.append(PlannedAction(
                        op="upsert_edge",
                        entity_or_rel="REFERENCES",
                        target_id=f"{cid}->{ref.target_id}",
                        details={
                            "rel_type": "REFERENCES",
                            "source_label": "Comment",
                            "source_identity": cid,
                            "target_label": "Document",
                            "target_identity": ref.target_id,
                            "properties": {"reference_text": ref.raw_text, "reference_type": "document"},
                        },
                    ))

            # Grounded decision extraction
            decisions = RuleBasedDecisionExtractor.extract_decisions(
                source_text=body,
                source_id=f"comment_{cid}",
                source_type="comment",
                source_url=event.source_url,
            )
            for dec in decisions:
                ver = DecisionVerifier.verify_decision(dec)
                if ver.is_valid:
                    actions.append(PlannedAction(
                        op="upsert_node",
                        entity_or_rel="Decision",
                        target_id=dec.id,
                        details={
                            "label": "Decision",
                            "identity": dec.id,
                            "properties": {
                                "id": dec.id,
                                "pattern": dec.pattern,
                                "quote": dec.quote,
                                "quote_start": dec.quote_start,
                                "quote_end": dec.quote_end,
                                "source_text": dec.source_text,
                                "source_id": dec.source_id,
                                "source_type": dec.source_type,
                                "status_state": dec.status_state,
                                "source_url": dec.source_url,
                            },
                        },
                    ))
                    actions.append(PlannedAction(
                        op="upsert_edge",
                        entity_or_rel="DECIDED_IN",
                        target_id=f"{dec.id}->{cid}",
                        details={
                            "rel_type": "DECIDED_IN",
                            "source_label": "Decision",
                            "source_identity": dec.id,
                            "target_label": "Comment",
                            "target_identity": cid,
                            "properties": {
                                "quote": dec.quote,
                                "quote_start": dec.quote_start,
                                "quote_end": dec.quote_end,
                            },
                        },
                    ))
                    if dec.affects_target:
                        target_val = dec.affects_target.strip("#")
                        target_label = "File" if "/" in target_val else "Issue"
                        target_ident = target_val if target_label == "File" else int(target_val)
                        actions.append(PlannedAction(
                            op="upsert_edge",
                            entity_or_rel="AFFECTS",
                            target_id=f"{dec.id}->{target_ident}",
                            details={
                                "rel_type": "AFFECTS",
                                "source_label": "Decision",
                                "source_identity": dec.id,
                                "target_label": target_label,
                                "target_identity": target_ident,
                            },
                        ))

        # 6. CODEOWNERS
        elif etype == EventType.CODEOWNERS_RULE_ADDED:
            pattern = d["pattern"]
            line = int(d.get("line_number", 1))
            owners = d.get("owners", [])
            covered_files = d.get("covered_files", [])

            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="OwnershipRule",
                target_id=pattern,
                details={
                    "label": "OwnershipRule",
                    "identity": pattern,
                    "properties": {"pattern": pattern, "line_number": line, "source_url": event.source_url},
                },
            ))
            for owner in owners:
                if owner.startswith("@") and "/" in owner:
                    actions.append(PlannedAction(
                        op="upsert_node",
                        entity_or_rel="Team",
                        target_id=owner,
                        details={"label": "Team", "identity": owner, "properties": {"name": owner}},
                    ))
                    actions.append(PlannedAction(
                        op="upsert_edge",
                        entity_or_rel="DECLARES_OWNER",
                        target_id=f"{pattern}->{owner}",
                        details={
                            "rel_type": "DECLARES_OWNER",
                            "source_label": "OwnershipRule",
                            "source_identity": pattern,
                            "target_label": "Team",
                            "target_identity": owner,
                        },
                    ))
                else:
                    login = owner.lstrip("@")
                    actions.append(PlannedAction(
                        op="upsert_node",
                        entity_or_rel="Person",
                        target_id=login,
                        details={"label": "Person", "identity": login, "properties": {"url": f"https://github.com/{login}"}},
                    ))
                    actions.append(PlannedAction(
                        op="upsert_edge",
                        entity_or_rel="DECLARES_OWNER",
                        target_id=f"{pattern}->{login}",
                        details={
                            "rel_type": "DECLARES_OWNER",
                            "source_label": "OwnershipRule",
                            "source_identity": pattern,
                            "target_label": "Person",
                            "target_identity": login,
                        },
                    ))

            for cov_file in covered_files:
                actions.append(PlannedAction(
                    op="upsert_edge",
                    entity_or_rel="COVERS",
                    target_id=f"{pattern}->{cov_file}",
                    details={
                        "rel_type": "COVERS",
                        "source_label": "OwnershipRule",
                        "source_identity": pattern,
                        "target_label": "File",
                        "target_identity": cov_file,
                    },
                ))
                for owner in owners:
                    if owner.startswith("@") and "/" in owner:
                        actions.append(PlannedAction(
                            op="upsert_edge",
                            entity_or_rel="OWNS",
                            target_id=f"{owner}->{cov_file}",
                            details={
                                "rel_type": "OWNS",
                                "source_label": "Team",
                                "source_identity": owner,
                                "target_label": "File",
                                "target_identity": cov_file,
                                "properties": {"rule_pattern": pattern},
                            },
                        ))

        elif etype == EventType.CODEOWNERS_OWNER_REMOVED:
            pattern = d["pattern"]
            owner_name = d["owner_name"]
            owner_type = "Team" if (owner_name.startswith("@") and "/" in owner_name) else "Person"
            ident = owner_name if owner_type == "Team" else owner_name.lstrip("@")
            covered_files = d.get("covered_files", [])

            actions.append(PlannedAction(
                op="close_edge",
                entity_or_rel="DECLARES_OWNER",
                target_id=f"{pattern}->{ident}",
                details={
                    "rel_type": "DECLARES_OWNER",
                    "source_label": "OwnershipRule",
                    "source_identity": pattern,
                    "target_label": owner_type,
                    "target_identity": ident,
                    "closed_at": event.timestamp,
                },
            ))
            if owner_type == "Team":
                for cov_file in covered_files:
                    actions.append(PlannedAction(
                        op="close_edge",
                        entity_or_rel="OWNS",
                        target_id=f"{owner_name}->{cov_file}",
                        details={
                            "rel_type": "OWNS",
                            "source_label": "Team",
                            "source_identity": owner_name,
                            "target_label": "File",
                            "target_identity": cov_file,
                            "closed_at": event.timestamp,
                        },
                    ))

        elif etype == EventType.CODEOWNERS_RULE_REMOVED:
            pattern = d["pattern"]
            actions.append(PlannedAction(
                op="tombstone_node",
                entity_or_rel="OwnershipRule",
                target_id=pattern,
                details={
                    "label": "OwnershipRule",
                    "identity": pattern,
                    "tombstoned_at": event.timestamp,
                },
            ))

        # 7. Markdown Documents
        elif etype in (EventType.DOCUMENT_ADDED, EventType.DOCUMENT_EDITED):
            doc_path = d["path"]
            doc_url = d.get("url", f"{event.source_url}#{doc_path}")
            content = d.get("content", "")
            title = d.get("title", "")
            if not title and content:
                title_match = re.search(r"^\s*#\s+(.+)$", content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else doc_path
            content_hash = d.get("content_hash", "")
            if not content_hash and content:
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            file_type = "adr" if ("adr" in doc_path.lower() or "decision" in doc_path.lower()) else "documentation"

            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="File",
                target_id=doc_path,
                details={"label": "File", "identity": doc_path, "properties": {"url": doc_url, "file_type": file_type}},
            ))
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Document",
                target_id=doc_path,
                details={
                    "label": "Document",
                    "identity": doc_path,
                    "properties": {
                        "path": doc_path,
                        "title": title or doc_path,
                        "content_hash": content_hash,
                        "file_type": file_type,
                        "url": doc_url,
                        "source_url": event.source_url,
                    },
                },
            ))

            # References in document
            if content:
                refs = extract_explicit_references(content)
                for ref in refs:
                    if ref.reference_type == "issue_or_pr":
                        t_num = int(ref.target_id)
                        actions.append(PlannedAction(
                            op="upsert_edge",
                            entity_or_rel="REFERENCES",
                            target_id=f"{doc_path}->{t_num}",
                            details={
                                "rel_type": "REFERENCES",
                                "source_label": "Document",
                                "source_identity": doc_path,
                                "target_label": "Issue",
                                "target_identity": t_num,
                                "properties": {"reference_text": ref.raw_text, "reference_type": "issue"},
                            },
                        ))

                # Decision extraction from markdown content
                decisions = RuleBasedDecisionExtractor.extract_decisions(
                    source_text=content,
                    source_id=doc_path,
                    source_type="document",
                    source_url=event.source_url,
                )
                for dec in decisions:
                    ver = DecisionVerifier.verify_decision(dec)
                    if ver.is_valid:
                        actions.append(PlannedAction(
                            op="upsert_node",
                            entity_or_rel="Decision",
                            target_id=dec.id,
                            details={
                                "label": "Decision",
                                "identity": dec.id,
                                "properties": {
                                    "id": dec.id,
                                    "pattern": dec.pattern,
                                    "quote": dec.quote,
                                    "quote_start": dec.quote_start,
                                    "quote_end": dec.quote_end,
                                    "source_text": dec.source_text,
                                    "source_id": dec.source_id,
                                    "source_type": dec.source_type,
                                    "status_state": dec.status_state,
                                    "source_url": dec.source_url,
                                },
                            },
                        ))
                        actions.append(PlannedAction(
                            op="upsert_edge",
                            entity_or_rel="DECIDED_IN",
                            target_id=f"{dec.id}->{doc_path}",
                            details={
                                "rel_type": "DECIDED_IN",
                                "source_label": "Decision",
                                "source_identity": dec.id,
                                "target_label": "Document",
                                "target_identity": doc_path,
                                "properties": {
                                    "quote": dec.quote,
                                    "quote_start": dec.quote_start,
                                    "quote_end": dec.quote_end,
                                },
                            },
                        ))
                        if dec.affects_target:
                            target_val = dec.affects_target.strip("#")
                            target_label = "File" if "/" in target_val else "Issue"
                            target_ident = target_val if target_label == "File" else int(target_val)
                            actions.append(PlannedAction(
                                op="upsert_edge",
                                entity_or_rel="AFFECTS",
                                target_id=f"{dec.id}->{target_ident}",
                                details={
                                    "rel_type": "AFFECTS",
                                    "source_label": "Decision",
                                    "source_identity": dec.id,
                                    "target_label": target_label,
                                    "target_identity": target_ident,
                                },
                            ))

        elif etype == EventType.DOCUMENT_DELETED:
            doc_path = d["path"]
            doc_url = d.get("url", f"{event.source_url}#{doc_path}")
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="File",
                target_id=doc_path,
                details={"label": "File", "identity": doc_path, "properties": {"url": doc_url}},
            ))
            actions.append(PlannedAction(
                op="tombstone_node",
                entity_or_rel="File",
                target_id=doc_path,
                details={"label": "File", "identity": doc_path, "tombstoned_at": event.timestamp},
            ))
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Document",
                target_id=doc_path,
                details={"label": "Document", "identity": doc_path, "properties": {"url": doc_url}},
            ))
            actions.append(PlannedAction(
                op="tombstone_node",
                entity_or_rel="Document",
                target_id=doc_path,
                details={"label": "Document", "identity": doc_path, "tombstoned_at": event.timestamp},
            ))

        # 8. Team Membership (evidence-grounded)
        elif etype == EventType.TEAM_MEMBER_ADDED:
            team_name = d["team_name"]
            member = d["member_login"]
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Team",
                target_id=team_name,
                details={"label": "Team", "identity": team_name, "properties": {"name": team_name}},
            ))
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Person",
                target_id=member,
                details={"label": "Person", "identity": member, "properties": {"url": f"https://github.com/{member}"}},
            ))
            actions.append(PlannedAction(
                op="upsert_edge",
                entity_or_rel="HAS_MEMBER",
                target_id=f"{team_name}->{member}",
                details={
                    "rel_type": "HAS_MEMBER",
                    "source_label": "Team",
                    "source_identity": team_name,
                    "target_label": "Person",
                    "target_identity": member,
                },
            ))

        # 9. Explicit Decision
        elif etype == EventType.DECISION_EXTRACTED:
            dec_id = d["id"]
            source_label = d.get("source_label", "Document")
            source_id = d.get("source_id", "")
            actions.append(PlannedAction(
                op="upsert_node",
                entity_or_rel="Decision",
                target_id=dec_id,
                details={
                    "label": "Decision",
                    "identity": dec_id,
                    "properties": {
                        "id": dec_id,
                        "pattern": d.get("pattern", "decision:"),
                        "quote": d.get("quote", ""),
                        "quote_start": d.get("quote_start", 0),
                        "quote_end": d.get("quote_end", 0),
                        "source_text": d.get("source_text", ""),
                        "source_id": str(source_id),
                        "source_type": d.get("source_type", "document"),
                        "status_state": d.get("status_state", "decided"),
                        "source_url": event.source_url,
                    },
                },
            ))
            if source_id:
                actions.append(PlannedAction(
                    op="upsert_edge",
                    entity_or_rel="DECIDED_IN",
                    target_id=f"{dec_id}->{source_id}",
                    details={
                        "rel_type": "DECIDED_IN",
                        "source_label": "Decision",
                        "source_identity": dec_id,
                        "target_label": source_label,
                        "target_identity": source_id,
                        "properties": {
                            "quote": d.get("quote", ""),
                            "quote_start": d.get("quote_start", 0),
                            "quote_end": d.get("quote_end", 0),
                        },
                    },
                ))
            if d.get("affects_target"):
                target_val = d["affects_target"]
                target_label = "File" if "/" in str(target_val) else "Issue"
                target_ident = target_val if target_label == "File" else int(str(target_val).strip("#"))
                actions.append(PlannedAction(
                    op="upsert_edge",
                    entity_or_rel="AFFECTS",
                    target_id=f"{dec_id}->{target_ident}",
                    details={
                        "rel_type": "AFFECTS",
                        "source_label": "Decision",
                        "source_identity": dec_id,
                        "target_label": target_label,
                        "target_identity": target_ident,
                    },
                ))
            if d.get("supersedes_id"):
                super_val = d["supersedes_id"]
                actions.append(PlannedAction(
                    op="upsert_edge",
                    entity_or_rel="SUPERSEDES",
                    target_id=f"{dec_id}->{super_val}",
                    details={
                        "rel_type": "SUPERSEDES",
                        "source_label": "Decision",
                        "source_identity": dec_id,
                        "target_label": "Decision",
                        "target_identity": super_val,
                    },
                ))

        return actions
