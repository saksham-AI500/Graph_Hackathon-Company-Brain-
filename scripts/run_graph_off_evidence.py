"""Run the two specified graph_off questions and print the full answer objects as JSON."""

import sys
sys.path.insert(0, ".")
import json
from src.agent.loop import AgentExecutionLoop
from src.agent.models import AgentRequest


def main():
    loop = AgentExecutionLoop()

    print("=" * 80)
    print("QUESTION 1 (factual): 'Which team owns the payments/ module, as far as you know?'")
    print("=" * 80)
    req1 = AgentRequest(
        question="Which team owns the payments/ module, as far as you know?",
        mode="graph_off",
    )
    ans1 = loop.run(req1)
    d1 = ans1.model_dump()
    print(json.dumps(d1, indent=2))

    print("\n" + "=" * 80)
    print("QUESTION 2 (unanswerable): 'Who is on call next week at Acme Platform?'")
    print("=" * 80)
    req2 = AgentRequest(
        question="Who is on call next week at Acme Platform?",
        mode="graph_off",
    )
    ans2 = loop.run(req2)
    d2 = ans2.model_dump()
    print(json.dumps(d2, indent=2))


if __name__ == "__main__":
    main()
