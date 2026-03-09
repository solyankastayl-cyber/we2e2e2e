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
| T6 | Strategy Logic Layer | ⏳ Next |
| T7 | Merge-Ready Contracts | ⏳ Pending |

### System Progress
- Research Infrastructure: 100%
- Backend Architecture: 100%
- Trading Capsule: 85% (T0-T5 done)
- Terminal Backend: 100%

## What's Been Implemented

### Trading Capsule T0-T4 (Previously Completed)
- T0: Contracts & Boundaries (Execution/Trading modes, Core entities)
- T1: Broker/Account Layer (Connection registry, adapters, health checks)
- T2: Order Management System (Orders, fills, trades, PnL tracking)
- T3: Execution Decision Layer (Signal normalization, intent building, preview)
- T4: Risk Control Layer (Pre-trade validation, exposure, averaging, drawdown)

### Trading Capsule T5: Terminal Backend (2026-03-09)

#### Architecture
T5 is the admin monitoring and control layer. It aggregates data from all subsystems:

```
Signal → T3 Execution → T4 Risk → T2 OMS → Broker → Exchange
                           ↓
                    T5 Terminal Backend
                   (monitoring + control)
```

#### Subsystems

**1. Account Monitor**
- AccountOverview entity with equity, balances, status, health
- Tracks open positions and orders per connection

**2. Positions Monitor**
- PositionView with unrealized PnL, exposure calculations
- Current price tracking for valuation

**3. Orders Monitor**
- OrderView with fill status, commission, source tracking
- Filters: open orders, order history

**4. PnL Engine**
- PnLView with realized/unrealized/total PnL
- Win rate, avg win/loss, profit factor
- Daily PnL tracking

**5. Execution Log**
- ExecutionLogEntry for all system events
- Event types: DECISION, INTENT_CREATED, RISK_BLOCKED, ORDER_SENT, ORDER_FILLED, etc.
- Severity levels: INFO, WARNING, ERROR

**6. Risk Monitor**
- RiskOverview aggregating T4 state
- Current exposure, drawdown, blocked trades

**7. Averaging Monitor**
- AveragingView with steps, capital, price distance
- Next entry trigger price calculation

**8. System State**
- TradingSystemState with mode, pause, kill switch status
- Connection counts, daily stats, uptime

**9. Terminal Actions**
- Pause/Resume trading
- Kill switch activate/deactivate
- Close position
- Cancel order/all orders

#### API Endpoints

```
# Health
GET  /api/trading/terminal/health

# Account Monitor
GET  /api/trading/terminal/accounts
GET  /api/trading/terminal/accounts/{connection_id}

# Positions Monitor
GET  /api/trading/terminal/positions
GET  /api/trading/terminal/positions/{asset}

# Orders Monitor
GET  /api/trading/terminal/orders
GET  /api/trading/terminal/orders/open
GET  /api/trading/terminal/orders/history

# PnL Engine
GET  /api/trading/terminal/pnl
GET  /api/trading/terminal/pnl/daily
GET  /api/trading/terminal/pnl/history

# Execution Log
GET  /api/trading/terminal/logs
GET  /api/trading/terminal/logs/{asset}

# Risk Monitor
GET  /api/trading/terminal/risk
GET  /api/trading/terminal/risk/exposure
GET  /api/trading/terminal/risk/drawdown

# Averaging Monitor
GET  /api/trading/terminal/averaging
GET  /api/trading/terminal/averaging/{asset}

# System State
GET  /api/trading/terminal/state

# Dashboard (aggregated)
GET  /api/trading/terminal/dashboard

# Terminal Actions
POST /api/trading/terminal/actions/pause
POST /api/trading/terminal/actions/resume
POST /api/trading/terminal/actions/kill-switch
POST /api/trading/terminal/actions/deactivate-kill-switch
POST /api/trading/terminal/actions/close-position
POST /api/trading/terminal/actions/cancel-order
POST /api/trading/terminal/actions/cancel-all-orders

# Utility
POST /api/trading/terminal/prices/update
```

## Complete API Summary

### Capsule Control (/api/trading/*)
```
GET  /health, /mode
POST /mode/select, /pause, /resume, /kill-switch/*
```

### Connections (T1)
```
GET/POST/DELETE /connections/*
```

### Accounts (T1)
```
GET/POST /accounts/*
```

### Orders (T2)
```
POST /orders/place, /orders/cancel
GET  /orders, /orders/active, /orders/{id}, /orders/health
```

### Fills & Trades (T2)
```
GET /fills, /trades, /trades/open, /trades/{id}, /stats
```

### Execution (T3)
```
GET  /execution/health, /execution/decisions, /execution/results
POST /execution/signal/ta, /execution/signal/manual
POST /execution/preview, /execution/execute
```

### Risk (T4)
```
GET  /risk/health, /risk/profile/full, /risk/context/*
POST /risk/profile/update, /risk/check
GET/POST /risk/averaging/*, /risk/pnl/*
GET  /risk/events
```

### Terminal (T5)
```
GET  /terminal/health, /terminal/state, /terminal/dashboard
GET  /terminal/accounts, /terminal/positions, /terminal/orders
GET  /terminal/pnl, /terminal/logs, /terminal/risk, /terminal/averaging
POST /terminal/actions/*
```

## Next Steps

### T6: Strategy Logic Layer (P1)
- Bounded averaging / controlled recovery logic
- Strategy configuration
- Signal generation rules
- Entry/exit conditions
- Position rebuild logic
- Capital ladder management

### T7: Merge-Ready Integration Contracts (P2)
- API contracts finalization
- Interface documentation
- Integration tests
- Migration scripts
- M-Brain interface hooks

## Testing

### Test Coverage
- T3 Execution Layer: 100% (18/18 tests)
- T4 Risk Layer: 100% (21/21 tests)
- T5 Terminal Backend: 100% (36/36 tests)
- Overall: 100% (95/95 tests)

### Test Files
- `/app/backend/tests/test_trading_t3_t4.py`
- `/app/backend/tests/test_trading_terminal_t5.py`

### Test Credentials
- Mock adapter: api_key must contain 'mock'
- Example: `{"api_key": "mock_test_123", "api_secret": "mock_secret"}`

## File Structure

```
/app/backend/modules/trading_capsule/
├── __init__.py
├── trading_types.py          # Core types (T0)
├── broker/                   # T1 Broker/Account Layer
│   ├── __init__.py
│   ├── broker_adapters.py
│   ├── broker_base.py
│   └── broker_registry.py
├── orders/                   # T2 Order Management System
│   ├── __init__.py
│   ├── order_service.py
│   └── order_types.py
├── execution/                # T3 Execution Decision Layer
│   ├── __init__.py
│   ├── execution_service.py
│   └── execution_types.py
├── risk/                     # T4 Risk Control Layer
│   ├── __init__.py
│   ├── risk_service.py
│   └── risk_types.py
├── terminal/                 # T5 Terminal Backend
│   ├── __init__.py
│   ├── terminal_service.py
│   ├── terminal_routes.py
│   └── terminal_types.py
└── routes/
    ├── __init__.py
    └── trading_routes.py     # Main router (includes terminal)
```

## Date
Last Updated: 2026-03-09
