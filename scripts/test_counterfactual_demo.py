"""Demonstration of FIX 4 Counterfactual Behavior (3 Exact Dev Fixtures).

Explicitly labeled as dev fixtures, not validation:
- Dev Fixture Case 1 (dev fixture, not validation): Claim supported by span elsewhere in source set
  - Emits citation_correction naming the supporting span.
  - Rewrites answer text to visibly show the correction: [S1 corrected to S2].
  - Reports post-hoc citations as a separate count, excluded from claims_fully_supported.
- Dev Fixture Case 2 (dev fixture, not validation): No span anywhere supports the claim
  - Refuses the claim.
- Dev Fixture Case 3 (dev fixture, not validation): Removing the only cited source leaves claim unsupported
  - Accepts citation (post_hoc = False, verified = True).
"""

import sys
sys.path.insert(0, ".")
import json
from src.agent.models import AgentAnswer, Claim, SourceItem
from src.agent.verifier import AgentEvidenceVerifier


def main():
    verifier = AgentEvidenceVerifier()

    print("=" * 80)
    print("Dev Fixture Case 1 (dev fixture, not validation): Claim supported elsewhere")
    print("=" * 80)
    ans1 = AgentAnswer(
        answer="Database timeout issues were resolved by refactoring the connection pool [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text="Database timeout issues were resolved by refactoring the connection pool.",
                claim_type="GENERAL",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=99,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/99",
                span_text="docs: update README documentation and badge layout for dark mode",
            ),
            SourceItem(
                id="S2",
                entity_type="PullRequest",
                identifier=236,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/236",
                span_text="Marcus Vance refactored the database connection pool in PR #236 to fix timeout errors.",
            ),
        ],
    )
    v1 = verifier.verify_answer(ans1)
    print(f"Status: {v1.status}")
    print(f"Original Answer Text: {ans1.answer}")
    print(f"Visible Answer Text:   {v1.answer}")
    print(f"Claims Total: {v1.verifier.get('claims_total')}")
    print(f"Claims Passed: {v1.verifier.get('claims_passed')}")
    print(f"Claims Fully Supported (excluding post-hoc): {v1.verifier.get('claims_fully_supported')}")
    print(f"Post-Hoc Citations Count (reported separately): {v1.verifier.get('post_hoc_citations')}")
    if v1.claims:
        c1 = v1.claims[0]
        print(f"Claim ID: {c1.claim_id}")
        print(f"Post-hoc: {c1.post_hoc}")
        print(f"Verified: {c1.verified}")
        print(f"Citation Correction: {json.dumps(c1.citation_correction, indent=2)}")
        print(f"Verification Path: {c1.verification_path}")
        print(f"Supporting Span: {c1.supporting_span}")

    print("\n" + "=" * 80)
    print("Dev Fixture Case 2 (dev fixture, not validation): No span supports claim")
    print("=" * 80)
    ans2 = AgentAnswer(
        answer="Elena Rostova secretly deployed unapproved database sharding code yesterday [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text="Elena Rostova secretly deployed unapproved database sharding code yesterday.",
                claim_type="GENERAL",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=1,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/1",
                span_text="refactor(notifications): update push_service and circuit_breaker",
            ),
            SourceItem(
                id="S2",
                entity_type="Document",
                identifier="docs/architecture/overview.md",
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/architecture/overview.md",
                span_text="Overview of the core architecture and service boundaries.",
            ),
        ],
    )
    v2 = verifier.verify_answer(ans2)
    print(f"Status: {v2.status}")
    print(f"Verified Claims Count: {len(v2.claims)}")
    print(f"Refusal Reason: {v2.refusal_reason}")
    print(f"Unresolved Notes: {v2.unresolved}")

    print("\n" + "=" * 80)
    print("Dev Fixture Case 3 (dev fixture, not validation): Essential single citation accepted")
    print("=" * 80)
    ans3 = AgentAnswer(
        answer="Database timeout issues were resolved by refactoring the connection pool [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text="Database timeout issues were resolved by refactoring the connection pool.",
                claim_type="GENERAL",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=236,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/236",
                span_text="Marcus Vance refactored the database connection pool in PR #236 to fix timeout errors.",
            ),
        ],
    )
    v3 = verifier.verify_answer(ans3)
    print(f"Status: {v3.status}")
    print(f"Visible Answer Text: {v3.answer}")
    print(f"Claims Fully Supported: {v3.verifier.get('claims_fully_supported')}")
    print(f"Post-Hoc Citations Count: {v3.verifier.get('post_hoc_citations')}")
    if v3.claims:
        c3 = v3.claims[0]
        print(f"Claim ID: {c3.claim_id}")
        print(f"Post-hoc: {c3.post_hoc}")
        print(f"Verified: {c3.verified}")
        print(f"Citation Correction: {c3.citation_correction}")
        print(f"Score: {c3.score:.4f}")
        print(f"Verification Path: {c3.verification_path}")
        print(f"Supporting Span: {c3.supporting_span}")


if __name__ == "__main__":
    main()
