"""Deterministic verifier for engineering decisions and quotes."""

import re
from typing import List, Optional
from src.decision.extractor import DISQUALIFIERS, PATTERNS
from src.decision.models import DecisionVerificationResult, ExtractedDecision


class DecisionVerifier:
    """Non-LLM verifier checking exact substring alignment, offsets, and evidence validity."""

    @classmethod
    def verify_decision(cls, decision: ExtractedDecision) -> DecisionVerificationResult:
        """Validate that a decision candidate satisfies exact substring and provenance gates."""
        reasons: List[str] = []

        # 1. Verify character offset boundaries
        src_len = len(decision.source_text)
        if decision.quote_start < 0:
            reasons.append(f"Invalid quote_start ({decision.quote_start} < 0)")
        if decision.quote_end > src_len:
            reasons.append(f"Invalid quote_end ({decision.quote_end} > source length {src_len})")
        if decision.quote_start >= decision.quote_end:
            reasons.append(f"Empty or inverted span ({decision.quote_start} >= {decision.quote_end})")

        # 2. Verify exact substring alignment
        if not reasons:
            actual_slice = decision.source_text[decision.quote_start:decision.quote_end]
            if actual_slice != decision.quote:
                reasons.append(
                    f"Quote mismatch at offsets [{decision.quote_start}:{decision.quote_end}]: "
                    f"expected '{decision.quote}', found '{actual_slice}'"
                )

        # 3. Verify pattern presence in the quote or document context
        matched_any = False
        if decision.pattern == "status: accepted":
            if re.search(r"(?i)\bstatus\s*:\s*accepted\b", decision.source_text):
                matched_any = True
        else:
            for _, pattern_regex, _ in PATTERNS:
                if pattern_regex.search(decision.quote):
                    matched_any = True
                    break
        if not matched_any:
            reasons.append(f"Quote does not contain any approved decision pattern: '{decision.quote}'")

        # 4. Verify disqualifiers (prompt injection, instructions, speculation)
        for disq in DISQUALIFIERS:
            if disq.search(decision.quote):
                reasons.append(f"Quote contains disqualified speculative or hostile content: '{disq.pattern}'")
                break

        # 5. Verify source URL format
        if not decision.source_url or not (
            decision.source_url.startswith("https://github.com/")
            or decision.source_url.startswith("file://")
            or decision.source_url.startswith("docs/")
            or decision.source_url.startswith("README")
        ):
            reasons.append(f"Invalid source_url: '{decision.source_url}'")

        is_valid = len(reasons) == 0
        return DecisionVerificationResult(
            is_valid=is_valid,
            rejection_reasons=reasons,
            decision_id=decision.id,
            verified_quote=decision.quote if is_valid else None,
            source_url=decision.source_url if is_valid else None,
        )
