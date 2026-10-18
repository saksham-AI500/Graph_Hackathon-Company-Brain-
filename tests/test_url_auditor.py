"""Unit tests for EvidenceURLAuditor using mock responses (zero internet dependency)."""

from unittest.mock import MagicMock, patch
import httpx
import pytest
from src.evaluation.url_auditor import EvidenceURLAuditor, URLAuditRecord


@pytest.fixture
def auditor():
    return EvidenceURLAuditor(timeout=1.0)


def test_url_auditor_reachable(auditor):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://github.com/FalkorDB/FalkorDB/pull/3307"

    mock_client = MagicMock()
    mock_client.head.return_value = mock_resp

    rec = auditor.check_url(mock_client, "https://github.com/FalkorDB/FalkorDB/pull/3307")
    assert rec.category == "REACHABLE"
    assert rec.status_code == 200
    assert rec.final_url == "https://github.com/FalkorDB/FalkorDB/pull/3307"


def test_url_auditor_fallback_to_get_on_405(auditor):
    mock_head_resp = MagicMock()
    mock_head_resp.status_code = 405

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.url = "https://github.com/FalkorDB/FalkorDB/blob/main/CODEOWNERS"

    mock_client = MagicMock()
    mock_client.head.return_value = mock_head_resp
    mock_client.get.return_value = mock_get_resp

    rec = auditor.check_url(mock_client, "https://github.com/FalkorDB/FalkorDB/blob/main/CODEOWNERS")
    assert rec.category == "REACHABLE"
    assert rec.status_code == 200


def test_url_auditor_not_found(auditor):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.url = "https://github.com/FalkorDB/FalkorDB/pull/99999"

    mock_client = MagicMock()
    mock_client.head.return_value = mock_resp

    rec = auditor.check_url(mock_client, "https://github.com/FalkorDB/FalkorDB/pull/99999")
    assert rec.category == "NOT_FOUND"
    assert rec.status_code == 404


def test_url_auditor_rate_limited(auditor):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "API rate limit exceeded"
    mock_resp.headers = {"x-ratelimit-remaining": "0"}
    mock_resp.url = "https://github.com/FalkorDB/FalkorDB/pull/3307"

    mock_client = MagicMock()
    mock_client.head.return_value = mock_resp

    rec = auditor.check_url(mock_client, "https://github.com/FalkorDB/FalkorDB/pull/3307")
    assert rec.category == "RATE_LIMITED"


def test_url_auditor_timeout(auditor):
    mock_client = MagicMock()
    mock_client.head.side_effect = httpx.TimeoutException("Connection timed out")

    rec = auditor.check_url(mock_client, "https://github.com/FalkorDB/FalkorDB/pull/3307")
    assert rec.category == "TIMEOUT"
    assert "timed out" in rec.error_message


def test_audit_urls_aggregates_categories(auditor):
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        # Return 200 for first, 404 for second
        r1 = MagicMock(status_code=200, url="https://github.com/FalkorDB/FalkorDB/pull/1")
        r2 = MagicMock(status_code=404, url="https://github.com/FalkorDB/FalkorDB/pull/2")
        mock_client.head.side_effect = [r1, r2]

        summary = auditor.audit_urls([
            "https://github.com/FalkorDB/FalkorDB/pull/1",
            "https://github.com/FalkorDB/FalkorDB/pull/2",
            "https://github.com/FalkorDB/FalkorDB/pull/1",  # duplicate should be deduplicated
        ])

        assert summary.total_audited == 2
        assert summary.reachable_count == 1
        assert summary.not_found_count == 1
        assert summary.reachability_pct == 50.0
