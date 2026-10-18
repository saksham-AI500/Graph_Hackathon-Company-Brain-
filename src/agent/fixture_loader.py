"""Runtime loader for authentic repository testbed fixtures.

Provides deterministic, runtime access to fixture files without hardcoding
fixture values in test files.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic" / "fixtures"


def get_pull_request_fixture(pr_number: int) -> Dict[str, Any]:
    """Load PR fixture JSON by PR number at runtime."""
    path = FIXTURES_DIR / "pulls" / f"{pr_number}.json"
    if not path.exists():
        raise FileNotFoundError(f"Fixture PR #{pr_number} not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_issue_fixture(issue_number: int) -> Dict[str, Any]:
    """Load Issue fixture JSON by Issue number at runtime."""
    path = FIXTURES_DIR / "issues" / f"{issue_number}.json"
    if not path.exists():
        raise FileNotFoundError(f"Fixture Issue #{issue_number} not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_codeowners_rules() -> List[Tuple[str, List[str]]]:
    """Load CODEOWNERS declarations as a list of (pattern, owners_list)."""
    path = FIXTURES_DIR / "codeowners.txt"
    if not path.exists():
        raise FileNotFoundError(f"CODEOWNERS fixture not found at {path}")
    rules = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            parts = line.split()
            if len(parts) >= 2:
                rules.append((parts[0], parts[1:]))
    return rules


def match_codeowners_pattern(pattern: str, file_path: str) -> bool:
    """Evaluate if normalized file_path matches a CODEOWNERS pattern according to GitHub rules.
    - Patterns are evaluated relative to repository root.
    - Pattern '*' matches all files.
    - Pattern ending with '/' matches that exact directory prefix and anything inside it.
    - Pattern without '/' matches a filename or wildcard anywhere or at root.
    - Pattern with '/' matches exact relative path or fnmatch relative to root.
    """
    clean_path = file_path.strip().lstrip("/")
    clean_pat = pattern.strip().lstrip("/")

    if clean_pat == "*":
        return True

    if clean_pat.endswith("/"):
        dir_prefix = clean_pat.rstrip("/")
        return clean_path == dir_prefix or clean_path.startswith(f"{dir_prefix}/")

    if "/" not in clean_pat:
        import fnmatch
        filename = clean_path.split("/")[-1]
        return clean_path == clean_pat or filename == clean_pat or fnmatch.fnmatch(filename, clean_pat)

    import fnmatch
    return clean_path == clean_pat or fnmatch.fnmatch(clean_path, clean_pat)


def get_codeowners_rule_for_path(target_path: str) -> Tuple[Optional[str], List[str]]:
    """Return the declared (pattern, owners) for target_path according to CODEOWNERS."""
    rules = get_codeowners_rules()
    best_rule: Optional[Tuple[str, List[str]]] = None
    for pattern, owners in rules:
        if match_codeowners_pattern(pattern, target_path):
            best_rule = (pattern, owners)
    if best_rule:
        return best_rule
    return None, []


def get_decision_stored_quote(decision_id: str) -> str:
    """Load exact stored quote for an ADR decision from fixture tools."""
    from src.agent.fixture_tools import execute_fixture_tool
    results, _ = execute_fixture_tool("trace_decision", {"query_or_pr": decision_id})
    for r in results:
        if r.get("decision_id", "").lower() == decision_id.lower() and "quote" in r:
            return r["quote"]
    raise KeyError(f"Stored quote for {decision_id} not found in decision fixtures.")
