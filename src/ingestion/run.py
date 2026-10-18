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
    use_seed: bool = False,
) -> None:
    """Execute bounded ingestion pipeline into FalkorDB repo_kg."""
    import json
    from pathlib import Path
    from src.ingestion.models import PullRequestRecord

    start_time = time.perf_counter()
    print("=" * 65)
    mode_str = "Seed Fixture (Offline)" if use_seed else f"GitHub API (Limit: {limit} PRs)"
    print(f"RepoBrain — Ingestion Pipeline: {repo} [{mode_str}]")
    print("=" * 65)

    client = FalkorDBClient()
    health = client.ping()
    print(f"[DB] Connected to FalkorDB at {health['host']}:{health['port']} (Graph: {health['graph_name']})")
    print(f"[DB] Initial Graph State: {client.get_counts()}")

    loader = GraphLoader(client)

    if use_seed:
        seed_path = Path(__file__).resolve().parent.parent / "fixtures" / "seed_repo_data.json"
        if not seed_path.exists():
            raise FileNotFoundError(f"Seed fixture not found at {seed_path}")
        with open(seed_path, "r", encoding="utf-8") as f:
            seed_data = json.load(f)
        full_records = [PullRequestRecord(**p) for p in seed_data["pull_requests"][:limit]]
        cache_hits = len(full_records)
        network_calls = 0
        print(f"[SEED] Loaded {len(full_records)} records from deterministic seed fixture.")
    else:
        gh_client = GitHubClient()
        print(f"[API] Fetching up to {limit} merged PRs from GitHub API...")
        raw_prs = gh_client.get_pull_requests(repo=repo, limit=limit)
        print(f"[API] Retrieved {len(raw_prs)} merged PRs. Enriching with files, reviews, and issues...")

        full_records = []
        for idx, raw_pr in enumerate(raw_prs, 1):
            num = raw_pr["number"]
            print(f"  [{idx}/{len(raw_prs)}] Fetching details for PR #{num}: {raw_pr.get('title', '')[:40]}...")
            record = gh_client.fetch_full_pr_record(repo, raw_pr)
            full_records.append(record)
        cache_hits = gh_client.cache_hits
        network_calls = gh_client.network_calls

    print(f"\n[INGEST] Records ready: {len(full_records)} (Cache Hits={cache_hits}, Network Calls={network_calls})")
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
    print(f"Cache Hits:           {cache_hits}")
    print(f"Network Requests:     {network_calls}")
    print(f"Total Pipeline Time:  {total_time}s")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RepoBrain Ingestion Runner")
    parser.add_argument("--repo", default="FalkorDB/FalkorDB", help="Target GitHub repository")
    parser.add_argument("--limit", type=int, default=25, help="Number of merged PRs to ingest")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass local cache")
    parser.add_argument("--seed", "--offline", dest="use_seed", action="store_true", help="Ingest from checked-in seed fixture (offline demo mode)")
    args = parser.parse_args()

    run_ingestion(
        repo=args.repo,
        limit=args.limit,
        force_refresh=args.force_refresh,
        use_seed=args.use_seed,
    )
