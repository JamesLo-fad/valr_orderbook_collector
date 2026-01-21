# valr_orderbook_recorder/__init__.py
"""
VALR Orderbook Recorder Package
VALR 订单簿数据采集器

本模块提供以下核心组件:
- OrderbookDatabase: SQLite 数据库操作类，负责数据存储和查询
- ValrOrderbookCollector: WebSocket 采集器，负责实时订阅和采集订单簿数据
- config: 配置常量和工具函数

使用示例:
    from valr_orderbook_recorder import ValrOrderbookCollector

    collector = ValrOrderbookCollector(
        trading_pair="BTC-ZAR",
        depth_levels=10,
        db_path="data/orderbook.db",
        duration_days=7
    )
    await collector.start()
"""

from .database import OrderbookDatabase
from .websocket_collector import ValrOrderbookCollector
from .config import (
    DEFAULT_TRADING_PAIRS,
    DEFAULT_DEPTH_LEVELS,
    DEFAULT_DURATION_DAYS,
    setup_logging,
    get_db_path
)

__all__ = [
    "OrderbookDatabase",
    "ValrOrderbookCollector",
    "DEFAULT_TRADING_PAIRS",
    "DEFAULT_DEPTH_LEVELS",
    "DEFAULT_DURATION_DAYS",
    "setup_logging",
    "get_db_path"
]
