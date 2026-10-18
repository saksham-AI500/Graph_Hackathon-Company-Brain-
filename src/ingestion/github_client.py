"""Rate-limit-aware GitHub client with local disk response caching."""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from src.ingestion.models import (
    FileRecord,
    IssueRecord,
    PersonRecord,
    PullRequestRecord,
    ReviewRecord,
)

BASE_URL = "https://api.github.com"
DEFAULT_CACHE_DIR = Path(".cache/github")


class GitHubClient:
    """Bounded, rate-limit-aware GitHub API client with persistent disk caching."""

    def __init__(
        self,
        token: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        timeout: float = 30.0,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.cache_hits = 0
        self.network_calls = 0

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RepoBrain-Ingestion-Engine",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_cache_path(self, endpoint: str) -> Path:
        """Derive a safe cache file path from endpoint."""
        # Sanitize endpoint for windows filesystem
        sanitized = endpoint.strip("/").replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "_")
        return self.cache_dir / f"{sanitized}.json"

    def _fetch_json(self, endpoint: str, force_refresh: bool = False) -> Any:
        """Fetch endpoint JSON, checking cache first, respecting rate limits."""
        cache_path = self._get_cache_path(endpoint)
        if not force_refresh and cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    self.cache_hits += 1
                    return json.load(f)
            except Exception:
                pass  # Fallback to network if cache read fails

        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers())
            self.network_calls += 1

            # Check rate limits
            remaining = resp.headers.get("x-ratelimit-remaining")
            if remaining is not None:
                rem_int = int(remaining)
                if rem_int <= 1:
                    reset_ts = int(resp.headers.get("x-ratelimit-reset", time.time() + 60))
                    wait_sec = max(1, reset_ts - int(time.time()))
                    print(f"[WARN] GitHub rate limit reached ({remaining} remaining). Waiting {wait_sec}s...")
                    time.sleep(wait_sec)

            if resp.status_code == 404:
                return None
            if resp.status_code in (403, 429):
                print(f"[WARN] GitHub API rate-limited or forbidden (HTTP {resp.status_code}). Gracefully terminating fetch.")
                return None
            resp.raise_for_status()
            data = resp.json()

            # Write to cache
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as exc:
                print(f"[WARN] Failed to cache {cache_path}: {exc}")

            return data

    def get_pull_requests(
        self, repo: str = "FalkorDB/FalkorDB", limit: int = 50, state: str = "closed"
    ) -> List[Dict[str, Any]]:
        """Fetch bounded list of merged pull requests across paginated requests."""
        merged_prs: List[Dict[str, Any]] = []
        page = 1
        per_page = 50 if limit <= 50 else 100

        while len(merged_prs) < limit:
            endpoint = f"repos/{repo}/pulls?state={state}&per_page={per_page}&page={page}"
            data = self._fetch_json(endpoint)
            if not data or not isinstance(data, list):
                break

            for pr in data:
                if pr.get("merged_at") is not None:
                    merged_prs.append(pr)
                    if len(merged_prs) >= limit:
                        break

            if len(data) < per_page:
                break
            page += 1

        return merged_prs

    def get_pr_files(self, repo: str, pr_number: int) -> List[FileRecord]:
        """Fetch files modified in a pull request."""
        endpoint = f"repos/{repo}/pulls/{pr_number}/files?per_page=100"
        data = self._fetch_json(endpoint)
        if not data or not isinstance(data, list):
            return []

        files: List[FileRecord] = []
        for item in data:
            filename = item.get("filename")
            if not filename:
                continue
            files.append(
                FileRecord(
                    path=filename,
                    url=item.get("blob_url") or f"https://github.com/{repo}/blob/master/{filename}",
                    additions=int(item.get("additions", 0)),
                    deletions=int(item.get("deletions", 0)),
                )
            )
        return files

    def get_pr_reviews(self, repo: str, pr_number: int) -> List[ReviewRecord]:
        """Fetch reviews submitted on a pull request."""
        endpoint = f"repos/{repo}/pulls/{pr_number}/reviews?per_page=50"
        data = self._fetch_json(endpoint)
        if not data or not isinstance(data, list):
            return []

        reviews: List[ReviewRecord] = []
        for item in data:
            user = item.get("user")
            if not user or not user.get("login"):
                continue
            reviews.append(
                ReviewRecord(
                    id=item.get("id"),
                    author_login=user["login"],
                    author_url=user.get("html_url") or f"https://github.com/{user['login']}",
                    state=item.get("state", "COMMENTED"),
                    submitted_at=item.get("submitted_at"),
                )
            )
        return reviews

    def get_issue(self, repo: str, issue_number: int) -> Optional[IssueRecord]:
        """Fetch details for a specific issue."""
        endpoint = f"repos/{repo}/issues/{issue_number}"
        data = self._fetch_json(endpoint)
        if not data or not isinstance(data, dict):
            return None
        user = data.get("user") or {}
        return IssueRecord(
            number=issue_number,
            title=data.get("title", f"Issue #{issue_number}"),
            url=data.get("html_url") or f"https://github.com/{repo}/issues/{issue_number}",
            state=data.get("state", "closed"),
            author_login=user.get("login"),
            author_url=user.get("html_url"),
            created_at=data.get("created_at"),
            closed_at=data.get("closed_at"),
        )

    def extract_linked_issue_numbers(self, body: Optional[str]) -> List[int]:
        """Extract referenced issue numbers from PR body via regex keywords."""
        if not body:
            return []
        patterns = [
            r"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+#(\d+)",
            r"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+https?://github\.com/[^/]+/[^/]+/issues/(\d+)",
            r"(?:ref|refs|see)\s+#(\d+)",
        ]
        issue_nums = set()
        for pat in patterns:
            for match in re.finditer(pat, body, flags=re.IGNORECASE):
                issue_nums.add(int(match.group(1)))
        return sorted(list(issue_nums))

    def fetch_full_pr_record(self, repo: str, raw_pr: Dict[str, Any]) -> PullRequestRecord:
        """Enrich raw PR with reviews, files, and linked issues."""
        pr_number = raw_pr["number"]
        user = raw_pr.get("user") or {}
        author_login = user.get("login", "unknown")
        author_url = user.get("html_url") or f"https://github.com/{author_login}"

        files = self.get_pr_files(repo, pr_number)
        reviews = self.get_pr_reviews(repo, pr_number)

        # Linked issues
        issue_numbers = self.extract_linked_issue_numbers(raw_pr.get("body"))
        resolved_issues: List[IssueRecord] = []
        for num in issue_numbers:
            issue = self.get_issue(repo, num)
            if issue:
                resolved_issues.append(issue)
            else:
                # Fallback to authentic public URL construct if issue API call failed or not found
                resolved_issues.append(
                    IssueRecord(
                        number=num,
                        title=f"Referenced Issue #{num}",
                        url=f"https://github.com/{repo}/issues/{num}",
                        state="closed",
                    )
                )

        return PullRequestRecord(
            number=pr_number,
            title=raw_pr.get("title", f"PR #{pr_number}"),
            url=raw_pr.get("html_url") or f"https://github.com/{repo}/pull/{pr_number}",
            state=raw_pr.get("state", "closed"),
            author_login=author_login,
            author_url=author_url,
            created_at=raw_pr.get("created_at"),
            merged_at=raw_pr.get("merged_at"),
            files=files,
            reviews=reviews,
            resolved_issues=resolved_issues,
        )
