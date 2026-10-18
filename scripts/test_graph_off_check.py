import sys
sys.path.insert(0, ".")
from src.agent.client import OpenRouterClient
from src.agent.prompt import COMPANY_BRAIN_SYSTEM_PROMPT

c = OpenRouterClient()
prompt = COMPANY_BRAIN_SYSTEM_PROMPT
prompt = prompt.replace(
    "Call tools before answering any question about this company's data. Never answer from memory about Acme.",
    "In graph_off mode, knowledge graph tools and repository access are disabled. Answer normally to the best of your understanding, stating uncertainty where appropriate. Do not invent fake repository URLs or citations."
)
prompt = prompt.replace(
    "Use only facts returned by tools. If a fact is not in a tool result, do not state it.",
    "State uncertainty when answering without tools, but do not refuse by default."
)
prompt = prompt.replace(
    'If a tool returns no evidence, say "I can\'t answer that from the data."',
    "If a question asks for private internal schedules (such as who is on call), refuse as appropriate."
)

print("=== Q1: Which team owns the payments/ module, as far as you know? ===")
r1 = c.create_chat_completion([
    {"role": "system", "content": prompt},
    {"role": "user", "content": "Which team owns the payments/ module, as far as you know?"}
], tools=None)
print(r1["choices"][0]["message"]["content"])

print("\n=== Q2: Who is on call next week at Acme Platform? ===")
r2 = c.create_chat_completion([
    {"role": "system", "content": prompt},
    {"role": "user", "content": "Who is on call next week at Acme Platform?"}
], tools=None)
print(r2["choices"][0]["message"]["content"])
