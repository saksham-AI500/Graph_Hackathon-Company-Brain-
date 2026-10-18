"""Run 3-question smoke test for RepoBrain answer engine and both modes."""

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import time
from src.agent.loop import AgentExecutionLoop
from src.agent.models import AgentRequest
from src.db import FalkorDBClient

def main():
    client = FalkorDBClient()
    loop = AgentExecutionLoop(client=client)

    test_questions = [
        "Who owns src/module.c?",
        "Why did we choose the retry policy? Quote the source.",
        "Who is on call next week?",
    ]

    results = {}

    for mode in ["graph_on", "graph_off"]:
        results[mode] = []
        for q in test_questions:
            t0 = time.perf_counter()
            req = AgentRequest(question=q, mode=mode)
            ans = loop.run(req)
            total_ms = round((time.perf_counter() - t0) * 1000, 2)

            resp = ans.to_api_response()
            resp["stage_timings_ms"] = {
                "total": total_ms,
                "tool_ms": sum(tc.get("ms", 0) for tc in resp.get("tool_calls", [])),
            }
            results[mode].append({
                "question": q,
                "answer_object": resp,
            })

    print(json.dumps(results, indent=2))

    with open("smoke_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
