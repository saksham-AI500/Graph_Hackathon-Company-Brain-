"""RepoBrain — Evaluation Summary Generator.

Derives objective, auditable Markdown tables and JSON summaries directly from
immutable evaluation run artifacts under project_context/eval_v2/.
Zero hardcoded metrics: all figures trace to raw JSON outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_evaluation_summary(summary_path: str) -> Dict[str, Any]:
    """Load and validate an evaluation summary artifact."""
    p = Path(summary_path)
    if not p.exists():
        raise FileNotFoundError(f"Evaluation summary artifact not found: {summary_path}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def format_markdown_summary_table(summary_data: Dict[str, Any]) -> str:
    """Format aggregate architecture metrics as a GitHub-flavored Markdown table."""
    archs = summary_data.get("architectures", {})
    if not archs:
        return "_No architecture metrics found in summary._"

    lines = [
        "| Architecture | Total Runs | Overall Accuracy | Answerable Acc | Refusal Acc | Citation Support | Unsupported Rate | Mean Latency | Fallback Runs | Unavailable |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for arch_key, m in archs.items():
        name = arch_key.replace("_", " ").title()
        if arch_key == "graph_on":
            name = "**Graph ON (Agent)**"
        elif arch_key == "plain_retrieval":
            name = "Plain Retrieval (Vector)"
        elif arch_key == "graph_off":
            name = "Graph OFF (Model Alone)"

        tot = m.get("total_evaluations", 0)
        overall_acc = f"{m.get('overall_accuracy_pct', 0.0):.1f}% ({m.get('overall_correct', 0)}/{tot})"
        ans_tot = m.get("answerable_count", 0)
        ans_acc = f"{m.get('answerable_accuracy_pct', 0.0):.1f}% ({m.get('answerable_correct', 0)}/{ans_tot})" if ans_tot else "N/A"
        ref_tot = m.get("unanswerable_count", 0)
        ref_acc = f"{m.get('refusal_accuracy_pct', 0.0):.1f}% ({m.get('refusal_correct', 0)}/{ref_tot})" if ref_tot else "N/A"
        cit_supp = f"{m.get('citation_support_rate_pct', 0.0):.1f}%"
        unsupp_rate = f"{m.get('unsupported_claim_rate_pct', 0.0):.1f}%"
        lat = f"{m.get('mean_latency_ms', 0.0):.1f} ms"
        fallbacks = f"{m.get('fallback_runs_count', 0)}"
        unavail = f"{m.get('unavailable_runs_count', 0)}"

        lines.append(
            f"| {name} | {tot} | {overall_acc} | {ans_acc} | {ref_acc} | {cit_supp} | {unsupp_rate} | {lat} | {fallbacks} | {unavail} |"
        )

    return "\n".join(lines)


def format_question_breakdown_table(summary_data: Dict[str, Any]) -> str:
    """Format individual question pass/fail status across architectures."""
    outcomes = summary_data.get("individual_outcomes", [])
    if not outcomes:
        return "_No individual outcomes found._"

    # Group by question_id
    by_q: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for o in outcomes:
        qid = o["question_id"]
        arch = o["architecture"]
        by_q.setdefault(qid, {}).setdefault(arch, []).append(o)

    lines = [
        "| Question ID | Split | Graph ON | Plain Retrieval | Graph OFF | Details |",
        "| :--- | :---: | :---: | :---: | :---: | :--- |",
    ]

    for qid in sorted(by_q.keys()):
        archs = by_q[qid]
        split = archs.get("graph_on", [{}])[0].get("split_name", "dev")

        def _verdict_icon(arch_outcomes: List[Dict[str, Any]]) -> str:
            if not arch_outcomes:
                return "⚪ N/A"
            corr = sum(1 for x in arch_outcomes if x.get("score", {}).get("correct"))
            total = len(arch_outcomes)
            if arch_outcomes[0].get("execution_type") == "UNAVAILABLE":
                return "⚠️ UNAVAIL"
            if corr == total:
                return f"✅ PASS ({corr}/{total})"
            elif corr > 0:
                return f"🟡 PARTIAL ({corr}/{total})"
            else:
                return f"❌ FAIL (0/{total})"

        gon_icon = _verdict_icon(archs.get("graph_on", []))
        vec_icon = _verdict_icon(archs.get("plain_retrieval", []))
        goff_icon = _verdict_icon(archs.get("graph_off", []))

        notes = ""
        sample_o = archs.get("graph_on", [{}])[0]
        if sample_o.get("score", {}).get("refused"):
            notes = "Correctly Refused" if sample_o.get("score", {}).get("refusal_correct") else "False Refusal"
        elif sample_o.get("score", {}).get("valid_citation_count", 0) > 0:
            notes = f"{sample_o['score']['valid_citation_count']} Verified Sources"

        lines.append(f"| `{qid}` | {split} | {gon_icon} | {vec_icon} | {goff_icon} | {notes} |")

    return "\n".join(lines)
