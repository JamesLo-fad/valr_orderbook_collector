#!/usr/bin/env python3
"""
Data Query and Export Tool

Usage:
    # Show database stats for a specific pair
    python query_data.py stats --pair BTC-ZAR

    # Show stats for all pairs
    python query_data.py stats --all

    # Export all data to CSV
    python query_data.py export --pair BTC-ZAR --output data.csv

    # Export specific date range
    python query_data.py export --pair BTC-ZAR --start 2025-01-21 --end 2025-01-22 --output day1.csv

    # Query recent snapshots
    python query_data.py query --pair BTC-ZAR --limit 100
"""

import argparse
import sys
from pathlib import Path
from typing import List

from valr_orderbook_recorder import (
    OrderbookDatabase,
    DEFAULT_TRADING_PAIRS,
    get_db_path
)


def get_all_available_dbs() -> List[tuple]:
    """Get all available database files with their trading pairs."""
    data_dir = Path("data")
    if not data_dir.exists():
        return []

    available = []
    for pair in DEFAULT_TRADING_PAIRS:
        db_path = get_db_path(pair)
        if Path(db_path).exists():
            available.append((pair, db_path))
    return available


def show_stats(db: OrderbookDatabase, trading_pair: str = None):
    """Show database statistics."""
    count = db.get_snapshot_count()
    size_mb = db.get_db_size_mb()

    print("=" * 50)
    if trading_pair:
        print(f"Database Statistics - {trading_pair}")
    else:
        print("Database Statistics")
    print("=" * 50)
    print(f"Database path: {db.db_path}")
    print(f"Total snapshots: {count:,}")
    print(f"Database size: {size_mb:.2f} MB")

    if count > 0:
        snapshots = db.query_snapshots(limit=1)
        first = snapshots[0] if snapshots else None
        snapshots = db.query_snapshots(limit=1, offset=count-1)
        last = snapshots[0] if snapshots else None

        if first and last:
            print(f"First snapshot: {first['timestamp']}")
            print(f"Last snapshot: {last['timestamp']}")
    print("=" * 50)


def show_all_stats():
    """Show statistics for all available databases."""
    available_dbs = get_all_available_dbs()

    if not available_dbs:
        print("No database files found in data/ directory")
        return

    print("\n" + "=" * 70)
    print("ALL TRADING PAIRS STATISTICS")
    print("=" * 70)

    for pair, db_path in available_dbs:
        db = OrderbookDatabase(db_path)
        count = db.get_snapshot_count()
        size_mb = db.get_db_size_mb()

        print(f"\n{pair}:")
        print(f"  Snapshots: {count:,}")
        print(f"  Size: {size_mb:.2f} MB")

        if count > 0:
            snapshots = db.query_snapshots(limit=1)
            first = snapshots[0] if snapshots else None
            snapshots = db.query_snapshots(limit=1, offset=count-1)
            last = snapshots[0] if snapshots else None

            if first and last:
                print(f"  First: {first['timestamp']}")
                print(f"  Last: {last['timestamp']}")

    print("\n" + "=" * 70)


def export_data(db: OrderbookDatabase, output: str, start: str = None, end: str = None):
    """Export data to CSV."""
    print(f"Exporting data to {output}...")
    count = db.export_to_csv(output, start_time=start, end_time=end)
    print(f"Exported {count:,} snapshots")


def query_data(db: OrderbookDatabase, limit: int, start: str = None, end: str = None):
    """Query and display snapshots."""
    snapshots = db.query_snapshots(start_time=start, end_time=end, limit=limit)

    for snap in snapshots:
        print(f"[{snap['timestamp']}] mid={snap['mid_price']:.2f} spread={snap['spread']:.2f}")


def main():
    parser = argparse.ArgumentParser(
        description="Query and export orderbook data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available pairs: {', '.join(DEFAULT_TRADING_PAIRS)}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.add_argument("--pair", help="Trading pair (e.g., BTC-ZAR)")
    stats_parser.add_argument("--all", action="store_true", help="Show stats for all pairs")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export to CSV")
    export_parser.add_argument("--pair", required=True, help="Trading pair (e.g., BTC-ZAR)")
    export_parser.add_argument("--output", "-o", required=True, help="Output CSV file")
    export_parser.add_argument("--start", help="Start time (YYYY-MM-DD or ISO format)")
    export_parser.add_argument("--end", help="End time (YYYY-MM-DD or ISO format)")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query snapshots")
    query_parser.add_argument("--pair", required=True, help="Trading pair (e.g., BTC-ZAR)")
    query_parser.add_argument("--limit", "-n", type=int, default=10, help="Number of results")
    query_parser.add_argument("--start", help="Start time")
    query_parser.add_argument("--end", help="End time")

    args = parser.parse_args()

    if args.command == "stats":
        if args.all:
            show_all_stats()
        elif args.pair:
            db_path = get_db_path(args.pair)
            if not Path(db_path).exists():
                print(f"Error: Database not found for {args.pair}")
                print(f"Expected path: {db_path}")
                sys.exit(1)
            db = OrderbookDatabase(db_path)
            show_stats(db, args.pair)
        else:
            print("Error: Please specify --pair or --all")
            sys.exit(1)

    elif args.command == "export":
        db_path = get_db_path(args.pair)
        if not Path(db_path).exists():
            print(f"Error: Database not found for {args.pair}")
            sys.exit(1)
        db = OrderbookDatabase(db_path)
        export_data(db, args.output, args.start, args.end)

    elif args.command == "query":
        db_path = get_db_path(args.pair)
        if not Path(db_path).exists():
            print(f"Error: Database not found for {args.pair}")
            sys.exit(1)
        db = OrderbookDatabase(db_path)
        query_data(db, args.limit, args.start, args.end)


if __name__ == "__main__":
    main()
