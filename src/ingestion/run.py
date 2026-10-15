"""CLI runner for bounded, rate-limit-aware FalkorDB repository ingestion."""

import argparse
import time
from src.db import FalkorDBClient
from src.ingestion.github_client import GitHubClient
from src.ingestion.loader import GraphLoader


def run_ingestion(
    repo: str = "FalkorDB/FalkorDB",
    limit: int = 15,
    force_refresh: bool = False,
) -> None:
    """Execute bounded ingestion pipeline into FalkorDB repo_kg."""
    start_time = time.perf_counter()
    print("=" * 65)
    print(f"RepoBrain — Ingestion Pipeline: {repo} (Limit: {limit} PRs)")
    print("=" * 65)

    client = FalkorDBClient()
    health = client.ping()
    print(f"[DB] Connected to FalkorDB at {health['host']}:{health['port']} (Graph: {health['graph_name']})")
    print(f"[DB] Initial Graph State: {client.get_counts()}")

    gh_client = GitHubClient()
    loader = GraphLoader(client)

    print(f"[API] Fetching up to {limit} merged PRs from GitHub API...")
    raw_prs = gh_client.get_pull_requests(repo=repo, limit=limit)
    print(f"[API] Retrieved {len(raw_prs)} merged PRs. Enriching with files, reviews, and issues...")

    full_records = []
    for idx, raw_pr in enumerate(raw_prs, 1):
        num = raw_pr["number"]
        print(f"  [{idx}/{len(raw_prs)}] Fetching details for PR #{num}: {raw_pr.get('title', '')[:40]}...")
        record = gh_client.fetch_full_pr_record(repo, raw_pr)
        full_records.append(record)

    print(f"\n[CACHE] Ingestion cache stats: Hits={gh_client.cache_hits}, Network Calls={gh_client.network_calls}")
    print("[LOADER] Ingesting enriched records into FalkorDB repo_kg (Idempotent MERGE)...")

    summary = loader.load_pull_requests(full_records)
    after_counts = summary["final_counts"]
    print(f"[LOADER] First pass complete. Nodes: {after_counts['nodes']}, Edges: {after_counts['edges']}")

    # Idempotency Verification Pass
    print("[LOADER] Executing second pass to verify idempotency...")
    re_summary = loader.load_pull_requests(full_records)
    re_counts = re_summary["final_counts"]
    print(f"[LOADER] Second pass complete. Nodes: {re_counts['nodes']}, Edges: {re_counts['edges']}")

    assert after_counts == re_counts, (
        f"Idempotency violation! Counts changed from {after_counts} to {re_counts}"
    )
    print("[LOADER] IDEMPOTENCY VERIFIED: Node and edge counts remained 100% identical.")

    total_time = round(time.perf_counter() - start_time, 2)
    print("=" * 65)
    print("RepoBrain — Ingestion Summary")
    print("=" * 65)
    print(f"Target Repository:    {repo}")
    print(f"PRs Ingested:         {len(full_records)}")
    print(f"Total Nodes:          {after_counts['nodes']}")
    print(f"Total Relationships:  {after_counts['edges']}")
    print(f"Cache Hits:           {gh_client.cache_hits}")
    print(f"Network Requests:     {gh_client.network_calls}")
    print(f"Total Pipeline Time:  {total_time}s")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RepoBrain Ingestion Runner")
    parser.add_argument("--repo", default="FalkorDB/FalkorDB", help="Target GitHub repository")
    parser.add_argument("--limit", type=int, default=15, help="Number of merged PRs to ingest")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass local cache")
    args = parser.parse_args()

    run_ingestion(repo=args.repo, limit=args.limit, force_refresh=args.force_refresh)
