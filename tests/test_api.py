"""Unit and integration regression tests for RepoBrain Backend FastAPI Server."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.server import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_root_endpoint(client):
    """Verify service information and exposed modes."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "RepoBrain Backend API"
    assert data["modes_supported"] == ["graph_on", "graph_off"]
    assert "POST /api/ask" in data["endpoints"]


def test_ask_graph_on_valid_structure(client):
    """Verify POST /api/ask under graph_on returns exact Part 3 answer object."""
    payload = {
        "question": "Who owns src/module.c?",
        "mode": "graph_on",
    }
    response = client.post("/api/ask", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Part 3 required fields
    required_keys = [
        "answer",
        "context",
        "ranking",
        "reasoning",
        "claims",
        "excluded",
        "unresolved",
        "sources",
        "mode",
        "as_of",
        "synced_at",
        "model",
        "tool_calls",
        "verifier",
    ]
    for key in required_keys:
        assert key in data, f"Missing required Part 3 key: {key}"

    assert data["mode"] == "graph_on"
    assert isinstance(data["claims"], list)
    assert isinstance(data["sources"], list)
    assert isinstance(data["verifier"], dict)
    assert "claims_total" in data["verifier"]
    assert "claims_passed" in data["verifier"]


def test_ask_graph_off_mode(client):
    """Verify POST /api/ask under graph_off returns answer with zero tools."""
    payload = {
        "question": "Who owns src/module.c?",
        "mode": "graph_off",
    }
    response = client.post("/api/ask", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["mode"] == "graph_off"
    # In graph_off, no repository data or tools should be called
    assert len(data.get("sources", [])) == 0 or len(data.get("tool_calls", [])) == 0


def test_ask_invalid_mode_rejected(client):
    """Plain retrieval baseline or arbitrary mode must be rejected with HTTP 400."""
    payload = {
        "question": "Who owns src/module.c?",
        "mode": "plain_retrieval",
    }
    response = client.post("/api/ask", json=payload)
    assert response.status_code == 400
    assert "strictly 'graph_on' and 'graph_off'" in response.json()["detail"]


def test_graph_neighborhood(client):
    """Verify GET /api/graph/neighborhood returns nodes and edges."""
    response = client.get("/api/graph/neighborhood?entity=marcus-vance")
    assert response.status_code == 200
    data = response.json()
    assert data["entity"] == "marcus-vance"
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
    assert len(data["nodes"]) > 0


def test_sync_endpoint(client):
    """Verify POST /api/sync returns run summary and changes list."""
    response = client.post("/api/sync")
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "status" in data
    assert "events_processed" in data
    assert "mutations_applied" in data
    assert "changes" in data
    assert isinstance(data["changes"], list)


def test_changes_feed(client):
    """Verify GET /api/changes returns change feed."""
    response = client.get("/api/changes")
    assert response.status_code == 200
    data = response.json()
    assert "changes" in data
    assert "count" in data
    assert isinstance(data["changes"], list)


def test_stats_endpoint(client):
    """Verify GET /api/stats returns counts, sync time, and model slug."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "node_count" in data
    assert "edge_count" in data
    assert "last_synced_at" in data
    assert "model_slug" in data
    assert data["model_slug"] == "deepseek/deepseek-chat"


def test_eval_run_dev_endpoint(client):
    """Verify POST /api/eval/run on dev split."""
    payload = {
        "split": "dev",
        "mode": "graph_on",
        "limit": 2,
    }
    response = client.post("/api/eval/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["split"] == "dev"
    assert data["mode"] == "graph_on"
    assert data["total_questions"] == 2
    assert "accuracy" in data
    assert "results" in data
