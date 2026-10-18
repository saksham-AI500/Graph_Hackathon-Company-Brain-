import json
import logging
import sys
from pathlib import Path
sys.path.insert(0, ".")

from src.agent.client import OpenRouterClient
from src.agent.tools import get_default_tool_registry
from src.agent.prompt import build_agent_system_prompt

llm_client = OpenRouterClient()
tools = get_default_tool_registry()
tool_defs = tools.get_tool_definitions()

for qid, q_text in [
    ("Q1", "Summarize everything known about the checkout timeout bug: the issue, linked PR, review discussion, and any doc that mentions it."),
    ("Q9", "Why did we choose the retry policy? Quote the source.")
]:
    print(f"\n{'='*20} RAW MODEL INSPECTION {qid} {'='*20}")
    system_prompt = build_agent_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": q_text},
    ]

    # Step 1: Model makes tool call(s) or outputs
    resp = llm_client.create_chat_completion(messages=messages, tools=tool_defs, temperature=0.0)
    msg = resp.get("choices")[0].get("message") or {}
    print(f"Step 1 message: content={msg.get('content')}, tool_calls={msg.get('tool_calls')}")
    messages.append(msg)

    tool_calls = llm_client.parse_tool_calls_from_response(resp)
    if tool_calls:
        for tc in tool_calls:
            print(f"Executing tool {tc.name} with args {tc.arguments}")
            tool_res = tools.execute(tc.name, tc.arguments)
            print(f"Tool success: {tool_res.success}, data length: {len(str(tool_res.data)) if tool_res.data else 0}")
            print(f"Tool raw data:\n{json.dumps(tool_res.data, indent=2)[:500]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.call_id or "call_1",
                "name": tc.name,
                "content": json.dumps(tool_res.data if tool_res.success else {"error": tool_res.error}),
            })

        # Step 2: Model synthesizes answer
        resp2 = llm_client.create_chat_completion(messages=messages, tools=tool_defs, temperature=0.0)
        msg2 = resp2.get("choices")[0].get("message") or {}
        print(f"\nStep 2 RAW MODEL OUTPUT:\n{msg2.get('content')}")
        print(f"Step 2 tool_calls: {msg2.get('tool_calls')}")
