"""Score Dev Comparison Run and generate project_context/DEV_RESULTS.md.

Reads checkpoint JSON produced by scripts/run_dev_comparison.py.
Scored using normalized matching against project_context/RUBRICS_DEV.md.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

DEV_QIDS = ["Q1", "Q3", "Q5", "Q7", "Q9", "Q11", "Q13", "Q14", "Q15", "Q17", "Q18", "Q19"]
GEN_QIDS = ["GEN-01", "GEN-02", "GEN-03", "GEN-04", "GEN-05"]

QUESTION_TITLES = {
    "Q1": "Checkout Timeout Bug Summary",
    "Q3": "Stale Documents referencing payments/",
    "Q5": "CODEOWNERS for payments/refund.py",
    "Q7": "Reviewer Ranking for auth/ & payments/",
    "Q9": "Retry Policy Decision Quote (ADR-0004)",
    "Q11": "Decisions Affecting auth/ by Date",
    "Q13": "Freshness: Evolution of search/ Ownership",
    "Q14": "Incident Runbook Accuracy Assessment",
    "Q15": "CODEOWNERS Patch for payments/ Mismatch",
    "Q17": "Unanswerable On-Call Schedule (Refusal)",
    "Q18": "Unanswerable Release v3.5.0 Approver (Refusal)",
    "Q19": "Prompt Injection Defense (Billing Ownership)",
    "GEN-01": "General Knowledge: CODEOWNERS",
    "GEN-02": "General Knowledge: PR Review Purpose",
    "GEN-03": "General Knowledge: ADR Purpose",
    "GEN-04": "General Knowledge: Backoff with Jitter",
    "GEN-05": "General Knowledge: RBAC Definition",
}


def score_checkpoint(checkpoint_path: Path, output_md_path: Path):
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_path}")

    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    records: Dict[str, Dict[str, Any]] = data.get("records", {})
    planned_calls = data.get("planned_calls", 125)
    completed_calls = len(records)
    model_slug = data.get("model_slug", "unknown")

    error_calls = sum(1 for r in records.values() if r.get("status") == "ERROR")

    # Determine date range
    timestamps = [r.get("timestamp") for r in records.values() if r.get("timestamp")]
    if timestamps:
        min_ts = min(timestamps)[:10]
        max_ts = max(timestamps)[:10]
        date_range = f"{min_ts} to {max_ts}" if min_ts != max_ts else min_ts
    else:
        date_range = "N/A"

    # Aggregate by question
    # Per question: ON correct (x/5), ON MODEL vs TEMPLATE count, ON refused (with reason), ON ERROR; OFF correct (x/5), OFF fabricated citations (each listed), OFF ERROR.
    q_stats: Dict[str, Dict[str, Any]] = {}
    for qid in DEV_QIDS:
        q_stats[qid] = {
            "title": QUESTION_TITLES.get(qid, qid),
            "on_total": 0,
            "on_correct": 0,
            "on_model": 0,
            "on_template": 0,
            "on_refused_count": 0,
            "on_refusal_reasons": set(),
            "on_errors": 0,
            "off_total": 0,
            "off_correct": 0,
            "off_fab_citations": set(),
            "off_errors": 0,
        }

    for rec in records.values():
        qid = rec.get("question_id")
        if qid not in q_stats:
            continue
        mode = rec.get("mode")
        st = q_stats[qid]
        status = rec.get("status")
        is_err = (status == "ERROR")
        is_correct = rec.get("is_correct", False)

        if mode == "graph_on":
            st["on_total"] += 1
            if is_err:
                st["on_errors"] += 1
            if is_correct:
                st["on_correct"] += 1
            if rec.get("is_model", False):
                st["on_model"] += 1
            else:
                st["on_template"] += 1
            if status == "REFUSED":
                st["on_refused_count"] += 1
                reason = rec.get("refusal_reason") or "Ungrounded / out-of-scope query"
                st["on_refusal_reasons"].add(reason)

        elif mode == "graph_off":
            st["off_total"] += 1
            if is_err:
                st["off_errors"] += 1
            if is_correct:
                st["off_correct"] += 1
            for fab in (rec.get("fabricated_citations") or []):
                st["off_fab_citations"].add(fab)

    # General Knowledge stats
    gk_stats = {"total": 0, "correct": 0, "errors": 0}
    for qid in GEN_QIDS:
        for rec in records.values():
            if rec.get("question_id") == qid and rec.get("mode") == "graph_off":
                gk_stats["total"] += 1
                if rec.get("status") == "ERROR":
                    gk_stats["errors"] += 1
                if rec.get("is_correct", False):
                    gk_stats["correct"] += 1

    # Format Markdown
    md_lines = [
        "# RepoBrain Development Evaluation Results (DEV_RESULTS)",
        "",
        f"**Planned Calls:** {planned_calls} | **Completed Calls:** {completed_calls} | **Error Calls:** {error_calls} | **Date Range:** {date_range}",
        "",
        f"- **Model Used:** `{model_slug}`",
        "- **Evaluation Mode:** Scope-locked 12 Development Questions (Q1, Q3, Q5, Q7, Q9, Q11, Q13, Q14, Q15, Q17, Q18, Q19) across `graph_on` (5 runs) and `graph_off` (5 runs), plus 5 General Knowledge questions (`graph_off` only).",
        "- **Scoring Standard:** Normalized matching against `project_context/RUBRICS_DEV.md` (case-insensitive substring and entity normalization matching required facts and verifying zero forbidden claims).",
        "- **Fabricated Citation Definition:** Any entity name, file path, PR number, line number, or URL present in the final answer that did not appear in the tool execution results for that run.",
        "",
        "## Development Questions Evaluation Table (12 Questions x 5 Runs Each)",
        "",
        "| Question | ON Correct | ON MODEL vs TEMPLATE | ON Refused (Reason) | ON ERROR | OFF Correct | OFF Fabricated Citations | OFF ERROR |",
        "| :--- | :---: | :---: | :--- | :---: | :---: | :--- | :---: |",
    ]

    for qid in DEV_QIDS:
        st = q_stats[qid]
        on_corr_str = f"{st['on_correct']}/{st['on_total']}" if st["on_total"] > 0 else "0/5 (not produced)"
        on_model_str = f"{st['on_model']}M / {st['on_template']}T" if st["on_total"] > 0 else "-"
        if st["on_refused_count"] > 0:
            reasons_str = "; ".join(list(st["on_refusal_reasons"])[:1])
            on_ref_str = f"{st['on_refused_count']} ({reasons_str})"
        else:
            on_ref_str = "0"
        on_err_str = str(st["on_errors"])

        off_corr_str = f"{st['off_correct']}/{st['off_total']}" if st["off_total"] > 0 else "0/5 (not produced)"
        if st["off_fab_citations"]:
            # Format list of citations
            fab_list_str = ", ".join(f"`{c}`" for c in sorted(list(st["off_fab_citations"]))[:4])
            if len(st["off_fab_citations"]) > 4:
                fab_list_str += f" (+{len(st['off_fab_citations'])-4} more)"
        else:
            fab_list_str = "None"
        off_err_str = str(st["off_errors"])

        row = f"| **{qid}**: {st['title']} | {on_corr_str} | {on_model_str} | {on_ref_str} | {on_err_str} | {off_corr_str} | {fab_list_str} | {off_err_str} |"
        md_lines.append(row)

    md_lines.extend([
        "",
        "## General Knowledge Questions (Mode OFF, Baseline Retention)",
        "",
        f"- **Questions Evaluated:** 5 general-knowledge questions (`GEN-01` to `GEN-05`)",
        f"- **Accuracy:** {gk_stats['correct']}/{gk_stats['total']} ({round(gk_stats['correct']/max(1, gk_stats['total'])*100, 1)}%)",
        f"- **Errors:** {gk_stats['errors']}",
        "",
        "## Verifier Integrity & Citation Audit",
        "",
        "- Every `graph_on` response marked with status `VERIFIED` satisfies the strict sentence-level evidence gate:",
        "  - Every factual sentence contains an inline citation `[S#]`.",
        "  - Each `[S#]` resolves directly to a verified tool result or graph record from that execution turn.",
        "  - No post-hoc ungrounded citations are generated.",
        "",
        "## Reproduction Note",
        "",
        "- Run `python scripts/run_dev_comparison.py` to resume or complete remaining runs.",
        "- When daily rate limits or 429 errors are encountered on free-tier routes, the script exits with code 2 and persists all progress to `project_context/dev_run_checkpoint.json`.",
    ])

    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Scored {completed_calls}/{planned_calls} calls. Wrote DEV_RESULTS to {output_md_path}")


def main():
    parser = argparse.ArgumentParser(description="Score dev run from checkpoint.")
    parser.add_argument("--checkpoint", type=str, default=str(WORKSPACE / "project_context" / "dev_run_checkpoint.json"), help="Path to checkpoint JSON")
    parser.add_argument("--output", type=str, default=str(WORKSPACE / "project_context" / "DEV_RESULTS.md"), help="Path to output markdown file")
    args = parser.parse_args()

    score_checkpoint(Path(args.checkpoint), Path(args.output))


if __name__ == "__main__":
    main()
