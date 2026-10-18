import json
import sys
from pathlib import Path

path = Path("project_context/test_runs/20261018_085304Z/raw_responses.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

on_runs = [d for d in data if d.get("mode") == "graph_on"]

print("=== STEP 1: ALL 60 ON RUNS TABLE ===")
print("QID | Run | Model Returned | Made Call | Timestamp | Status | Claims | Sources | Path Setting Status")
print("-" * 100)

model_call_count = 0
fallback_count = 0
fallback_causes = {}

for r in on_runs:
    qid = r["question_id"]
    run_idx = r["run_index"]
    m = r.get("model_string_returned")
    ts = r.get("timestamp")
    status = r.get("status")
    claims = r.get("claims", [])
    sources = r.get("sources", [])
    ans = r.get("final_answer_text", "")

    # Check if openrouter call was made
    # If model is deepseek/deepseek-chat, call was made
    # If deterministic_fallback, call was either not made or fell back after error
    made_call = "Yes" if m == "deepseek/deepseek-chat" else "No (Fallback)"
    if m == "deepseek/deepseek-chat":
        model_call_count += 1
    else:
        fallback_count += 1

    # Code path setting status
    # In src/agent/loop.py:
    # If status is VERIFIED, was it set by deterministic template or verifier?
    path_info = "verifier" if status == "VERIFIED" else "refusal"

    print(f"{qid:3} | {run_idx:3} | {m:22} | {made_call:13} | {ts:25} | {status:8} | {len(claims):6} | {len(sources):7} | {path_info}")

print(f"\nTotal ON runs making model call (deepseek/deepseek-chat): {model_call_count}/60")
print(f"Total ON runs using deterministic_fallback: {fallback_count}/60")
