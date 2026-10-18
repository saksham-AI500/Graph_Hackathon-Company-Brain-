"""Tests for DeepSeek model restriction, low-token stability configuration, and safety rules."""

import os
import pytest
from unittest.mock import MagicMock, patch

from src.agent.client import (
    OpenRouterClient,
    OpenRouterClientError,
    OpenRouterAuthError,
    DEFAULT_MODEL,
    ALLOWED_DEEPSEEK_MODELS,
)
from src.agent.loop import AgentExecutionLoop, MAX_STEPS_DEFAULT, MAX_TOOL_RETRIES
from src.agent.models import AgentRequest, AgentAnswer, SourceItem, Claim
from src.db import FalkorDBClient


def test_default_model_is_nemotron():
    """Verify default model is set."""
    assert DEFAULT_MODEL in ALLOWED_DEEPSEEK_MODELS
    client = OpenRouterClient(api_key=None)
    assert client.model == DEFAULT_MODEL


def test_unauthorized_non_deepseek_model_rejection():
    """Verify non-allowed models are strictly rejected with OpenRouterClientError."""
    forbidden_models = [
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o",
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.3-70b-instruct",
        "mistralai/mistral-large",
        "deepseek/deepseek-r1",
        "deepseek/deepseek-v3.2",
        "thinkingmachines/inkling:free",
    ]
    for m in forbidden_models:
        with pytest.raises(OpenRouterClientError) as exc_info:
            OpenRouterClient(model=m, api_key=None)
        assert "Unauthorized model" in str(exc_info.value)


def test_allowed_deepseek_models_accepted():
    """Verify allowed models are accepted."""
    assert "liquid/lfm-2.5-2.6b:free" in ALLOWED_DEEPSEEK_MODELS
    for m in ALLOWED_DEEPSEEK_MODELS:
        client = OpenRouterClient(model=m, api_key=None)
        assert client.model == m


def test_low_token_stability_limits():
    """Verify step limit is 5 and retry limit is 1."""
    assert MAX_STEPS_DEFAULT == 5
    assert MAX_TOOL_RETRIES == 1


def test_create_chat_completion_token_ceiling():
    """Verify max_tokens is capped at 1500 and temperature is forced to 0.0."""
    client = OpenRouterClient(api_key="sk-or-v1-testkey1234567890abcdef")

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Test response", "role": "assistant"}}]
        }
        mock_post.return_value = mock_resp

        # Request 10000 tokens (must be locked to 1500)
        client.create_chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10000,
            temperature=0.7,
        )

        _, kwargs = mock_post.call_args
        payload = kwargs.get("json", {})
        assert payload["max_tokens"] == 1500
        assert payload["temperature"] == 0.0
        assert payload["model"] == DEFAULT_MODEL


def test_request_body_max_tokens_never_exceeds_2000():
    """Fail if any request body sent to OpenRouter has max_tokens above 2000."""
    client = OpenRouterClient(api_key="sk-or-v1-testkey1234567890abcdef")

    test_inputs = [0, 500, 1024, 1500, 2000, 2001, 4096, 100000]
    for req_tokens in test_inputs:
        with patch("httpx.Client.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "ok", "role": "assistant"}}]
            }
            mock_post.return_value = mock_resp

            client.create_chat_completion(
                messages=[{"role": "user", "content": "test"}],
                max_tokens=req_tokens,
            )

            _, kwargs = mock_post.call_args
            payload = kwargs.get("json", {})
            actual_max_tokens = payload.get("max_tokens", 0)
            assert actual_max_tokens <= 2000, f"Violation: max_tokens was {actual_max_tokens} > 2000!"
            assert actual_max_tokens == 1500


def test_secret_redaction_in_errors():
    """Verify API key is never leaked in error messages or logs."""
    secret_key = "sk-or-v1-supersecretkey998877"
    client = OpenRouterClient(api_key=secret_key)

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        # Simulated upstream error containing the secret key
        mock_resp.text = f"Internal server error with request using {secret_key}"
        mock_post.return_value = mock_resp

        with pytest.raises(OpenRouterClientError) as exc_info:
            client.create_chat_completion([{"role": "user", "content": "hi"}])

        err_msg = str(exc_info.value)
        assert secret_key not in err_msg
        assert "[REDACTED]" in err_msg


def test_deterministic_fallback_labeling_when_no_key():
    """Verify deterministic fallback is explicitly labeled when no key is set."""
    db = FalkorDBClient()
    loop = AgentExecutionLoop(client=db, llm_client=OpenRouterClient(api_key=None))
    req = AgentRequest(question="Who owns src/module.c?", api_key="no_key")
    ans = loop.run(req)

    assert ans.model_used == "deterministic_fallback"
    assert ans.status in ("VERIFIED", "PARTIALLY_VERIFIED")
