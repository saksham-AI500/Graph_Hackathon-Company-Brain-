"""OpenRouter API client with OpenAI-compatible tool-calling and credentials safety."""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
import httpx

from src.agent.models import ToolCall

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free"
ALLOWED_DEEPSEEK_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
]
MAX_TOKENS_CONSTANT: int = 1500


class OpenRouterClientError(RuntimeError):
    """Raised on non-retryable OpenRouter API errors."""
    pass


class OpenRouterRateLimitError(OpenRouterClientError):
    """Raised when HTTP 429 rate limit is returned."""
    pass


class OpenRouterAuthError(OpenRouterClientError):
    """Raised when authentication fails (HTTP 401/403)."""
    pass


_SENTINEL = object()


def load_dotenv_if_gitignored(dotenv_path: str = ".env") -> bool:
    """Load key-value pairs from .env into os.environ if .env exists and is gitignored."""
    from pathlib import Path
    p = Path(dotenv_path)
    if not p.exists():
        return False
    # Verify .gitignore contains .env
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        gi_text = gitignore_path.read_text(encoding="utf-8")
        if ".env" not in gi_text and "*.env" not in gi_text:
            logger.warning(".env is not listed in .gitignore! Skipping auto-load for security.")
            return False
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                if k and v and k not in os.environ:
                    os.environ[k] = v
        return True
    except Exception as ex:
        logger.warning(f"Failed to read {dotenv_path}: {ex}")
        return False


class OpenRouterClient:
    """Secure client for OpenRouter chat completions with function / tool calling."""

    def __init__(
        self,
        api_key: Any = _SENTINEL,
        model: Optional[str] = None,
        timeout_seconds: float = 60.0,
        base_url: Optional[str] = None,
    ):
        if api_key is _SENTINEL:
            load_dotenv_if_gitignored()
            self._api_key = os.getenv("OPENROUTER_API_KEY")
        else:
            self._api_key = api_key

        raw_model = model or os.getenv("OPENROUTER_MODEL") or DEFAULT_MODEL
        if raw_model not in ALLOWED_DEEPSEEK_MODELS:
            raise OpenRouterClientError(
                f"Unauthorized model '{raw_model}'. RepoBrain strictly requires a verified DeepSeek model "
                f"from {ALLOWED_DEEPSEEK_MODELS}. Never silently switch providers."
            )
        self.model = raw_model
        self.timeout_seconds = timeout_seconds
        self.base_url = (base_url or os.getenv("OPENROUTER_BASE_URL") or OPENROUTER_BASE_URL).rstrip("/")

    @property
    def api_key(self) -> Optional[str]:
        """Return configured API key string or None."""
        return self._api_key

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
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """Invoke OpenRouter chat completions endpoint with DeepSeek low-token stability constraints."""
        if not self.has_credentials:
            raise OpenRouterAuthError("No valid OPENROUTER_API_KEY configured.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://github.com/FalkorDB/RepoBrain",
            "X-Title": "RepoBrain Company Brain",
            "Content-Type": "application/json",
        }

        # Token cap: Enforce 1500 tokens for every call in the client as a single constant
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,  # Enforce temperature=0 for deterministic stability
            "max_tokens": MAX_TOKENS_CONSTANT,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.post(url, json=payload, headers=headers)

                    # Never leak API key in error messages
                    safe_text = resp.text
                    if self._api_key and self._api_key in safe_text:
                        safe_text = safe_text.replace(self._api_key, "[REDACTED]")

                    # On HTTP 402 (Payment Required / in-flight budget), raise immediately without retrying
                    if resp.status_code == 402:
                        raise OpenRouterClientError(f"OpenRouter API call failed (HTTP 402): {safe_text}")
                    elif resp.status_code == 429 and attempt < max_retries:
                        retry_after = 5.0 * (attempt + 1)
                        if "Retry-After" in resp.headers:
                            try:
                                retry_after = min(float(resp.headers["Retry-After"]), 10.0)
                            except ValueError:
                                pass
                        logger.warning(
                            "OpenRouter rate limit 429. Waiting %.1fs (attempt %d/%d)...",
                            retry_after,
                            attempt + 1,
                            max_retries,
                        )
                        time.sleep(retry_after)
                        continue

                    if resp.status_code == 429:
                        raise OpenRouterRateLimitError(f"OpenRouter rate limit reached (HTTP 429): {safe_text}")
                    elif resp.status_code in (401, 403):
                        raise OpenRouterAuthError(f"OpenRouter authentication failure (HTTP {resp.status_code})")
                    elif resp.status_code >= 500:
                        raise OpenRouterClientError(f"OpenRouter server error (HTTP {resp.status_code}): {safe_text}")
                    elif resp.status_code != 200:
                        raise OpenRouterClientError(f"OpenRouter API call failed (HTTP {resp.status_code}): {safe_text}")

                    return resp.json()
            except httpx.TimeoutException as te:
                if attempt < max_retries:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise OpenRouterClientError(f"OpenRouter request timed out after {self.timeout_seconds}s: {te}")
            except httpx.RequestError as re:
                if attempt < max_retries:
                    time.sleep(2.0 * (attempt + 1))
                    continue
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

    def generate(self, prompt: str, temperature: float = 0.0, max_tokens: int = 1024) -> str:
        """Simple text generation helper for direct prompt querying (e.g. Graph OFF)."""
        messages = [{"role": "user", "content": prompt}]
        resp = self.create_chat_completion(messages=messages, temperature=0.0, max_tokens=max_tokens)
        choices = resp.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            return msg.get("content") or ""
        return ""
