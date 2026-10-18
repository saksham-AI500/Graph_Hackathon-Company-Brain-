"""Tests for P5: graph_off fairness, status, and mode/architecture leakage.

Ensures:
1. The answer text does not leak mode or architecture terms:
   Fails if the answer text contains "graph_off", "graph_on", "mode", or "tools".
2. A zero-claim answer NEVER gets status VERIFIED.
   Uses ANSWERED_UNCERTAIN for answers with stated uncertainty.
   Uses REFUSED for refusals.
   Uses VERIFIED only when all claims pass.
3. System prompt parity: Prompt strings for graph_on and graph_off are identical.
4. Model string is recorded on answer object.
"""

import pytest
from src.agent.loop import AgentExecutionLoop, AgentRequest
from src.agent.models import AgentAnswer, Claim, SourceItem
from src.agent.prompt import build_agent_system_prompt
from src.agent.verifier import AgentEvidenceVerifier


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


def test_graph_off_answers_free_of_mode_and_architecture_leakage():
    """Verify that graph_off answers contain no mode or architecture leakage."""
    loop = AgentExecutionLoop()

    # Question 1: Factual question in graph_off
    req1 = AgentRequest(
        question="Which team owns the payments/ module?",
        mode="graph_off",
    )
    ans1 = loop.run(req1)
    text1_lower = ans1.answer.lower()
    for forbidden in ["graph_off", "graph_on", "mode", "tools"]:
        assert forbidden not in text1_lower, f"graph_off answer 1 leaks forbidden token '{forbidden}': {ans1.answer}"
    assert ans1.status in ("ANSWERED_UNCERTAIN", "REFUSED")
    assert ans1.status != "VERIFIED"
    assert ans1.model_used is not None

    # Question 2: Unanswerable private operational question in graph_off
    req2 = AgentRequest(
        question="Who is on call next week for payments?",
        mode="graph_off",
    )
    ans2 = loop.run(req2)
    text2_lower = ans2.answer.lower()
    for forbidden in ["graph_off", "graph_on", "mode", "tools"]:
        assert forbidden not in text2_lower, f"graph_off answer 2 leaks forbidden token '{forbidden}': {ans2.answer}"
    assert ans2.status == "REFUSED"
    assert ans2.status != "VERIFIED"
    assert ans2.model_used is not None
