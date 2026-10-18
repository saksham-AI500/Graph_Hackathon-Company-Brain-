"""Opt-in URL Reachability and Integrity Auditor for RepoBrain evidence citations.

Differentiates:
1. Ground-Truth Matching (evaluator benchmark criteria)
2. HTTP Reachability (network-level reachability via HTTP/HTTPS)
3. Claim Support (semantic backing of claim by cited source)

Does NOT run in standard offline unit tests; available via opt-in CLI or mocked tests.
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import httpx


class URLAuditRecord(BaseModel):
    """Result of auditing an individual evidence citation URL."""
    url: str
    final_url: Optional[str] = None
    status_code: Optional[int] = None
    category: str  # REACHABLE, NOT_FOUND, RATE_LIMITED, AUTH_REQUIRED, TIMEOUT, NETWORK_ERROR, INCONCLUSIVE
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    checked_at: str


class URLAuditSummary(BaseModel):
    """Aggregate statistics for a URL audit run."""
    total_audited: int = 0
    reachable_count: int = 0
    rate_limited_count: int = 0
    auth_required_count: int = 0
    not_found_count: int = 0
    timeout_count: int = 0
    network_error_count: int = 0
    inconclusive_count: int = 0
    records: List[URLAuditRecord] = []

    @property
    def reachability_pct(self) -> float:
        return (
            round((self.reachable_count / self.total_audited) * 100, 1)
            if self.total_audited > 0
            else 0.0
        )


class EvidenceURLAuditor:
    """Audits HTTP reachability of citations with bounded timeouts and category classification."""

    def __init__(self, timeout: float = 5.0, user_agent: str = "RepoBrain-Citation-Auditor/1.0"):
        self.timeout = timeout
        self.headers = {"User-Agent": user_agent}

    def check_url(self, client: httpx.Client, url: str) -> URLAuditRecord:
        """Check a single URL via HTTP HEAD / GET."""
        t0 = time.perf_counter()
        now_utc = datetime.now(timezone.utc).isoformat()
        try:
            # Try HEAD first for efficiency
            resp = client.head(url, headers=self.headers, follow_redirects=True, timeout=self.timeout)
            if resp.status_code == 405:  # Method Not Allowed -> fallback to GET
                resp = client.get(url, headers=self.headers, follow_redirects=True, timeout=self.timeout)

            latency = round((time.perf_counter() - t0) * 1000.0, 2)
            code = resp.status_code
            final_url = str(resp.url)

            if code < 400:
                cat = "REACHABLE"
            elif code in (429, 403) and ("rate" in resp.text.lower() or "rate" in str(resp.headers).lower()):
                cat = "RATE_LIMITED"
            elif code in (401, 403):
                cat = "AUTH_REQUIRED"
            elif code == 404:
                cat = "NOT_FOUND"
            else:
                cat = "INCONCLUSIVE"

            return URLAuditRecord(
                url=url,
                final_url=final_url,
                status_code=code,
                category=cat,
                latency_ms=latency,
                checked_at=now_utc,
            )

        except httpx.TimeoutException:
            latency = round((time.perf_counter() - t0) * 1000.0, 2)
            return URLAuditRecord(
                url=url,
                category="TIMEOUT",
                latency_ms=latency,
                error_message="Request timed out after bounded threshold",
                checked_at=now_utc,
            )
        except httpx.NetworkError as exc:
            latency = round((time.perf_counter() - t0) * 1000.0, 2)
            return URLAuditRecord(
                url=url,
                category="NETWORK_ERROR",
                latency_ms=latency,
                error_message=str(exc),
                checked_at=now_utc,
            )
        except Exception as exc:
            latency = round((time.perf_counter() - t0) * 1000.0, 2)
            return URLAuditRecord(
                url=url,
                category="INCONCLUSIVE",
                latency_ms=latency,
                error_message=str(exc),
                checked_at=now_utc,
            )

    def audit_urls(self, urls: List[str]) -> URLAuditSummary:
        """Audit a list of unique URLs sequentially to avoid triggering GitHub abuse limits."""
        unique_urls = list(dict.fromkeys(urls))
        summary = URLAuditSummary(total_audited=len(unique_urls))

        with httpx.Client(timeout=self.timeout) as client:
            for u in unique_urls:
                rec = self.check_url(client, u)
                summary.records.append(rec)
                if rec.category == "REACHABLE":
                    summary.reachable_count += 1
                elif rec.category == "RATE_LIMITED":
                    summary.rate_limited_count += 1
                elif rec.category == "AUTH_REQUIRED":
                    summary.auth_required_count += 1
                elif rec.category == "NOT_FOUND":
                    summary.not_found_count += 1
                elif rec.category == "TIMEOUT":
                    summary.timeout_count += 1
                elif rec.category == "NETWORK_ERROR":
                    summary.network_error_count += 1
                else:
                    summary.inconclusive_count += 1

        return summary

    def audit_evaluation_file(self, eval_path: Path) -> URLAuditSummary:
        """Extract unique URLs from evaluation JSON output and audit reachability."""
        with open(eval_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        urls = []
        results = data.get("results", {})
        for mode, q_results in results.items():
            for qr in q_results:
                urls.extend(qr.get("evidence_urls", []))

        return self.audit_urls(urls)


def main():
    parser = argparse.ArgumentParser(description="RepoBrain Evidence URL Reachability Auditor")
    parser.add_argument(
        "--input",
        default="project_context/evaluation_raw_results.json",
        help="Path to evaluation raw results JSON file",
    )
    parser.add_argument(
        "--output",
        default="project_context/url_audit_results.json",
        help="Path to save URL audit report",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP request timeout in seconds")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Error: input file {in_path} does not exist.")
        raise SystemExit(1)

    print("=" * 65)
    print("RepoBrain — Evidence URL Reachability Audit")
    print(f"Input: {in_path}")
    print(f"Output: {args.output}")
    print("=" * 65)

    auditor = EvidenceURLAuditor(timeout=args.timeout)
    summary = auditor.audit_evaluation_file(in_path)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary.model_dump(), f, indent=2)

    print("\nAudit Complete:")
    print(f"Total Unique URLs Audited: {summary.total_audited}")
    print(f"Reachable (2xx/3xx):      {summary.reachable_count} ({summary.reachability_pct}%)")
    print(f"Rate Limited (403/429):   {summary.rate_limited_count}")
    print(f"Not Found (404):          {summary.not_found_count}")
    print(f"Timeouts:                 {summary.timeout_count}")
    print(f"Network Errors:           {summary.network_error_count}")
    print(f"Report saved to:          {out_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()
