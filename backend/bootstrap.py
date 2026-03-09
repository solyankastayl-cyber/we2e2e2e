#!/usr/bin/env python3
"""
TA Engine Bootstrap System v2
=============================

Быстрое развёртывание TA Engine с:
- MongoDB коллекции
- Исторические данные (BTC, SPX, DXY, GOLD)
- Calibration конфиг (Phase 8.6)
- Strategy registry (Phase 8.8)
- Regime activation map (Phase 8.9)
- Cross-asset baseline (Phase 9.0)
- Coinbase provider setup

БЕЗ фрактал логики - только OHLCV данные и наши модули.

Usage:
    python bootstrap.py                 # Full bootstrap
    python bootstrap.py --status        # Check status
    python bootstrap.py --reset         # Reset and rebuild
"""

import os
import sys
import json
import csv
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

# Project root
PROJECT_ROOT = Path(__file__).parent

# MongoDB
try:
    from pymongo import MongoClient
    MONGO_OK = True
except ImportError:
    MONGO_OK = False


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

MONGO_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "ta_engine"

# Data sources - Use frozen canonical datasets (v1)
DATASETS_DIR = PROJECT_ROOT / "datasets"
DATA_FILES = {
    "BTC": DATASETS_DIR / "btc_daily_v1.csv",
    "SPX": DATASETS_DIR / "spx_daily_v1.csv",
    "DXY": DATASETS_DIR / "dxy_daily_v1.csv",
}

# ═══════════════════════════════════════════════════════════════
# Phase 8.6 — Calibration Config
# ═══════════════════════════════════════════════════════════════

CALIBRATION_CONFIG = {
    "version": "phase8.6",
    "enabled": True,
    
    # Volatility Filter: ATR > SMA(ATR) * 0.8
    "volatilityFilter": {
        "enabled": True,
        "atrMultiplier": 0.8,
        "atrPeriod": 14,
        "smaPeriod": 14
    },
    
    # Trend Alignment: Trade in EMA50/EMA200 direction
    "trendAlignment": {
        "enabled": True,
        "emaShortPeriod": 50,
        "emaLongPeriod": 200,
        "requireBothAligned": False
    },
    
    # Volume Breakout: volume > SMA(volume) * 1.4
    "volumeBreakout": {
        "enabled": True,
        "volumeMultiplier": 1.4,
        "smaPeriod": 20
    },
    
    # ATR-based TP/SL: SL=1.5*ATR, TP=2.5*ATR
    "atrRiskManagement": {
        "enabled": True,
        "stopLossATR": 1.5,
        "takeProfitATR": 2.5
    },
    
    # Disabled weak strategies
    "disabledStrategies": [
        "LIQUIDITY_SWEEP",
        "LIQUIDITY_SWEEP_HIGH",
        "LIQUIDITY_SWEEP_LOW",
        "RANGE_REVERSAL"
    ]
}

# ═══════════════════════════════════════════════════════════════
# Phase 8.8 — Strategy Registry
# ═══════════════════════════════════════════════════════════════

STRATEGIES = [
    # APPROVED - Production ready
    {"id": "MTF_BREAKOUT", "status": "APPROVED", "wr": 0.64, "pf": 2.1},
    {"id": "DOUBLE_BOTTOM", "status": "APPROVED", "wr": 0.66, "pf": 2.3},
    {"id": "DOUBLE_TOP", "status": "APPROVED", "wr": 0.63, "pf": 2.0},
    {"id": "CHANNEL_BREAKOUT", "status": "APPROVED", "wr": 0.58, "pf": 1.8},
    {"id": "MOMENTUM_CONTINUATION", "status": "APPROVED", "wr": 0.62, "pf": 1.9},
    
    # LIMITED - Conditional use
    {"id": "HEAD_SHOULDERS", "status": "LIMITED", "wr": 0.52, "pf": 1.25},
    {"id": "HARMONIC_ABCD", "status": "LIMITED", "wr": 0.54, "pf": 1.4},
    {"id": "WEDGE_RISING", "status": "LIMITED", "wr": 0.51, "pf": 1.15},
    {"id": "WEDGE_FALLING", "status": "LIMITED", "wr": 0.53, "pf": 1.2},
    
    # DEPRECATED - Removed from production
    {"id": "LIQUIDITY_SWEEP", "status": "DEPRECATED", "reason": "WR 37-46%"},
    {"id": "RANGE_REVERSAL", "status": "DEPRECATED", "reason": "WR 34-38%"},
]

# ═══════════════════════════════════════════════════════════════
# Phase 8.9 — Regime Activation Map
# ═══════════════════════════════════════════════════════════════

REGIME_MAP = {
    #                    TREND_UP  TREND_DOWN  RANGE   COMPRESSION  EXPANSION
    "MTF_BREAKOUT":      ["ON",    "ON",       "WATCH", "WATCH",    "ON"],
    "DOUBLE_BOTTOM":     ["ON",    "LIMITED",  "ON",    "LIMITED",  "ON"],
    "DOUBLE_TOP":        ["WATCH", "ON",       "ON",    "LIMITED",  "ON"],
    "CHANNEL_BREAKOUT":  ["ON",    "ON",       "OFF",   "LIMITED",  "ON"],
    "MOMENTUM_CONT":     ["ON",    "ON",       "OFF",   "OFF",      "ON"],
    "HEAD_SHOULDERS":    ["OFF",   "ON",       "WATCH", "WATCH",    "ON"],
    "HARMONIC_ABCD":     ["ON",    "LIMITED",  "ON",    "LIMITED",  "LIMITED"],
    "WEDGE_RISING":      ["OFF",   "ON",       "WATCH", "LIMITED",  "LIMITED"],
    "WEDGE_FALLING":     ["ON",    "OFF",      "WATCH", "LIMITED",  "ON"],
}

REGIMES = ["TREND_UP", "TREND_DOWN", "RANGE", "COMPRESSION", "EXPANSION"]

# ═══════════════════════════════════════════════════════════════
# Phase 9.0 — Cross-Asset Baseline
# ═══════════════════════════════════════════════════════════════

CROSS_ASSET_RESULTS = {
    "systemVerdict": "UNIVERSAL",
    "assets": {
        "BTC": {"verdict": "PASS", "pf": 2.24, "wr": 0.56},
        "ETH": {"verdict": "PASS", "pf": 2.54, "wr": 0.57},
        "SOL": {"verdict": "PASS", "pf": 3.24, "wr": 0.62},
        "SPX": {"verdict": "PASS", "pf": 2.47, "wr": 0.64},
        "GOLD": {"verdict": "PASS", "pf": 1.95, "wr": 0.60},
        "DXY": {"verdict": "PASS", "pf": 2.08, "wr": 0.60},
    }
}

# ═══════════════════════════════════════════════════════════════
# Coinbase Provider Config
# ═══════════════════════════════════════════════════════════════

COINBASE_CONFIG = {
    "provider": "coinbase",
    "baseUrl": "https://api.exchange.coinbase.com",
    "endpoints": {
        "candles": "/products/{product_id}/candles",
        "ticker": "/products/{product_id}/ticker",
        "products": "/products"
    },
    "supportedPairs": [
        "BTC-USD", "ETH-USD", "SOL-USD",
        "BTC-USDT", "ETH-USDT", "SOL-USDT"
    ],
    "granularities": {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400
    }
}


# ═══════════════════════════════════════════════════════════════
# Bootstrap Class
# ═══════════════════════════════════════════════════════════════

class Bootstrap:
    def __init__(self):
        self.client = None
        self.db = None
    
    def connect(self) -> bool:
        if not MONGO_OK:
            print("❌ pymongo not installed: pip install pymongo")
            return False
        
        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client[DB_NAME]
            print(f"✅ MongoDB connected: {DB_NAME}")
            return True
        except Exception as e:
            print(f"❌ MongoDB error: {e}")
            return False
    
    def init_collections(self):
        """Create collections and indexes"""
        print("\n📦 Collections...")
        
        collections = ["candles", "config", "strategies", "regime_map", "validation"]
        
        for name in collections:
            if name not in self.db.list_collection_names():
                self.db.create_collection(name)
                print(f"  + {name}")
            else:
                print(f"  ✓ {name}")
        
        # Indexes
        self.db.candles.create_index([("symbol", 1), ("timeframe", 1), ("timestamp", -1)])
        print("  ✓ indexes")
    
    def load_candles(self):
        """Load OHLCV data from CSV"""
        print("\n📊 Loading candles...")
        
        for symbol, filepath in DATA_FILES.items():
            if not filepath.exists():
                print(f"  ⚠ {symbol}: file not found")
                continue
            
            # Check existing
            count = self.db.candles.count_documents({"symbol": symbol})
            if count > 1000:
                print(f"  ✓ {symbol}: {count} candles (cached)")
                continue
            
            # Parse CSV
            candles = self._parse_csv(symbol, filepath)
            
            if candles:
                # Batch insert
                for i in range(0, len(candles), 1000):
                    self.db.candles.insert_many(candles[i:i+1000])
                print(f"  + {symbol}: {len(candles)} candles")
    
    def _parse_csv(self, symbol: str, filepath: Path) -> List[dict]:
        """Parse CSV file - canonical format: date,open,high,low,close,volume"""
        candles = []
        
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    date_str = row.get('date', '')
                    if not date_str:
                        continue
                    
                    # Parse YYYY-MM-DD format
                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                    ts = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
                    
                    candles.append({
                        "symbol": symbol,
                        "timeframe": "1d",
                        "timestamp": ts,
                        "open": float(row['open']),
                        "high": float(row['high']),
                        "low": float(row['low']),
                        "close": float(row['close']),
                        "volume": float(row.get('volume', 0)),
                    })
                except Exception as e:
                    continue
        
        return candles
    
    def init_config(self):
        """Save calibration config"""
        print("\n⚙️  Config...")
        
        self.db.config.update_one(
            {"_id": "calibration"},
            {"$set": {"_id": "calibration", **CALIBRATION_CONFIG}},
            upsert=True
        )
        print("  ✓ calibration (Phase 8.6)")
        
        self.db.config.update_one(
            {"_id": "coinbase"},
            {"$set": {"_id": "coinbase", **COINBASE_CONFIG}},
            upsert=True
        )
        print("  ✓ coinbase provider")
    
    def init_strategies(self):
        """Save strategy registry"""
        print("\n📋 Strategies...")
        
        for s in STRATEGIES:
            self.db.strategies.update_one(
                {"id": s["id"]},
                {"$set": s},
                upsert=True
            )
        
        approved = len([s for s in STRATEGIES if s["status"] == "APPROVED"])
        limited = len([s for s in STRATEGIES if s["status"] == "LIMITED"])
        deprecated = len([s for s in STRATEGIES if s["status"] == "DEPRECATED"])
        
        print(f"  ✓ {approved} APPROVED, {limited} LIMITED, {deprecated} DEPRECATED")
    
    def init_regime_map(self):
        """Save regime activation map"""
        print("\n🎯 Regime Map...")
        
        for strategy_id, activations in REGIME_MAP.items():
            regime_dict = dict(zip(REGIMES, activations))
            self.db.regime_map.update_one(
                {"strategyId": strategy_id},
                {"$set": {"strategyId": strategy_id, "activations": regime_dict}},
                upsert=True
            )
        
        print(f"  ✓ {len(REGIME_MAP)} strategies × {len(REGIMES)} regimes")
    
    def init_validation(self):
        """Save cross-asset validation baseline"""
        print("\n📈 Validation Baseline...")
        
        self.db.validation.update_one(
            {"_id": "phase9.0"},
            {"$set": {"_id": "phase9.0", **CROSS_ASSET_RESULTS}},
            upsert=True
        )
        print(f"  ✓ Phase 9.0: {CROSS_ASSET_RESULTS['systemVerdict']}")
    
    def save_snapshots(self):
        """Save JSON snapshots"""
        print("\n💾 Snapshots...")
        
        snapshots_dir = PROJECT_ROOT / "snapshots"
        snapshots_dir.mkdir(exist_ok=True)
        
        files = {
            "calibration.json": CALIBRATION_CONFIG,
            "strategies.json": STRATEGIES,
            "regime_map.json": REGIME_MAP,
            "cross_asset.json": CROSS_ASSET_RESULTS,
            "coinbase.json": COINBASE_CONFIG,
        }
        
        for filename, data in files.items():
            with open(snapshots_dir / filename, 'w') as f:
                json.dump(data, f, indent=2)
        
        print(f"  ✓ Saved to {snapshots_dir}")
    
    def status(self):
        """Print system status"""
        if not self.connect():
            return
        
        print("\n" + "=" * 50)
        print("TA ENGINE STATUS")
        print("=" * 50)
        
        # Candles
        print("\n📊 Candles:")
        for symbol in ["BTC", "SPX", "DXY"]:
            count = self.db.candles.count_documents({"symbol": symbol})
            print(f"  {symbol}: {count}")
        
        # Config
        print("\n⚙️  Config:")
        cal = self.db.config.find_one({"_id": "calibration"})
        print(f"  Calibration: {'✅' if cal else '❌'}")
        cb = self.db.config.find_one({"_id": "coinbase"})
        print(f"  Coinbase: {'✅' if cb else '❌'}")
        
        # Strategies
        strat_count = self.db.strategies.count_documents({})
        print(f"\n📋 Strategies: {strat_count}")
        
        # Regime
        regime_count = self.db.regime_map.count_documents({})
        print(f"🎯 Regime Map: {regime_count}")
        
        # Validation
        val = self.db.validation.find_one({"_id": "phase9.0"})
        print(f"📈 Validation: {'✅ ' + val.get('systemVerdict', '') if val else '❌'}")
    
    def reset(self):
        """Drop and rebuild"""
        if not self.connect():
            return
        
        print("\n⚠️  Resetting database...")
        self.client.drop_database(DB_NAME)
        print("  ✓ Database dropped")
        
        self.db = self.client[DB_NAME]
        self.run()
    
    def run(self):
        """Full bootstrap"""
        print("\n" + "=" * 50)
        print("TA ENGINE BOOTSTRAP")
        print("=" * 50)
        
        if not self.connect():
            return
        
        self.init_collections()
        self.load_candles()
        self.init_config()
        self.init_strategies()
        self.init_regime_map()
        self.init_validation()
        self.save_snapshots()
        
        print("\n" + "=" * 50)
        print("✅ BOOTSTRAP COMPLETE")
        print("=" * 50)
        
        self.status()


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="TA Engine Bootstrap")
    parser.add_argument("--status", action="store_true", help="Check status")
    parser.add_argument("--reset", action="store_true", help="Reset and rebuild")
    args = parser.parse_args()
    
    bootstrap = Bootstrap()
    
    if args.status:
        bootstrap.status()
    elif args.reset:
        bootstrap.reset()
    else:
        bootstrap.run()


if __name__ == "__main__":
    main()
