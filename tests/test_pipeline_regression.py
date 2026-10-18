"""Regression tests for generic pipeline fixes.

Uses fixture facts NOT in the dev set (ADR-0001, PR #1, Issue #1).
Verifies:
1. Sentence-level claim parsing and verification against authentic fixture spans.
2. Effective source ID mapping from verified claims when citations are grouped.
3. Robust entity identifier parsing when identifier strings contain titles.
"""

import pytest
from src.agent.fixture_loader import (
    get_pull_request_fixture,
    get_issue_fixture,
    get_decision_stored_quote,
)
from src.agent.models import AgentAnswer, Claim, SourceItem
from src.agent.verifier import AgentEvidenceVerifier
from src.agent.loop import AgentExecutionLoop


@pytest.fixture
def verifier():
    return AgentEvidenceVerifier()


def test_regression_adr0003_sentence_verification(verifier):
    """Verify that multi-sentence decision outputs are parsed and verified using ADR-0003 (not in dev set)."""
    stored_quote = get_decision_stored_quote("ADR-0003")
    ans_text = (
        f"We standardise on architectural logging format. "
        f"The architecture board decided: \"{stored_quote}\" [S1]. "
        f"This decision governs repository RFCs."
    )
    ans = AgentAnswer(
        answer=ans_text,
        claims=[
            Claim(
                claim_id="C1",
                text=f"The architecture board decided: \"{stored_quote}\"",
                claim_type="DECISION",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="Decision",
                identifier="ADR-0003",
                url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0003-structured-json-logging.md",
                span_text=f"ADR-0003: Structured JSON Logging. {stored_quote}",
            )
        ],
    )
    res = verifier.verify_answer(ans)
    assert res.status == "VERIFIED", f"Expected VERIFIED, got {res.status}"
    assert len(res.claims) == 1
    assert res.claims[0].verified is True


def test_regression_pr1_descriptive_identifier_extraction(verifier):
    """Verify PR #1 (author Tanya Popova) entity verification when identifier is descriptive (not in dev set)."""
    pr1 = get_pull_request_fixture(1)
    author_login = pr1["user"]["login"]
    
    # Identifier is formatted with descriptive title instead of pure digits
    descriptive_ident = f"PR #1, \"{pr1['title']}\""
    ans = AgentAnswer(
        answer=f"PR #1 was authored by {author_login} [S1].",
        claims=[
            Claim(
                claim_id="C1",
                text=f"PR #1 was authored by {author_login}",
                claim_type="ENTITY",
                source_ids=["S1"],
            )
        ],
        sources=[
            SourceItem(
                id="S1",
                entity_type="PullRequest",
                identifier=descriptive_ident,
                url=f"https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/1",
                span_text=f"PR #1: {pr1['title']} authored by {author_login}",
            )
        ],
    )
    res = verifier.verify_answer(ans)
    assert res.status == "VERIFIED", f"Expected VERIFIED, got {res.status}"
    assert len(res.claims) == 1
    assert res.claims[0].verified is True
    assert res.claims[0].verification_path == "exact_lookup"


def test_regression_loop_parser_sentence_claims():
    """Verify AgentExecutionLoop._parse_structured_answer_from_text builds sentence claims with sources."""
    loop = AgentExecutionLoop()
    raw_text = (
        "PR #1 was authored by tanya-popova.\n"
        "The change implemented push notification service.\n\n"
        "Sources:\n"
        "[S1] PR #1, feat(push): implement push notification service, https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/1"
    )
    tool_sources = [
        SourceItem(
            id="S1",
            entity_type="PullRequest",
            identifier="1",
            url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/1",
            span_text="PR #1: feat(push): implement push notification service. Author: tanya-popova.",
        )
    ]
    parsed = loop._parse_structured_answer_from_text(
        text=raw_text,
        norm_as_of="2026-09-30T23:59:59Z",
        fresh_checked=False,
        step_count=1,
        tools_used=["find_entity"],
        execution_log=[],
        model_used="deepseek/deepseek-chat",
        accumulated_sources=tool_sources,
    )
    assert len(parsed.sources) == 1
    # Check that tool source span_text was NOT overwritten with None
    assert parsed.sources[0].span_text is not None
    assert "tanya-popova" in parsed.sources[0].span_text
    # Check that individual claims were created
    assert len(parsed.claims) >= 1
    assert any("tanya-popova" in c.text for c in parsed.claims)
