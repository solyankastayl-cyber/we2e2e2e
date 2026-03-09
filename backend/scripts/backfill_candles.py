"""
Candles Backfill Script
Downloads historical OHLCV data from Binance and stores in MongoDB

Usage:
  python scripts/backfill_candles.py --symbols BTCUSDT,ETHUSDT --timeframes 1h,4h,1d --start 2017-01-01
"""

import os
import sys
import time
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any

import requests
from pymongo import MongoClient, ASCENDING
from pymongo.errors import BulkWriteError

# Binance API
BINANCE_API = "https://api.binance.com/api/v3/klines"

# Timeframe to milliseconds
TF_MS = {
    "1m": 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
    "1w": 7 * 24 * 60 * 60 * 1000,
}


def fetch_klines(
    symbol: str,
    interval: str,
    start_time: int,
    end_time: int = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """Fetch klines from Binance"""
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "limit": limit
    }
    if end_time:
        params["endTime"] = end_time
    
    try:
        response = requests.get(BINANCE_API, params=params, timeout=30)
        response.raise_for_status()
        
        candles = []
        for k in response.json():
            candles.append({
                "asset": symbol,
                "tf": interval,
                "ts": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "close_time": k[6],
                "quote_volume": float(k[7]),
                "trades": k[8],
            })
        return candles
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch {symbol} {interval}: {e}")
        return []


def backfill_symbol(
    db,
    symbol: str,
    interval: str,
    start_date: datetime,
    end_date: datetime = None
):
    """Backfill candles for a symbol/interval"""
    
    collection = db["ta_candles"]
    
    # Ensure indexes
    collection.create_index([("asset", ASCENDING), ("tf", ASCENDING), ("ts", ASCENDING)], unique=True)
    
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int((end_date or datetime.now(timezone.utc)).timestamp() * 1000)
    
    tf_ms = TF_MS.get(interval, 24 * 60 * 60 * 1000)
    
    print(f"[BACKFILL] {symbol} {interval}: {start_date.date()} -> {datetime.fromtimestamp(end_ts/1000, tz=timezone.utc).date()}")
    
    current_ts = start_ts
    total_inserted = 0
    total_skipped = 0
    
    while current_ts < end_ts:
        candles = fetch_klines(symbol, interval, current_ts, end_ts)
        
        if not candles:
            print(f"[INFO] No more candles for {symbol} {interval}")
            break
        
        # Bulk insert
        try:
            result = collection.insert_many(candles, ordered=False)
            total_inserted += len(result.inserted_ids)
        except BulkWriteError as e:
            total_inserted += e.details.get("nInserted", 0)
            total_skipped += len(candles) - e.details.get("nInserted", 0)
        
        # Move to next batch
        last_ts = candles[-1]["ts"]
        current_ts = last_ts + tf_ms
        
        # Rate limiting
        time.sleep(0.2)
        
        if total_inserted % 5000 == 0 and total_inserted > 0:
            print(f"  Progress: {total_inserted} inserted, {total_skipped} skipped")
    
    print(f"[DONE] {symbol} {interval}: {total_inserted} inserted, {total_skipped} skipped")
    return total_inserted


def main():
    parser = argparse.ArgumentParser(description="Backfill candles from Binance")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT",
                       help="Comma-separated symbols")
    parser.add_argument("--timeframes", default="1h,4h,1d",
                       help="Comma-separated timeframes")
    parser.add_argument("--start", default="2020-01-01",
                       help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None,
                       help="End date (YYYY-MM-DD), defaults to now")
    parser.add_argument("--mongo-url", default=None,
                       help="MongoDB URL")
    
    args = parser.parse_args()
    
    # Connect to MongoDB
    mongo_url = args.mongo_url or os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "ta_engine")
    
    print(f"[MONGO] Connecting to {mongo_url}/{db_name}")
    client = MongoClient(mongo_url)
    db = client[db_name]
    
    # Parse dates
    start_date = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_date = None
    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    timeframes = [t.strip() for t in args.timeframes.split(",")]
    
    print(f"[CONFIG] Symbols: {symbols}")
    print(f"[CONFIG] Timeframes: {timeframes}")
    print(f"[CONFIG] Start: {start_date.date()}")
    print()
    
    total = 0
    for symbol in symbols:
        for tf in timeframes:
            count = backfill_symbol(db, symbol, tf, start_date, end_date)
            total += count
    
    print()
    print(f"[COMPLETE] Total candles inserted: {total}")
    
    # Show collection stats
    stats = db["ta_candles"].aggregate([
        {"$group": {"_id": {"asset": "$asset", "tf": "$tf"}, "count": {"$sum": 1}}},
        {"$sort": {"_id.asset": 1, "_id.tf": 1}}
    ])
    
    print()
    print("[COLLECTION STATS]")
    for s in stats:
        print(f"  {s['_id']['asset']} {s['_id']['tf']}: {s['count']} candles")


if __name__ == "__main__":
    main()
