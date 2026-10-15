"""Pydantic models for validated GitHub entities and relationships."""

from typing import List, Optional
from pydantic import BaseModel, Field


class PersonRecord(BaseModel):
    """A GitHub user/contributor."""
    login: str
    url: str


class FileRecord(BaseModel):
    """A file modified in a pull request."""
    path: str
    url: str
    additions: int = 0
    deletions: int = 0


class ReviewRecord(BaseModel):
    """A review submitted on a pull request."""
    author_login: str
    author_url: str
    state: str = "COMMENTED"  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    submitted_at: Optional[str] = None


class IssueRecord(BaseModel):
    """An issue resolved or linked to a pull request."""
    number: int
    title: str
    url: str
    state: str = "closed"
    author_login: Optional[str] = None
    author_url: Optional[str] = None
    created_at: Optional[str] = None
    closed_at: Optional[str] = None


class PullRequestRecord(BaseModel):
    """A GitHub pull request with associated reviews, touched files, and linked issues."""
    number: int
    title: str
    url: str
    state: str = "closed"
    author_login: str
    author_url: str
    created_at: Optional[str] = None
    merged_at: Optional[str] = None
    files: List[FileRecord] = Field(default_factory=list)
    reviews: List[ReviewRecord] = Field(default_factory=list)
    resolved_issues: List[IssueRecord] = Field(default_factory=list)
