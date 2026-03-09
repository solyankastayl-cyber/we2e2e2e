"""
Shadow Portfolio Types
======================

Phase 9.30 - Data structures for shadow portfolio system.

Shadow Portfolio provides:
- Production-like simulation without real money
- Full allocator / risk / governance integration
- Equity tracking and PnL accounting
- Trade logging with metadata
- Governance event recording
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class PositionDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    STOPPED = "STOPPED"        # Hit stop-loss
    TAKE_PROFIT = "TAKE_PROFIT"  # Hit take-profit
    FORCE_CLOSED = "FORCE_CLOSED"  # Governance forced close


class StrategyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"          # Temporarily paused by governance
    DISABLED = "DISABLED"       # Disabled by risk engine
    REMOVED = "REMOVED"         # Removed from portfolio


class GovernanceEventType(str, Enum):
    STRATEGY_ADDED = "STRATEGY_ADDED"
    STRATEGY_REMOVED = "STRATEGY_REMOVED"
    STRATEGY_PAUSED = "STRATEGY_PAUSED"
    STRATEGY_RESUMED = "STRATEGY_RESUMED"
    STRATEGY_DISABLED = "STRATEGY_DISABLED"
    WEIGHT_CHANGED = "WEIGHT_CHANGED"
    REGIME_SWITCH = "REGIME_SWITCH"
    EXPOSURE_REDUCED = "EXPOSURE_REDUCED"
    DRAWDOWN_WARNING = "DRAWDOWN_WARNING"
    DRAWDOWN_BREACH = "DRAWDOWN_BREACH"
    POSITION_FORCE_CLOSED = "POSITION_FORCE_CLOSED"
    CYCLE_COMPLETED = "CYCLE_COMPLETED"
    PORTFOLIO_RESET = "PORTFOLIO_RESET"


class CycleStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RiskRegime(str, Enum):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    STRESS = "STRESS"
    CRISIS = "CRISIS"


@dataclass
class ShadowStrategy:
    """Strategy entry in Shadow Portfolio"""
    strategy_id: str
    alpha_id: str
    name: str = ""
    family: str = "EXPERIMENTAL"
    asset_classes: List[str] = field(default_factory=lambda: ["CRYPTO"])
    timeframes: List[str] = field(default_factory=lambda: ["1D"])

    # Portfolio weight & health
    weight: float = 0.0
    health: float = 1.0
    confidence: float = 0.5
    regime_fit: float = 0.5

    # Status
    status: StrategyStatus = StrategyStatus.ACTIVE

    # Source
    tournament_run_id: str = ""
    tournament_score: float = 0.0

    # Performance in shadow
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0

    # Timestamps
    added_at: int = 0
    last_signal_at: int = 0


@dataclass
class ShadowPosition:
    """Open/closed position in Shadow Portfolio"""
    position_id: str
    strategy_id: str
    alpha_id: str
    asset: str

    direction: PositionDirection = PositionDirection.LONG
    status: PositionStatus = PositionStatus.OPEN

    entry_price: float = 0.0
    exit_price: float = 0.0
    position_size: float = 0.0
    notional_value: float = 0.0

    stop_loss: float = 0.0
    take_profit: float = 0.0

    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_bars: int = 0

    regime_at_entry: str = "NORMAL"
    regime_at_exit: str = ""

    # Timestamps
    opened_at: int = 0
    closed_at: int = 0


@dataclass
class ShadowTrade:
    """Completed trade record"""
    trade_id: str
    position_id: str
    strategy_id: str
    alpha_id: str
    asset: str

    direction: str = "LONG"
    entry_price: float = 0.0
    exit_price: float = 0.0
    position_size: float = 0.0

    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_bars: int = 0

    regime_at_entry: str = "NORMAL"
    regime_at_exit: str = "NORMAL"
    family: str = ""

    # Timestamps
    opened_at: int = 0
    closed_at: int = 0


@dataclass
class EquitySnapshot:
    """Equity curve data point"""
    timestamp: int
    equity: float
    cash: float
    exposure: float
    drawdown: float
    drawdown_pct: float
    regime: str = "NORMAL"
    open_positions: int = 0
    cycle_number: int = 0


@dataclass
class GovernanceEvent:
    """Governance/management event"""
    event_id: str
    event_type: GovernanceEventType
    timestamp: int

    strategy_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class ShadowPortfolioMetrics:
    """Aggregated portfolio metrics"""
    total_return: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_holding_bars: float = 0.0
    turnover: float = 0.0
    exposure_avg: float = 0.0
    strategy_contributions: Dict[str, float] = field(default_factory=dict)
    family_contributions: Dict[str, float] = field(default_factory=dict)
    computed_at: int = 0


@dataclass
class CycleResult:
    """Result of a single portfolio cycle"""
    cycle_id: str
    cycle_number: int
    timestamp: int

    status: CycleStatus = CycleStatus.COMPLETED

    # Signals generated
    signals_generated: int = 0
    positions_opened: int = 0
    positions_closed: int = 0

    # Equity after cycle
    equity_before: float = 0.0
    equity_after: float = 0.0
    cycle_pnl: float = 0.0

    # Risk
    exposure_after: float = 0.0
    regime: str = "NORMAL"

    # Governance
    governance_events: int = 0

    duration_ms: int = 0


@dataclass
class ShadowPortfolioConfig:
    """Configuration for shadow portfolio"""
    # Capital
    initial_capital: float = 100000.0

    # Strategy limits
    max_strategies: int = 10
    max_position_per_strategy: float = 0.10
    max_total_exposure: float = 1.0

    # Risk
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04

    # Drawdown limits
    drawdown_warning: float = 0.10
    drawdown_stress: float = 0.20
    drawdown_crisis: float = 0.30

    # Regime exposure multipliers
    regime_exposure: Dict[str, float] = field(default_factory=lambda: {
        "NORMAL": 1.0,
        "ELEVATED": 0.7,
        "STRESS": 0.4,
        "CRISIS": 0.1
    })

    # Allocation
    equal_weight: bool = True
    min_strategy_weight: float = 0.05
    max_strategy_weight: float = 0.30
