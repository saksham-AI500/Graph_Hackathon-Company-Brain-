"""Test all 8 API endpoints with live or fixture-backed requests.

Endpoints tested:
1. GET  /api/health
2. POST /api/ask
3. POST /api/compare
4. GET  /api/graph/neighborhood
5. POST /api/sync
6. GET  /api/changes
7. GET  /api/stats
8. POST /api/eval/run
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from fastapi.testclient import TestClient
from src.api.server import app

client = TestClient(app)

print("=== RUNNING API ENDPOINT CHECKS ===\n")

endpoints_to_test = [
    ("GET", "/api/health", None),
    ("POST", "/api/ask", {"question": "Who owns payments/refund.py according to CODEOWNERS?", "mode": "graph_on"}),
    ("POST", "/api/compare", {"question": "Who owns payments/refund.py according to CODEOWNERS?"}),
    ("GET", "/api/graph/neighborhood?entity=marcus-vance", None),
    ("POST", "/api/sync", None),
    ("GET", "/api/changes", None),
    ("GET", "/api/stats", None),
    ("POST", "/api/eval/run", {"split": "dev", "mode": "graph_on", "limit": 1}),
]

mock_completion = {
    "id": "gen-mock",
    "model": "nvidia/nemotron-3.5-lightning:free",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "According to CODEOWNERS, payments/refund.py is owned by Marcus Vance [S1].",
            "tool_calls": None
        },
        "finish_reason": "stop"
    }],
    "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
}

with patch("src.agent.client.OpenRouterClient.create_chat_completion", return_value=mock_completion):
    for method, path, body in endpoints_to_test:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json=body or {})

        print(f"[{method}] {path}")
        print(f"Status Code: {resp.status_code}")
        try:
            body_json = resp.json()
            snippet = json.dumps(body_json, indent=2)[:300]
        except Exception:
            snippet = resp.text[:300]
        print(f"Body Excerpt:\n{snippet}\n")
        print("-" * 60)
