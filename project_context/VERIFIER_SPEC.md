# RepoBrain Verifier Specification (Part A Deliverable)

**Specification Version:** 2.0.0  
**Effective Date:** 2026-10-18T11:45:00Z  
**Primary Engine:** Dual-Path Sentence- & Claim-Level Grounding Gate  
**NLI Model:** `cross-encoder/nli-MiniLM2-L6-H768` (Quantized AVX2 ONNX)  
**NLI Runtime:** Local CPU via `onnxruntime` and HuggingFace `tokenizers` (completely independent from generative answering model `deepseek/deepseek-chat`)

---

## 1. Core Principles

Every factual assertion presented to the user must be grounded in authentic graph records or source text spans. The verifier enforces a non-negotiable gate:
1. **Sentence-Level Completeness:** The verifier parses the generated answer into discrete sentences. Every sentence making factual assertions must link to at least one valid claim with active bracketed source citations (`[S1]`, `[S2]`). Sentences lacking valid source citations cause verification failure.
2. **Dual-Path Routing:**
   - **Structured Path:** Exact attribute and relationship lookup in the graph (e.g. `OWNERSHIP`, `DECISION`, `KNOWLEDGE`, `STALENESS`, `PR_INVESTIGATION`). Quotes must be verbatim substrings. Timestamps must be valid at $T = \text{as\_of}$.
   - **Prose Path:** Local Natural Language Inference (NLI) scoring for free-text assertions from pull request bodies, comments, issues, and team chat transcripts.
3. **Span-Level Grounding:** Sources store specific character offsets (`start_offset`, `end_offset`) and `span_text`. Citations point to granular spans rather than entire files.
4. **Counterfactual Faithfulness Testing:** Sources are tested for necessity. If a claim cites multiple sources and remains fully supported when a source is removed, that source is flagged as decorative/post-hoc and counted in `post_hoc_citations`.
5. **Deterministic Refusal:** If support is weak or fails verification, unsupported claims are dropped or marked unresolved. If primary claims fail, the answer is refused.

---

## 2. Thresholds, Provenance & Unit Equivalence

### 2.1 Threshold Provenance
- **Dev Threshold**: `0.50 (TUNED)`. This threshold was empirically tuned on outputs from 17 October 2026. The 18 October commit (`abbc7923`) labeled it as TUNED; it is not a pre-registration.
- **Role**: `0.50` is retained strictly as the development threshold for intermediate gating.
- **Final Threshold**: The final operational threshold is determined from the hard calibration set (FIX 3) and committed before evaluation runs.

### 2.2 Unit Equivalence Rule
1. **Time Units**:
   - Milliseconds to seconds: $X\text{ ms} \equiv (X / 1000)\text{ s}$ (e.g. `5000 ms` $\equiv$ `5 s`, `1000 ms` $\equiv$ `1 s`, `250 ms` $\equiv$ `0.25 s`).
   - Seconds to minutes: $X\text{ s} \equiv (X / 60)\text{ min}$.
   - Minutes to hours: $X\text{ min} \equiv (X / 60)\text{ hr}$.
2. **Digital Storage Units**:
   - $1024\text{ KB} \equiv 1\text{ MB}$, $1024\text{ MB} \equiv 1\text{ GB}$.
3. **Equivalence Principle**:
   - When a source span specifies a numerical quantity with standard physical or computational units, and a claim restates that quantity in mathematically equivalent canonical units, the claim is evaluated under canonicalized units.
   - If the canonicalized value and unit match, the claim is accepted as factually entailed.
   - Non-equivalent unit modifications (e.g. source `5000 ms` vs claim `5000 s` or `50 s`) represent numerical errors and are strictly rejected.

| Parameter | Value | Rationale |
| :--- | :---: | :--- |
| **`DEV_ENTAILMENT_THRESHOLD`** | **0.50 (TUNED)** | Dev threshold tuned on 17 Oct outputs. Pinned for dev suites. |
| **`FINAL_THRESHOLD`** | *To be selected from FIX 3 calibration* | Committed alongside calibration SHA-256 before evaluation. |
| **NLI Model Checkpoint** | `cross-encoder/nli-MiniLM2-L6-H768` | Pre-trained 6-layer NLI cross-encoder for factual entailment scoring. |
| **NLI Inference Engine** | `onnxruntime` (sequential, intra_op=2) | Deterministic, offline-capable CPU inference in <15ms. |
| **Unit Equivalence** | Canonical SI / Binary Scaling | Canonicalizes equivalent units (e.g., 5000 ms $\equiv$ 5 s). |
| **Quote Matching Rule** | Exact Case-Insensitive Substring | Decision and ADR citations must match stored quotes verbatim. |
| **Temporal Check Rule** | $T_{\text{observed}} \le T_{\text{as\_of}} < T_{\text{tombstoned}}$ | Ensures historical cutoffs isolate future data leakage. |

---

## 3. Sentence-Level Verification Pipeline

```text
Answer Text (Markdown)
       │
       ▼
[Strip Markdown Code & Headers]
       │
       ▼
[Sentence Splitter (re.split)]
       │
       ▼
For each sentence:
  ├─ Check if factual (entities, actions, numbers, code paths)
  │    ├─ If non-factual (greeting, refusal disclaimer) -> Pass
  │    └─ If factual:
  │         ├─ Extract bracketed citations [S1], [S2]
  │         ├─ Map to AgentAnswer.claims
  │         └─ If no mapped claim or no citations -> FAIL (logged)
  ▼
[Sentence Verification Log] -> answer.verifier["sentence_logs"]
```

---

## 4. Counterfactual Faithfulness & Visible Citation Correction

1. **Detection of Post-Hoc / Misattributed Citations**:
   - Single-source case: If a claim cites $S_1$, and $S_1$ does not support the claim, but a different span $S_2$ elsewhere in the source set supports it:
     - The verifier emits a `citation_correction`: `{"original_source_ids": ["S1"], "corrected_source_id": "S2", "supporting_span": "..."}`.
     - The answer text visibly reflects the correction: `[S1]` is rewritten to `[S1 corrected to S2]`. Citations are never silently altered.
     - The claim is marked `post_hoc = True` and kept `VERIFIED` under the corrected citation.
     - `answer.verifier["post_hoc_citations"]` is incremented. Post-hoc citations are recorded in a separate count and are **not** counted as fully supported.
   - Multi-source case: For claim $C$ citing sources $S = \{s_1, \dots, s_k\}$ ($k > 1$), if removing $s_i$ leaves $C$ supported, $s_i$ is flagged `post_hoc = True`.
2. **Refusal on Unsupported Claims**:
   - If no span in the source set supports the claim, the claim is rejected and the answer is `REFUSED`.
3. **Citation Acceptance**:
   - If removing the only cited source leaves the claim unsupported, the citation is essential and accepted (`post_hoc = False`, `verified = True`).
4. **Evaluation Scope**:
   - The three counterfactual demonstration cases are explicitly designated as **dev fixtures**, not validation.

---

## 5. Per-Sentence Verification Log Schema

Stored in `answer.verifier["sentence_logs"]`:
```json
{
  "sentence": "The checkout timeout bug was reported in Issue #44 [S1].",
  "claim_ids": ["C1"],
  "cited_sources": ["S1"],
  "verification_path": "structured",
  "score": 1.0,
  "passed": true,
  "reason": null
}
```
If verification fails:
```json
{
  "sentence": "The database was sharded across three clusters without approval.",
  "claim_ids": [],
  "cited_sources": [],
  "verification_path": "none",
  "score": 0.0,
  "passed": false,
  "reason": "Factual sentence missing mapped verified claim or bracketed source citation."
}
```

---

## 6. Model Route Decision: Free Tier Selection

- **Date:** 2026-10-18T17:15:00Z
- **Decision:** Selected `nvidia/nemotron-3.5-lightning:free` as the active LLM provider route.
- **Evaluation Order & Findings:**
  1. `thinkingmachines/inkling:free` / `thinkingmachines/inkling-small:free`: Rejected. `tool_choice` is absent from `supported_parameters`, and direct API requests are blocked with `HTTP 403 Forbidden` (`Gate Free Endpoints by Agentic Harness`).
  2. `nvidia/nemotron-3.5-lightning:free`: **Accepted**. Fully verified on OpenRouter API:
     - `pricing.prompt = "0"`, `pricing.completion = "0"`
     - `supported_parameters` includes both `"tools"` and `"tool_choice"`
     - Live call with production payload (temperature 0.0, max_tokens 1500, full system prompt, Q1, tools on) succeeded with `HTTP 200`, cost `0`, and returned valid native function calls (`finish_reason: "tool_calls"`).
  3. `moonshotai/kimi-k2.6:free`: Not found in OpenRouter catalog with `:free` tag.
  4. `deepseek/deepseek-v4-flash:free`: Not found in OpenRouter catalog with `:free` tag.

