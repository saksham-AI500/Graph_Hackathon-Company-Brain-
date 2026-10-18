"""Deterministic Intent Router for RepoBrain Company Brain.

Classifies user questions into structured intent types before entity matching
or tool selection. This prevents the agent from falling through to naive
entity search when the question requires structured reasoning (e.g., reviewer
ranking, multi-module ownership queries).
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class IntentType(Enum):
    """Recognized question intent categories."""
    REVIEWER_RECOMMENDATION = "reviewer_recommendation"
    CODE_OWNERSHIP = "code_ownership"
    EXPERTISE_QUERY = "expertise_query"
    DECISION_TRACING = "decision_tracing"
    STALENESS_AUDIT = "staleness_audit"
    PR_INVESTIGATION = "pr_investigation"
    ISSUE_INVESTIGATION = "issue_investigation"
    SYNC_STATUS = "sync_status"
    MAINTAINER_RANKING = "maintainer_ranking"
    CODEOWNERS_RULES = "codeowners_rules"
    GENERAL_ENTITY_SEARCH = "general_entity_search"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    INJECTION_ATTEMPT = "injection_attempt"


@dataclass
class RoutedIntent:
    """Result of intent classification with extracted parameters."""
    intent: IntentType
    confidence: float  # 0.0 – 1.0
    modules: List[str] = field(default_factory=list)  # e.g., ["auth/", "payments/"]
    file_paths: List[str] = field(default_factory=list)
    pr_numbers: List[int] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    raw_question: str = ""
    requires_ranking: bool = False
    requires_evidence: bool = False


# ---------------------------------------------------------------------------
# Pattern definitions for each intent
# ---------------------------------------------------------------------------

_REVIEWER_PATTERNS = [
    r"who\s+should\s+review",
    r"suggest\s+reviewer",
    r"reviewer\s+recommendation",
    r"recommend\s+reviewer",
    r"review(?:er)?s?\s+for\s+(?:a\s+)?(?:pr|pull\s+request|change)",
    r"who\s+(?:can|would|could|is\s+best\s+to)\s+review",
    r"rank\s+(?:the\s+)?reviewer",
    r"best\s+reviewer",
    r"who\s+reviews?\s+(?:prs?\s+)?(?:touching|modifying|changing|in)\b",
]

_OWNERSHIP_PATTERNS = [
    r"who\s+owns",
    r"owner\s+of",
    r"ownership\s+(?:of|for|drift)",
    r"who\s+maintains",
    r"codeowner\s+(?:for|of)",
]

_EXPERTISE_PATTERNS = [
    r"who\s+knows",
    r"expert\s+(?:on|in|for|with)",
    r"knows?\s+most\s+about",
    r"knowledge\s+(?:of|about|on)",
    r"most\s+experienced\s+(?:with|in|on)",
]

_DECISION_PATTERNS = [
    r"(?:what|why)\s+(?:was|were)\s+(?:it\s+)?decided",
    r"why\s+did\s+(?:we|they)\s+decide",
    r"decision\s+(?:about|on|for|regarding|to)",
    r"trace\s+(?:the\s+)?decision",
    r"who\s+decided",
    r"design\s+decision",
    r"architectural\s+decision",
    r"rationale\s+(?:for|behind)",
]

_STALENESS_PATTERNS = [
    r"stale\s+doc",
    r"outdated\s+doc",
    r"documentation\s+(?:freshness|staleness|drift)",
    r"are\s+(?:there\s+)?(?:any\s+)?stale",
]

_PR_PATTERNS = [
    r"(?:pr|pull\s+request)\s*#?\s*\d+",
    r"what\s+(?:is|was)\s+(?:the\s+)?(?:pr|pull\s+request)",
    r"brief\s+for\s+(?:pr|pull\s+request)",
    r"who\s+(?:authored|created|wrote|opened)\s+(?:pr|pull\s+request)",
    r"files?\s+(?:changed|modified|touched)\s+(?:in|by)\s+(?:pr|pull\s+request)",
]

_ISSUE_PATTERNS = [
    r"issue\s*#?\s*\d+",
    r"what\s+(?:is|was)\s+(?:the\s+)?issue",
    r"who\s+reported\s+issue",
]

_SYNC_PATTERNS = [
    r"sync\s+status",
    r"freshness\s+(?:status|check)",
    r"last\s+sync",
    r"current\s+sync",
]

_MAINTAINER_PATTERNS = [
    r"top\s+(?:maintainer|contributor)",
    r"pagerank",
    r"most\s+active\s+(?:maintainer|contributor|developer)",
    r"maintainer\s+ranking",
]

_CODEOWNERS_PATTERNS = [
    r"codeowner(?:s)?\s+(?:rule|all|show|list|what)",
    r"show\s+(?:all\s+)?codeowner",
    r"list\s+(?:all\s+)?(?:ownership\s+)?rules",
]

_INJECTION_PATTERNS = [
    r"ignore\s+all\s+prior\s+instructions",
    r"system:\s*override",
    r"grant\s+root",
    r"reveal\s+(?:system\s+)?prompt",
    r"you\s+are\s+now\s+(?:a\s+)?(?:new|different)",
]

# Module/directory extraction patterns
_MODULE_PATTERN = re.compile(
    r"(?:(?:both|and|,)\s+)?[`'\"]?(\w[\w\-.]*/?)[\s`'\"]?"
    r"(?:\s+(?:and|,|&)\s+[`'\"]?(\w[\w\-.]*/?)[\s`'\"]?)?",
    re.IGNORECASE,
)

_DIR_PATTERN = re.compile(
    r"(?:touching|modifying|in|changing|across|both)\s+"
    r"(?:both\s+)?[`'\"]?(\w[\w\-.]*/?)[\s`'\"]?"
    r"(?:\s+(?:and|,|&)\s+[`'\"]?(\w[\w\-.]*/?)[\s`'\"]?)?",
    re.IGNORECASE,
)

_FILE_PATTERN = re.compile(
    r"([\w\-./]+\.[a-zA-Z0-9]+|src/[\w\-./]+|\.github/[\w\-./]+|build/[\w\-./]+)"
)

_PR_NUM_PATTERN = re.compile(r"(?:#|pr\s*#?\s*|pull\s+request\s*#?\s*)(\d{2,6})\b", re.IGNORECASE)

_ISSUE_NUM_PATTERN = re.compile(r"(?:issue\s*#?\s*)(\d{2,6})\b", re.IGNORECASE)


def _matches_any(text: str, patterns: list) -> bool:
    """Check if text matches any of the given regex patterns."""
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def _extract_modules(question: str) -> List[str]:
    """Extract directory/module references from the question."""
    modules: List[str] = []

    # 1. Match explicit directory patterns with trailing slashes (e.g. auth/, payments/, src/)
    explicit_dirs = re.findall(r"[`'\"]?(\b[a-zA-Z0-9_\-.]+/)[`'\"]?", question)
    for d in explicit_dirs:
        clean = d.strip("`'\"")
        if clean and not clean.startswith(("http:/", "https:/")) and clean not in modules:
            modules.append(clean)

    # 2. Contextual pattern for words after touching/in/both without slashes
    m = _DIR_PATTERN.search(question)
    if m:
        for g in m.groups():
            if g:
                clean = g.strip().strip("`'\"")
                if clean and len(clean) >= 2 and clean.lower() not in {"both", "and"}:
                    if not clean.endswith("/") and "." not in clean:
                        clean += "/"
                    if clean not in modules:
                        modules.append(clean)

    return modules


def _extract_file_paths(question: str) -> List[str]:
    """Extract file paths from the question."""
    matches = _FILE_PATTERN.findall(question)
    return [m.lstrip("/") for m in matches]


def _extract_pr_numbers(question: str) -> List[int]:
    """Extract PR numbers from the question."""
    return [int(m) for m in _PR_NUM_PATTERN.findall(question)]


def _extract_issue_numbers(question: str) -> List[int]:
    """Extract issue numbers from the question."""
    return [int(m) for m in _ISSUE_NUM_PATTERN.findall(question)]


def classify_intent(question: str) -> RoutedIntent:
    """Classify a user question into a structured intent with extracted parameters.

    Intent routing is deterministic and runs before any entity matching or
    tool selection. This ensures that structured queries (reviewer ranking,
    multi-module ownership) are handled by dedicated logic paths rather than
    falling through to generic entity search.

    Args:
        question: The raw user question string.

    Returns:
        A RoutedIntent with the classified intent type, confidence, and
        extracted parameters (modules, file paths, PR numbers, etc.).
    """
    q = question.strip()
    lower_q = q.lower()

    # 1. Security: Check for injection attempts first
    if _matches_any(lower_q, _INJECTION_PATTERNS):
        return RoutedIntent(
            intent=IntentType.INJECTION_ATTEMPT,
            confidence=1.0,
            raw_question=q,
        )

    # 2. Reviewer Recommendation (highest priority structured intent)
    if _matches_any(lower_q, _REVIEWER_PATTERNS):
        modules = _extract_modules(q)
        files = _extract_file_paths(q)
        prs = _extract_pr_numbers(q)
        has_rank_request = bool(re.search(r"rank|ranked|ranking|evidence", lower_q, re.IGNORECASE))
        return RoutedIntent(
            intent=IntentType.REVIEWER_RECOMMENDATION,
            confidence=0.95,
            modules=modules,
            file_paths=files,
            pr_numbers=prs,
            raw_question=q,
            requires_ranking=True,
            requires_evidence=has_rank_request,
        )

    # 3. Code Ownership
    if _matches_any(lower_q, _OWNERSHIP_PATTERNS):
        files = _extract_file_paths(q)
        modules = _extract_modules(q) if not files else []
        return RoutedIntent(
            intent=IntentType.CODE_OWNERSHIP,
            confidence=0.9,
            modules=modules,
            file_paths=files,
            raw_question=q,
        )

    # 4. Expertise / Who Knows
    if _matches_any(lower_q, _EXPERTISE_PATTERNS):
        files = _extract_file_paths(q)
        return RoutedIntent(
            intent=IntentType.EXPERTISE_QUERY,
            confidence=0.9,
            file_paths=files,
            raw_question=q,
        )

    # 5. CODEOWNERS Rules Listing
    if _matches_any(lower_q, _CODEOWNERS_PATTERNS):
        return RoutedIntent(
            intent=IntentType.CODEOWNERS_RULES,
            confidence=0.9,
            raw_question=q,
        )

    # 6. Decision Tracing
    if _matches_any(lower_q, _DECISION_PATTERNS):
        return RoutedIntent(
            intent=IntentType.DECISION_TRACING,
            confidence=0.85,
            raw_question=q,
        )

    # 7. Staleness
    if _matches_any(lower_q, _STALENESS_PATTERNS):
        return RoutedIntent(
            intent=IntentType.STALENESS_AUDIT,
            confidence=0.9,
            raw_question=q,
        )

    # 8. Sync Status
    if _matches_any(lower_q, _SYNC_PATTERNS):
        return RoutedIntent(
            intent=IntentType.SYNC_STATUS,
            confidence=0.9,
            raw_question=q,
        )

    # 9. Maintainer Ranking
    if _matches_any(lower_q, _MAINTAINER_PATTERNS):
        return RoutedIntent(
            intent=IntentType.MAINTAINER_RANKING,
            confidence=0.9,
            raw_question=q,
        )

    # 10. PR Investigation (by number)
    prs = _extract_pr_numbers(q)
    if prs or _matches_any(lower_q, _PR_PATTERNS):
        return RoutedIntent(
            intent=IntentType.PR_INVESTIGATION,
            confidence=0.85,
            pr_numbers=prs,
            raw_question=q,
        )

    # 11. Issue Investigation
    issues = _extract_issue_numbers(q)
    if issues or _matches_any(lower_q, _ISSUE_PATTERNS):
        return RoutedIntent(
            intent=IntentType.ISSUE_INVESTIGATION,
            confidence=0.85,
            pr_numbers=issues,  # reuse field for issue nums
            raw_question=q,
        )

    # 12. Check for bare number references (could be PR or Issue)
    bare_num = re.search(r"\b#?(\d{2,6})\b", q)
    if bare_num:
        return RoutedIntent(
            intent=IntentType.PR_INVESTIGATION,
            confidence=0.6,
            pr_numbers=[int(bare_num.group(1))],
            raw_question=q,
        )

    # 13. General or ambiguous
    files = _extract_file_paths(q)
    if files:
        return RoutedIntent(
            intent=IntentType.GENERAL_ENTITY_SEARCH,
            confidence=0.5,
            file_paths=files,
            raw_question=q,
        )

    return RoutedIntent(
        intent=IntentType.GENERAL_ENTITY_SEARCH,
        confidence=0.3,
        raw_question=q,
    )
