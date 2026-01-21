#!/usr/bin/env python3
"""
VALR Multi-Pair Orderbook Recorder

Records orderbook data for multiple trading pairs concurrently.
Each pair gets its own database file and runs in a separate async task.

Usage:
    # Record all default pairs (USDT-ZAR, SOL-ZAR, ETH-ZAR, BTC-ZAR, XRP-ZAR, BNB-ZAR)
    python run_multi_pair_recorder.py

    # Record specific pairs
    python run_multi_pair_recorder.py --pairs BTC-ZAR ETH-ZAR

    # Custom duration
    python run_multi_pair_recorder.py --days 30

    # Run in background
    nohup python run_multi_pair_recorder.py > recorder.log 2>&1 &
"""

import argparse
import asyncio
import logging
import signal
from pathlib import Path
from typing import List

from valr_orderbook_recorder import (
    ValrOrderbookCollector,
    setup_logging,
    get_db_path,
    DEFAULT_TRADING_PAIRS,
    DEFAULT_DEPTH_LEVELS,
    DEFAULT_DURATION_DAYS
)


async def run_single_collector(
    trading_pair: str,
    depth_levels: int,
    duration_days: int,
    logger: logging.Logger
):
    """Run collector for a single trading pair."""
    db_path = get_db_path(trading_pair)

    collector = ValrOrderbookCollector(
        trading_pair=trading_pair,
        depth_levels=depth_levels,
        db_path=db_path,
        duration_days=duration_days
    )

    logger.info(f"[{trading_pair}] Starting collector -> {db_path}")

    try:
        await collector.start()
    except Exception as e:
        logger.error(f"[{trading_pair}] Collector failed: {e}")


async def run_multi_collector(
    trading_pairs: List[str],
    depth_levels: int,
    duration_days: int,
    logger: logging.Logger
):
    """Run collectors for multiple trading pairs concurrently."""
    logger.info("=" * 70)
    logger.info("VALR Multi-Pair Orderbook Recorder")
    logger.info("=" * 70)
    logger.info(f"Trading Pairs: {', '.join(trading_pairs)}")
    logger.info(f"Depth Levels: {depth_levels}")
    logger.info(f"Duration: {duration_days} days")
    logger.info(f"Total collectors: {len(trading_pairs)}")
    logger.info("=" * 70)

    # Create data directory
    Path("data").mkdir(parents=True, exist_ok=True)

    # Create tasks for all trading pairs
    tasks = [
        run_single_collector(pair, depth_levels, duration_days, logger)
        for pair in trading_pairs
    ]

    # Handle graceful shutdown
    collectors_running = True

    def shutdown_handler():
        nonlocal collectors_running
        logger.info("Shutdown signal received, stopping all collectors...")
        collectors_running = False
        for task in tasks:
            task.cancel()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler)

    # Run all collectors concurrently
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        logger.info("All collectors stopped")

    logger.info("Multi-pair recording session ended")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="VALR Multi-Pair Orderbook Recorder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Default pairs: {', '.join(DEFAULT_TRADING_PAIRS)}"
    )
    parser.add_argument(
        "--pairs",
        nargs="+",
        default=DEFAULT_TRADING_PAIRS,
        help="Trading pairs to record (e.g., BTC-ZAR ETH-ZAR)"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_DEPTH_LEVELS,
        help="Orderbook depth levels"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DURATION_DAYS,
        help="Recording duration in days"
    )

    args = parser.parse_args()
    logger = setup_logging(log_prefix="multi_recorder")

    asyncio.run(run_multi_collector(args.pairs, args.depth, args.days, logger))


if __name__ == "__main__":
    main()

