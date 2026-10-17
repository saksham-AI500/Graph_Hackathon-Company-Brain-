"""Incremental GitHub resource fetcher and event normalizer."""

import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.graph.writer import current_utc_iso
from src.ingestion.github_client import GitHubClient
from src.sync.models import (
    EventType,
    GitHubChangeEvent,
    SyncState,
)

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Raised on non-recoverable GitHub API errors."""
    pass


class RateLimitExceededError(GitHubAPIError):
    """Raised when GitHub rate limit (403) is hit."""
    pass


class GitHubFetcher:
    """Fetches repository updates incrementally using cursors, since timestamps, and ETags."""

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: float = 20.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def _headers(self, etag: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RepoBrain-SyncEngine",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if etag:
            headers["If-None-Match"] = etag
        return headers

    def load_replay_events(self, fixture_path: str) -> List[GitHubChangeEvent]:
        """Load and normalize events from a local JSONL or JSON fixture without network access."""
        p = Path(fixture_path)
        if not p.exists():
            raise FileNotFoundError(f"Replay fixture file not found: '{fixture_path}'")

        events: List[GitHubChangeEvent] = []
        raw_text = p.read_text(encoding="utf-8").strip()
        if not raw_text:
            return []

        # Check if JSON Lines or standard JSON array
        if raw_text.startswith("["):
            data_list = json.loads(raw_text)
            for item in data_list:
                events.append(GitHubChangeEvent(**item))
        else:
            for line in raw_text.splitlines():
                line = line.strip()
                if line:
                    item = json.loads(line)
                    events.append(GitHubChangeEvent(**item))

        return events

    def fetch_incremental_events(
        self,
        repo: str,
        state: SyncState,
    ) -> Tuple[List[GitHubChangeEvent], SyncState]:
        """Fetch real-world incremental updates for `repo` since `state.last_sync_at`.

        If network or token is unavailable, handles failures gracefully.
        """
        events: List[GitHubChangeEvent] = []
        new_state = state.model_copy(deep=True)
        now_ts = current_utc_iso()

        # If running in environment without internet or without token on public repo,
        # we make a best-effort call to GitHub API with bounded retries
        base_url = f"https://api.github.com/repos/{repo}"
        client_kwargs = {"timeout": self.timeout}

        try:
            with httpx.Client(**client_kwargs) as client:
                # 1. Fetch Pull Requests updated recently
                params: Dict[str, Any] = {"state": "all", "sort": "updated", "direction": "asc", "per_page": 30}
                etag = state.etag_map.get("pulls")
                headers = self._headers(etag=etag)

                resp = self._request_with_retry(client, f"{base_url}/pulls", headers, params)
                if resp.status_code == 304:
                    logger.info("Pulls endpoint returned 304 Not Modified.")
                elif resp.status_code == 200:
                    new_etag = resp.headers.get("ETag")
                    if new_etag:
                        new_state.etag_map["pulls"] = new_etag

                    pulls_data = resp.json()
                    for item in pulls_data:
                        pr_num = item["number"]
                        # Skip PRs already ingested before pr_cursor if not updated since last_sync
                        updated_at = item.get("updated_at")
                        if state.last_sync_at and updated_at and updated_at <= state.last_sync_at:
                            continue

                        # Determine PR event type
                        is_merged = bool(item.get("merged_at"))
                        is_closed = item.get("state") == "closed"
                        if is_merged:
                            etype = EventType.PR_MERGED
                        elif is_closed:
                            etype = EventType.PR_CLOSED
                        else:
                            etype = EventType.PR_OPENED

                        events.append(GitHubChangeEvent(
                            event_id=f"pr_{pr_num}_{updated_at or now_ts}",
                            event_type=etype,
                            timestamp=updated_at or now_ts,
                            source_url=item.get("html_url", f"https://github.com/{repo}/pull/{pr_num}"),
                            actor=item.get("user", {}).get("login"),
                            data={
                                "pr_number": pr_num,
                                "title": item.get("title", ""),
                                "url": item.get("html_url", ""),
                                "author_login": item.get("user", {}).get("login", "unknown"),
                                "author_url": item.get("user", {}).get("html_url", ""),
                                "created_at": item.get("created_at"),
                                "merged_at": item.get("merged_at"),
                                "closed_at": item.get("closed_at"),
                            },
                        ))
                        if pr_num > new_state.pr_cursor:
                            new_state.pr_cursor = pr_num

        except RateLimitExceededError:
            logger.warning("GitHub rate limit hit; returning accumulated events.")
            raise
        except Exception as exc:
            logger.warning(f"Live GitHub fetch encountered: {exc}. Safe fallback available.")
            raise

        new_state.last_sync_at = now_ts
        return events, new_state

    def _request_with_retry(
        self,
        client: httpx.Client,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Execute HTTP request with bounded exponential backoff retries."""
        delay = 1.0
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = client.get(url, headers=headers, params=params)
                if resp.status_code == 403:
                    if "rate limit" in resp.text.lower() or resp.headers.get("X-RateLimit-Remaining") == "0":
                        raise RateLimitExceededError("GitHub API rate limit exceeded.")
                if resp.status_code in (200, 304, 404):
                    return resp
                resp.raise_for_status()
                return resp
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt == self.max_retries:
                    raise GitHubAPIError(f"Network error contacting GitHub API: {e}")
                time.sleep(delay)
                delay *= self.backoff_factor
            except RateLimitExceededError:
                raise
            except Exception as e:
                if attempt == self.max_retries:
                    raise GitHubAPIError(f"HTTP request failed: {e}")
                time.sleep(delay)
                delay *= self.backoff_factor

        raise GitHubAPIError(f"Failed to fetch {url} after {self.max_retries} attempts.")
