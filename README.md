# VALR Orderbook Recorder

VALR 交易所订单簿数据采集器 - 通过 WebSocket 实时采集订单簿数据并存储到 SQLite 数据库。

## 功能特性

- **实时采集**: 通过 WebSocket 连接 VALR 交易所，订阅订单簿更新
- **多交易对支持**: 同时采集多个交易对数据（USDT-ZAR, SOL-ZAR, ETH-ZAR, BTC-ZAR, XRP-ZAR, BNB-ZAR）
- **多档深度**: 支持配置采集深度（默认 10 档）
- **持久存储**: 数据存储到 SQLite 数据库，支持长期运行
- **自动重连**: 断线自动重连机制
- **数据导出**: 支持导出为 CSV 格式
- **统计查询**: 内置数据统计和查询工具

## 项目结构

```
valr-orderbook-recorder/
├── run_recorder.py              # 单交易对采集器
├── run_multi_pair_recorder.py   # 多交易对并发采集器（推荐）
├── query_data.py                # 数据查询和导出工具
├── requirements.txt             # Python 依赖
├── README.md                    # 本文档
└── valr_orderbook_recorder/     # 核心模块
    ├── __init__.py
    ├── database.py              # SQLite 数据库操作
    └── websocket_collector.py   # WebSocket 采集器
```

## 安装

```bash
cd valr-orderbook-recorder
pip install -r requirements.txt
```

## 使用方法

### 启动多交易对采集器（推荐）

```bash
# 采集所有默认交易对（USDT-ZAR, SOL-ZAR, ETH-ZAR, BTC-ZAR, XRP-ZAR, BNB-ZAR）
python run_multi_pair_recorder.py

# 采集指定交易对
python run_multi_pair_recorder.py --pairs BTC-ZAR ETH-ZAR SOL-ZAR

# 自定义时长和深度
python run_multi_pair_recorder.py --days 30 --depth 20

# 后台运行
nohup python run_multi_pair_recorder.py > recorder.log 2>&1 &
```

### 启动单交易对采集器

```bash
# 默认采集 BTC-ZAR，90 天
python run_recorder.py

# 自定义交易对和时长
python run_recorder.py --pair ETH-ZAR --days 7 --depth 20

# 后台运行
nohup python run_recorder.py > recorder.log 2>&1 &
```

### 查询数据

```bash
# 查看所有交易对的统计信息
python query_data.py stats --all

# 查看特定交易对的统计信息
python query_data.py stats --pair BTC-ZAR

# 导出特定交易对的全部数据到 CSV
python query_data.py export --pair BTC-ZAR --output btc_data.csv

# 导出指定日期范围
python query_data.py export --pair ETH-ZAR --start 2025-01-21 --end 2025-01-22 --output eth_day1.csv

# 查询最近的快照
python query_data.py query --pair SOL-ZAR --limit 100
```

## 数据格式

### 数据库表结构

**orderbook_snapshots** - 订单簿快照表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| timestamp | DATETIME | 时间戳 |
| trading_pair | TEXT | 交易对 (如 BTC-ZAR) |
| sequence_number | INTEGER | 交易所序列号 |
| bids | TEXT | 买盘 JSON (价格, 数量) |
| asks | TEXT | 卖盘 JSON (价格, 数量) |
| bid_depth | REAL | 买盘深度 (总价值) |
| ask_depth | REAL | 卖盘深度 (总价值) |
| spread | REAL | 买卖价差 |
| mid_price | REAL | 中间价 |

### CSV 导出格式

导出的 CSV 文件包含以下列：
- 基础信息: id, timestamp, trading_pair, sequence_number
- 计算指标: spread, mid_price, bid_depth, ask_depth
- 10档买卖盘: bid1_price, bid1_qty, bid2_price, bid2_qty, ..., ask1_price, ask1_qty, ...

## 技术说明

- WebSocket 端点: `wss://api.valr.com/ws/trade`
- 订阅事件: `FULL_ORDERBOOK_UPDATE`
- 数据库: SQLite (轻量级，无需额外服务)
- 并发采集: 使用 asyncio 实现多交易对并发采集
- 数据库文件: 每个交易对独立存储（如 `data/btc_zar_orderbook.db`）

## 部署到生产环境

如需部署到 AWS EC2 或其他云服务器进行 24/7 数据采集，请参考：

📖 **[AWS EC2 部署指南](AWS_DEPLOYMENT_GUIDE.md)**

包含完整的部署步骤、监控脚本、故障排查和最佳实践。
