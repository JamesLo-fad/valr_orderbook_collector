"""
Configuration and shared utilities for VALR Orderbook Recorder
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Default configuration constants
DEFAULT_TRADING_PAIRS = [
    "USDT-ZAR",
    "SOL-ZAR",
    "ETH-ZAR",
    "BTC-ZAR",
    "XRP-ZAR",
    "BNB-ZAR"
]

DEFAULT_DEPTH_LEVELS = 10
DEFAULT_DURATION_DAYS = 90


def setup_logging(log_dir: str = "logs", log_prefix: str = "recorder") -> logging.Logger:
    """
    Setup logging to both console and file.

    Args:
        log_dir: Directory for log files
        log_prefix: Prefix for log filename

    Returns:
        Configured logger instance
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = f"{log_dir}/{log_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file)
        ]
    )
    return logging.getLogger(__name__)


def get_db_path(trading_pair: str) -> str:
    """
    Get database path for a trading pair.

    Args:
        trading_pair: Trading pair (e.g., "BTC-ZAR")

    Returns:
        Database file path
    """
    return f"data/{trading_pair.lower().replace('-', '_')}_orderbook.db"
