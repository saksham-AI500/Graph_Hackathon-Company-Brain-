import json
import logging
import sys
from pathlib import Path
sys.path.insert(0, ".")
from src.agent.loop import AgentExecutionLoop
from src.agent.models import AgentRequest
from src.agent.client import OpenRouterClient
from src.db import FalkorDBClient

logging.basicConfig(level=logging.DEBUG)

db_client = FalkorDBClient()
llm_client = OpenRouterClient()
loop = AgentExecutionLoop(client=db_client, llm_client=llm_client)

for qid, q_text in [
    ("Q1", "Summarize everything known about the checkout timeout bug: the issue, linked PR, review discussion, and any doc that mentions it."),
    ("Q9", "Why did we choose the retry policy? Quote the source.")
]:
    print(f"\n{'='*20} TRACING {qid} {'='*20}")
    req = AgentRequest(
        question=q_text,
        mode="graph_on",
        as_of="2026-09-30T23:59:59Z",
    )
    ans = loop.run(req)
    print(f"\n--- {qid} RESULT ---")
    print("Status:", ans.status)
    print("Model used:", ans.model_used)
    print("Answer text:\n", ans.answer)
    print("Claims count:", len(ans.claims))
    print("Claims:", ans.claims)
    print("Sources count:", len(ans.sources))
    print("Sources:", ans.sources)
    print("Verifier dict:", ans.verifier)
    print("Execution log:")
    for entry in ans.execution_log:
        print("  ", entry)
