"""Generate real sample responses by calling each endpoint with a fixture-backed request.

Saves raw JSON responses to docs/api_samples/<endpoint>.json
"""

import json
import os
import sys
import hashlib
from pathlib import Path

# Ensure fixture-backed execution
os.environ["PYTEST_CURRENT_TEST"] = "test_api_samples"

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from fastapi.testclient import TestClient
from src.api.server import app

OUT_DIR = WORKSPACE / "docs" / "api_samples"
OUT_DIR.mkdir(parents=True, exist_ok=True)

client = TestClient(app)

endpoints = [
    {
        "filename": "get_api_health.json",
        "alias": "health.json",
        "method": "GET",
        "path": "/api/health",
        "payload": None,
    },
    {
        "filename": "get_api_stats.json",
        "alias": "stats.json",
        "method": "GET",
        "path": "/api/stats",
        "payload": None,
    },
    {
        "filename": "post_api_ask_graph_on.json",
        "alias": "ask_graph_on.json",
        "method": "POST",
        "path": "/api/ask",
        "payload": {
            "question": "Who owns payments/refund.py according to CODEOWNERS?",
            "mode": "graph_on"
        },
    },
    {
        "filename": "post_api_ask_graph_off.json",
        "alias": "ask_graph_off.json",
        "method": "POST",
        "path": "/api/ask",
        "payload": {
            "question": "Who owns payments/refund.py according to CODEOWNERS?",
            "mode": "graph_off"
        },
    },
    {
        "filename": "post_api_compare.json",
        "alias": "compare.json",
        "method": "POST",
        "path": "/api/compare",
        "payload": {
            "question": "Who owns payments/refund.py according to CODEOWNERS?"
        },
    },
    {
        "filename": "get_api_graph_neighborhood.json",
        "alias": "graph_neighborhood.json",
        "method": "GET",
        "path": "/api/graph/neighborhood?entity=marcus-vance",
        "payload": None,
    },
    {
        "filename": "post_api_sync.json",
        "alias": "sync.json",
        "method": "POST",
        "path": "/api/sync",
        "payload": {},
    },
    {
        "filename": "get_api_changes.json",
        "alias": "changes.json",
        "method": "GET",
        "path": "/api/changes",
        "payload": None,
    },
    {
        "filename": "post_api_eval_run.json",
        "alias": "eval_run.json",
        "method": "POST",
        "path": "/api/eval/run",
        "payload": {
            "split": "failure",
            "mode": "graph_on",
            "limit": 1
        },
    },
    {
        "filename": "get_api_eval_results.json",
        "alias": "eval_results.json",
        "method": "GET",
        "path": "/api/eval/results",
        "payload": None,
    },
]

print("=== GENERATING RAW API SAMPLES ===\n")

hashes = {}

for ep in endpoints:
    if ep["method"] == "GET":
        resp = client.get(ep["path"])
    else:
        resp = client.post(ep["path"], json=ep["payload"])

    assert resp.status_code == 200, f"Endpoint {ep['path']} returned {resp.status_code}: {resp.text}"
    
    data = resp.json()
    formatted = json.dumps(data, indent=2) + "\n"

    p1 = OUT_DIR / ep["filename"]
    p2 = OUT_DIR / ep["alias"]
    p1.write_text(formatted, encoding="utf-8")
    p2.write_text(formatted, encoding="utf-8")

    sha256 = hashlib.sha256(formatted.encode("utf-8")).hexdigest()
    hashes[ep["filename"]] = sha256
    hashes[ep["alias"]] = sha256
    print(f"[{ep['method']}] {ep['path']} -> {ep['filename']} (SHA-256: {sha256})")

print("\nAll sample responses saved successfully!")
