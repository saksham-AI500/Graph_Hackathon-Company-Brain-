import sys
from pathlib import Path
sys.path.insert(0, ".")

from src.agent.verifier import AgentEvidenceVerifier, split_into_sentences
from src.agent.models import AgentAnswer, Claim, SourceItem

verifier = AgentEvidenceVerifier()

# Test grounded Q1 text with actual fixture facts
raw_text = """The checkout timeout bug was a high-concurrency issue in the Checkout API, resolved by optimizing database connection timeouts in PR #145.

Elena Rostova approved the fix after verifying boundary checks.

Docs in payment-pipeline-recovery.md document the incident recovery steps.

Sources:
[S1] PR #145: fix(payments): resolve checkout database deadlock, https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/145
[S2] Doc: payment-pipeline-recovery.md, https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/runbooks/payment-pipeline-recovery.md
"""

sources = [
    SourceItem(
        id="S1",
        entity_type="PullRequest",
        identifier=145,
        url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/145",
        title_or_desc="PR #145",
        span_text="PR #145: fix(payments): resolve checkout database deadlock under high concurrency. Author: Marcus Vance. Review: Approved by Elena Rostova: 'LGTM. Changes look clean and well-structured.'"
    ),
    SourceItem(
        id="S2",
        entity_type="Document",
        identifier="payment-pipeline-recovery.md",
        url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/runbooks/payment-pipeline-recovery.md",
        title_or_desc="payment-pipeline-recovery.md",
        span_text="Doc payment-pipeline-recovery.md documents checkout database deadlock recovery under high concurrency."
    ),
]

sentences = [s.strip() for s in split_into_sentences(raw_text.split("Sources:")[0]) if len(s.strip()) > 10]
claims = [
    Claim(claim_id=f"C{i+1}", text=s, claim_type="GENERAL", source_ids=["S1", "S2"])
    for i, s in enumerate(sentences)
]

ans = AgentAnswer(
    answer=raw_text,
    claims=claims,
    sources=sources,
    status="VERIFIED",
    model_used="deepseek/deepseek-chat",
)

# Test before and after logic
# Let's inspect each claim verification
for c in claims:
    is_valid, v_path, v_score, fail_reason, supp_span = verifier._verify_claim(c, {s.id: s for s in sources}, "2026-09-30T23:59:59Z")
    print(f"Claim: '{c.text}'")
    print(f"  Valid: {is_valid}, Path: {v_path}, Score: {v_score}, Fail reason: {fail_reason}\n")
