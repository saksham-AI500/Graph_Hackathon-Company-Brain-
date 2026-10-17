"""Explicit reference extractor for PRs, issues, documents, and URLs.

Extracts only explicit, recognizable entity and document references from text.
Never infers relationships based on semantic similarity.
"""

import re
from typing import List, Optional
from pydantic import BaseModel

ISSUE_OR_PR_PATTERN = re.compile(r"(?:^|[\s(,;\[])#(\d+)\b")
DOC_PATH_PATTERN = re.compile(r"(?:^|[\s(,;\[])((?:docs|src)/[\w/.-]+\.md|README\.md)\b")
GITHUB_URL_PATTERN = re.compile(r"(?:^|[\s(,;\[])(https://github\.com/[\w_.-]+/[\w_.-]+/(?:pull|issues)/\d+|https://github\.com/[\w_.-]+/[\w_.-]+/blob/[\w_.-]+/[\w_/.-]+)")


class ExplicitReference(BaseModel):
    """An explicit, syntactically grounded reference to another repository entity."""

    reference_type: str  # "issue_or_pr", "document_path", "source_url"
    target_id: str  # e.g. "123", "docs/sync_architecture.md", "https://github.com/..."
    raw_text: str


def extract_explicit_references(text: str) -> List[ExplicitReference]:
    """Extract explicit references from repository text without semantic extrapolation."""
    if not text:
        return []

    refs: List[ExplicitReference] = []
    seen = set()

    # 1. Issue or PR references: #123
    for match in ISSUE_OR_PR_PATTERN.finditer(text):
        target_num = match.group(1)
        raw_text = f"#{target_num}"
        key = ("issue_or_pr", target_num)
        if key not in seen:
            seen.add(key)
            refs.append(
                ExplicitReference(
                    reference_type="issue_or_pr",
                    target_id=target_num,
                    raw_text=raw_text,
                )
            )

    # 2. Document paths: docs/..., README.md
    for match in DOC_PATH_PATTERN.finditer(text):
        path = match.group(1)
        key = ("document_path", path)
        if key not in seen:
            seen.add(key)
            refs.append(
                ExplicitReference(
                    reference_type="document_path",
                    target_id=path,
                    raw_text=path,
                )
            )

    # 3. Explicit GitHub URLs
    for match in GITHUB_URL_PATTERN.finditer(text):
        url = match.group(1).rstrip(".,)]>")
        key = ("source_url", url)
        if key not in seen:
            seen.add(key)
            refs.append(
                ExplicitReference(
                    reference_type="source_url",
                    target_id=url,
                    raw_text=url,
                )
            )

    return refs
