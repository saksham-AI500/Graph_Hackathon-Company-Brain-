"""RepoBrain - Ownership extraction, observed activity, discrepancy analysis, and verification."""

from src.ownership.codeowners import CodeownersParser, CodeownersMatch
from src.ownership.metrics import get_file_authorship, get_file_review_activity, get_reviewer_concentration
from src.ownership.discrepancy import evaluate_ownership_discrepancy, OwnershipDiscrepancyReport
from src.ownership.verifier import NonLLMEvidenceVerifier, VerificationResult

__all__ = [
    "CodeownersParser",
    "CodeownersMatch",
    "get_file_authorship",
    "get_file_review_activity",
    "get_reviewer_concentration",
    "evaluate_ownership_discrepancy",
    "OwnershipDiscrepancyReport",
    "NonLLMEvidenceVerifier",
    "VerificationResult",
]
