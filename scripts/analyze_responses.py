import json
from pathlib import Path
import numpy as np

raw_file = Path("project_context/test_runs/20261018_085304Z/raw_responses.json")
data = json.loads(raw_file.read_text(encoding="utf-8"))

dev_records = [r for r in data if r["question_id"].startswith("Q")]
gen_records = [r for r in data if r["question_id"].startswith("GEN")]

qids = ["Q1", "Q3", "Q5", "Q7", "Q9", "Q11", "Q13", "Q14", "Q15", "Q17", "Q18", "Q19"]

stats = {qid: {"on_correct": 0, "off_correct": 0, "on_faithful": 0, "off_fab": 0, "on_fab": 0} for qid in qids}

for r in dev_records:
    qid = r["question_id"]
    mode = r["mode"]
    if mode == "graph_on":
        if r.get("is_correct"): stats[qid]["on_correct"] += 1
        if r.get("is_faithful"): stats[qid]["on_faithful"] += 1
        stats[qid]["on_fab"] += r.get("fabricated_citation_count", 0)
    else:
        if r.get("is_correct"): stats[qid]["off_correct"] += 1
        stats[qid]["off_fab"] += r.get("fabricated_citation_count", 0)

print("| Question | ON Correct | OFF Correct | ON Faithful | OFF Fabricated Citations | ON Fabricated Citations |")
print("| :--- | :---: | :---: | :---: | :---: | :---: |")
for qid in qids:
    s = stats[qid]
    print(f"| {qid} | {s['on_correct']}/5 | {s['off_correct']}/5 | {s['on_faithful']}/5 | {s['off_fab']} | {s['on_fab']} |")

on_lats = [r["latency_ms"] for r in dev_records if r["mode"] == "graph_on" and "latency_ms" in r]
off_lats = [r["latency_ms"] for r in dev_records if r["mode"] == "graph_off" and "latency_ms" in r]

print("\nLATENCY STATS:")
print(f"Mode ON:  Mean = {np.mean(on_lats):.2f} ms, p90 = {np.percentile(on_lats, 90):.2f} ms")
print(f"Mode OFF: Mean = {np.mean(off_lats):.2f} ms, p90 = {np.percentile(off_lats, 90):.2f} ms")

errors = [r for r in data if r.get("status") == "ERROR" or "402" in r.get("final_answer_text", "") or "failed" in r.get("final_answer_text", "").lower()]
print(f"\nTotal Errored Calls: {len(errors)}")
for e in errors:
    print(f"- [{e['mode']}] {e['question_id']} (run {e.get('run_index')}): {e.get('error') or e.get('final_answer_text')}")
