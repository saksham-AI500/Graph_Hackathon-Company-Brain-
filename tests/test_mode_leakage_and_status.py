"""Tests for FIX 5: graph_off fairness, status, extended leakage, and fabricated citation harness.

Ensures:
1. The answer text, unresolved list, and refusal_reason do not leak forbidden terms:
   Fails if any field contains:
   "graph_on", "graph_off", "mode", "tools", "tool", "baseline", "disabled", "unavailable in", "graph".
2. A zero-claim answer NEVER gets status VERIFIED.
   Uses ANSWERED_UNCERTAIN for answers with stated uncertainty.
   Uses REFUSED for refusals.
   Uses VERIFIED only when all claims pass.
3. System prompt parity: Prompt strings for graph_on and graph_off are identical.
4. Model string is recorded on answer object.
5. Harness check: Fabricated citations count is recorded in answer.verifier["fabricated_citations"].
   If fabricated_citations > 0, status must NEVER be ANSWERED_UNCERTAIN.
"""

import pytest
from src.agent.loop import AgentExecutionLoop, AgentRequest
from src.agent.models import AgentAnswer, Claim, SourceItem
from src.agent.prompt import build_agent_system_prompt
from src.agent.verifier import AgentEvidenceVerifier

FORBIDDEN_LEAKAGE_TOKENS = [
    "graph_on",
    "graph_off",
    "mode",
    "tools",
    "tool",
    "baseline",
    "disabled",
    "unavailable in",
    "graph",
]


def test_system_prompt_parity_between_modes():
    """Verify that graph_on and graph_off share the exact same system prompt with zero mode leakage."""
    prompt = build_agent_system_prompt()
    assert "graph_on" not in prompt.lower(), "System prompt must not mention graph_on"
    assert "graph_off" not in prompt.lower(), "System prompt must not mention graph_off"
    assert "mode" not in prompt.lower(), "System prompt must not mention mode"


def test_zero_claim_answer_never_verified():
    """A zero-claim answer must not get status VERIFIED."""
    verifier = AgentEvidenceVerifier()

    # Zero-claim answer with uncertain statement
    uncertain_ans = AgentAnswer(
        answer="The payments/ module is likely owned by @acme/payments, though this cannot be confirmed.",
        claims=[],
        sources=[],
        status="ANSWERED_UNCERTAIN",
    )
    v_uncertain = verifier.verify_answer(uncertain_ans)
    assert v_uncertain.status != "VERIFIED", "Zero-claim answer must NEVER be VERIFIED"
    assert v_uncertain.status == "ANSWERED_UNCERTAIN"

    # Zero-claim answer with refusal
    refusal_ans = AgentAnswer(
        answer="I cannot answer who is on call next week from the data.",
        claims=[],
        sources=[],
        status="REFUSED",
    )
    v_refusal = verifier.verify_answer(refusal_ans)
    assert v_refusal.status == "REFUSED"


def test_graph_off_extended_leakage_and_harness_check():
    """Verify that graph_off answers, unresolved notes, and refusal reasons are strictly leakage-free."""
    loop = AgentExecutionLoop()

    # Question 1: Exact original wording for factual question
    req1 = AgentRequest(
        question="Which team owns the payments/ module, as far as you know?",
        mode="graph_off",
    )
    ans1 = loop.run(req1)
    
    # Check all fields for forbidden leakage tokens
    fields_to_check_1 = [
        ("answer", ans1.answer.lower()),
        ("refusal_reason", (ans1.refusal_reason or "").lower()),
    ] + [("unresolved", u.lower()) for u in ans1.unresolved]

    for field_name, text in fields_to_check_1:
        for forbidden in FORBIDDEN_LEAKAGE_TOKENS:
            assert forbidden not in text, (
                f"graph_off answer 1 field '{field_name}' leaks forbidden token '{forbidden}': '{text}'"
            )

    assert ans1.status in ("ANSWERED_UNCERTAIN", "REFUSED")
    assert ans1.status != "VERIFIED"
    assert ans1.model_used is not None
    assert "fabricated_citations" in ans1.verifier
    if ans1.verifier["fabricated_citations"] > 0:
        assert ans1.status != "ANSWERED_UNCERTAIN", "Fabricated repository claims must NOT be ANSWERED_UNCERTAIN"

    # Question 2: Exact original wording for unanswerable question
    req2 = AgentRequest(
        question="Who is on call next week at Acme Platform?",
        mode="graph_off",
    )
    ans2 = loop.run(req2)
    
    fields_to_check_2 = [
        ("answer", ans2.answer.lower()),
        ("refusal_reason", (ans2.refusal_reason or "").lower()),
    ] + [("unresolved", u.lower()) for u in ans2.unresolved]

    for field_name, text in fields_to_check_2:
        for forbidden in FORBIDDEN_LEAKAGE_TOKENS:
            assert forbidden not in text, (
                f"graph_off answer 2 field '{field_name}' leaks forbidden token '{forbidden}': '{text}'"
            )

    assert ans2.status == "REFUSED"
    assert ans2.status != "VERIFIED"
    assert ans2.model_used is not None
    assert "fabricated_citations" in ans2.verifier
