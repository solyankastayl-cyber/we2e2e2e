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
| T7 | Merge-Ready Contracts | ⏳ Pending |

### System Progress
- Research Infrastructure: 100%
- Backend Architecture: 100%
- Trading Capsule: 95% (T0-T6 done)
- Terminal Backend: 100%
- Strategy Runtime: 100%

## What's Been Implemented

### Trading Capsule T6: Strategy Runtime Engine (2026-03-09)

#### Architecture
T6 is the strategy management and execution layer. It orchestrates strategies:

```
Signal (TA/Manual/MBrain)
↓
T6 Strategy Runtime
↓
Strategy Plugins (evaluate)
↓
StrategyAction
↓
T3 Execution Layer
↓
T4 Risk Control
↓
T2 OMS
↓
Exchange
```

#### Core Components

**1. StrategyPlugin Interface**
- `strategy_id`: Unique identifier
- `on_signal()`: Signal notification
- `on_market_update()`: Real-time data
- `on_position_update()`: Position changes  
- `evaluate()`: Main decision method → StrategyAction

**2. StrategyAction Types**
- ENTER_LONG / EXIT_LONG
- ENTER_SHORT / EXIT_SHORT
- AVERAGE (add to position)
- HOLD (no action)
- SCALE_IN / SCALE_OUT
- FLIP (reverse position)

**3. StrategyContext**
Contains all data for strategy evaluation:
- Signal data
- Market data (asset, price)
- Account state (equity, cash)
- Position state (has_position, side, size, pnl)
- Risk state (daily_pnl, drawdown)
- Capsule state (paused, kill_switch)

**4. Strategy Registry**
- `register()` / `unregister()` strategies
- Metadata storage
- Strategy lookup

**5. Strategy State Manager**
- `enable()` / `disable()` strategies
- `pause()` / `resume()` strategies
- Track metrics (signals, actions, errors)
- Auto-disable on error threshold

**6. Strategy Runtime**
- Build context from system state
- Route signals to active strategies
- Collect actions from strategies
- Publish events to Event Bus
- Multi-strategy mode support

**7. Strategy Engine**
- Unified interface for all operations
- Auto-execute actions through Execution Layer
- Event publishing

#### Built-in Strategies

1. **TA_SIGNAL_FOLLOWER** (enabled by default)
   - Follows TA signals with confidence filter
   - BULLISH → ENTER_LONG
   - BEARISH → EXIT_LONG
   - Min confidence: 60%

2. **MANUAL_SIGNAL_EXECUTOR** (enabled by default)
   - Executes manual signals directly
   - Maps action from signal payload

3. **MBRAIN_SIGNAL_ROUTER** (disabled by default)
   - Routes M-Brain ensemble signals
   - Consensus checking
   - Min confidence: 70%

#### API Endpoints

```
# Health
GET  /api/trading/strategies/health

# Strategy Management
GET  /api/trading/strategies                 - List all strategies
GET  /api/trading/strategies/active          - Get active strategies
GET  /api/trading/strategies/config          - Get configuration
GET  /api/trading/strategies/{id}            - Get strategy by ID
POST /api/trading/strategies/{id}/enable     - Enable strategy
POST /api/trading/strategies/{id}/disable    - Disable strategy
POST /api/trading/strategies/{id}/pause      - Pause strategy
POST /api/trading/strategies/{id}/resume     - Resume strategy

# Signal Processing
POST /api/trading/strategies/signal/ta       - Process TA signal
POST /api/trading/strategies/signal/manual   - Process manual signal
POST /api/trading/strategies/signal/mbrain   - Process M-Brain signal

# Configuration
POST /api/trading/strategies/config/mode     - Set multi-strategy mode
```

#### Event Bus Events (T6)
- `strategy_registered` / `strategy_unregistered`
- `strategy_enabled` / `strategy_disabled`
- `strategy_paused` / `strategy_resumed`
- `strategy_action_generated`
- `strategy_error`

## File Structure

```
/app/backend/modules/trading_capsule/
├── __init__.py
├── trading_types.py          # Core types (T0)
├── broker/                   # T1 Broker/Account Layer
├── orders/                   # T2 Order Management System
├── execution/                # T3 Execution Decision Layer
├── risk/                     # T4 Risk Control Layer
├── terminal/                 # T5 Terminal Backend
├── strategy/                 # T6 Strategy Runtime Engine
│   ├── __init__.py
│   ├── strategy_types.py     # StrategyAction, StrategyContext, StrategyPlugin
│   ├── strategy_registry.py  # Registry for strategy plugins
│   ├── strategy_state.py     # State manager (enable/disable/pause)
│   ├── strategy_runtime.py   # Signal routing, context building
│   ├── strategy_engine.py    # Unified interface
│   ├── strategy_routes.py    # REST API endpoints
│   └── builtin_strategies.py # Default strategy implementations
└── routes/
    └── trading_routes.py     # Main router (includes T5, T6)
```

## Next Steps

### T7: Merge-Ready Integration Contracts (P1)
- API contracts finalization
- Interface documentation
- Integration tests
- Migration scripts
- M-Brain interface hooks
- Capsule isolation verification

## Testing

### Test Coverage
- T3 Execution Layer: 100%
- T4 Risk Layer: 100%
- T5 Terminal Backend: 100%
- T6 Strategy Runtime: 100%
- Overall: 100%

### Test Credentials
- Mock adapter: api_key must contain 'mock'
- Example: `{"api_key": "mock_test_123", "api_secret": "mock_secret"}`

## Date
Last Updated: 2026-03-09
