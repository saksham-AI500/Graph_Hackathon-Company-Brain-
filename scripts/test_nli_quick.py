import sys
from pathlib import Path
sys.path.insert(0, ".")

from src.agent.nli_verifier import LocalNLIVerifier

nli = LocalNLIVerifier()
span = "PR #145: fix(payments): resolve checkout database deadlock under high concurrency. Author: Marcus Vance. Approved by reviewer Elena Rostova: LGTM. Changes look clean and well-structured."

test_claims = [
    "The checkout timeout bug was resolved in PR #145 by Marcus Vance.",
    "Elena Rostova approved the fix in PR #145.",
    "The fix was authored by Tanya Popova."
]

for claim in test_claims:
    ok, path, score, best = nli.verify_claim_against_spans(claim, [span])
    print(f"Claim: '{claim}' -> Supported: {ok}, Path: {path}, Score: {score}")
