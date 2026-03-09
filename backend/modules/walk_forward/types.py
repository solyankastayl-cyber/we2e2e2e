"""
Walk-Forward Types and Constants
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class SimulationMode(str, Enum):
    FULL_SYSTEM = "full_system"           # All layers active
    FULL_SYSTEM_BIAS = "full_system_bias" # All layers + Structural Bias
    FULL_OVERLAY = "full_overlay"         # All layers + Portfolio Overlay
    FULL_HIERARCHICAL = "full_hierarchical"  # All layers + Hierarchical Allocator (Phase 9.3F)
    NO_META = "no_meta"                   # Without Meta-Strategy
    NO_HEALING = "no_healing"             # Without Self-Healing  
    CORE_ONLY = "core_only"               # Only APPROVED strategies
    CORE_BIAS = "core_bias"               # Core + Structural Bias
    CORE_OVERLAY = "core_overlay"         # Core + Portfolio Overlay
    HIERARCHICAL_ONLY = "hierarchical_only"  # Hierarchical allocation only (Phase 9.3F)


class RegimeType(str, Enum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    COMPRESSION = "COMPRESSION"
    EXPANSION = "EXPANSION"
    CRISIS = "CRISIS"


# Historical SPX regime periods
HISTORICAL_REGIMES = {
    "1950-1968": {"label": "Post-War Expansion", "dominant": RegimeType.TREND_UP},
    "1968-1982": {"label": "Inflation/Unstable", "dominant": RegimeType.RANGE},
    "1982-2000": {"label": "Secular Bull", "dominant": RegimeType.TREND_UP},
    "2000-2009": {"label": "Dotcom + GFC", "dominant": RegimeType.CRISIS},
    "2009-2020": {"label": "QE Bull Market", "dominant": RegimeType.TREND_UP},
    "2020-2026": {"label": "Post-COVID", "dominant": RegimeType.EXPANSION},
}


@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    @property
    def date(self) -> datetime:
        return datetime.utcfromtimestamp(self.timestamp / 1000)


@dataclass
class Signal:
    id: str
    strategy_id: str
    direction: str  # LONG / SHORT
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    timestamp: int
    pattern_type: str = ""
    regime: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trade:
    id: str
    signal_id: str
    strategy_id: str
    direction: str
    entry_price: float
    entry_time: int
    exit_price: float = 0.0
    exit_time: int = 0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    size: float = 1.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    outcome: str = ""  # WIN / LOSS / BREAKEVEN
    exit_reason: str = ""  # TP / SL / SIGNAL / TIMEOUT
    regime: str = ""
    decade: str = ""
    bars_held: int = 0
    max_favorable: float = 0.0  # MFE
    max_adverse: float = 0.0    # MAE


@dataclass
class PortfolioState:
    timestamp: int
    equity: float
    cash: float
    positions_value: float
    open_positions: int
    drawdown: float
    drawdown_pct: float
    peak_equity: float
    regime: str = ""
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    family_budgets: Dict[str, float] = field(default_factory=dict)


@dataclass
class DayResult:
    timestamp: int
    date_str: str
    candle: Candle
    regime: str
    signals_generated: int
    trades_opened: int
    trades_closed: int
    pnl: float
    equity: float
    drawdown_pct: float
    events: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DecadeMetrics:
    decade: str
    start_year: int
    end_year: int
    trades: int
    win_rate: float
    profit_factor: float
    sharpe: float
    max_drawdown: float
    total_return: float
    avg_r: float
    best_strategy: str = ""
    worst_strategy: str = ""


@dataclass
class RegimeMetrics:
    regime: str
    trades: int
    win_rate: float
    profit_factor: float
    sharpe: float
    max_drawdown: float
    avg_r: float
    active_strategies: List[str] = field(default_factory=list)
    family_performance: Dict[str, float] = field(default_factory=dict)


@dataclass
class StrategyMetrics:
    strategy_id: str
    status: str
    trades: int
    win_rate: float
    profit_factor: float
    avg_r: float
    max_drawdown: float
    contribution_pct: float
    demotions: int = 0
    promotions: int = 0
    healing_events: int = 0


@dataclass
class FailureEvent:
    timestamp: int
    type: str  # FALSE_BREAKOUT, EARLY_EXIT, WRONG_REGIME, LATE_HEALING, BAD_ALLOCATION
    strategy_id: str
    trade_id: str
    description: str
    loss_amount: float
    regime: str
    decade: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WalkForwardConfig:
    asset: str = "SPX"
    timeframe: str = "1d"
    start_date: str = "1950-01-01"
    end_date: str = "2026-03-01"
    mode: SimulationMode = SimulationMode.FULL_SYSTEM
    initial_capital: float = 100000.0
    warmup_bars: int = 500
    max_positions: int = 3  # Reduced from 5
    position_size_pct: float = 0.01  # 1% risk per trade (reduced from 2%)
    slippage_bps: float = 10.0
    fee_bps: float = 10.0
    rebalance_frequency: str = "weekly"  # daily, weekly, monthly
    max_daily_weight_change: float = 0.10
    max_weekly_weight_change: float = 0.25


@dataclass
class WalkForwardResult:
    run_id: str
    config: WalkForwardConfig
    mode: str
    started_at: int
    completed_at: int
    
    # Global metrics
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    total_return: float = 0.0
    cagr: float = 0.0
    expectancy: float = 0.0
    max_losing_streak: int = 0
    avg_recovery_bars: int = 0
    
    # Final state
    final_equity: float = 0.0
    peak_equity: float = 0.0
    
    # Breakdowns
    decade_metrics: List[DecadeMetrics] = field(default_factory=list)
    regime_metrics: List[RegimeMetrics] = field(default_factory=list)
    strategy_metrics: List[StrategyMetrics] = field(default_factory=list)
    
    # Events
    governance_events: int = 0
    healing_events: int = 0
    kill_switch_events: int = 0
    meta_reallocations: int = 0
    
    # Failures
    failure_events: List[FailureEvent] = field(default_factory=list)
    
    # Timeline
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    daily_results: List[DayResult] = field(default_factory=list)
