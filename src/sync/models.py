"""Data models for RepoBrain incremental synchronization engine."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from src.graph.writer import current_utc_iso


class EventType(str, Enum):
    """Supported GitHub change event types."""

    # Pull Request lifecycle
    PR_OPENED = "pr_opened"
    PR_CLOSED = "pr_closed"
    PR_MERGED = "pr_merged"
    PR_REOPENED = "pr_reopened"

    # PR Files
    PR_FILE_ADDED = "pr_file_added"
    PR_FILE_REMOVED = "pr_file_removed"
    PR_FILE_RENAMED = "pr_file_renamed"

    # Reviews
    REVIEW_SUBMITTED = "review_submitted"
    REVIEW_DISMISSED = "review_dismissed"

    # Issues
    ISSUE_OPENED = "issue_opened"
    ISSUE_EDITED = "issue_edited"
    ISSUE_CLOSED = "issue_closed"
    ISSUE_REOPENED = "issue_reopened"
    ISSUE_RESOLVED_BY_PR = "issue_resolved_by_pr"

    # Comments
    COMMENT_CREATED = "comment_created"

    # CODEOWNERS
    CODEOWNERS_RULE_ADDED = "codeowners_rule_added"
    CODEOWNERS_OWNER_REMOVED = "codeowners_owner_removed"
    CODEOWNERS_RULE_REMOVED = "codeowners_rule_removed"

    # Markdown Documents
    DOCUMENT_ADDED = "document_added"
    DOCUMENT_EDITED = "document_edited"
    DOCUMENT_DELETED = "document_deleted"

    # Team Membership (evidence-grounded)
    TEAM_MEMBER_ADDED = "team_member_added"

    # Decision Extraction
    DECISION_EXTRACTED = "decision_extracted"


class GitHubChangeEvent(BaseModel):
    """Normalized GitHub change event representing a discrete repository event."""

    event_id: str
    event_type: EventType
    timestamp: str = Field(default_factory=current_utc_iso)
    source_url: str
    actor: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class SyncState(BaseModel):
    """Persistent synchronization cursor state for a repository."""

    repo: str
    last_sync_at: Optional[str] = None
    last_run_id: Optional[str] = None
    pr_cursor: int = 0
    issue_cursor: int = 0
    commit_cursor: Optional[str] = None
    etag_map: Dict[str, str] = Field(default_factory=dict)
    status: str = "idle"  # idle, in_progress, failed
    locked_at: Optional[str] = None


class PlannedAction(BaseModel):
    """An action calculated during reconciliation (used for dry-run and execution)."""

    op: str  # upsert_node, upsert_edge, close_edge, tombstone_node
    entity_or_rel: str
    target_id: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ReconciliationResult(BaseModel):
    """Summary of a reconciliation execution."""

    run_id: str
    repo: str
    events_processed: int = 0
    mutations_applied: int = 0
    no_ops: int = 0
    failures: int = 0
    errors: List[str] = Field(default_factory=list)
    dry_run: bool = False
    cursor_advanced: bool = False
