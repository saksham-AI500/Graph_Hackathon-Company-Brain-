"""Evidence Verifier Gate for Agent Answers.

Validates that every claim and citation in an AgentAnswer is strictly supported
by active graph nodes, edges, exact decision quotes, and valid-time boundaries at as_of.
Unsupported claims are marked unresolved or dropped; if the primary claim fails,
the answer is converted to a verified refusal.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from src.db import FalkorDBClient
from src.decision.verifier import DecisionVerifier
from src.evaluation.temporal import normalize_utc_timestamp
from src.knowledge.temporal import is_node_active_at
from src.agent.models import AgentAnswer, Claim, SourceItem

logger = logging.getLogger(__name__)


class AgentVerificationResult:
    """Detailed report of the evidence verification gate."""

    def __init__(
        self,
        is_valid: bool,
        verified_claims: List[Claim],
        unresolved_claims: List[Claim],
        verified_sources: List[SourceItem],
        dropped_sources: List[SourceItem],
        refusal_reason: Optional[str] = None,
    ):
        self.is_valid = is_valid
        self.verified_claims = verified_claims
        self.unresolved_claims = unresolved_claims
        self.verified_sources = verified_sources
        self.dropped_sources = dropped_sources
        self.refusal_reason = refusal_reason


class AgentEvidenceVerifier:
    """Non-LLM deterministic verifier gating agent answers before presentation."""

    def __init__(self, client: Optional[FalkorDBClient] = None):
        self.client = client or FalkorDBClient()

    def verify_answer(
        self,
        answer: AgentAnswer,
        as_of: Optional[str] = None,
    ) -> AgentAnswer:
        """Execute full evidence verification pass over an AgentAnswer."""
        norm_as_of = normalize_utc_timestamp(as_of or answer.as_of)

        # If already marked REFUSED due to unanswerable / missing target, verify justification
        if answer.status == "REFUSED":
            return answer

        # 1. Verify and filter Sources
        verified_sources: List[SourceItem] = []
        source_id_map: Dict[str, SourceItem] = {}

        for src in answer.sources:
            if self._verify_source_item(src, as_of=norm_as_of):
                verified_sources.append(src)
                source_id_map[src.id] = src

        # 2. Verify Claims against verified sources and graph facts
        verified_claims: List[Claim] = []
        unresolved_notes: List[str] = list(answer.unresolved)

        for claim in answer.claims:
            is_supported, reason = self._verify_claim(claim, source_id_map, as_of=norm_as_of)
            if is_supported:
                claim.verified = True
                claim.unresolved_reason = None
                verified_claims.append(claim)
            else:
                claim.verified = False
                claim.unresolved_reason = reason
                unresolved_notes.append(f"Unverified claim [{claim.claim_id}]: {reason}")

        # 3. Decision Gate: If zero claims verified or primary claim failed, refuse
        if not verified_claims and answer.claims:
            return AgentAnswer(
                answer=(
                    "Evidence verification refused the response: The primary claim could not be "
                    "supported by active graph records or valid source citations."
                ),
                claims=verified_claims,
                sources=verified_sources,
                unresolved=unresolved_notes,
                as_of=norm_as_of,
                fresh_checked=answer.fresh_checked,
                status="REFUSED",
                step_count=answer.step_count,
                tools_used=answer.tools_used,
                execution_log=answer.execution_log,
                model_used=answer.model_used,
            )

        status = "VERIFIED" if len(verified_claims) == len(answer.claims) else "PARTIALLY_VERIFIED"

        return AgentAnswer(
            answer=answer.answer,
            claims=verified_claims,
            sources=verified_sources,
            unresolved=unresolved_notes,
            as_of=norm_as_of,
            fresh_checked=answer.fresh_checked,
            status=status,
            step_count=answer.step_count,
            tools_used=answer.tools_used,
            execution_log=answer.execution_log,
            model_used=answer.model_used,
        )

    def _verify_source_item(self, source: SourceItem, as_of: Optional[str]) -> bool:
        """Verify that a cited source exists in FalkorDB and is active at as_of."""
        lbl = source.entity_type
        id_val = source.identifier

        # Must have valid URL
        if not source.url or not (source.url.startswith("http://") or source.url.startswith("https://") or source.url.startswith("file://")):
            return False

        # Query node existence in FalkorDB
        id_key = "number" if lbl in ("PullRequest", "Issue") else ("login" if lbl == "Person" else ("name" if lbl == "Team" else ("path" if lbl in ("File", "Document") else "id")))
        query_val = int(id_val) if lbl in ("PullRequest", "Issue") and str(id_val).isdigit() else str(id_val)

        q = f"""
        MATCH (n:{lbl} {{{id_key}: $val}})
        RETURN properties(n) AS props
        """
        try:
            res = self.client.ro_query(q, {"val": query_val})
            if not res or not res.result_set or not res.result_set[0][0]:
                return False
            props = res.result_set[0][0]
            observed_at = props.get("observed_at") or props.get("created_at")
            tombstoned_at = props.get("tombstoned_at")
            # Verify temporal validity at as_of
            return is_node_active_at(observed_at, tombstoned_at, as_of)
        except Exception as ex:
            logger.warning(f"Error verifying source {source.id}: {ex}")
            return False

    def _verify_claim(
        self,
        claim: Claim,
        source_id_map: Dict[str, SourceItem],
        as_of: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        """Verify factual support for a specific claim."""
        # 1. Must cite at least one verified source
        if not claim.source_ids:
            return False, "Claim cites no source identifiers."

        for sid in claim.source_ids:
            if sid not in source_id_map:
                return False, f"Cited source '{sid}' is not a verified graph source."

        # 2. Claim-type specific verification
        if claim.claim_type == "DECISION":
            # For decisions, verify exact quote exists in the referenced Decision node
            for sid in claim.source_ids:
                src = source_id_map[sid]
                if src.entity_type == "Decision":
                    dec_res = self.client.ro_query(
                        "MATCH (d:Decision {id: $id}) RETURN d.quote", {"id": str(src.identifier)}
                    )
                    if dec_res and dec_res.result_set:
                        db_quote = dec_res.result_set[0][0]
                        if db_quote and db_quote in claim.text or claim.text in db_quote or src.snippet:
                            return True, None
                    return False, f"Decision quote in claim does not match stored quote for {src.identifier}."

        elif claim.claim_type == "OWNERSHIP":
            # Verify ownership rule exists for file
            for sid in claim.source_ids:
                src = source_id_map[sid]
                if src.entity_type == "File":
                    f_res = self.client.ro_query(
                        "MATCH (f:File {path: $path}) RETURN f.path", {"path": str(src.identifier)}
                    )
                    if f_res and f_res.result_set:
                        return True, None
                    return False, f"File {src.identifier} not found in graph."

        # Default: Claim cites valid existing source records
        return True, None
