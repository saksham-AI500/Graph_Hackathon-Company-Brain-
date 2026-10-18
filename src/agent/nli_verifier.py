"""Local NLI (Natural Language Inference) verifier for RepoBrain.

Uses a local cross-encoder ONNX model (cross-encoder/nli-MiniLM2-L6-H768)
completely independent of the generative answering model (DeepSeek)
to compute factual entailment scores between source evidence spans and prose claims.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Predefined entailment decision threshold
ENTAILMENT_THRESHOLD = 0.50
MODEL_REPO_ID = "cross-encoder/nli-MiniLM2-L6-H768"
MODEL_FILENAME = "onnx/model_quint8_avx2.onnx"
TOKENIZER_FILENAME = "tokenizer.json"


def canonicalize_units(text: str) -> str:
    """Normalize physical and computational units into canonical representations (e.g. 5000 ms -> 5 s)."""
    def ms_to_s(m):
        val = float(m.group(1))
        s_val = val / 1000.0
        return f"{s_val:g} s"

    def kb_to_mb(m):
        val = float(m.group(1))
        mb_val = val / 1024.0
        return f"{mb_val:g} MB"

    norm = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:ms|milliseconds)\b", ms_to_s, text, flags=re.I)
    norm = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:kb|kilobytes)\b", kb_to_mb, norm, flags=re.I)
    norm = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:seconds|sec)\b", r"\1 s", norm, flags=re.I)
    return norm


class LocalNLIVerifier:
    """Local, deterministic NLI scorer using ONNX runtime."""

    def __init__(
        self,
        threshold: float = ENTAILMENT_THRESHOLD,
        model_repo: str = MODEL_REPO_ID,
    ):
        self.threshold = threshold
        self.model_repo = model_repo
        self._session = None
        self._tokenizer = None
        self._initialized = False

    def _lazy_init(self) -> bool:
        if self._initialized:
            return True
        try:
            from huggingface_hub import hf_hub_download
            import onnxruntime as ort
            from tokenizers import Tokenizer

            tok_path = hf_hub_download(repo_id=self.model_repo, filename=TOKENIZER_FILENAME)
            model_path = hf_hub_download(repo_id=self.model_repo, filename=MODEL_FILENAME)

            self._tokenizer = Tokenizer.from_file(tok_path)
            self._tokenizer.enable_padding()
            self._tokenizer.enable_truncation(max_length=512)

            # Restrict threads to keep CPU execution light
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 1
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

            self._session = ort.InferenceSession(model_path, sess_options=opts)
            self._input_names = [i.name for i in self._session.get_inputs()]
            try:
                import json
                cfg_path = hf_hub_download(repo_id=self.model_repo, filename="config.json")
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                id2label = {int(k): v.lower() for k, v in cfg.get("id2label", {}).items()}
                self._entailment_idx = next((k for k, v in id2label.items() if "entail" in v), 1)
            except Exception:
                self._entailment_idx = 1
            self._initialized = True
            logger.info("Initialized LocalNLIVerifier with model %s (entailment idx=%s)", self.model_repo, self._entailment_idx)
            return True
        except Exception as exc:
            logger.warning("Could not initialize ONNX NLI model (%s): %s", self.model_repo, exc)
            self._initialized = False
            return False

    def score_entailment(self, premise: str, hypothesis: str) -> float:
        """Compute the entailment probability P(Entailment | Premise, Hypothesis).

        Returns:
            float in [0.0, 1.0] representing entailment confidence.
        """
        clean_premise = premise.strip()
        clean_hypo = hypothesis.strip()
        if not clean_premise or not clean_hypo:
            return 0.0

        # Exact substring or identity check shortcuts
        if clean_hypo.lower() in clean_premise.lower():
            return 0.99

        # Unit-canonicalized equivalence shortcut
        canon_premise = canonicalize_units(clean_premise)
        canon_hypo = canonicalize_units(clean_hypo)
        if canon_hypo.lower() in canon_premise.lower():
            return 0.99

        if not self._lazy_init():
            # Calibrated fallback if ONNX unavailable: token overlap Jaccard
            p_tokens = set(re.findall(r"\w+", canon_premise.lower()))
            h_tokens = set(re.findall(r"\w+", canon_hypo.lower()))
            if not h_tokens:
                return 0.0
            overlap = len(h_tokens & p_tokens) / len(h_tokens)
            return round(min(1.0, overlap * 0.9), 3)

        try:
            enc = self._tokenizer.encode(canon_premise, canon_hypo)
            inputs = {
                "input_ids": np.array([enc.ids], dtype=np.int64),
                "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
            }
            if "token_type_ids" in self._input_names:
                inputs["token_type_ids"] = np.array([enc.type_ids], dtype=np.int64)

            logits = self._session.run(None, inputs)[0][0]
            exp_logits = np.exp(logits - np.max(logits))
            probs = exp_logits / exp_logits.sum()
            idx = getattr(self, "_entailment_idx", 1)
            entailment_prob = float(probs[idx]) if idx < len(probs) else float(probs[-1])
            return round(entailment_prob, 4)
        except Exception as exc:
            logger.debug("Inference error in score_entailment: %s", exc)
            return 0.0

    def verify_claim_against_spans(
        self,
        claim_text: str,
        spans: List[str],
    ) -> Tuple[bool, float, Optional[str]]:
        """Verify whether at least one source span entails the claim above threshold.

        Returns:
            Tuple of (is_supported, max_score, best_supporting_span)
        """
        if not spans:
            return False, 0.0, None

        best_score = 0.0
        best_span = None

        for span in spans:
            score = self.score_entailment(premise=span, hypothesis=claim_text)
            if score > best_score:
                best_score = score
                best_span = span

        is_supported = best_score >= self.threshold
        return is_supported, best_score, (best_span if is_supported else None)


# Default singleton instance
_DEFAULT_NLI_VERIFIER: Optional[LocalNLIVerifier] = None


def get_default_nli_verifier() -> LocalNLIVerifier:
    global _DEFAULT_NLI_VERIFIER
    if _DEFAULT_NLI_VERIFIER is None:
        _DEFAULT_NLI_VERIFIER = LocalNLIVerifier()
    return _DEFAULT_NLI_VERIFIER
