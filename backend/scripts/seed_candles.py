"""
Candles Seed Script - Generate realistic synthetic candles
Based on historical BTC price patterns
"""

import os
import random
import math
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, ASCENDING

# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "ta_engine")

# Assets to seed
ASSETS = {
    "BTCUSDT": {"base": 42000, "volatility": 0.025, "trend": 0.0002},
    "ETHUSDT": {"base": 2400, "volatility": 0.03, "trend": 0.0001},
    "BNBUSDT": {"base": 310, "volatility": 0.028, "trend": 0.00015},
    "SOLUSDT": {"base": 100, "volatility": 0.035, "trend": 0.00018},
}

TIMEFRAMES = {
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


def generate_candles(asset: str, tf: str, start_date: datetime, end_date: datetime):
    """Generate realistic OHLCV data"""
    
    config = ASSETS[asset]
    tf_ms = TIMEFRAMES[tf]
    
    candles = []
    price = config["base"]
    
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)
    
    current_ts = start_ts
    
    # Use fixed seed for reproducibility
    rng = random.Random(hash(f"{asset}_{tf}"))
    
    while current_ts < end_ts:
        # Random walk with trend and mean reversion
        trend_factor = config["trend"]
        vol = config["volatility"]
        
        # Add some cyclical patterns (bull/bear cycles)
        cycle_phase = math.sin(current_ts / (90 * 24 * 60 * 60 * 1000) * 2 * math.pi)
        trend_adj = trend_factor * (1 + cycle_phase * 0.5)
        
        # Daily volatility pattern (higher volatility at certain times)
        hour = (current_ts // (60 * 60 * 1000)) % 24
        vol_adj = vol * (1.2 if 14 <= hour <= 18 else 0.8 if 2 <= hour <= 6 else 1.0)
        
        # Random change
        change = (rng.gauss(0, 1) * vol_adj) + trend_adj
        
        # Mean reversion
        mean_rev = (config["base"] - price) / config["base"] * 0.02
        change += mean_rev
        
        # Apply change
        price = price * (1 + change)
        price = max(price, config["base"] * 0.3)  # Floor
        price = min(price, config["base"] * 3.0)  # Ceiling
        
        # Generate OHLC
        open_price = price
        range_pct = 0.005 + rng.random() * 0.02  # 0.5-2.5% range
        range_abs = open_price * range_pct
        
        # Determine candle direction
        is_bullish = rng.random() > 0.48  # Slight bull bias
        
        if is_bullish:
            high = open_price + range_abs * (0.6 + rng.random() * 0.4)
            low = open_price - range_abs * rng.random() * 0.4
            close = low + (high - low) * (0.6 + rng.random() * 0.4)
        else:
            high = open_price + range_abs * rng.random() * 0.4
            low = open_price - range_abs * (0.6 + rng.random() * 0.4)
            close = low + (high - low) * rng.random() * 0.4
        
        # Volume (correlated with price movement)
        base_volume = 1000000 if "BTC" in asset else 500000 if "ETH" in asset else 100000
        volume = base_volume * (0.5 + rng.random() * 1.5) * (1 + abs(change) * 10)
        
        candles.append({
            "asset": asset,
            "tf": tf,
            "ts": current_ts,
            "open": round(open_price, 2),
            "high": round(max(open_price, high, close), 2),
            "low": round(min(open_price, low, close), 2),
            "close": round(close, 2),
            "volume": round(volume, 2),
        })
        
        price = close
        current_ts += tf_ms
    
    return candles


def main():
    print(f"[MONGO] Connecting to {MONGO_URL}/{DB_NAME}")
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    collection = db["ta_candles"]
    
    # Create indexes
    collection.create_index([("asset", ASCENDING), ("tf", ASCENDING), ("ts", ASCENDING)], unique=True)
    print("[INDEX] Created compound index on (asset, tf, ts)")
    
    # Date range: 2017-01-01 to now
    start_date = datetime(2017, 1, 1, tzinfo=timezone.utc)
    end_date = datetime.now(timezone.utc)
    
    total = 0
    
    for asset in ASSETS:
        for tf in TIMEFRAMES:
            print(f"[GENERATE] {asset} {tf}...")
            
            candles = generate_candles(asset, tf, start_date, end_date)
            
            # Clear existing
            collection.delete_many({"asset": asset, "tf": tf})
            
            # Insert
            if candles:
                collection.insert_many(candles)
                total += len(candles)
                print(f"  Inserted {len(candles)} candles")
    
    print(f"\n[COMPLETE] Total: {total} candles")
    
    # Show stats
    stats = list(collection.aggregate([
        {"$group": {"_id": {"asset": "$asset", "tf": "$tf"}, "count": {"$sum": 1}}},
        {"$sort": {"_id.asset": 1, "_id.tf": 1}}
    ]))
    
    print("\n[COLLECTION STATS]")
    for s in stats:
        print(f"  {s['_id']['asset']} {s['_id']['tf']}: {s['count']} candles")


if __name__ == "__main__":
    main()
