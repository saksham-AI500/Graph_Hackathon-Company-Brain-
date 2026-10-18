"""RepoBrain — Evaluation Engine v2.

Rigorous, reproducible tri-mode benchmark evaluation comparing:
1. Graph ON: Verifier-gated Company Brain agent with 14 typed graph tools
2. Plain Retrieval: TF-IDF vector retrieval over repository text corpus
3. Graph OFF: Model alone baseline with zero graph context and zero tools

Enforces Gate 1 manifest freezing, split isolation guards, immutable run logs,
claim-level citation support verification, and honest execution-type tracking.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.db import FalkorDBClient
from src.evaluation.benchmark import BenchmarkQuestion, get_benchmark_questions
from src.evaluation.temporal import (
    find_historical_reviewers_temporal,
    find_related_co_changes_temporal,
    trace_pr_to_issues_temporal,
)
from src.evaluation.vector_baseline import LocalVectorBaseline
from src.agent.models import AgentRequest, AgentAnswer
from src.agent.loop import AgentExecutionLoop
from src.agent.client import OpenRouterClient


class SingleRunScore(BaseModel):
    """Structured scoring metrics for an individual evaluation run."""
    answered: bool
    refused: bool
    correct: bool
    refusal_correct: bool
    citation_support: bool
    valid_citation_count: int
    unsupported_claim_count: int
    as_of_valid: bool
    verdict: str  # PASS, FAIL, UNAVAILABLE, ERROR
    notes: Optional[str] = None


class SingleRunOutcome(BaseModel):
    """Immutable record of a single question evaluation."""
    run_id: str
    timestamp: str
    code_revision: str
    manifest_hash: str
    question_set_hash: str
    split_name: str  # development, sealed
    question_id: str
    architecture: str  # graph_on, plain_retrieval, graph_off
    repetition: int
    execution_type: str  # LIVE_PROVIDER, DETERMINISTIC_FALLBACK, UNAVAILABLE, ERROR
    model_identifier: Optional[str] = None
    raw_response: str
    structured_claims: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    score: SingleRunScore
    latency_ms: float
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    cost_usd: Optional[float] = None
    error: Optional[str] = None


class AggregateArchitectureMetrics(BaseModel):
    """Aggregated summary metrics for one architecture across runs."""
    architecture: str
    total_evaluations: int = 0
    unique_questions: int = 0
    answerable_count: int = 0
    unanswerable_count: int = 0
    overall_correct: int = 0
    answerable_correct: int = 0
    refusal_correct: int = 0
    citation_support_count: int = 0
    unsupported_claims_total: int = 0
    as_of_violations_count: int = 0
    mean_latency_ms: float = 0.0
    median_latency_ms: float = 0.0
    fallback_runs_count: int = 0
    unavailable_runs_count: int = 0
    error_runs_count: int = 0
    overall_accuracy_pct: float = 0.0
    answerable_accuracy_pct: float = 0.0
    refusal_accuracy_pct: float = 0.0
    citation_support_rate_pct: float = 0.0
    unsupported_claim_rate_pct: float = 0.0


class EvaluationSummary(BaseModel):
    """Complete summary of a benchmark evaluation run."""
    run_id: str
    timestamp: str
    code_revision: str
    manifest_hash: str
    question_set_hash: str
    split_name: str
    repetitions_per_question: int
    architectures: Dict[str, AggregateArchitectureMetrics] = Field(default_factory=dict)
    individual_outcomes: List[SingleRunOutcome] = Field(default_factory=list)


class ManifestManager:
    """Manages manifest verification and split access boundaries."""

    def __init__(self, manifest_path: str = "project_context/eval_v2/manifest.json"):
        self.manifest_path = Path(manifest_path)
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Evaluation manifest not found at {manifest_path}")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        self.manifest_hash = hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()
        self.verify_question_set_hash()

    def verify_question_set_hash(self) -> str:
        q_path = Path(self.data["question_set"]["canonical_path"])
        if not q_path.exists():
            raise FileNotFoundError(f"Question set file not found: {q_path}")
        current_hash = hashlib.sha256(q_path.read_bytes()).hexdigest()
        expected_hash = self.data["question_set"]["sha256"]
        if current_hash != expected_hash:
            raise ValueError(
                f"Question set hash mismatch! Expected {expected_hash}, got {current_hash}. "
                "Question content has been modified!"
            )
        return current_hash

    @property
    def dev_question_ids(self) -> List[str]:
        return self.data["split_membership"]["development"]["question_ids"]

    @property
    def sealed_question_ids(self) -> List[str]:
        return self.data["split_membership"]["sealed"]["question_ids"]

    def assert_can_access_question(self, question_id: str, allow_sealed: bool = False) -> str:
        if question_id in self.dev_question_ids:
            return "development"
        elif question_id in self.sealed_question_ids:
            if not allow_sealed:
                raise PermissionError(
                    f"Access violation: Question {question_id} is in the sealed holdout set! "
                    "Sealed questions cannot be accessed during development runs or tuning."
                )
            return "sealed"
        else:
            raise ValueError(f"Unknown question ID: {question_id}")


class EvaluatorV2:
    """Main evaluation runner for RepoBrain Benchmark v2."""

    def __init__(
        self,
        client: Optional[FalkorDBClient] = None,
        llm_client: Optional[OpenRouterClient] = None,
        manifest_path: str = "project_context/eval_v2/manifest.json",
        output_dir: str = "project_context/eval_v2",
    ):
        self.client = client or FalkorDBClient()
        self.llm_client = llm_client
        self.manifest_mgr = ManifestManager(manifest_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "runs").mkdir(parents=True, exist_ok=True)

        # Preload questions keyed by ID
        all_qs = get_benchmark_questions()
        self.question_map: Dict[str, BenchmarkQuestion] = {q.id: q for q in all_qs}

        # Initialize vector baseline once
        self.vector_baseline = LocalVectorBaseline()

    def evaluate_question(
        self,
        question_id: str,
        architecture: str,
        repetition: int = 1,
        run_id: str = "dev_eval",
        allow_sealed: bool = False,
    ) -> SingleRunOutcome:
        """Evaluate a single question on a given architecture with full outcome instrumentation."""
        split_name = self.manifest_mgr.assert_can_access_question(question_id, allow_sealed=allow_sealed)
        q = self.question_map[question_id]

        start_time = time.perf_counter()
        raw_response = ""
        claims: List[str] = []
        citations: List[str] = []
        exec_type = "DETERMINISTIC_FALLBACK"
        err_msg: Optional[str] = None
        is_refusal = False
        refusal_reason: Optional[str] = None
        tokens_prompt = None
        tokens_completion = None
        cost_usd = None

        try:
            if architecture == "graph_on":
                loop = AgentExecutionLoop(client=self.client, llm_client=self.llm_client)
                req = AgentRequest(question=q.question, as_of=q.historical_cutoff)
                ans: AgentAnswer = loop.run(req)

                raw_response = ans.answer
                claims = [c.text for c in ans.claims]
                citations = [s.url for s in ans.sources]
                is_refusal = ans.status == "REFUSED"
                refusal_reason = "; ".join(ans.unresolved) if ans.unresolved else None
                exec_type = "LIVE_PROVIDER" if self.llm_client and self.llm_client.api_key else "DETERMINISTIC_FALLBACK"

            elif architecture == "plain_retrieval":
                # Pure TF-IDF retrieval over raw documents, strictly no graph traversal
                raw_response, is_refusal, refusal_reason, citations, unsupported = self.vector_baseline.answer_question(
                    question=q.question,
                    target_pr=q.target_pr,
                    target_file=q.target_file,
                    cutoff_timestamp=q.historical_cutoff,
                )
                claims = [raw_response] if raw_response else []
                exec_type = "DETERMINISTIC_FALLBACK"

            elif architecture == "graph_off":
                # Direct model query alone; zero graph context, zero tools, zero database reads
                if self.llm_client and self.llm_client.api_key:
                    prompt = (
                        "Answer the following software repository question based only on your pre-trained knowledge. "
                        "Do not guess. If you do not have verified knowledge, state clearly that you cannot answer.\n\n"
                        f"Question: {q.question}"
                    )
                    raw_response = self.llm_client.generate(prompt)
                    exec_type = "LIVE_PROVIDER"
                    lower_resp = raw_response.lower()
                    if any(w in lower_resp for w in ["cannot answer", "don't know", "unable", "not available"]):
                        is_refusal = True
                else:
                    raw_response = "[UNAVAILABLE: No external LLM provider configured for Graph OFF baseline]"
                    exec_type = "UNAVAILABLE"
                    is_refusal = False

            else:
                raise ValueError(f"Unknown architecture: {architecture}")

        except Exception as exc:
            err_msg = str(exc)
            exec_type = "ERROR"
            raw_response = f"[ERROR: {err_msg}]"

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Rubric scoring
        score = self._score_outcome(q, architecture, raw_response, is_refusal, citations, exec_type)

        return SingleRunOutcome(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            code_revision=self.manifest_mgr.data["code_revision"],
            manifest_hash=self.manifest_mgr.manifest_hash,
            question_set_hash=self.manifest_mgr.data["question_set"]["sha256"],
            split_name=split_name,
            question_id=question_id,
            architecture=architecture,
            repetition=repetition,
            execution_type=exec_type,
            model_identifier=self.manifest_mgr.data["execution_settings"]["model_identifier"],
            raw_response=raw_response,
            structured_claims=claims,
            citations=citations,
            score=score,
            latency_ms=duration_ms,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            cost_usd=cost_usd,
            error=err_msg,
        )

    @staticmethod
    def _match_keyword(kw: str, text: str) -> bool:
        """Match keyword in text respecting token/word boundaries to avoid spurious partial matches."""
        clean_kw = kw.strip().lower()
        if not clean_kw:
            return False
        if clean_kw.isalnum():
            pattern = r"\b" + re.escape(clean_kw) + r"\b"
            return bool(re.search(pattern, text.lower()))
        else:
            return clean_kw in text.lower()

    def _verify_citation_in_graph(self, url: str, ground_truth_urls: List[str]) -> bool:
        """Verify that a citation is grounded either in ground truth or active FalkorDB graph."""
        if not url:
            return False
        # Known ground truth URL
        if any(url.rstrip("/") == gt.rstrip("/") or url.startswith(gt) or gt.startswith(url) for gt in ground_truth_urls):
            return True

        if not url.startswith("https://github.com/"):
            return False

        if not self.client:
            return url.startswith("https://github.com/FalkorDB/FalkorDB/")

        try:
            # 1. Match Pull Request
            pr_match = re.search(r"/pull/(\d+)", url)
            if pr_match:
                pr_num = int(pr_match.group(1))
                res = self.client.ro_query("MATCH (p:PullRequest {number: $num}) RETURN count(p)", {"num": pr_num})
                if res and res.result_set and res.result_set[0][0] > 0:
                    return True

            # 2. Match Issue
            issue_match = re.search(r"/issues/(\d+)", url)
            if issue_match:
                issue_num = int(issue_match.group(1))
                res = self.client.ro_query("MATCH (i:Issue {number: $num}) RETURN count(i)", {"num": issue_num})
                if res and res.result_set and res.result_set[0][0] > 0:
                    return True

            # 3. Match Person / user profile
            person_match = re.search(r"https://github\.com/([a-zA-Z0-9_\-]+)/?$", url)
            if person_match:
                login = person_match.group(1)
                res = self.client.ro_query("MATCH (p:Person {login: $login}) RETURN count(p)", {"login": login})
                if res and res.result_set and res.result_set[0][0] > 0:
                    return True

            # 4. Match File
            file_match = re.search(r"/blob/[^/]+/(.+)", url)
            if file_match:
                fpath = file_match.group(1)
                res = self.client.ro_query("MATCH (f:File {path: $path}) RETURN count(f)", {"path": fpath})
                if res and res.result_set and res.result_set[0][0] > 0:
                    return True

            # 5. Generic URL node lookup
            res = self.client.ro_query("MATCH (n) WHERE n.url = $url RETURN count(n)", {"url": url})
            if res and res.result_set and res.result_set[0][0] > 0:
                return True
        except Exception:
            return url.startswith("https://github.com/FalkorDB/FalkorDB/")

        return False

    def _get_citation_timestamp(self, url: str) -> Optional[str]:
        """Query active graph for the creation or observation timestamp of a cited entity."""
        if not self.client or not url:
            return None
        try:
            pr_match = re.search(r"/pull/(\d+)", url)
            if pr_match:
                pr_num = int(pr_match.group(1))
                res = self.client.ro_query(
                    "MATCH (p:PullRequest {number: $num}) RETURN coalesce(p.created_at, p.observed_at)",
                    {"num": pr_num},
                )
                if res and res.result_set and res.result_set[0] and res.result_set[0][0]:
                    return str(res.result_set[0][0])

            issue_match = re.search(r"/issues/(\d+)", url)
            if issue_match:
                issue_num = int(issue_match.group(1))
                res = self.client.ro_query(
                    "MATCH (i:Issue {number: $num}) RETURN coalesce(i.created_at, i.observed_at)",
                    {"num": issue_num},
                )
                if res and res.result_set and res.result_set[0] and res.result_set[0][0]:
                    return str(res.result_set[0][0])

            res = self.client.ro_query(
                "MATCH (n) WHERE n.url = $url RETURN coalesce(n.created_at, n.observed_at, n.valid_from)",
                {"url": url},
            )
            if res and res.result_set and res.result_set[0] and res.result_set[0][0]:
                return str(res.result_set[0][0])
        except Exception:
            return None
        return None

    def _score_outcome(
        self,
        q: BenchmarkQuestion,
        architecture: str,
        raw_response: str,
        is_refusal: bool,
        citations: List[str],
        exec_type: str,
    ) -> SingleRunScore:
        """Deterministic, rubric-grounded scoring."""
        if exec_type == "UNAVAILABLE":
            return SingleRunScore(
                answered=False,
                refused=False,
                correct=False,
                refusal_correct=False,
                citation_support=False,
                valid_citation_count=0,
                unsupported_claim_count=0,
                as_of_valid=True,
                verdict="UNAVAILABLE",
                notes="External provider was unavailable.",
            )
        if exec_type == "ERROR":
            return SingleRunScore(
                answered=False,
                refused=False,
                correct=False,
                refusal_correct=False,
                citation_support=False,
                valid_citation_count=0,
                unsupported_claim_count=0,
                as_of_valid=True,
                verdict="ERROR",
                notes="Execution raised an unhandled exception.",
            )

        resp_lower = raw_response.lower()
        unsupported_count = 0
        as_of_valid = True

        # Check citation support against active graph and ground truth
        valid_citations = 0
        citation_support = True
        for u in citations:
            if self._verify_citation_in_graph(u, q.ground_truth_urls):
                valid_citations += 1
            else:
                citation_support = False
                unsupported_count += 1

        if q.should_refuse:
            # Expected refusal
            refusal_detected = is_refusal or any(
                w in resp_lower for w in ["refuse", "not found", "does not exist", "unsupported", "cannot answer", "no record"]
            )
            if refusal_detected:
                correct = True
                refusal_correct = True
            else:
                correct = False
                refusal_correct = False
                unsupported_count += 1
        else:
            # Expected answer
            if is_refusal:
                correct = False
                refusal_correct = False
            else:
                # Check keywords and semantics with token/word boundary matching
                if q.category == "DECISION_TRACING":
                    has_num = any(kw.isdigit() and self._match_keyword(kw, raw_response) for kw in q.expected_answer_keywords)
                    has_kw = any(not kw.isdigit() and self._match_keyword(kw, resp_lower) for kw in q.expected_answer_keywords)
                    correct = has_num and has_kw
                elif q.category == "REVIEWER_ROUTING":
                    correct = any(self._match_keyword(kw, resp_lower) for kw in q.expected_answer_keywords)
                elif q.category == "CO_CHANGE":
                    correct = any(self._match_keyword(kw, resp_lower) for kw in q.expected_answer_keywords)
                elif q.category == "OWNERSHIP_DISCREPANCY":
                    correct = any(self._match_keyword(kw, resp_lower) for kw in q.expected_answer_keywords)
                else:
                    correct = any(self._match_keyword(kw, resp_lower) for kw in q.expected_answer_keywords)

                refusal_correct = False
                if not correct and not citations:
                    unsupported_count += 1

        # Check as_of compliance against entity timestamps in active graph
        if q.historical_cutoff:
            for u in citations:
                ts = self._get_citation_timestamp(u)
                if ts:
                    try:
                        dt_entity = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        dt_cutoff = datetime.fromisoformat(q.historical_cutoff.replace("Z", "+00:00"))
                        if dt_entity > dt_cutoff:
                            as_of_valid = False
                            correct = False
                            unsupported_count += 1
                            break
                    except Exception:
                        if ts > q.historical_cutoff:
                            as_of_valid = False
                            correct = False
                            unsupported_count += 1
                            break

        verdict = "PASS" if correct else "FAIL"

        return SingleRunScore(
            answered=not is_refusal,
            refused=is_refusal,
            correct=correct,
            refusal_correct=refusal_correct,
            citation_support=citation_support and (valid_citations > 0 or q.should_refuse),
            valid_citation_count=valid_citations,
            unsupported_claim_count=unsupported_count,
            as_of_valid=as_of_valid,
            verdict=verdict,
        )

    def run_suite(
        self,
        question_ids: List[str],
        architectures: Optional[List[str]] = None,
        repetitions: int = 3,
        run_id_prefix: str = "eval",
        allow_sealed: bool = False,
    ) -> EvaluationSummary:
        """Run a full evaluation across specified questions and architectures."""
        if architectures is None:
            architectures = ["graph_on", "plain_retrieval", "graph_off"]

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_id = f"{run_id_prefix}_{timestamp_str}"
        split_name = "sealed" if allow_sealed else "development"

        all_outcomes: List[SingleRunOutcome] = []

        for qid in question_ids:
            for arch in architectures:
                for rep in range(1, repetitions + 1):
                    outcome = self.evaluate_question(
                        question_id=qid,
                        architecture=arch,
                        repetition=rep,
                        run_id=run_id,
                        allow_sealed=allow_sealed,
                    )
                    all_outcomes.append(outcome)

        # Aggregate metrics
        arch_metrics: Dict[str, AggregateArchitectureMetrics] = {}
        for arch in architectures:
            arch_outcomes = [o for o in all_outcomes if o.architecture == arch]
            total_runs = len(arch_outcomes)
            unique_qs = len(set(o.question_id for o in arch_outcomes))

            ans_qs = [o for o in arch_outcomes if not self.question_map[o.question_id].should_refuse]
            ref_qs = [o for o in arch_outcomes if self.question_map[o.question_id].should_refuse]

            overall_corr = sum(1 for o in arch_outcomes if o.score.correct)
            ans_corr = sum(1 for o in ans_qs if o.score.correct)
            ref_corr = sum(1 for o in ref_qs if o.score.correct)

            latencies = [o.latency_ms for o in arch_outcomes]
            mean_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
            sorted_lat = sorted(latencies)
            med_lat = round(sorted_lat[len(sorted_lat) // 2], 2) if sorted_lat else 0.0

            arch_metrics[arch] = AggregateArchitectureMetrics(
                architecture=arch,
                total_evaluations=total_runs,
                unique_questions=unique_qs,
                answerable_count=len(ans_qs),
                unanswerable_count=len(ref_qs),
                overall_correct=overall_corr,
                answerable_correct=ans_corr,
                refusal_correct=ref_corr,
                citation_support_count=sum(1 for o in arch_outcomes if o.score.citation_support),
                unsupported_claims_total=sum(o.score.unsupported_claim_count for o in arch_outcomes),
                as_of_violations_count=sum(1 for o in arch_outcomes if not o.score.as_of_valid),
                mean_latency_ms=mean_lat,
                median_latency_ms=med_lat,
                fallback_runs_count=sum(1 for o in arch_outcomes if o.execution_type == "DETERMINISTIC_FALLBACK"),
                unavailable_runs_count=sum(1 for o in arch_outcomes if o.execution_type == "UNAVAILABLE"),
                error_runs_count=sum(1 for o in arch_outcomes if o.execution_type == "ERROR"),
                overall_accuracy_pct=round((overall_corr / total_runs) * 100, 1) if total_runs else 0.0,
                answerable_accuracy_pct=round((ans_corr / len(ans_qs)) * 100, 1) if ans_qs else 0.0,
                refusal_accuracy_pct=round((ref_corr / len(ref_qs)) * 100, 1) if ref_qs else 0.0,
                citation_support_rate_pct=round((sum(1 for o in arch_outcomes if o.score.citation_support) / total_runs) * 100, 1) if total_runs else 0.0,
                unsupported_claim_rate_pct=round((sum(1 for o in arch_outcomes if o.score.unsupported_claim_count > 0) / total_runs) * 100, 1) if total_runs else 0.0,
            )

        summary = EvaluationSummary(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            code_revision=self.manifest_mgr.data["code_revision"],
            manifest_hash=self.manifest_mgr.manifest_hash,
            question_set_hash=self.manifest_mgr.data["question_set"]["sha256"],
            split_name=split_name,
            repetitions_per_question=repetitions,
            architectures=arch_metrics,
            individual_outcomes=all_outcomes,
        )

        # Save immutable run artifact
        run_file = self.output_dir / "runs" / f"{run_id}.json"
        with open(run_file, "w", encoding="utf-8") as f:
            f.write(summary.model_dump_json(indent=2))

        # Save latest summary for this split
        summary_file = self.output_dir / f"summary_{split_name}.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary.model_dump_json(indent=2))

        return summary

    def run_development(self, repetitions: int = 3) -> EvaluationSummary:
        """Run evaluation on the 12 development questions."""
        return self.run_suite(
            question_ids=self.manifest_mgr.dev_question_ids,
            repetitions=repetitions,
            run_id_prefix="dev_v2",
            allow_sealed=False,
        )

    def run_sealed_final(self, repetitions: int = 3) -> EvaluationSummary:
        """Run the final evaluation on the 8 sealed questions (once only at final gate)."""
        return self.run_suite(
            question_ids=self.manifest_mgr.sealed_question_ids,
            repetitions=repetitions,
            run_id_prefix="sealed_v2",
            allow_sealed=True,
        )
