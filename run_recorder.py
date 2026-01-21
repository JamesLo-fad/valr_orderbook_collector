#!/usr/bin/env python3
"""
VALR Orderbook Recorder - Single Pair Entry Point

Records orderbook data for a single trading pair via WebSocket.
Data is stored in SQLite database.

Usage:
    python run_recorder.py
    python run_recorder.py --pair ETH-ZAR --days 3

To run in background:
    nohup python run_recorder.py > recorder.log 2>&1 &

To stop:
    Ctrl+C or kill the process
"""

import argparse
import asyncio
import signal

from valr_orderbook_recorder import (
    ValrOrderbookCollector,
    setup_logging,
    get_db_path,
    DEFAULT_DEPTH_LEVELS,
    DEFAULT_DURATION_DAYS
)

# Default configuration
DEFAULT_TRADING_PAIR = "BTC-ZAR"


async def run_collector(args, logger):
    """Run the collector with given arguments."""
    db_path = get_db_path(args.pair)

    collector = ValrOrderbookCollector(
        trading_pair=args.pair,
        depth_levels=args.depth,
        db_path=db_path,
        duration_days=args.days
    )

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()

    def shutdown_handler():
        logger.info("Shutdown signal received...")
        asyncio.create_task(collector.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler)

    logger.info("=" * 60)
    logger.info("VALR Orderbook Recorder")
    logger.info("=" * 60)
    logger.info(f"Trading Pair: {args.pair}")
    logger.info(f"Depth Levels: {args.depth}")
    logger.info(f"Duration: {args.days} days")
    logger.info(f"Database: {db_path}")
    logger.info("=" * 60)

    await collector.start()


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="VALR Orderbook Recorder")
    parser.add_argument("--pair", default=DEFAULT_TRADING_PAIR, help="Trading pair (e.g., BTC-ZAR)")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH_LEVELS, help="Orderbook depth levels")
    parser.add_argument("--days", type=int, default=DEFAULT_DURATION_DAYS, help="Recording duration in days")

    args = parser.parse_args()
    logger = setup_logging(log_prefix="recorder")

    asyncio.run(run_collector(args, logger))


if __name__ == "__main__":
    main()
