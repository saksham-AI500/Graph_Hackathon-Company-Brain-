"""OpenRouter API client with OpenAI-compatible tool-calling and credentials safety."""

import json
import logging
import os
from typing import Any, Dict, List, Optional
import httpx

from src.agent.models import ToolCall

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"


class OpenRouterClientError(RuntimeError):
    """Raised on non-retryable OpenRouter API errors."""
    pass


class OpenRouterRateLimitError(OpenRouterClientError):
    """Raised when HTTP 429 rate limit is returned."""
    pass


class OpenRouterAuthError(OpenRouterClientError):
    """Raised when authentication fails (HTTP 401/403)."""
    pass


class OpenRouterClient:
    """Secure client for OpenRouter chat completions with function / tool calling."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 30.0,
        base_url: Optional[str] = None,
    ):
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("OPENROUTER_MODEL") or DEFAULT_MODEL
        self.timeout_seconds = timeout_seconds
        self.base_url = (base_url or os.getenv("OPENROUTER_BASE_URL") or OPENROUTER_BASE_URL).rstrip("/")

    @property
    def has_credentials(self) -> bool:
        """Check if a valid, non-placeholder API key is configured."""
        if not self._api_key:
            return False
        clean = self._api_key.strip()
        if not clean or clean in ("your_openrouter_api_key_here", "sk-mock-dummy"):
            return False
        return True

    def create_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        """Invoke OpenRouter chat completions endpoint with optional tool definitions."""
        if not self.has_credentials:
            raise OpenRouterAuthError("No valid OPENROUTER_API_KEY configured.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://github.com/FalkorDB/RepoBrain",
            "X-Title": "RepoBrain Company Brain",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)

                if resp.status_code == 429:
                    raise OpenRouterRateLimitError(f"OpenRouter rate limit reached (HTTP 429): {resp.text}")
                elif resp.status_code in (401, 403):
                    raise OpenRouterAuthError(f"OpenRouter authentication failure (HTTP {resp.status_code})")
                elif resp.status_code >= 500:
                    raise OpenRouterClientError(f"OpenRouter server error (HTTP {resp.status_code}): {resp.text}")
                elif resp.status_code != 200:
                    raise OpenRouterClientError(f"OpenRouter API call failed (HTTP {resp.status_code}): {resp.text}")

                return resp.json()
        except httpx.TimeoutException as te:
            raise OpenRouterClientError(f"OpenRouter request timed out after {self.timeout_seconds}s: {te}")
        except httpx.RequestError as re:
            raise OpenRouterClientError(f"OpenRouter network transport error: {re}")

    @classmethod
    def parse_tool_calls_from_response(cls, response: Dict[str, Any]) -> List[ToolCall]:
        """Extract ToolCall objects safely from OpenRouter completion payload."""
        tool_calls: List[ToolCall] = []
        choices = response.get("choices") or []
        if not choices:
            return tool_calls

        message = choices[0].get("message") or {}
        raw_calls = message.get("tool_calls") or []

        for c in raw_calls:
            call_id = c.get("id")
            func = c.get("function") or {}
            fname = func.get("name")
            raw_args = func.get("arguments")

            if not fname:
                continue

            args: Dict[str, Any] = {}
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except Exception as ex:
                    logger.warning(f"Failed to parse tool call arguments JSON for '{fname}': {ex}")
                    args = {"_raw": raw_args}
            elif isinstance(raw_args, dict):
                args = raw_args

            tool_calls.append(ToolCall(name=fname, arguments=args, call_id=call_id))

        return tool_calls
