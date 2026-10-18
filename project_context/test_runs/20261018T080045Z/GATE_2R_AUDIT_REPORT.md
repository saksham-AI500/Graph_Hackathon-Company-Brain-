# Gate 2R Audit and Correction Report
**Run Identifier / Timestamp (UTC):** `20261018T080045Z`  
**Evaluation Target:** RepoBrain Backend (Track 03)  
**Status:** Gate 2R Remediation Audit Complete. All claims verified by raw session outputs. Gate 3 NOT started.

---

## 1. Git Provenance and Artifact Hashes

### Git Log & Shows
- `gh auth status` active account: `saksham-AI500`
- `git log -n 10 --oneline --decorate`:
```text
d5c701e (HEAD -> main) fix(verifier): complete Gate 2R fixes 1-7 with controls, visible corrections, prompt rule, and leakage tests
4ed6b85 fix(nli): commit builder calibration dataset SHA-256 20b789d69c01e08abb150c1098d1bcdf07704ce2fed741289a8d5d1fc42d9bc9 and calibration report
75f4723 spec: update VERIFIER_SPEC.md with unit equivalence rule, threshold provenance, and visible citation correction
409cf03 fix(verifier): implement Gate 2R P2 14 adversarial tests, P4 counterfactual citation correction, and P5 zero-claim status handling
abbc792 spec: commit initial VERIFIER_SPEC.md with TUNED 0.50 NLI threshold
96c59cd docs: author Phase 7 evaluation report and document Benchmark v2 in README and PROGRESS
2975234 test: add 10 evaluation v2 tests and connect UI Benchmark tab to raw summaries
bb6e70d feat: implement Evaluation Engine v2 with frozen manifest and summary generator
1deb13b docs: author Phase 7 evaluation baseline audit and artifact inventory
75749ca docs: author Phase 6 UI verification and dashboard report
```

- `git show --stat 75f4723b`:
```text
commit 75f4723b3a1c3b5ce809bce54ee100c9cc4b0aad
Author: saksham-AI500 <saksham-AI500@example.com>
Date:   Sun Oct 18 12:56:49 2026 +0530

    spec: update VERIFIER_SPEC.md with unit equivalence rule, threshold provenance, and visible citation correction

 project_context/VERIFIER_SPEC.md | 50 ++++++++++++++++++++++++++++++----------
 1 file changed, 38 insertions(+), 12 deletions(-)
```

- `git show --stat 4ed6b858`:
```text
commit 4ed6b8581d02d9404f176c5937c63c6928776318
Author: saksham-AI500 <saksham-AI500@example.com>
Date:   Sun Oct 18 13:05:52 2026 +0530

    fix(nli): commit builder calibration dataset SHA-256 20b789d69c01e08abb150c1098d1bcdf07704ce2fed741289a8d5d1fc42d9bc9 and calibration report

 data/calibration/builder_calibration_pairs.json | 252 ++++++++++++++
 project_context/NLI_CALIBRATION.md              |  73 ++++
 scripts/calibrate_builder_pairs.py              | 426 ++++++++++++++++++++++++
 3 files changed, 751 insertions(+)
```

### Session Audit File Manifest & SHA-256 Hashes
Directory: `project_context/test_runs/20261018T080045Z/`
- `pytest_adversarial_and_leakage.log`: `91299b00faf94d2bedaf94c1e788d74fa28732e32f2a370bf60f851993e39922`
- `graph_off_acme_and_general_answers.json`: `bd68c886ad4db900c922cccf132a3f3998a663db75440fd806834228c03ba05c`
- `openrouter_model_route_audit.json`: `d1f0259babf669797dd870a8f6c7afa1e0bf796469472900c71b99ed075ecf8d`
- `builder_calibration_run.log`: `87b7ad4266a227d32f17787b4f39b8e48166a2c87954ee1e4fdb65624b2e560e`
- `MANIFEST.json`: `6599f5a7ecb9a22db34b9d5c317ad1ae02fbfa816e053f3e69fe0e5b7b919d3f`

### Explanation of Prior Report Unverified Status
In the previous report, pytest commands ran interactively in shell stdout without being piped to disk logs in `project_context/test_runs/`. The message "awaiting results" appeared because commands were launched asynchronously in powershell backgrounds. Because no persistent log files existed on disk for those specific test executions, all results in that prior report are marked **UNVERIFIED**. All numbers in this current report are backed by the on-disk hashed files above.

---

## 2. Fixture Grounding Table (B1) and Not Grounded List (B2)

### B1: Fixture Grounding Table (14 Adversarial Cases + 20 Controls)

| Test ID | Asserted / Contradicted Fact | Fixture Path & Location | Found | Verification Path |
|---|---|---|---|---|
| `adversarial_1` | ADR-0003 quote: `"must log"` (claim: `"should log"`) | `src/agent/fixture_tools.py:283` (ADR-0003 quote) | YES | PASSED BY EXACT LOOKUP |
| `adversarial_2` | PR #1 push_service: `35 additions` (claim: `50 additions`) | `data/synthetic/fixtures/pulls/1.json:30` (`files[0].additions`) | YES | PASSED BY NLI |
| `adversarial_3` | PR #1 approved by Samir Patel (claim: `not approved`) | `data/synthetic/fixtures/pulls/1.json:87-91` (`reviews[0].state`) | YES | PASSED BY NLI |
| `adversarial_4` | `payments/refunds/ @acme/legacy-settlements` (claim: `payments/`) | `data/synthetic/fixtures/codeowners.txt:10-11` | YES | PASSED BY EXACT LOOKUP |
| `adversarial_5` | Marcus Vance authored PR #145 (claim: `Gabriel Santos`) | `data/synthetic/fixtures/pulls/145.json:8` (`user.login`) | YES | PASSED BY NLI |
| `adversarial_6` | PR #1 merged `2025-10-04T09:01:35Z` (claim: `2025-10-05`) | `data/synthetic/fixtures/pulls/1.json:15` (`merged_at`) | YES | PASSED BY EXACT LOOKUP |
| `adversarial_7` | PR #85 backpressure in search_indexer (claim: Citus migration) | `data/synthetic/fixtures/pulls/85.json:5-8` (`title`) | YES | PASSED BY NLI |
| `adversarial_8` | PR #145 timeout: `5000ms` (claim: `5000 s`, 1000x error) | `data/synthetic/fixtures/pulls/145.json:6` (`body`) | YES | PASSED BY NLI |
| `adversarial_9` | `payments/ @acme/payments` (claim: `@acme/growth`) | `data/synthetic/fixtures/codeowners.txt:10` | YES | PASSED BY EXACT LOOKUP |
| `adversarial_10` | PR #1 merged `2025-10-04` (claim: `2025-10-05`) | `data/synthetic/fixtures/pulls/1.json:15` (`merged_at`) | YES | PASSED BY EXACT LOOKUP |
| `adversarial_11` | Uncited factual sentence following cited CODEOWNERS root rule | `data/synthetic/fixtures/codeowners.txt:5` | YES | PASSED BY SENTENCE CHECK |
| `adversarial_12` | PR #1 notifications refactoring (claim: Citus sharding) | `data/synthetic/fixtures/pulls/1.json:5` (`title`) | YES | PASSED BY NLI |
| `adversarial_13` | ADR-0004 quote: `"Retry policy: exponential backoff..."` (claim: `"immediate retry"`) | `src/agent/fixture_tools.py:206` (ADR-0004 quote) | YES | PASSED BY EXACT LOOKUP |
| `adversarial_14` | PR #11 search index stats (claim: timeout configuration) | `data/synthetic/fixtures/pulls/11.json:5` (`title`) | YES | PASSED BY NLI |
| `control_1` | PR #145 timeout `5000ms` -> `5 s` | `data/synthetic/fixtures/pulls/145.json:6` (`body`) | YES | PASSED BY NORMALIZATION |
| `control_2` | PR #145 timeout `5000 ms` -> `5 s` (paraphrase) | `data/synthetic/fixtures/pulls/145.json:6` (`body`) | YES | PASSED BY NORMALIZATION |
| `control_3` | PR #1 merged `2025-10-04T09:01:35Z` -> `2025-10-04` (UTC) | `data/synthetic/fixtures/pulls/1.json:15` (`merged_at`) | YES | PASSED BY EXACT LOOKUP |
| `control_4` | PR #1 merged `2025-10-04T09:01:35+00:00` -> `2025-10-04` (TZ offset) | `data/synthetic/fixtures/pulls/1.json:15` (`merged_at`) | YES | PASSED BY EXACT LOOKUP |
| `control_5` | Marcus Vance authored PR #145 | `data/synthetic/fixtures/pulls/145.json:5-8` (`user.login`) | YES | PASSED BY NLI |
| `control_6` | Tanya Popova authored PR #1 | `data/synthetic/fixtures/pulls/1.json:6-8` (`user.login`) | YES | PASSED BY NLI |
| `control_7` | Samir Patel approved PR #1 review | `data/synthetic/fixtures/pulls/1.json:87-91` (`reviews[0]`) | YES | PASSED BY NLI |
| `control_8` | Liam Chen authored PR #42 | `data/synthetic/fixtures/pulls/42.json:5-8` (`user.login`) | YES | PASSED BY NLI |
| `control_9` | Dmitri Volkov declared owner for `search/indexer/` | `data/synthetic/fixtures/codeowners.txt:17` | YES | PASSED BY EXACT LOOKUP |
| `control_10` | `@acme/payments` owns `payments/` | `data/synthetic/fixtures/codeowners.txt:10` | YES | PASSED BY EXACT LOOKUP |
| `control_11` | `@acme/platform` owns root `*` | `data/synthetic/fixtures/codeowners.txt:5` | YES | PASSED BY EXACT LOOKUP |
| `control_12` | `@acme/identity` owns `auth/` | `data/synthetic/fixtures/codeowners.txt:6` | YES | PASSED BY EXACT LOOKUP |
| `control_13` | PR #1 notifications module push service refactoring | `data/synthetic/fixtures/pulls/1.json:5` (`title`) | YES | PASSED BY NLI |
| `control_14` | PR #145 checkout database deadlocks resolution | `data/synthetic/fixtures/pulls/145.json:5` (`title`) | YES | PASSED BY NLI |
| `control_15` | PR #11 search index statistics performance | `data/synthetic/fixtures/pulls/11.json:5` (`title`) | YES | PASSED BY NLI |
| `control_16` | PR #85 search indexer backpressure handling | `data/synthetic/fixtures/pulls/85.json:5` (`title`) | YES | PASSED BY NLI |
| `control_17` | PR #10 growth referrals campaign testing | `data/synthetic/fixtures/pulls/10.json:5` (`title`) | YES | PASSED BY NLI |
| `control_18` | Issue #1 api-gateway caching bug tracking | `data/synthetic/fixtures/issues/1.json:3` (`title`) | YES | PASSED BY NLI |
| `control_19` | ADR-0004 quote: `"Retry policy: exponential backoff with jitter, max 5 attempts."` | `src/agent/fixture_tools.py:206` | YES | PASSED BY EXACT LOOKUP |
| `control_20` | ADR-0003 quote: `"All services must log structured JSON objects strictly to standard output (`stdout`)."` | `src/agent/fixture_tools.py:283` | YES | PASSED BY EXACT LOOKUP |

### B2: List of Ungrounded Cases from Prior Suite and Replacements

1. **`Dmitri Volkov's 42 commits in docs/contributors.md`**:
   - Status: **NOT GROUNDED** (file `docs/contributors.md` and commit count 42 do not exist in testbed fixtures).
   - Remediation: Replaced with real fixture ownership fact: `search/indexer/ @acme/growth dmitri-volkov` in `data/synthetic/fixtures/codeowners.txt:17` and real PR #85 (`pulls/85.json:8`).
2. **`PR #9999 merged on 2025-10-04T23:30:00-05:00`**:
   - Status: **NOT GROUNDED** (PR #9999 does not exist in `data/synthetic/fixtures/pulls/`).
   - Remediation: Replaced with real PR #1 merged_at timestamp `2025-10-04T09:01:35Z` in `data/synthetic/fixtures/pulls/1.json:15`.
3. **`PR #236 authored by Marcus Vance`**:
   - Status: **NOT GROUNDED** (author of PR #236 in `pulls/236.json` is `lucas-vogel`, not Marcus Vance).
   - Remediation: Replaced with Marcus Vance's real fixture PR #145 (`data/synthetic/fixtures/pulls/145.json:8`).
4. **`PR #305 approved by Gabriel Santos`**:
   - Status: **NOT GROUNDED** (PR #305 in `pulls/305.json` is unmerged with 0 reviews).
   - Remediation: Replaced with real fixture review: Samir Patel approving PR #1 (`data/synthetic/fixtures/pulls/1.json:87-91`).
5. **`PR #142 merged by Elena Rostova`**:
   - Status: **NOT GROUNDED** (author of PR #142 in `pulls/142.json` is `hassan-el-sayed`).
   - Remediation: Replaced with Tanya Popova authoring PR #1 (`data/synthetic/fixtures/pulls/1.json:6-8`).
6. **`docs/auth.md (1000 ms TTL)`**:
   - Status: **NOT GROUNDED** (file `docs/auth.md` does not exist in repository fixtures).
   - Remediation: Replaced with real unit-canonicalized timeout from PR #145 (`pulls/145.json:6`).
7. **`docs/webhooks.md (1024 KB)`**:
   - Status: **NOT GROUNDED** (file `docs/webhooks.md` does not exist in repository fixtures).
   - Remediation: Replaced with real unit-canonicalized timeout from PR #145 (`pulls/145.json:6`).
8. **`docs/sync.md (5 attempts)`**:
   - Status: **NOT GROUNDED** (file `docs/sync.md` does not exist in repository fixtures).
   - Remediation: Replaced with real additions in PR #1 (`pulls/1.json:30`).
9. **`ADR-002, ADR-009, ADR-004 in docs/adr/`**:
   - Status: **NOT GROUNDED** (files did not exist on disk).
   - Remediation: Grounded in real Decision fixture records in `src/agent/fixture_tools.py:206, 283`.

---

## 3. Test Results After Fixes

### Full Test Suite Execution Summary
- Command: `python -m pytest -v tests/test_verifier_adversarial.py tests/test_mode_leakage_and_status.py`
- Output Log File: `project_context/test_runs/20261018T080045Z/pytest_adversarial_and_leakage.log`
- SHA-256: `91299b00faf94d2bedaf94c1e788d74fa28732e32f2a370bf60f851993e39922`
- Result: **40 passed in 55.37s** (Exit code: 0)
- Planted Adversarial Errors Rejected: **14 / 14 (100.0%)**
- Controls Accepted: **20 / 20 (100.0%)**
- False Rejection Rate on Controls: **0 / 20 (0.0%)**

---

## 4. graph_off Raw Answers and Fabricated-Citation Counts

Log File: `project_context/test_runs/20261018T080045Z/graph_off_acme_and_general_answers.json`  
SHA-256: `bd68c886ad4db900c922cccf132a3f3998a663db75440fd806834228c03ba05c`

### Question 1 (Factual Question - Exact Original Wording)
- **Question:** `"Which team owns the payments/ module, as far as you know?"`
- **Status:** `ANSWERED_UNCERTAIN`
- **Model Used:** `deepseek/deepseek-chat`
- **Fabricated Citations:** `0`
- **Reasoning:** The term `"payments/"` appears in the user's question, so by definition D1 & D2 it is excluded from being a fabricated citation. The model makes no claims about specific people, lines, or commits, and states it does not have Acme repository records. Under E3, this is correctly marked `ANSWERED_UNCERTAIN`.
- **Raw Answer Text:**
```text
I don't have Acme's repository data, so I cannot answer which team owns the payments/ module. To determine this, I would need access to the repository's CODEOWNERS file or module ownership documentation.
```

### Question 2 (Unanswerable Question - Exact Original Wording)
- **Question:** `"Who is on call next week at Acme Platform?"`
- **Status:** `REFUSED`
- **Model Used:** `deepseek/deepseek-chat`
- **Fabricated Citations:** `0`
- **Reasoning:** On-call schedules are unanswerable operational records. The model refuses the question without asserting repository records.
- **Raw Answer Text:**
```text
I don't have Acme's repository data, so I cannot answer who is on call next week. To find this information, check the company's on-call schedule or contact the team responsible for managing it.
```
*(Note on earlier run: The earlier test used `"Who is on call next week for payments?"`, which was a different question wording.)*

### General-Knowledge Baseline Questions (Set: `data/evaluation/general_knowledge_questions.json`)
All 5 answered using general engineering knowledge with zero invented Acme records:
1. `"What does a CODEOWNERS file do?"` -> `status: ANSWERED_UNCERTAIN`, `fabricated_citations: 0`
   - *Raw Answer:* `"A CODEOWNERS file specifies who should review changes to specific files or directories in a repository. It ensures that the right people are automatically requested as reviewers when a pull request touches those areas. Context: This is a general software engineering concept, not specific to Acme's repository data..."*
2. `"What is a pull request review?"` -> `status: ANSWERED_UNCERTAIN`, `fabricated_citations: 0`
   - *Raw Answer:* `"A pull request review is a process where team members examine proposed changes to a codebase before they are merged, ensuring quality, correctness, and alignment with project goals. Context: This is a general software engineering concept, not specific to Acme Platform Inc..."*
3. `"What is an ADR?"` -> `status: ANSWERED_UNCERTAIN`, `fabricated_citations: 0`
   - *Raw Answer:* `"An ADR (Architectural Decision Record) is a document that captures a significant architectural decision made in a project, including the context, options considered, and the rationale for the chosen solution. Context: ADRs are commonly used in software engineering to provide transparency and traceability for key design choices..."*
4. `"Why use exponential backoff with jitter?"` -> `status: ANSWERED_UNCERTAIN`, `fabricated_citations: 0`
   - *Raw Answer:* `"Exponential backoff with jitter is used to prevent synchronization and reduce contention in distributed systems when retrying failed operations. It combines exponential delays with random variation to avoid thundering herd problems. Context: Exponential backoff increases the delay between retries exponentially (e.g., 1s, 2s, 4s), while jitter adds randomness to these delays..."*
5. `"What does RBAC mean?"` -> `status: ANSWERED_UNCERTAIN`, `fabricated_citations: 0`
   - *Raw Answer:* `"RBAC stands for Role-Based Access Control, a method of restricting system access to authorized users based on their roles within an organization. Context: RBAC is a widely used security model in software engineering and IT systems, applicable as of today..."*

---

## 5. Model Route Decision and OpenRouter API Evidence

Log File: `project_context/test_runs/20261018T080045Z/openrouter_model_route_audit.json`  
SHA-256: `d1f0259babf669797dd870a8f6c7afa1e0bf796469472900c71b99ed075ecf8d`

### OpenRouter API Models Query (`https://openrouter.ai/api/v1/models`)
```json
{
  "id": "deepseek/deepseek-chat",
  "canonical_slug": "deepseek/deepseek-chat-v3",
  "name": "DeepSeek: DeepSeek V3",
  "created": 1735241320,
  "supported_parameters": [
    "frequency_penalty",
    "logit_bias",
    "max_tokens",
    "min_p",
    "presence_penalty",
    "repetition_penalty",
    "response_format",
    "seed",
    "stop",
    "structured_outputs",
    "temperature",
    "tool_choice",
    "tools",
    "top_k",
    "top_p"
  ]
}
```

### Route Analysis
1. OpenRouter exposes the model under ID `deepseek/deepseek-chat` and designates `deepseek/deepseek-chat-v3` as its `canonical_slug`.
2. The model supports tool calling (`"tools"`, `"tool_choice"`, `"structured_outputs"` are in `supported_parameters`).
3. Calling the chat completions endpoint with either `deepseek/deepseek-chat` or `deepseek/deepseek-chat-v3` succeeds, and in both cases the API returns:
   - `response["model"]`: `"deepseek/deepseek-chat"`
4. Configured Route: `deepseek/deepseek-chat` (canonical endpoint ID). No mismatch between configured ID and returned model field.

---

## 6. Calibration Report (F1 to F3)

Log File: `project_context/test_runs/20261018T080045Z/builder_calibration_run.log`  
SHA-256: `87b7ad4266a227d32f17787b4f39b8e48166a2c87954ee1e4fdb65624b2e560e`  
Dataset File: `data/calibration/builder_calibration_pairs.json`  
SHA-256: `20b789d69c01e08abb150c1098d1bcdf07704ce2fed741289a8d5d1fc42d9bc9`

### F1: EER Interval
- Maximum score across all negative pairs (contradictions & hard negatives): `0.0915`
- Minimum score across all positive pairs (entailments): `0.9236`
- **Zero-Error Threshold Range (EER Interval):** `[0.0916, 0.9235]` (or `(0.0915, 0.9236)`). Any threshold within this open interval achieves zero false positives and zero false negatives on the builder set. We do NOT report "EER = 0.00%".

### F2: Threshold Status
- Dev Threshold: `0.50 (TUNED)` on 17 October dev outputs.
- Final Threshold: **NOT CHOSEN YET**. The final operating threshold will be selected only after the independent calibration pairs are received and scored.

### F3: Hard-Negative Assessment
- The builder set contains 10 hard-negative pairs (wrong number, wrong date, negation, wrong entity, wrong scope).
- Scores on hard negatives: Min = `0.0004`, Median = `0.0056`, Mean = `0.0268`, Max = `0.0915`.
- **Finding:** The builder set contains no cases in the uncertain zone (`0.10` to `0.90`). The builder set is **easy** because its hard negatives are cleanly separated by the NLI cross-encoder. Real-world edge cases must be evaluated on the independent set.

---

## 7. What Remains Open

1. **Independent Calibration Set:** Awaiting receipt of 10 pairs written by an external person. When received, the file will be committed with its SHA-256 before scoring.
2. **Holdout Evaluation File:** The holdout evaluation set has not been viewed or executed. Its SHA-256 must be committed before any holdout run.
3. **Final Threshold Selection:** The production threshold will be chosen and committed to `VERIFIER_SPEC.md` only after independent calibration scoring.
4. **Gate 3 Status:** Gate 3 is NOT started. Awaiting user review and explicit confirmation of Gate 2R.
