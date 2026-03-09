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
| S1.3 | Simulated Broker | ⏳ Next |
| S1.4 | Metrics Engine | ⏳ Pending |

### Roadmap
```
CORE INFRASTRUCTURE (DONE)
T0-T6: Complete trading capsule with execution-faithful architecture

SIMULATION ENGINE (IN PROGRESS)
S1.1 Simulation Core        ✅
S1.2 Market Replay          ✅
S1.3 Simulated Broker       ⏳ NEXT
S1.4 Metrics Engine         ⏳

FUTURE PHASES
S2 Strategy Research Lab
S3 Capital Allocation Layer
S4 Strategy Sandbox
S5 Strategy Development
T7 Integration Layer (merge ready)
```

## What's Been Implemented

### S1.1 Simulation Core (2026-03-09)

**SimulationRun** - Configuration and lifecycle:
- strategy_id, asset, market_type, timeframe
- start_date, end_date
- capital_profile (MICRO=$100, SMALL=$1000, MEDIUM=$10000, LARGE=$100000)
- status: CREATED → RUNNING → PAUSED → COMPLETED/FAILED

**SimulationState** - Runtime state:
- equity_usd, cash_usd
- open_positions, open_orders
- realized_pnl, unrealized_pnl
- peak_equity, max_drawdown

**Determinism Guard**:
- SimulationFingerprint (captures all inputs)
- FrozenSimulationConfig (immutable after start)
- Config hash for reproducibility validation

### S1.2 Market Replay Engine (2026-03-09)

**Event-Driven Replay** with deterministic step orchestration:
```
Replay Driver
↓
Market Tick Event
↓
Step Orchestrator (ensures event order)
↓
Strategy Runtime (T6)
↓
Execution Layer (T3)
↓
Risk Layer (T4)
↓
OMS (T2)
↓
Simulated Broker (stub)
↓
State Update
```

**Components**:
- MarketDatasetService: Manages OHLCV data
- ReplayCursorService: Tracks replay position
- StepOrchestratorService: Ensures deterministic event order
- ReplayDriverService: Controls replay execution

**Replay Modes**:
- STEP: Manual step-by-step
- AUTO: Automatic replay
- FAST: Maximum speed

### API Endpoints (S1)

```
# Health
GET  /api/trading/simulation/health

# Run Management
POST /api/trading/simulation/runs                  - Create simulation
GET  /api/trading/simulation/runs                  - List simulations  
GET  /api/trading/simulation/runs/{runId}          - Get simulation
POST /api/trading/simulation/runs/{runId}/start    - Start (freeze config)
POST /api/trading/simulation/runs/{runId}/run      - Run full simulation
POST /api/trading/simulation/runs/{runId}/pause    - Pause
POST /api/trading/simulation/runs/{runId}/resume   - Resume
POST /api/trading/simulation/runs/{runId}/stop     - Stop

# Step Control
POST /api/trading/simulation/runs/{runId}/step     - Single step

# State
GET  /api/trading/simulation/runs/{runId}/state    - Current state
GET  /api/trading/simulation/runs/{runId}/positions - Positions
GET  /api/trading/simulation/runs/{runId}/equity   - Equity history

# Determinism
GET  /api/trading/simulation/runs/{runId}/fingerprint - Fingerprint
```

## File Structure

```
/app/backend/modules/trading_capsule/
├── simulation/                    # S1 Trading Simulation Engine
│   ├── __init__.py
│   ├── simulation_types.py        # All types and enums
│   ├── simulation_run_service.py  # S1.1 Run Manager
│   ├── simulation_state_service.py # S1.1 State Manager
│   ├── simulation_determinism_service.py # S1.1 Determinism Guard
│   ├── simulation_engine.py       # Main engine
│   ├── simulation_routes.py       # REST API
│   └── replay/                    # S1.2 Market Replay
│       ├── __init__.py
│       ├── dataset_service.py     # Market data
│       ├── cursor_service.py      # Replay position
│       ├── orchestrator_service.py # Step orchestration
│       └── driver_service.py      # Replay control
├── strategy/                      # T6 Strategy Runtime
├── terminal/                      # T5 Terminal Backend
├── execution/                     # T3 Execution Layer
├── risk/                          # T4 Risk Control
├── orders/                        # T2 OMS
└── broker/                        # T1 Broker Layer
```

## Key Architecture Decisions

### Execution-Faithful Simulation
Simulation uses the SAME pipeline as real trading:
```
Signal → T6 Strategy → T3 Execution → T4 Risk → T2 OMS → Broker
```
Only the Broker Adapter changes: Real vs Simulated.

### Determinism Rules
1. Fixed event order per step (MARKET_TICK → STRATEGY_ACTION → ... → STEP_COMPLETED)
2. No real time usage (only replay timestamp)
3. No live data access in simulation mode
4. Config frozen at start

### Capital Profiles
| Profile | Amount |
|---------|--------|
| MICRO | $100 |
| SMALL | $1,000 |
| MEDIUM | $10,000 |
| LARGE | $100,000 |

## Next Steps

### S1.3 Simulated Broker Adapter (P1)
- Order submission simulation
- Fill simulation (market/limit)
- Position tracking
- PnL calculation
- Slippage model

### S1.4 Metrics Engine (P2)
- Equity curve
- Drawdown tracking
- Win rate, profit factor
- Sharpe ratio
- Trade analytics

## Testing

### Test Coverage
- T0-T6: 100%
- S1.1 Simulation Core: 100%
- S1.2 Market Replay: 100%
- Overall: 100%

## Date
Last Updated: 2026-03-09
