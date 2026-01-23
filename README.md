# VALR Orderbook Recorder

Real-time orderbook data collector for VALR exchange - Collects orderbook data via WebSocket and stores to SQLite database.

## Features

- **Real-time Collection**: Connect to VALR exchange via WebSocket and subscribe to orderbook updates
- **Multi-Pair Support**: Collect data for multiple trading pairs simultaneously (USDT-ZAR, SOL-ZAR, ETH-ZAR, BTC-ZAR, XRP-ZAR, BNB-ZAR)
- **Configurable Depth**: Support configurable collection depth (default 10 levels)
- **Persistent Storage**: Store data to SQLite database for long-term operation
- **Auto Reconnect**: Automatic reconnection mechanism on disconnection
- **Data Export**: Support export to CSV format
- **Statistics Query**: Built-in data statistics and query tools

## Project Structure

```
valr_orderbook_collector/
├── run_recorder.py              # Single-pair collector
├── run_multi_pair_recorder.py   # Multi-pair concurrent collector (recommended)
├── query_data.py                # Data query and export tool
├── requirements.txt             # Python dependencies
├── README.md                    # This document
└── valr_orderbook_recorder/     # Core module
    ├── __init__.py
    ├── database.py              # SQLite database operations
    └── websocket_collector.py   # WebSocket collector
```

## Installation

```bash
cd valr_orderbook_collector
pip install -r requirements.txt
```

## Usage

### Start Multi-Pair Collector (Recommended)

```bash
# Collect all default trading pairs (USDT-ZAR, SOL-ZAR, ETH-ZAR, BTC-ZAR, XRP-ZAR, BNB-ZAR)
python run_multi_pair_recorder.py

# Collect specific trading pairs
python run_multi_pair_recorder.py --pairs BTC-ZAR ETH-ZAR SOL-ZAR

# Custom duration and depth
python run_multi_pair_recorder.py --days 30 --depth 20

# Run in background
nohup python run_multi_pair_recorder.py > recorder.log 2>&1 &
```

### Start Single-Pair Collector

```bash
# Default: collect BTC-ZAR for 90 days
python run_recorder.py

# Custom trading pair and duration
python run_recorder.py --pair ETH-ZAR --days 7 --depth 20

# Run in background
nohup python run_recorder.py > recorder.log 2>&1 &
```

### Query Data

```bash
# View statistics for all trading pairs
python query_data.py stats --all

# View statistics for specific trading pair
python query_data.py stats --pair BTC-ZAR

# Export all data for specific trading pair to CSV
python query_data.py export --pair BTC-ZAR --output btc_data.csv

# Export specific date range
python query_data.py export --pair ETH-ZAR --start 2025-01-21 --end 2025-01-22 --output eth_day1.csv

# Query recent snapshots
python query_data.py query --pair SOL-ZAR --limit 100
```

## Data Format

### Database Table Structure

**orderbook_snapshots** - Orderbook snapshot table
| Field | Type | Description |
|------|------|------|
| id | INTEGER | Primary key |
| timestamp | DATETIME | Timestamp |
| trading_pair | TEXT | Trading pair (e.g. BTC-ZAR) |
| sequence_number | INTEGER | Exchange sequence number |
| bids | TEXT | Bid side JSON (price, quantity) |
| asks | TEXT | Ask side JSON (price, quantity) |
| bid_depth | REAL | Bid depth (total value) |
| ask_depth | REAL | Ask depth (total value) |
| spread | REAL | Bid-ask spread |
| mid_price | REAL | Mid price |

### CSV Export Format

Exported CSV files contain the following columns:
- Basic info: id, timestamp, trading_pair, sequence_number
- Calculated metrics: spread, mid_price, bid_depth, ask_depth
- 10-level orderbook: bid1_price, bid1_qty, bid2_price, bid2_qty, ..., ask1_price, ask1_qty, ...

## Technical Details

- WebSocket endpoint: `wss://api.valr.com/ws/trade`
- Subscription event: `FULL_ORDERBOOK_UPDATE`
- Database: SQLite (lightweight, no additional services required)
- Concurrent collection: Multi-pair concurrent collection using asyncio
- Database files: Each trading pair stored independently (e.g. `data/btc_zar_orderbook.db`)

## Production Deployment

For deploying to AWS EC2 or other cloud servers for 24/7 data collection, refer to:

📋 **[Deployment Checklist](DEPLOYMENT_CHECKLIST.md)** - One-page deployment steps (recommended)

📖 **[AWS EC2 Deployment Guide](AWS_DEPLOYMENT_GUIDE.md)** - Complete deployment guide (695 lines of detailed instructions)

📦 **[S3 Export Configuration Guide](S3_EXPORT_GUIDE.md)** - S3 weekly export and data access
