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

## 2. Thresholds & Operational Parameters

| Parameter | Value | Rationale |
| :--- | :---: | :--- |
| **`ENTAILMENT_THRESHOLD`** | **0.50 (TUNED)** | Calibrated probability threshold $P(\text{Entailment} \mid \text{Span}, \text{Claim})$. Labeled TUNED (established after prior evaluation outputs). Final threshold to be pinned against independent 40-pair hard calibration set. |
| **NLI Model Checkpoint** | `cross-encoder/nli-MiniLM2-L6-H768` | Pre-trained 6-layer NLI cross-encoder optimized for factual entailment scoring. |
| **NLI Inference Engine** | `onnxruntime` (sequential, intra_op=2) | Deterministic, offline-capable CPU inference in <15ms without GPU or PyTorch overhead. |
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

## 4. Counterfactual Faithfulness Algorithm

For any claim $C$ citing sources $S = \{s_1, s_2, \dots, s_k\}$ where $k > 1$:
1. For each $s_i \in S$:
   - Construct reduced source set $S' = S \setminus \{s_i\}$.
   - Re-evaluate verification of claim $C$ using only $S'$.
   - If $C$ is still fully supported by $S'$, then $s_i$ is non-essential (decorative citation).
   - Flag $s_i$ as `post_hoc = True` and increment `answer.verifier["post_hoc_citations"]`.

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
