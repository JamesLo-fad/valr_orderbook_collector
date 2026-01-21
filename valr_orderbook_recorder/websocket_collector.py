# valr_orderbook_recorder/websocket_collector.py
"""
WebSocket Collector for VALR Orderbook Data
VALR 订单簿 WebSocket 采集器

本模块提供 ValrOrderbookCollector 类，负责:
1. 建立与 VALR 交易所的 WebSocket 连接
2. 订阅指定交易对的订单簿更新事件
3. 解析订单簿数据并存储到数据库
4. 自动重连和错误处理

VALR WebSocket API:
- 端点: wss://api.valr.com/ws/trade
- 事件: FULL_ORDERBOOK_UPDATE (订单簿完整更新)
- 数据格式: 每个价格档位包含 Price 和 Orders 数组
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable

import websockets

from .database import OrderbookDatabase

logger = logging.getLogger(__name__)

# VALR WebSocket 交易端点
VALR_WS_TRADE_URL = "wss://api.valr.com/ws/trade"


class ValrOrderbookCollector:
    """
    VALR 订单簿数据采集器

    通过 WebSocket 实时订阅订单簿更新，支持:
    - 可配置的采集深度 (默认 10 档)
    - 可配置的采集时长 (默认 7 天)
    - 自动断线重连
    - 进度日志输出
    """

    def __init__(
        self,
        trading_pair: str,
        depth_levels: int = 10,
        db_path: str = "orderbook_data.db",
        duration_days: int = 7
    ):
        """
        初始化采集器

        Args:
            trading_pair: 交易对 (如 "BTC-ZAR")
            depth_levels: 采集深度档位数 (默认 10)
            db_path: 数据库文件路径
            duration_days: 采集持续天数 (默认 7)
        """
        self.trading_pair = trading_pair
        self.exchange_pair = trading_pair.replace("-", "")  # BTC-ZAR -> BTCZAR (VALR 格式)
        self.depth_levels = depth_levels
        self.db = OrderbookDatabase(db_path)
        self.duration_days = duration_days

        # 内部状态
        self._running = False                                    # 运行标志
        self._ws: Optional[websockets.WebSocketClientProtocol] = None  # WebSocket 连接
        self._snapshot_count = 0                                 # 已采集快照数
        self._session_id: Optional[int] = None                   # 当前会话 ID
        self._start_time: Optional[datetime] = None              # 开始时间
        self._last_log_time: Optional[datetime] = None           # 上次日志时间

    async def start(self):
        """
        启动订单簿数据采集

        主循环逻辑:
        1. 初始化会话和计时
        2. 连接 WebSocket 并订阅数据
        3. 断线时自动重连 (5秒间隔)
        4. 达到设定时长后自动停止
        """
        self._running = True
        self._start_time = datetime.utcnow()
        self._session_id = self.db.start_session(self.trading_pair, self.depth_levels)
        end_time = self._start_time + timedelta(days=self.duration_days)

        logger.info(f"Starting orderbook collection for {self.trading_pair}")
        logger.info(f"Duration: {self.duration_days} days (until {end_time})")
        logger.info(f"Depth levels: {self.depth_levels}")

        while self._running and datetime.utcnow() < end_time:
            try:
                await self._connect_and_collect()
            except Exception as e:
                logger.error(f"Connection error: {e}")
                if self._running:
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)

        await self.stop()

    async def stop(self):
        """停止采集并清理资源"""
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._session_id:
            self.db.end_session(self._session_id, self._snapshot_count)
        logger.info(f"Collection stopped. Total snapshots: {self._snapshot_count}")

    async def _connect_and_collect(self):
        """
        建立 WebSocket 连接并开始采集

        订阅 FULL_ORDERBOOK_UPDATE 事件获取完整订单簿更新
        """
        async with websockets.connect(VALR_WS_TRADE_URL) as ws:
            self._ws = ws
            logger.info("Connected to VALR WebSocket")

            # Subscribe to full orderbook updates
            # 订阅完整订单簿更新事件
            subscribe_msg = {
                "type": "SUBSCRIBE",
                "subscriptions": [
                    {"event": "FULL_ORDERBOOK_UPDATE", "pairs": [self.exchange_pair]}
                ]
            }
            await ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to FULL_ORDERBOOK_UPDATE for {self.exchange_pair}")

            async for message in ws:
                if not self._running:
                    break
                await self._process_message(message)

    async def _process_message(self, message: str):
        """
        处理 WebSocket 消息

        消息类型:
        - FULL_ORDERBOOK_SNAPSHOT: 订单簿完整快照
        - FULL_ORDERBOOK_UPDATE: 订单簿增量更新
        - SUBSCRIBED: 订阅确认
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            # Handle both snapshot and update messages
            # 处理快照和更新两种消息类型
            if msg_type in ("FULL_ORDERBOOK_SNAPSHOT", "FULL_ORDERBOOK_UPDATE"):
                await self._handle_orderbook_update(data)
            elif msg_type == "SUBSCRIBED":
                logger.info(f"Subscription confirmed: {data}")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse message: {e}")

    async def _handle_orderbook_update(self, data: dict):
        """
        处理订单簿更新并存储到数据库

        VALR 数据格式:
        {
            "Bids": [{"Price": "100.00", "Orders": [{"quantity": "1.5"}, ...]}, ...],
            "Asks": [{"Price": "101.00", "Orders": [{"quantity": "2.0"}, ...]}, ...],
            "LastChange": 12345  // 序列号
        }

        每个价格档位可能有多个订单，需要聚合数量
        """
        # Data structure: Asks/Bids at top level or in 'data' field
        # 数据可能在顶层或嵌套在 'data' 字段中
        inner_data = data.get("data", data)
        bids_raw = inner_data.get("Bids", [])
        asks_raw = inner_data.get("Asks", [])
        sequence = inner_data.get("LastChange")

        # VALR format: each level has Price and Orders array
        # Need to aggregate quantity from all orders at each price level
        # VALR 格式: 每个档位有 Price 和 Orders 数组，需要聚合同价位的所有订单数量
        def parse_levels(levels_raw):
            """解析价格档位，聚合同价位订单数量"""
            result = []
            for level in levels_raw[:self.depth_levels]:
                price = float(level.get("Price", 0))
                # Sum quantities from all orders at this price
                # 聚合该价位所有订单的数量
                orders = level.get("Orders", [])
                total_qty = sum(float(o.get("quantity", 0)) for o in orders)
                if price > 0 and total_qty > 0:
                    result.append((price, total_qty))
            return result

        bids = parse_levels(bids_raw)
        asks = parse_levels(asks_raw)

        if not bids or not asks:
            return

        # Store in database / 存储到数据库
        self.db.insert_snapshot(
            trading_pair=self.trading_pair,
            bids=bids,
            asks=asks,
            sequence_number=sequence
        )
        self._snapshot_count += 1

        # Log progress every 60 seconds / 每 60 秒输出一次进度日志
        now = datetime.utcnow()
        if self._last_log_time is None or (now - self._last_log_time).seconds >= 60:
            self._last_log_time = now
            elapsed = now - self._start_time
            db_size = self.db.get_db_size_mb()
            logger.info(
                f"Progress: {self._snapshot_count} snapshots | "
                f"Elapsed: {elapsed} | DB size: {db_size:.2f} MB"
            )
