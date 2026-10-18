# Status: INVALID

## Reason
This run is marked INVALID because:
1. OpenRouter HTTP 402 `in_flight_budget_exhausted` occurred on almost all calls due to concurrency limits on the key without an extended cooldown, resulting in 59/60 ON runs exiting with ERROR.
2. The CODEOWNERS pattern matching bug (matching `payments/refunds/` rule for `payments/refund.py` instead of exact directory prefix rule `payments/`) was active during this run.
3. Sentence-level verifier relaxation was tested rather than the strict inline citation requirement.
