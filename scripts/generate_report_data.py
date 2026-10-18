"""Analyze and tabulate post-fix dev results from project_context/test_runs/20261018_094404Z/"""

import json
from pathlib import Path

run_dir = Path("project_context/test_runs/20261018_094404Z")
raw_file = run_dir / "raw_responses.json"

if not raw_file.exists():
    print("Run still executing...")
    runs = list((run_dir / "runs").glob("*.json"))
    print(f"Current progress: {len(runs)}/125 runs")
else:
    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    on_runs = [d for d in data if d.get("mode") == "graph_on"]
    off_runs = [d for d in data if d.get("mode") == "graph_off" and d.get("question_id", "").startswith("Q")]
    gen_runs = [d for d in data if d.get("mode") == "graph_off" and not d.get("question_id", "").startswith("Q")]

    print(f"Total records: {len(data)} (ON: {len(on_runs)}, OFF: {len(off_runs)}, General: {len(gen_runs)})")

    # Group by question
    print("\n| Question | ON Model Correct | ON Template | ON Refused (Reason) | ON Error | OFF Correct | OFF Fab Citations |")
    print("|---|---|---|---|---|---|---|")

    dev_qids = [f"Q{i}" for i in [1, 3, 5, 7, 9, 11, 13, 14, 15, 17, 18, 19]]

    for qid in dev_qids:
        q_on = [r for r in on_runs if r.get("question_id") == qid]
        q_off = [r for r in off_runs if r.get("question_id") == qid]

        on_model_correct = 0
        on_template = 0
        on_refused = 0
        on_error = 0
        refusal_reasons = []

        for r in q_on:
            m = r.get("model_string_returned")
            status = r.get("status")
            ans = r.get("final_answer_text", "")
            is_correct = r.get("is_correct", False)

            if m == "deterministic_fallback":
                on_template += 1
            elif status == "ERROR":
                on_error += 1
            elif status == "REFUSED":
                on_refused += 1
                reason = r.get("refusal_reason") or "Verifier / ungrounded refusal"
                if reason not in refusal_reasons:
                    refusal_reasons.append(reason)
            elif is_correct and m == "deepseek/deepseek-chat":
                on_model_correct += 1

        off_correct = sum(1 for r in q_off if r.get("is_correct"))
        off_fab = sum(r.get("fabricated_citation_count", 0) for r in q_off)

        refusal_str = f"{on_refused} ({'; '.join(refusal_reasons)[:40]})" if on_refused else "0"
        print(f"| {qid:4} | {on_model_correct}/5 | {on_template}/5 | {refusal_str:30} | {on_error}/5 | {off_correct}/5 | {off_fab} |")
