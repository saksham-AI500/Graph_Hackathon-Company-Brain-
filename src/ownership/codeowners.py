"""GitHub CODEOWNERS parser and pattern matcher following official specification."""

import fnmatch
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

DEFAULT_CODEOWNERS_URL = "https://github.com/FalkorDB/FalkorDB/blob/main/CODEOWNERS"


@dataclass
class CodeownersRule:
    """A single rule parsed from CODEOWNERS."""
    pattern: str
    owners: List[str]
    line_number: int
    is_team: bool = False


@dataclass
class CodeownersMatch:
    """Result of matching a file path against CODEOWNERS rules."""
    file_path: str
    matched: bool
    owners: List[str] = field(default_factory=list)
    rule_pattern: Optional[str] = None
    line_number: Optional[int] = None
    source_url: str = DEFAULT_CODEOWNERS_URL
    is_team: bool = False
    ambiguity: Optional[str] = None
    overlapping_rules: List[CodeownersRule] = field(default_factory=list)


class CodeownersParser:
    """Parses and evaluates GitHub CODEOWNERS rules according to GitHub specification.

    Rules follow .gitignore syntax:
    - Order matters: the LAST matching pattern takes precedence.
    - Patterns starting with '/' match relative to repository root.
    - Patterns ending with '/' match directory and all recursive contents.
    - Patterns with '*' wildcard match within path segments.
    """

    def __init__(self, content: Optional[str] = None, source_url: str = DEFAULT_CODEOWNERS_URL):
        self.source_url = source_url
        self.rules: List[CodeownersRule] = []
        if content is not None:
            self.parse(content)

    @classmethod
    def from_file(cls, path: Path, source_url: str = DEFAULT_CODEOWNERS_URL) -> "CodeownersParser":
        """Load and parse CODEOWNERS from a local file path."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return cls(content=content, source_url=source_url)

    @classmethod
    def from_cache_or_default(cls, cache_dir: Path = Path(".cache/github")) -> "CodeownersParser":
        """Load from cache if present, then seed fixture, then bundled fallback."""
        cached_file = cache_dir / "CODEOWNERS"
        if cached_file.exists():
            return cls.from_file(cached_file)
        
        # Check checked-in seed fixture (for fresh clones without cache)
        seed_path = Path(__file__).resolve().parent.parent / "fixtures" / "seed_repo_data.json"
        if seed_path.exists():
            try:
                import json
                with open(seed_path, "r", encoding="utf-8") as f:
                    seed_data = json.load(f)
                co_text = seed_data.get("codeowners")
                if co_text:
                    return cls(content=co_text)
            except Exception:
                pass

        # Bundled official fallback content from FalkorDB/FalkorDB main branch
        bundled = """
/build/          @FalkorDB/falkordb-core
/.github/        @FalkorDB/falkordb-core
/CODEOWNERS      @FalkorDB/falkordb-core
"""
        return cls(content=bundled)

    def parse(self, content: str) -> None:
        """Parse raw CODEOWNERS file content into structured rules."""
        self.rules.clear()
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            # Ignore comments and empty lines
            if not stripped or stripped.startswith("#"):
                continue

            parts = stripped.split()
            if len(parts) < 2:
                continue

            pattern = parts[0]
            owners = parts[1:]
            is_team = any("/" in owner for owner in owners)

            self.rules.append(
                CodeownersRule(
                    pattern=pattern,
                    owners=owners,
                    line_number=idx,
                    is_team=is_team,
                )
            )

    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Evaluate if normalized file_path matches a CODEOWNERS pattern."""
        # Normalize file_path: forward slashes, strip leading/trailing slashes
        norm_path = file_path.replace("\\", "/").strip("/")

        # Rule 1: Directory pattern ending with '/' (e.g., '/build/' or 'build/')
        if pattern.endswith("/"):
            prefix = pattern.strip("/")
            if norm_path == prefix or norm_path.startswith(f"{prefix}/"):
                return True
            # Also handle wildcard directory like '*/build/'
            if pattern.startswith("*"):
                pattern_no_slash = pattern.rstrip("/")
                if fnmatch.fnmatch(norm_path, f"{pattern_no_slash}/*") or fnmatch.fnmatch(norm_path, pattern_no_slash):
                    return True
            return False

        # Rule 2: Root-anchored file pattern (starts with '/')
        if pattern.startswith("/"):
            clean_pat = pattern.lstrip("/")
            return fnmatch.fnmatch(norm_path, clean_pat)

        # Rule 3: General pattern matching anywhere in path (e.g. '*.rs' or 'src/lib.rs')
        if "/" not in pattern:
            # Matches filename in any directory
            filename = os.path.basename(norm_path)
            return fnmatch.fnmatch(filename, pattern)

        # Pattern with relative subpath
        return fnmatch.fnmatch(norm_path, pattern) or fnmatch.fnmatch(norm_path, f"*/{pattern}")

    def match_all(self, file_path: str) -> List[CodeownersRule]:
        """Find all matching rules for a file in definition order, exposing overlapping rules."""
        norm_path = file_path.replace("\\", "/").strip("/")
        return [rule for rule in self.rules if self._matches_pattern(norm_path, rule.pattern)]

    def match(self, file_path: str) -> CodeownersMatch:
        """Determine declared ownership for a file. Last matching rule wins per GitHub specification."""
        norm_path = file_path.replace("\\", "/").strip("/")
        matching_rules = self.match_all(norm_path)

        if matching_rules:
            winning_rule = matching_rules[-1]
            return CodeownersMatch(
                file_path=norm_path,
                matched=True,
                owners=winning_rule.owners,
                rule_pattern=winning_rule.pattern,
                line_number=winning_rule.line_number,
                source_url=self.source_url,
                is_team=winning_rule.is_team,
                ambiguity=None,
                overlapping_rules=matching_rules,
            )

        return CodeownersMatch(
            file_path=norm_path,
            matched=False,
            owners=[],
            rule_pattern=None,
            line_number=None,
            source_url=self.source_url,
            is_team=False,
            ambiguity="File does not match any declared pattern in CODEOWNERS (unowned/open)",
            overlapping_rules=[],
        )
