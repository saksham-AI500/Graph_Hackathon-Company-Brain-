# Status: INVALID

## Reason
This run is marked INVALID because:
1. Provider in-flight budget errors (HTTP 402) resulted in widespread silent fallbacks to deterministic templates (`deterministic_fallback`) in 24 of 60 ON runs.
2. The remaining 36 ON runs were incorrectly refused by verifier bugs (sentence-level parser mismatch and backtick entity deletion).
3. Evaluated rubrics contained ungrounded PR #237 fact in Q11.
