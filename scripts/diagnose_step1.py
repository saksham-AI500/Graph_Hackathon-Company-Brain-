import json
from pathlib import Path

path = Path("project_context/test_runs/20261018_085304Z/raw_responses.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

on_runs = [d for d in data if d.get("mode") == "graph_on"]
print(f"Total graph_on runs: {len(on_runs)}")

for i, r in enumerate(on_runs):
    qid = r["question_id"]
    run_idx = r["run_index"]
    m = r.get("model_string_returned")
    ts = r.get("timestamp")
    status = r.get("status")
    claims = r.get("claims", [])
    sources = r.get("sources", [])
    ans = r.get("final_answer_text", "")
    ans_snippet = ans[:60].replace("\n", " ")
    print(f"[{qid} run {run_idx}] model: {m} | ts: {ts} | status: {status} | claims: {len(claims)} | sources: {len(sources)} | text: {ans_snippet}")
