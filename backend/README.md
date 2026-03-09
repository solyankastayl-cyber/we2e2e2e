# TA Trading Engine

Technical Analysis Trading Engine with calibration loop, regime validation, and cross-asset support.

## Quick Start

```bash
# 1. Bootstrap (first time)
python bootstrap.py

# 2. Start
./start.sh

# Or combined
./start.sh --bootstrap
```

## System Status

```bash
# Check status
./start.sh --status

# Or via API
curl http://localhost:8001/api/system/status
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    TA Engine                            │
├─────────────────────────────────────────────────────────┤
│  Python API (8001)          Node.js TA Engine (3001)    │
│  ├── Calibration            ├── Pattern Detection       │
│  ├── Regime Validation      ├── Scenario Generation     │
│  ├── Strategy Pruning       ├── Decision Engine         │
│  ├── Cross-Asset Validation └── Technical Analysis      │
│  └── Coinbase Provider                                  │
├─────────────────────────────────────────────────────────┤
│                    MongoDB                              │
│  ├── candles (OHLCV data)                              │
│  ├── config (calibration, coinbase)                    │
│  ├── strategies (registry)                             │
│  ├── regime_map (activation map)                       │
│  └── validation (cross-asset results)                  │
└─────────────────────────────────────────────────────────┘
```

## Completed Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 8.6 | Core Calibration Loop | ✅ |
| 8.7 | BTC Re-Validation | ✅ |
| 8.8 | Strategy Pruning | ✅ |
| 8.9 | Regime Validation | ✅ |
| 9.0 | Cross-Asset Validation | ✅ UNIVERSAL |

## API Endpoints

### System
```
GET  /api/system/status      # System status
GET  /api/system/config      # All configuration
```

### Coinbase Data
```
GET  /api/coinbase/ticker/{product_id}   # Live price
GET  /api/coinbase/candles/{product_id}  # OHLCV data
GET  /api/coinbase/products              # Available pairs
```

### Calibration (Phase 8.6)
```
GET  /api/calibration/config    # Calibration config
POST /api/calibration/apply     # Apply filters
POST /api/calibration/batch     # Batch filter
```

### Validation (Phase 8.7)
```
POST /api/revalidation/btc/run    # Run BTC validation
GET  /api/revalidation/btc/summary
```

### Strategy Pruning (Phase 8.8)
```
POST /api/pruning/run           # Run pruning
GET  /api/pruning/summary       # Strategy status
GET  /api/pruning/deprecated    # Deprecated list
POST /api/pruning/check         # Check strategy
```

### Regime Validation (Phase 8.9)
```
POST /api/regime/validate             # Run validation
GET  /api/regime/activation-map       # Full map
GET  /api/regime/{regime}/strategies  # Strategies for regime
POST /api/regime/check                # Check strategy+regime
GET  /api/regime/policy               # Trading policy
```

### Cross-Asset (Phase 9.0)
```
POST /api/crossasset/validate    # Run validation
GET  /api/crossasset/summary     # Results summary
GET  /api/crossasset/comparison  # Comparison matrix
```

### TA Analysis
```
POST /api/ta/analyze          # Run technical analysis
GET  /api/ta/patterns         # Pattern registry
GET  /api/ta/health           # TA engine health
```

## Configuration

### Calibration (Phase 8.6)
- **Volatility Filter**: ATR > SMA(ATR) × 0.8
- **Trend Alignment**: Trade in EMA50/EMA200 direction
- **Volume Breakout**: volume > SMA(volume) × 1.4
- **ATR-based TP/SL**: SL = 1.5×ATR, TP = 2.5×ATR

### Strategy Status (Phase 8.8)
- **APPROVED**: MTF_BREAKOUT, DOUBLE_BOTTOM, DOUBLE_TOP, CHANNEL_BREAKOUT, MOMENTUM_CONTINUATION
- **LIMITED**: HEAD_SHOULDERS, HARMONIC_ABCD, WEDGE_RISING, WEDGE_FALLING
- **DEPRECATED**: LIQUIDITY_SWEEP, RANGE_REVERSAL

### Regime Activation (Phase 8.9)
- **TREND_UP**: 6 strategies ON
- **TREND_DOWN**: 6 strategies ON
- **RANGE**: 3 strategies ON
- **EXPANSION**: 8 strategies ON

### Cross-Asset Results (Phase 9.0)
| Asset | PF | WR | Verdict |
|-------|----|----|---------|
| SOL | 3.24 | 62% | PASS |
| ETH | 2.54 | 57% | PASS |
| SPX | 2.47 | 64% | PASS |
| BTC | 2.24 | 56% | PASS |
| DXY | 2.08 | 60% | PASS |
| GOLD | 1.95 | 60% | PASS |

## Files

```
backend/
├── bootstrap.py           # Bootstrap script
├── start.sh              # Startup script
├── server.py             # Python API
├── src/server.ta.ts      # Node.js TA Engine
├── modules/
│   ├── data/
│   │   └── coinbase_provider.py
│   └── validation/
│       ├── btc_revalidation.py
│       ├── strategy_pruning.py
│       ├── regime_validation.py
│       └── cross_asset_validation.py
├── snapshots/            # Config snapshots
└── data/                 # Historical data
```

## Requirements

- Python 3.10+
- Node.js 20+
- MongoDB 7+

```bash
pip install pymongo httpx fastapi uvicorn
npm install
```
