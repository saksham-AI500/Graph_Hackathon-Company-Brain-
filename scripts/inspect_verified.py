import json
from pathlib import Path

path = Path("project_context/test_runs/20261018_085304Z/raw_responses.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

verified_runs = [d for d in data if d.get("mode") == "graph_on" and d.get("status") == "VERIFIED"]

print(f"Total VERIFIED ON runs: {len(verified_runs)}")
for r in verified_runs:
    qid = r["question_id"]
    run_idx = r["run_index"]
    m = r.get("model_string_returned")
    text = r.get("final_answer_text")
    print(f"\n[{qid} run {run_idx}] model={m}")
    print("Answer text:\n", text[:250])
