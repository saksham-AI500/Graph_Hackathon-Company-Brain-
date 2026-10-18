"""Adversarial Rejection Test Suite for RepoBrain Verifier.

Tests that each of the 14 planted errors is rejected by the verifier,
and that the test fails if any planted error is accepted:
1. modal change: "must" -> "should" in a decision quote
2. number change: "5 attempts" -> "3 attempts"
3. negation: "approved" -> "not approved"
4. scope change: "payments/" -> "payments/refunds/"
5. entity swap: a true statement with Marcus Vance's name replaced by Gabriel Santos's
6. date shift with a timezone: 2025-10-04T23:30:00-05:00 presented as 2025-10-05
7. partial claim: a claim with two facts where only one is in the span
8. numeric unit change: 5000 ms -> 5 s
9. wrong owner: a real team or person with no CODEOWNERS rule for the module
10. wrong date: a merge date off by one day from the fixture
11. uncited sentence: a factual sentence with no [S#] marker
12. mis-cited sentence: a real [S#] whose span does not contain the sentence's fact
13. altered quote: an exact quote with one word changed ("mandate" -> "forbid")
14. loosely related citation: a true claim cited to a span that mentions the topic but not the fact
"""

import pytest
from src.agent.models import AgentAnswer, Claim, SourceItem
from src.agent.verifier import AgentEvidenceVerifier


@pytest.fixture
def verifier():
    return AgentEvidenceVerifier()


def test_adversarial_1_modal_change_rejected(verifier):
    """1. modal change: 'must' -> 'should' in a decision quote."""
    true_quote = "All database migrations must obtain two staff engineer approvals before execution."
    altered_quote = "All database migrations should obtain two staff engineer approvals before execution."
    ans = AgentAnswer(
        answer=f"The architectural board decided: \"{altered_quote}\" [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=f"The decision states: \"{altered_quote}\"",
                claim_type="DECISION",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="Decision",
                identifier="ADR-009",
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/009.md",
                span_text=true_quote,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject decision claim with modal change ('must' -> 'should')"
    assert len(verified.claims) == 0
    assert any("does not match exact stored quote" in note for note in verified.unresolved)


def test_adversarial_2_number_change_rejected(verifier):
    """2. number change: '5 attempts' -> '3 attempts' in general prose."""
    span = "The background sync retry policy specifies 5 attempts before dead-letter routing."
    claim_text = "The background sync retry policy specifies 3 attempts before dead-letter routing."
    ans = AgentAnswer(
        answer=f"{claim_text} [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=claim_text,
                claim_type="GENERAL",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="Document",
                identifier="docs/architecture/sync.md",
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/architecture/sync.md",
                span_text=span,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject claim with number change ('5 attempts' -> '3 attempts')"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_3_negation_rejected(verifier):
    """3. negation: 'approved' -> 'not approved'."""
    span = "PR #42 was approved by Gabriel Santos after reviewing security implications."
    claim_text = "PR #42 was not approved by Gabriel Santos."
    ans = AgentAnswer(
        answer=f"Pull request status: {claim_text} [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=claim_text,
                claim_type="GENERAL",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=42,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/42",
                span_text=span,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject claim with negation ('approved' -> 'not approved')"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_4_scope_change_rejected(verifier):
    """4. scope change: 'payments/' -> 'payments/refunds/'."""
    span = "The new rate limiter applies strictly to payments/."
    claim_text = "The new rate limiter applies strictly to payments/refunds/."
    ans = AgentAnswer(
        answer=f"{claim_text} [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=claim_text,
                claim_type="GENERAL",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="Document",
                identifier="docs/architecture/rate-limiting.md",
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/architecture/rate-limiting.md",
                span_text=span,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject claim with scope change ('payments/' -> 'payments/refunds/')"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_5_entity_swap_rejected(verifier):
    """5. entity swap: a true statement with Marcus Vance's name replaced by Gabriel Santos's."""
    span = "Marcus Vance refactored the auth token validation service."
    claim_text = "Gabriel Santos refactored the auth token validation service."
    ans = AgentAnswer(
        answer=f"Engineering changes: {claim_text} [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=claim_text,
                claim_type="GENERAL",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=55,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/55",
                span_text=span,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject claim with entity swap (Marcus Vance -> Gabriel Santos)"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_6_date_shift_with_timezone_rejected(verifier):
    """6. date shift with a timezone: 2025-10-04T23:30:00-05:00 presented as 2025-10-05."""
    span = "PR #10 merged_at: 2025-10-04T23:30:00-05:00"
    claim_text = "Pull Request #10 was merged on 2025-10-05."
    ans = AgentAnswer(
        answer=f"{claim_text} [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=claim_text,
                claim_type="PR_INVESTIGATION",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=10,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/10",
                span_text=span,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject date shift where 2025-10-04T23:30:00-05:00 is presented as 2025-10-05"
    assert len(verified.claims) == 0
    assert any("does not match PR #10 record" in note for note in verified.unresolved)


def test_adversarial_7_partial_claim_rejected(verifier):
    """7. partial claim: a claim with two facts where only one is in the span."""
    span = "Marcus Vance updated the auth service configuration."
    claim_text = "Marcus Vance updated the auth service configuration and migrated the database to PostgreSQL."
    ans = AgentAnswer(
        answer=f"Recent sprint activity: {claim_text} [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=claim_text,
                claim_type="GENERAL",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=72,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/72",
                span_text=span,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject partial claim where second fact is unsupported"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_8_numeric_unit_change_rejected(verifier):
    """8. numeric unit change: 5000 ms -> 5 s."""
    span = "Database connection pool timeout was reconfigured to 5000 ms."
    claim_text = "Database connection pool timeout was reconfigured to 5 s."
    ans = AgentAnswer(
        answer=f"Configuration update: {claim_text} [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=claim_text,
                claim_type="GENERAL",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=88,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/88",
                span_text=span,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject claim with numeric unit change ('5000 ms' -> '5 s')"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_9_wrong_owner_rejected(verifier):
    """9. wrong owner: @acme/growth is a real team, but payments/ is owned by @acme/payments."""
    ans = AgentAnswer(
        answer="The payments/ module is owned by @acme/growth in CODEOWNERS [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text="The payments/ module is owned by @acme/growth in CODEOWNERS.",
                claim_type="OWNERSHIP",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="File",
                identifier="payments/",
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS",
                span_text="payments/ @acme/payments",
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject answer with wrong owner"
    assert len(verified.claims) == 0
    assert any("not declared in CODEOWNERS" in note for note in verified.unresolved)


def test_adversarial_10_wrong_date_off_by_one_day_rejected(verifier):
    """10. wrong date: PR #1 was merged on 2025-10-04, but claim asserts 2025-10-05 (off by one day)."""
    ans = AgentAnswer(
        answer="Pull Request #1 was merged on 2025-10-05 after notifications refactoring [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text="Pull Request #1 was merged on 2025-10-05.",
                claim_type="PR_INVESTIGATION",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=1,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/1",
                span_text="PR #1 merged_at: 2025-10-04T09:01:35Z",
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject answer with date off by one day"
    assert len(verified.claims) == 0
    assert any("does not match PR #1 record" in note for note in verified.unresolved)


def test_adversarial_11_uncited_factual_sentence_rejected(verifier):
    """11. uncited factual sentence: an answer contains a factual sentence with no [S#] marker."""
    ans = AgentAnswer(
        answer=(
            "File src/module.c is owned by @acme/platform [S1]. "
            "Elena Rostova secretly deployed unapproved database sharding code to production yesterday."
        ),
        claims=[
            Claim(
                claim_id="C1",
                text="File src/module.c is owned by @acme/platform.",
                claim_type="OWNERSHIP",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="File",
                identifier="src/module.c",
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS",
                span_text="* @acme/platform",
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject answer with uncited factual sentence"
    logs = verified.verifier.get("sentence_logs", [])
    assert len(logs) == 2
    assert logs[0]["passed"] is True
    assert logs[1]["passed"] is False
    assert "missing mapped verified claim or bracketed source citation" in logs[1]["reason"]


def test_adversarial_12_mis_cited_sentence_rejected(verifier):
    """12. mis-cited sentence: a real [S1] whose span does not contain the sentence's fact."""
    ans = AgentAnswer(
        answer="The database engine was migrated to distributed Citus sharding in PR #1 [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text="The database engine was migrated to distributed Citus sharding in PR #1.",
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
                span_text="refactor(notifications): update push_service and circuit_breaker for notifications module",
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject claim when cited span does not contain the fact"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_13_altered_quote_rejected(verifier):
    """13. altered quote: exact stored quote has one word changed ('mandate' -> 'forbid')."""
    true_quote = "We mandate Redis Cluster for caching and session state."
    altered_quote = "We forbid Redis Cluster for caching and session state."

    ans = AgentAnswer(
        answer=f"The architecture board decided: \"{altered_quote}\" [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=f"The decision states: \"{altered_quote}\"",
                claim_type="DECISION",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="Decision",
                identifier="ADR-004",
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/004.md",
                span_text=true_quote,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject decision claim with altered quote"
    assert len(verified.claims) == 0
    assert any("does not match exact stored quote" in note for note in verified.unresolved)


def test_adversarial_14_loosely_related_citation_rejected(verifier):
    """14. loosely related citation: span mentions the general topic (database) but not the fact (5000ms timeout)."""
    topic_span = "We reviewed general database performance, metric dashboards, and indexing strategies in yesterday's team meeting."
    fact_claim = "Database connection pool timeout was explicitly reconfigured to 5000ms."

    ans = AgentAnswer(
        answer=f"Database configuration was updated: {fact_claim} [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=fact_claim,
                claim_type="GENERAL",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=12,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/12",
                span_text=topic_span,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED", "Verifier MUST reject true claim cited to loosely related span lacking the fact"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)
