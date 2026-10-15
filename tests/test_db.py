"""Unit tests for FalkorDB connection and health checks."""

import pytest
from src.db import FalkorDBClient


def test_falkordb_ping():
    client = FalkorDBClient()
    result = client.ping()
    assert result["status"] == "healthy"
    assert result["ping"] == 1
    assert result["graph_name"] == "repo_kg"
    assert result["latency_ms"] >= 0


def test_falkordb_ro_query():
    client = FalkorDBClient()
    res = client.ro_query("RETURN $val AS num", {"val": 99})
    assert res.result_set == [[99]]


def test_falkordb_counts_returns_dict():
    client = FalkorDBClient()
    counts = client.get_counts()
    assert "nodes" in counts
    assert "edges" in counts
    assert isinstance(counts["nodes"], int)
    assert isinstance(counts["edges"], int)
