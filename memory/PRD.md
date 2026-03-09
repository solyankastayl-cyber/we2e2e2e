# PRD: Quant Research OS - Trading Capsule

## Project Overview
Quant Research OS - модульная платформа для алгоритмического трейдинга и research.

## Architecture Status

### Trading Capsule Phases
| Phase | Description | Status |
|-------|-------------|--------|
| T0 | Capsule Contract & Boundaries | ✅ 100% |
| T1 | Broker / Account Layer | ✅ 100% |
| T2 | Order Management System | ✅ 100% |
| T3 | Execution Decision Layer | ✅ 100% |
| T4 | Risk Control Layer | ✅ 100% |
| T5 | Terminal Backend | ✅ 100% |
| T6 | Strategy Runtime Engine | ✅ 100% |
| S1.1 | Simulation Core | ✅ 100% |
| S1.2 | Market Replay Engine | ✅ 100% |
| S1.3 | Simulated Broker | ✅ 100% |
| S1.4 | Metrics Engine | ⏳ Next |

### Roadmap
```
CORE INFRASTRUCTURE (DONE)
T0-T6: Complete trading capsule

SIMULATION ENGINE (IN PROGRESS)
S1.1 Simulation Core        ✅
S1.2 Market Replay          ✅
S1.3 Simulated Broker       ✅
S1.4 Metrics Engine         ⏳ NEXT

FUTURE PHASES
S2 Strategy Research Lab
S3 Capital Allocation Layer
S4 Strategy Sandbox
S5 Strategy Development
T7 Integration Layer
```

## What's Been Implemented

### S1.3 Simulated Broker Adapter (2026-03-09)

**Fill Models:**
- `InstantFillModel`: Fill at candle close (simple)
- `SlippageFillModel`: Fill with configurable slippage (0.05% base + size impact)

**Fee Calculator:**
- Maker fee: 0.1%
- Taker fee: 0.1%

**Order Management:**
- Market orders: Immediate fill simulation
- Limit orders: Pending until price touches level
- Order lifecycle: NEW → FILLED/PARTIAL/CANCELLED

**Position Tracking:**
- Entry price averaging on multiple buys
- Unrealized PnL calculation
- Position closing with realized PnL

**Strategy Integration:**
- Signal generation from candle price movements
- Position-aware context building
- Smart signal routing (Manual → MANUAL_SIGNAL_EXECUTOR)

### Full Simulation Pipeline (Execution-Faithful)
```
Market Replay (candle data)
↓
Signal Generation (price momentum)
↓
Strategy Runtime (T6)
  - TA_SIGNAL_FOLLOWER (BULLISH/BEARISH → ENTER/EXIT)
  - MANUAL_SIGNAL_EXECUTOR (direct execution)
↓
Simulated Broker
  - Order submission
  - Fill simulation (slippage + fees)
  - Position management
↓
State Update
  - Equity tracking
  - PnL calculation
  - Drawdown monitoring
```

### API Endpoints (S1)

```
# Simulation Management
POST /api/trading/simulation/runs           - Create
GET  /api/trading/simulation/runs           - List  
GET  /api/trading/simulation/runs/{id}      - Get details
POST /api/trading/simulation/runs/{id}/run  - Run full simulation
POST /api/trading/simulation/runs/{id}/step - Single step

# Trading Data
GET  /api/trading/simulation/runs/{id}/state     - Portfolio state
GET  /api/trading/simulation/runs/{id}/positions - Positions
GET  /api/trading/simulation/runs/{id}/fills     - Fill history
GET  /api/trading/simulation/runs/{id}/orders    - Order history
GET  /api/trading/simulation/runs/{id}/equity    - Equity curve

# Determinism
GET  /api/trading/simulation/runs/{id}/fingerprint - Reproducibility
```

## File Structure

```
/app/backend/modules/trading_capsule/simulation/
├── __init__.py
├── simulation_types.py           # All types
├── simulation_engine.py          # Main engine
├── simulation_routes.py          # REST API
├── simulation_run_service.py     # S1.1 Run Manager
├── simulation_state_service.py   # S1.1 State Manager
├── simulation_determinism_service.py # S1.1 Determinism Guard
├── replay/                       # S1.2 Market Replay
│   ├── dataset_service.py
│   ├── cursor_service.py
│   ├── orchestrator_service.py
│   └── driver_service.py
└── broker/                       # S1.3 Simulated Broker
    ├── __init__.py
    └── simulated_broker.py
```

## Key Architecture Decisions

### Execution-Faithful Simulation
```
Real Trading:  Strategy → Execution → Risk → OMS → Binance
Simulation:    Strategy → Execution → Risk → OMS → SimulatedBroker
```
Only the broker adapter changes!

### Capital Profiles
| Profile | Amount |
|---------|--------|
| MICRO | $100 |
| SMALL | $1,000 |
| MEDIUM | $10,000 |
| LARGE | $100,000 |

### Signal Generation (Simulation)
- Candle close > open by 1% → BULLISH
- Candle close < open by 1% → BEARISH
- Otherwise → NEUTRAL

## Next Steps

### S1.4 Metrics Engine (P1)
- Sharpe ratio calculation
- Profit factor
- Win rate / loss rate
- Average win/loss size
- Trade analytics
- Equity curve smoothing
- Drawdown analysis

### S2 Strategy Research Lab (P2)
- Strategy comparison
- A/B testing
- Performance ranking
- Parameter optimization

## Testing

### Test Coverage
- T0-T6: 100%
- S1.1-S1.3: 100%
- Overall: 100%

## Date
Last Updated: 2026-03-09
