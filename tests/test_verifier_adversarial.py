"""Adversarial Rejection and Control Acceptance Test Suite for RepoBrain Verifier.

Tests both:
Part 1: 14 Planted Adversarial Errors
  Each planted error contradicts an explicit source value and MUST be REJECTED.
Part 2: 20 Correct Control Claims
  Includes paraphrases, unit-equivalent values (5000 ms == 5 s), date formats with timezone,
  and correct entity names. Each control MUST be ACCEPTED (status == VERIFIED).
"""

import pytest
from src.agent.models import AgentAnswer, Claim, SourceItem
from src.agent.verifier import AgentEvidenceVerifier


@pytest.fixture
def verifier():
    return AgentEvidenceVerifier()


# =============================================================================
# PART 1: 14 Planted Adversarial Errors (Must Be Rejected)
# =============================================================================

def test_adversarial_1_modal_change_rejected(verifier):
    """1. modal change: 'must' -> 'should'. Contradicts source modal requirement 'must'."""
    source_val = "must"
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
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("does not match exact stored quote" in note for note in verified.unresolved)


def test_adversarial_2_number_change_rejected(verifier):
    """2. number change: '5 attempts' -> '3 attempts'. Contradicts source value '5 attempts'."""
    source_val = "5 attempts"
    span = f"The background sync retry policy specifies {source_val} before dead-letter routing."
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
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_3_negation_rejected(verifier):
    """3. negation: 'approved' -> 'not approved'. Contradicts source value 'approved'."""
    source_val = "approved"
    span = f"PR #42 was {source_val} by Gabriel Santos after reviewing security implications."
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
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_4_scope_change_rejected(verifier):
    """4. scope change: 'payments/' -> 'payments/refunds/'. Contradicts source scope 'payments/'."""
    source_val = "payments/"
    span = f"The new rate limiter applies strictly to {source_val}."
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
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_5_entity_swap_rejected(verifier):
    """5. entity swap: Marcus Vance -> Gabriel Santos. Contradicts source entity 'Marcus Vance'."""
    source_val = "Marcus Vance"
    span = f"{source_val} refactored the auth token validation service."
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
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_6_date_shift_with_timezone_rejected(verifier):
    """6. date shift with timezone: 2025-10-04T23:30:00-05:00 presented as 2025-10-05. Contradicts source date 2025-10-04."""
    source_val = "2025-10-04T23:30:00-05:00"
    span = f"PR #9999 merged_at: {source_val}"
    claim_text = "Pull Request #9999 was merged on 2025-10-05."
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
                identifier=9999,
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/9999",
                span_text=span,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("does not match PR #9999 record" in note for note in verified.unresolved)


def test_adversarial_7_partial_claim_rejected(verifier):
    """7. partial claim: two facts asserted where only one is in source. Contradicts source completeness."""
    source_val = "Marcus Vance updated the auth service configuration."
    span = source_val
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
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_8_numeric_unit_change_rejected(verifier):
    """8. numeric unit change: source value is explicitly 5000 ms, claim asserts 5000 s (1000x error). Contradicts source value '5000 ms'."""
    source_val = "5000 ms"
    span = f"Database connection pool timeout was reconfigured to {source_val}."
    claim_text = "Database connection pool timeout was reconfigured to 5000 s."
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
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_9_wrong_owner_rejected(verifier):
    """9. wrong owner: @acme/growth. Contradicts CODEOWNERS source value '@acme/payments'."""
    source_val = "@acme/payments"
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
                span_text=f"payments/ {source_val}",
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("not declared in CODEOWNERS" in note for note in verified.unresolved)


def test_adversarial_10_wrong_date_off_by_one_day_rejected(verifier):
    """10. wrong date: 2025-10-05. Contradicts source merge date '2025-10-04'."""
    source_val = "2025-10-04"
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
                span_text=f"PR #1 merged_at: {source_val}T09:01:35Z",
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("does not match PR #1 record" in note for note in verified.unresolved)


def test_adversarial_11_uncited_factual_sentence_rejected(verifier):
    """11. uncited factual sentence. Contradicts grounding rule (no ungrounded factual assertions)."""
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
    assert verified.status == "REFUSED"
    logs = verified.verifier.get("sentence_logs", [])
    assert len(logs) == 2
    assert logs[0]["passed"] is True
    assert logs[1]["passed"] is False


def test_adversarial_12_mis_cited_sentence_rejected(verifier):
    """12. mis-cited sentence. Contradicts source span topic (notifications vs Citus sharding)."""
    source_val = "refactor(notifications): update push_service and circuit_breaker"
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
                span_text=source_val,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


def test_adversarial_13_altered_quote_rejected(verifier):
    """13. altered quote: 'forbid'. Contradicts exact stored quote 'mandate'."""
    source_val = "mandate"
    true_quote = f"We {source_val} Redis Cluster for caching and session state."
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
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("does not match exact stored quote" in note for note in verified.unresolved)


def test_adversarial_14_loosely_related_citation_rejected(verifier):
    """14. loosely related citation lacking the fact. Contradicts source span (meeting overview vs 5000ms timeout)."""
    source_val = "We reviewed general database performance, metric dashboards, and indexing strategies in yesterday's team meeting."
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
                span_text=source_val,
            )
        ],
    )
    verified = verifier.verify_answer(ans)
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0
    assert any("below threshold" in note.lower() for note in verified.unresolved)


# =============================================================================
# PART 2: 20 Correct Control Claims (Must Be Accepted)
# =============================================================================

def test_control_1_unit_equivalence_5000ms_to_5s(verifier):
    """Control 1: Unit equivalence: source '5000 ms' -> claim '5 s'. Must be ACCEPTED."""
    span = "Database connection pool timeout was reconfigured to 5000 ms."
    claim = "Database connection pool timeout was reconfigured to 5 s."
    ans = AgentAnswer(
        answer=f"Configuration update: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=88, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/88", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_2_unit_equivalence_1000ms_to_1s(verifier):
    """Control 2: Unit equivalence: source '1000 ms' -> claim '1 s'. Must be ACCEPTED."""
    span = "The auth token cache TTL is set to 1000 ms."
    claim = "The auth token cache TTL is set to 1 s."
    ans = AgentAnswer(
        answer=f"Auth cache setting: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Document", identifier="docs/auth.md", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/auth.md", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_3_unit_equivalence_1024kb_to_1mb(verifier):
    """Control 3: Unit equivalence: source '1024 KB' -> claim '1 MB'. Must be ACCEPTED."""
    span = "Maximum payload size for webhook notifications is capped at 1024 KB."
    claim = "Maximum payload size for webhook notifications is capped at 1 MB."
    ans = AgentAnswer(
        answer=f"Webhook limits: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Document", identifier="docs/webhooks.md", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/webhooks.md", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_4_date_format_utc_timezone(verifier):
    """Control 4: Date format with UTC timezone: source '2025-10-04T09:01:35Z' -> claim '2025-10-04'."""
    span = "PR #1 merged_at: 2025-10-04T09:01:35Z"
    claim = "Pull Request #1 was merged on 2025-10-04."
    ans = AgentAnswer(
        answer=f"{claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="PR_INVESTIGATION", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/1", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_5_date_format_offset_timezone(verifier):
    """Control 5: Date format with offset timezone: source '2025-10-04T23:30:00-05:00' -> claim '2025-10-04'."""
    span = "PR #9999 merged_at: 2025-10-04T23:30:00-05:00"
    claim = "Pull Request #9999 was merged on 2025-10-04."
    ans = AgentAnswer(
        answer=f"{claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="PR_INVESTIGATION", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=9999, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/9999", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_6_correct_entity_marcus_vance(verifier):
    """Control 6: Correct entity name Marcus Vance for PR #236."""
    span = "Marcus Vance refactored the database connection pool in PR #236 to fix timeout errors."
    claim = "Marcus Vance refactored the database connection pool in PR #236."
    ans = AgentAnswer(
        answer=f"Database maintenance: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=236, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/236", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_7_correct_entity_gabriel_santos(verifier):
    """Control 7: Correct entity name Gabriel Santos for token refresh review."""
    span = "Gabriel Santos reviewed and approved PR #305 regarding token refresh rotation."
    claim = "Gabriel Santos reviewed and approved PR #305 regarding token refresh rotation."
    ans = AgentAnswer(
        answer=f"PR approval: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=305, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/305", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_8_correct_entity_elena_rostova(verifier):
    """Control 8: Correct entity name Elena Rostova for Redis clustering PR #142."""
    span = "Elena Rostova merged PR #142 to enable Redis clustering in production."
    claim = "Elena Rostova merged PR #142 to enable Redis clustering in production."
    ans = AgentAnswer(
        answer=f"Production deployment: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=142, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/142", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_9_correct_entity_dmitri_volkov(verifier):
    """Control 9: Correct entity name Dmitri Volkov for search/indexer module."""
    span = "Dmitri Volkov is the primary contributor to search/indexer with 42 commits."
    claim = "Dmitri Volkov contributed 42 commits to search/indexer."
    ans = AgentAnswer(
        answer=f"Module contributions: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Document", identifier="docs/contributors.md", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/contributors.md", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_10_correct_codeowners_payments(verifier):
    """Control 10: Correct declared owner @acme/payments for payments/ module."""
    ans = AgentAnswer(
        answer="The payments/ module is owned by @acme/payments in CODEOWNERS [S1].",
        claims=[Claim(claim_id="C1", text="The payments/ module is owned by @acme/payments in CODEOWNERS.", claim_type="OWNERSHIP", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="File", identifier="payments/", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS", span_text="payments/ @acme/payments")],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_11_correct_codeowners_platform(verifier):
    """Control 11: Correct declared owner @acme/platform for src/module.c."""
    ans = AgentAnswer(
        answer="File src/module.c is owned by @acme/platform in CODEOWNERS [S1].",
        claims=[Claim(claim_id="C1", text="File src/module.c is owned by @acme/platform in CODEOWNERS.", claim_type="OWNERSHIP", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="File", identifier="src/module.c", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS", span_text="* @acme/platform")],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_12_paraphrase_redis_clustering(verifier):
    """Control 12: Paraphrase of Redis clustering enablement."""
    span = "Elena Rostova merged PR #142 to enable Redis clustering in production."
    claim = "Redis clustering was enabled in production by merging PR #142."
    ans = AgentAnswer(
        answer=f"Production architecture: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=142, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/142", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_13_paraphrase_database_pool(verifier):
    """Control 13: Paraphrase of database connection pool refactor."""
    span = "Marcus Vance refactored the database connection pool in PR #236 to fix timeout errors."
    claim = "Database connection pool was refactored in PR #236 to resolve timeout issues."
    ans = AgentAnswer(
        answer=f"Reliability refactoring: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=236, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/236", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_14_paraphrase_retry_policy(verifier):
    """Control 14: Paraphrase of background sync retry attempts."""
    span = "The background sync retry policy specifies 5 attempts before dead-letter routing."
    claim = "The sync worker retries up to 5 times prior to dead-letter queue routing."
    ans = AgentAnswer(
        answer=f"Retry handling: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Document", identifier="docs/sync.md", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/sync.md", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_15_paraphrase_adr002_grpc_mtls(verifier):
    """Control 15: Paraphrase of ADR-002 microservice communication policy."""
    span = "We decided in ADR-002 that all internal microservice communication must use gRPC with mTLS."
    claim = "ADR-002 specifies that microservices communicate using gRPC and mTLS."
    ans = AgentAnswer(
        answer=f"Communication policy: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Decision", identifier="ADR-002", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/002.md", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_16_paraphrase_search_cluster_migration(verifier):
    """Control 16: Paraphrase of search cluster migration date."""
    span = "The search cluster migration was completed on 2026-08-15 without data loss."
    claim = "Search cluster migration finished on 2026-08-15."
    ans = AgentAnswer(
        answer=f"Cluster operations: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=180, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/180", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_17_paraphrase_rabbitmq_dead_letter(verifier):
    """Control 17: Paraphrase of notifications dead-letter routing."""
    span = "The notifications service uses RabbitMQ dead-letter exchanges for failed push deliveries."
    claim = "Failed push deliveries in notifications service are routed to dead-letter exchanges."
    ans = AgentAnswer(
        answer=f"Queue infrastructure: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Document", identifier="docs/notifications.md", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/notifications.md", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_18_paraphrase_rate_limiter_scope(verifier):
    """Control 18: Paraphrase of rate limiter scoping to payments/."""
    span = "The new rate limiter applies strictly to payments/."
    claim = "Payments module traffic is restricted by the new rate limiter."
    ans = AgentAnswer(
        answer=f"Rate limiting: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Document", identifier="docs/rate-limiting.md", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/rate-limiting.md", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_19_exact_decision_quote_redis_cluster(verifier):
    """Control 19: Exact stored decision quote from ADR-004."""
    quote = "We mandate Redis Cluster for caching and session state."
    ans = AgentAnswer(
        answer=f"The architecture board decided: \"{quote}\" [S1].",
        claims=[Claim(claim_id="C1", text=f"The decision states: \"{quote}\"", claim_type="DECISION", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Decision", identifier="ADR-004", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/004.md", span_text=quote)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1


def test_control_20_exact_decision_quote_migrations(verifier):
    """Control 20: Exact stored decision quote from ADR-009."""
    quote = "All database migrations must obtain two staff engineer approvals before execution."
    ans = AgentAnswer(
        answer=f"The architectural board decided: \"{quote}\" [S1].",
        claims=[Claim(claim_id="C1", text=f"The decision states: \"{quote}\"", claim_type="DECISION", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Decision", identifier="ADR-009", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/009.md", span_text=quote)],
    )
    v = verifier.verify_answer(ans)
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
