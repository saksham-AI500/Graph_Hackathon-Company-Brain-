"""Command-line interface for RepoBrain incremental synchronization engine."""

import argparse
import logging
import sys

from src.db import FalkorDBClient
from src.sync.engine import SyncEngine


def main() -> None:
    """CLI entrypoint for RepoBrain GitHub synchronization."""
    parser = argparse.ArgumentParser(
        prog="repobrain-sync",
        description="Incremental GitHub synchronization engine for FalkorDB repo_kg",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="FalkorDB/FalkorDB",
        help="Target GitHub repository slug (default: FalkorDB/FalkorDB)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Perform a single synchronization cycle and exit",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Poll periodically for repository updates",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Polling interval in seconds for --watch mode (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate reconciliation and print planned mutations without changing graph data or cursors",
    )
    parser.add_argument(
        "--replay",
        type=str,
        metavar="FILE",
        help="Replay normalized change events from a local JSON or JSONL fixture file without network access",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable detailed debug logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not args.once and not args.watch and not args.replay and not args.dry_run:
        parser.print_help()
        sys.exit(0)

    client = FalkorDBClient()
    engine = SyncEngine(client=client)

    if args.watch:
        print(f"Starting RepoBrain sync watcher for '{args.repo}' (interval: {args.interval}s, dry_run: {args.dry_run})...")
        try:
            engine.run_watch(repo=args.repo, interval=args.interval, dry_run=args.dry_run)
        except KeyboardInterrupt:
            print("\nSync watcher stopped.")
            sys.exit(0)
    else:
        print(f"Executing RepoBrain sync for '{args.repo}' (dry_run: {args.dry_run}, replay: {args.replay or 'None'})...")
        res = engine.run_once(
            repo=args.repo,
            dry_run=args.dry_run,
            replay_fixture=args.replay,
        )
        print("=" * 60)
        print("RepoBrain Synchronization Summary")
        print("=" * 60)
        print(f"Run ID:             {res.run_id}")
        print(f"Repository:         {res.repo}")
        print(f"Dry Run:            {res.dry_run}")
        print(f"Events Processed:   {res.events_processed}")
        print(f"Mutations Applied:  {res.mutations_applied}")
        print(f"No-Ops (Idempotent):{res.no_ops}")
        print(f"Failures:           {res.failures}")
        print(f"Cursor Advanced:    {res.cursor_advanced}")
        if res.errors:
            print("Errors encountered:")
            for err in res.errors:
                print(f"  - {err}")
        print("=" * 60)

        if res.failures > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
