import time
import os
import sys
sys.path.insert(0, ".")

t0 = time.time()
print("1. Starting...", flush=True)

from src.agent.loop import AgentExecutionLoop
print("2. Imported AgentExecutionLoop in", round(time.time() - t0, 2), "s", flush=True)

from src.agent.models import AgentRequest
print("3. Imported AgentRequest in", round(time.time() - t0, 2), "s", flush=True)

loop = AgentExecutionLoop()
print("4. Initialized AgentExecutionLoop in", round(time.time() - t0, 2), "s", flush=True)

req = AgentRequest(question="Who owns src/module.c?")
print("5. Starting loop.run...", flush=True)

ans = loop.run(req)
print("6. Done loop.run in", round(time.time() - t0, 2), "s. Status:", ans.status, flush=True)
