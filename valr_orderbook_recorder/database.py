# valr_orderbook_recorder/database.py
"""
SQLite Database Model for Orderbook Data Storage
SQLite 数据库模型 - 用于存储订单簿数据

本模块提供 OrderbookDatabase 类，负责:
1. 数据库初始化和表结构创建
2. 订单簿快照的插入和查询
3. 采集会话的管理
4. 数据导出功能 (CSV)

数据库表结构:
- orderbook_snapshots: 存储每个订单簿快照
- recording_sessions: 记录采集会话元数据
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional
import json


class OrderbookDatabase:
    """
    SQLite 数据库操作类

    负责订单簿数据的持久化存储，包括:
    - 快照数据的插入和查询
    - 自动计算衍生指标 (价差、中间价、深度)
    - 支持按时间范围查询和导出
    """

    def __init__(self, db_path: str = "orderbook_data.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """
        初始化数据库表结构

        创建两个表:
        1. orderbook_snapshots - 订单簿快照主表
        2. recording_sessions - 采集会话记录表

        同时创建索引以优化查询性能
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Main orderbook snapshots table
            # 订单簿快照主表 - 存储每次订单簿更新的完整数据
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orderbook_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    trading_pair TEXT NOT NULL,
                    sequence_number INTEGER,
                    bids TEXT NOT NULL,
                    asks TEXT NOT NULL,
                    bid_depth REAL,
                    ask_depth REAL,
                    spread REAL,
                    mid_price REAL
                )
            """)

            # Create indexes for efficient querying
            # 创建索引以加速按时间和交易对的查询
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON orderbook_snapshots(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trading_pair
                ON orderbook_snapshots(trading_pair)
            """)

            # Metadata table for recording sessions
            # 采集会话元数据表 - 记录每次采集的开始/结束时间和统计信息
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recording_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    trading_pair TEXT NOT NULL,
                    depth_levels INTEGER NOT NULL,
                    total_snapshots INTEGER DEFAULT 0
                )
            """)

            conn.commit()

    def insert_snapshot(
        self,
        trading_pair: str,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        sequence_number: Optional[int] = None,
        timestamp: Optional[datetime] = None
    ) -> int:
        """
        插入一条订单簿快照

        Args:
            trading_pair: 交易对符号 (如 "BTC-ZAR")
            bids: 买盘列表 [(价格, 数量), ...]，按价格从高到低排序
            asks: 卖盘列表 [(价格, 数量), ...]，按价格从低到高排序
            sequence_number: 交易所序列号 (用于检测数据连续性)
            timestamp: 快照时间戳 (默认为当前 UTC 时间)

        Returns:
            插入记录的 ID

        自动计算的衍生指标:
            - spread: 买卖价差 = best_ask - best_bid
            - mid_price: 中间价 = (best_bid + best_ask) / 2
            - bid_depth: 买盘深度 = sum(price * quantity)
            - ask_depth: 卖盘深度 = sum(price * quantity)
        """
        timestamp = timestamp or datetime.utcnow()

        # Calculate metrics / 计算衍生指标
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        spread = best_ask - best_bid if best_bid and best_ask else None
        mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else None
        bid_depth = sum(p * q for p, q in bids) if bids else 0
        ask_depth = sum(p * q for p, q in asks) if asks else 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orderbook_snapshots
                (timestamp, trading_pair, sequence_number, bids, asks,
                 bid_depth, ask_depth, spread, mid_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp.isoformat(),
                trading_pair,
                sequence_number,
                json.dumps(bids),
                json.dumps(asks),
                bid_depth,
                ask_depth,
                spread,
                mid_price
            ))
            conn.commit()
            return cursor.lastrowid

    def start_session(self, trading_pair: str, depth_levels: int) -> int:
        """开始新的采集会话，返回会话 ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recording_sessions (start_time, trading_pair, depth_levels)
                VALUES (?, ?, ?)
            """, (datetime.utcnow().isoformat(), trading_pair, depth_levels))
            conn.commit()
            return cursor.lastrowid

    def end_session(self, session_id: int, total_snapshots: int):
        """结束采集会话，记录结束时间和快照总数"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE recording_sessions
                SET end_time = ?, total_snapshots = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), total_snapshots, session_id))
            conn.commit()

    def get_snapshot_count(self, trading_pair: Optional[str] = None) -> int:
        """获取快照总数，可按交易对筛选"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if trading_pair:
                cursor.execute(
                    "SELECT COUNT(*) FROM orderbook_snapshots WHERE trading_pair = ?",
                    (trading_pair,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM orderbook_snapshots")
            return cursor.fetchone()[0]

    def get_db_size_mb(self) -> float:
        """获取数据库文件大小 (MB)"""
        if self.db_path.exists():
            return self.db_path.stat().st_size / (1024 * 1024)
        return 0.0

    def query_snapshots(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        trading_pair: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[dict]:
        """
        查询订单簿快照

        Args:
            start_time: 开始时间 (ISO 格式或 YYYY-MM-DD)
            end_time: 结束时间
            trading_pair: 交易对筛选
            limit: 返回记录数限制
            offset: 分页偏移量

        Returns:
            快照字典列表
        """
        query = "SELECT * FROM orderbook_snapshots WHERE 1=1"
        params = []

        if trading_pair:
            query += " AND trading_pair = ?"
            params.append(trading_pair)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp ASC"

        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def export_to_csv(
        self,
        output_path: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        flatten_orderbook: bool = True
    ):
        """
        导出数据到 CSV 文件

        Args:
            output_path: 输出文件路径
            start_time: 开始时间筛选
            end_time: 结束时间筛选
            flatten_orderbook: 是否展开订单簿为独立列
                True: bid1_price, bid1_qty, bid2_price, ... (便于分析)
                False: bids, asks 保持 JSON 格式

        Returns:
            导出的记录数
        """
        import csv

        snapshots = self.query_snapshots(start_time=start_time, end_time=end_time)

        with open(output_path, 'w', newline='') as f:
            if flatten_orderbook:
                # Flatten bids/asks into separate columns
                # 将买卖盘展开为独立列，便于数据分析
                fieldnames = ['id', 'timestamp', 'trading_pair', 'sequence_number',
                              'spread', 'mid_price', 'bid_depth', 'ask_depth']
                for i in range(10):
                    fieldnames.extend([f'bid{i+1}_price', f'bid{i+1}_qty',
                                       f'ask{i+1}_price', f'ask{i+1}_qty'])

                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for snap in snapshots:
                    row = {
                        'id': snap['id'],
                        'timestamp': snap['timestamp'],
                        'trading_pair': snap['trading_pair'],
                        'sequence_number': snap['sequence_number'],
                        'spread': snap['spread'],
                        'mid_price': snap['mid_price'],
                        'bid_depth': snap['bid_depth'],
                        'ask_depth': snap['ask_depth']
                    }
                    bids = json.loads(snap['bids'])
                    asks = json.loads(snap['asks'])
                    for i in range(10):
                        if i < len(bids):
                            row[f'bid{i+1}_price'] = bids[i][0]
                            row[f'bid{i+1}_qty'] = bids[i][1]
                        if i < len(asks):
                            row[f'ask{i+1}_price'] = asks[i][0]
                            row[f'ask{i+1}_qty'] = asks[i][1]
                    writer.writerow(row)
            else:
                fieldnames = ['id', 'timestamp', 'trading_pair', 'sequence_number',
                              'bids', 'asks', 'spread', 'mid_price']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for snap in snapshots:
                    writer.writerow({k: snap[k] for k in fieldnames})

        return len(snapshots)
