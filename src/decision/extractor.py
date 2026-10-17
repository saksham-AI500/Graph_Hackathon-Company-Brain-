"""Conservative, deterministic decision extractor for RepoBrain.

Extracts explicit engineering decisions from PR bodies, issues, comments,
and architecture documents using deterministic rule-based pattern matching.
Zero LLM dependencies. Every decision preserves exact source text and character offsets.
"""

import re
from typing import List, Optional, Tuple
from src.decision.models import ExtractedDecision

# Explicit decision patterns required by specification
PATTERNS = [
    ("we decided", re.compile(r"\bwe\s+decided\b", re.IGNORECASE), "decided"),
    ("decision:", re.compile(r"\bdecision\s*:", re.IGNORECASE), "decided"),
    ("won't fix", re.compile(r"\bwon'?t\s+fix\b", re.IGNORECASE), "wont_fix"),
    ("going with", re.compile(r"\bgoing\s+with\b", re.IGNORECASE), "decided"),
    ("status: accepted", re.compile(r"(?i)(?:^|\n)\s*status\s*:\s*accepted\b"), "accepted"),
]

# Speculation, ambiguity, or prompt injection indicators that must be rejected
DISQUALIFIERS = [
    re.compile(r"\bmaybe\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+if\b", re.IGNORECASE),
    re.compile(r"\bcould\s+we\b", re.IGNORECASE),
    re.compile(r"\bnot\s+sure\b", re.IGNORECASE),
    re.compile(r"\bif\s+we\s+decided\b", re.IGNORECASE),
    re.compile(r"\btodo\b", re.IGNORECASE),
    re.compile(r"\bwip\b", re.IGNORECASE),
    re.compile(r"\bunresolved\b", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+(?:prompt|override|instruction)", re.IGNORECASE),
    re.compile(r"user\s+request\s*:", re.IGNORECASE),
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"<untrusted_data", re.IGNORECASE),
]

# Entity reference pattern for detecting affected targets (e.g., #3339, src/db.py)
AFFECTS_PATTERN = re.compile(r"(?:#\d+|src/[\w/.-]+\.\w+|docs/[\w/.-]+\.md)")


def _find_sentence_bounds(text: str, match_start: int, match_end: int) -> Tuple[int, int]:
    """Find the start and end indices of the sentence enclosing the match."""
    # Look backward for sentence start
    start = match_start
    while start > 0 and text[start - 1] not in ".\n\r?!":
        start -= 1
    
    # Look forward for sentence end
    end = match_end
    while end < len(text) and text[end] not in ".\n\r?!":
        end += 1
    if end < len(text) and text[end] in ".!?":
        end += 1  # Include terminal punctuation

    # Adjust for leading/trailing whitespace without breaking exact slice identity
    raw_slice = text[start:end]
    stripped = raw_slice.strip()
    if not stripped:
        return match_start, match_end
    
    leading_ws = len(raw_slice) - len(raw_slice.lstrip())
    final_start = start + leading_ws
    final_end = final_start + len(stripped)
    return final_start, final_end


class RuleBasedDecisionExtractor:
    """Deterministic extractor for source-quoted engineering decisions."""

    @classmethod
    def extract_decisions(
        cls,
        source_text: str,
        source_id: str,
        source_type: str,
        source_url: str,
    ) -> List[ExtractedDecision]:
        """Extract all verified decisions from source_text.
        
        Guarantees that:
        source_text[decision.quote_start:decision.quote_end] == decision.quote
        """
        if not source_text or not source_text.strip():
            return []

        decisions: List[ExtractedDecision] = []
        seen_spans = set()

        for pattern_name, pattern_regex, status_state in PATTERNS:
            for match in pattern_regex.finditer(source_text):
                # Handle ADR status block
                if pattern_name == "status: accepted":
                    # For ADRs, check if there is a '## Decision' section following Status: accepted
                    dec_section_match = re.search(r"(?i)##\s*decision\s*\n+([^#\n\r][^\n\r]+)", source_text)
                    if dec_section_match:
                        raw_start, raw_end = dec_section_match.start(1), dec_section_match.end(1)
                    else:
                        raw_start, raw_end = match.start(), match.end()
                    q_start, q_end = _find_sentence_bounds(source_text, raw_start, raw_end)
                else:
                    q_start, q_end = _find_sentence_bounds(source_text, match.start(), match.end())

                quote = source_text[q_start:q_end]
                if not quote:
                    continue

                # Ensure span not duplicated
                if (q_start, q_end) in seen_spans:
                    continue

                # Validate disqualifiers (speculation, ambiguity, prompt injection)
                if any(disq.search(quote) for disq in DISQUALIFIERS):
                    continue

                seen_spans.add((q_start, q_end))

                # Detect explicitly affected entities
                affects_target: Optional[str] = None
                aff_match = AFFECTS_PATTERN.search(quote)
                if aff_match:
                    affects_target = aff_match.group(0).rstrip(".,;:!?")

                # Detect supersession
                supersedes_id: Optional[str] = None
                super_match = re.search(r"(?i)supersedes\s+([#\w.-]+)", quote)
                if super_match:
                    supersedes_id = super_match.group(1).rstrip(".,;:!?")

                decision_id = ExtractedDecision.generate_id(source_id, q_start, q_end)

                decisions.append(
                    ExtractedDecision(
                        id=decision_id,
                        pattern=pattern_name,
                        quote=quote,
                        quote_start=q_start,
                        quote_end=q_end,
                        source_text=source_text,
                        source_id=source_id,
                        source_type=source_type,
                        source_url=source_url,
                        status_state=status_state,
                        affects_target=affects_target,
                        supersedes_id=supersedes_id,
                    )
                )

        return decisions
