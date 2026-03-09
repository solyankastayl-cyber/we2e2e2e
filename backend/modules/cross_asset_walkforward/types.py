"""
Cross-Asset Walk-Forward Types
==============================

Core data structures for the cross-asset simulation engine.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime


class AssetClass(str, Enum):
    """Asset class categories"""
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    FX = "FX"
    COMMODITY = "COMMODITY"
    UNKNOWN = "UNKNOWN"


class SimMode(str, Enum):
    """Simulation modes"""
    CORE_ONLY = "core_only"
    FULL_SYSTEM = "full_system"
    FULL_HIERARCHICAL = "full_hierarchical"
    FULL_ORTHOGONAL = "full_orthogonal"      # Future: after 9.3G
    FULL_RISK_REGIME = "full_risk_regime"    # Future: after 9.3H


class RunStatus(str, Enum):
    """Walk-forward run status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RebalanceFrequency(str, Enum):
    """Rebalance frequency options"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class GovernanceLayer(str, Enum):
    """Governance event source layers"""
    REGIME = "REGIME"
    SELF_HEALING = "SELF_HEALING"
    META_STRATEGY = "META_STRATEGY"
    ALLOCATOR = "ALLOCATOR"
    OVERLAY = "OVERLAY"
    RISK = "RISK"
    BIAS = "BIAS"
    KILL_SWITCH = "KILL_SWITCH"


class TradingCalendar(str, Enum):
    """Trading calendar types"""
    DAILY_MARKET = "DAILY_MARKET"      # Traditional markets (Mon-Fri)
    CRYPTO_24_7 = "CRYPTO_24_7"        # 24/7 crypto markets


class ExecutionProfile(str, Enum):
    """Execution assumption profiles"""
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    FX = "FX"
    COMMODITY = "COMMODITY"


# ============================================
# Dataset Descriptor
# ============================================

@dataclass
class DatasetDescriptor:
    """
    Dataset metadata for an asset.
    
    Manages what the engine knows about available data.
    """
    asset: str
    asset_class: AssetClass
    dataset_version: str
    
    start_date: str                    # ISO format "YYYY-MM-DD"
    end_date: str
    
    base_timeframe: str = "1D"
    supported_derived_timeframes: List[str] = field(default_factory=lambda: ["1W", "1M"])
    
    has_volume: bool = True
    has_open_interest: bool = False
    has_macro_fields: bool = False
    
    total_bars: int = 0
    gaps_detected: int = 0
    
    # Metadata
    source: str = "internal"
    checksum: str = ""
    created_at: str = ""


# ============================================
# Asset Adapter
# ============================================

@dataclass
class AssetAdapter:
    """
    Asset-class specific behavior adapter.
    
    Normalizes how different asset classes are handled
    without introducing asset-specific hacks in the core engine.
    """
    asset: str
    asset_class: AssetClass
    
    # Calendar
    trading_calendar: TradingCalendar = TradingCalendar.DAILY_MARKET
    
    # Trading rules
    allow_shorts: bool = True
    
    # Execution assumptions
    execution_profile: ExecutionProfile = ExecutionProfile.EQUITY
    default_fee_bps: float = 10.0
    default_slippage_bps: float = 5.0
    
    # Structural properties
    structural_bias_allowed: bool = False    # e.g., SPX has long bias
    regime_policy_profile: str = "default"
    
    # Self-healing calibration (from Phase 9.3F fix)
    demote_winrate_threshold: float = 0.35
    promote_winrate_threshold: float = 0.60
    weight_decay_factor: float = 0.90
    weight_boost_factor: float = 1.05
    
    # Risk parameters
    max_position_pct: float = 0.10
    max_drawdown_trigger: float = 0.40


# ============================================
# Walk-Forward Run
# ============================================

@dataclass
class WalkForwardRun:
    """
    Walk-forward simulation run configuration and state.
    """
    run_id: str
    
    # Asset config
    asset: str
    asset_class: AssetClass
    timeframe: str = "1D"
    
    # Mode
    mode: SimMode = SimMode.FULL_SYSTEM
    
    # Date range
    start_date: str = ""
    end_date: str = ""
    warmup_bars: int = 200
    
    # Snapshots for reproducibility
    dataset_version: str = ""
    policy_snapshot_id: str = ""
    strategy_snapshot_id: str = ""
    
    # Capital
    initial_capital: float = 100000.0
    
    # Rebalance settings
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.WEEKLY
    max_weekly_weight_change: float = 0.10
    
    # Status
    status: RunStatus = RunStatus.PENDING
    progress_pct: float = 0.0
    current_bar: int = 0
    total_bars: int = 0
    
    # Timing
    created_at: int = 0
    started_at: int = 0
    completed_at: int = 0
    
    # Error handling
    error_message: str = ""


# ============================================
# Simulated Trade
# ============================================

@dataclass
class SimulatedTrade:
    """
    Simulated trade record with full context.
    """
    trade_id: str
    run_id: str
    asset: str
    strategy_id: str
    
    # Timing
    entry_date: str
    exit_date: str
    entry_timestamp: int = 0
    exit_timestamp: int = 0
    
    # Direction and prices
    side: str = "LONG"    # LONG or SHORT
    entry_price: float = 0.0
    exit_price: float = 0.0
    
    # Size and P&L
    size: float = 0.0
    notional_value: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    
    # Costs
    fees_paid: float = 0.0
    slippage_cost: float = 0.0
    
    # Context at entry
    regime_at_entry: str = ""
    risk_state_at_entry: str = ""
    strategy_health_at_entry: float = 1.0
    overlay_multiplier_at_entry: float = 1.0
    
    # Exit reason
    exit_reason: str = ""    # TP, SL, TIME, SIGNAL, END
    
    # Outcome
    outcome: str = ""        # WIN, LOSS, BREAKEVEN


# ============================================
# Governance Event
# ============================================

@dataclass
class GovernanceEvent:
    """
    Governance event for audit trail.
    
    Logs all system decisions for transparency and debugging.
    """
    event_id: str
    run_id: str
    timestamp: int
    bar_index: int
    asset: str
    
    layer: GovernanceLayer
    action: str
    
    # Details
    old_state: str = ""
    new_state: str = ""
    reason: str = ""
    
    # Additional context
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================
# Metrics Structures
# ============================================

@dataclass
class TradeMetrics:
    """Trade-level metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_r_multiple: float = 0.0
    
    max_win: float = 0.0
    max_loss: float = 0.0
    
    max_winning_streak: int = 0
    max_losing_streak: int = 0


@dataclass
class PortfolioMetrics:
    """Portfolio-level metrics"""
    total_return: float = 0.0
    total_return_pct: float = 0.0
    
    cagr: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_drawdown: float = 0.0
    
    volatility: float = 0.0
    downside_volatility: float = 0.0
    
    final_equity: float = 0.0
    peak_equity: float = 0.0
    
    ulcer_index: float = 0.0


@dataclass
class StrategyMetrics:
    """Per-strategy metrics"""
    strategy_id: str
    
    trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    contribution_pct: float = 0.0
    
    # Governance
    demotion_count: int = 0
    recovery_count: int = 0
    survival_rate: float = 1.0
    
    avg_health_score: float = 1.0
    min_health_score: float = 1.0


@dataclass 
class GovernanceMetrics:
    """Governance-level metrics"""
    total_events: int = 0
    
    healing_events: int = 0
    meta_reallocations: int = 0
    overlay_triggers: int = 0
    kill_switch_events: int = 0
    bias_rejections: int = 0
    
    regime_changes: int = 0
    blocked_trades: int = 0


@dataclass
class RegimeBreakdown:
    """Per-regime performance breakdown"""
    regime: str
    
    trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_r: float = 0.0
    max_dd: float = 0.0
    
    best_families: List[str] = field(default_factory=list)


@dataclass
class DecadeBreakdown:
    """Per-decade performance breakdown (for long histories)"""
    decade: str    # e.g., "1950s", "2000s"
    
    trades: int = 0
    profit_factor: float = 0.0
    cagr: float = 0.0
    max_dd: float = 0.0
    
    dominant_regime: str = ""
    notes: str = ""


# ============================================
# Walk-Forward Report
# ============================================

@dataclass
class WalkForwardReport:
    """
    Complete walk-forward simulation report.
    
    Contains all metrics and breakdowns for analysis.
    """
    run_id: str
    asset: str
    asset_class: str
    mode: str
    
    # Date range
    start_date: str
    end_date: str
    total_bars: int
    years_simulated: float
    
    # Core metrics
    trade_metrics: TradeMetrics = field(default_factory=TradeMetrics)
    portfolio_metrics: PortfolioMetrics = field(default_factory=PortfolioMetrics)
    governance_metrics: GovernanceMetrics = field(default_factory=GovernanceMetrics)
    
    # Breakdowns
    strategy_breakdown: List[StrategyMetrics] = field(default_factory=list)
    regime_breakdown: List[RegimeBreakdown] = field(default_factory=list)
    decade_breakdown: List[DecadeBreakdown] = field(default_factory=list)
    
    # Timestamps
    generated_at: int = 0
    
    # Reproducibility
    dataset_version: str = ""
    policy_snapshot_id: str = ""


# ============================================
# Batch Run Types
# ============================================

@dataclass
class BatchRunRequest:
    """Request for batch multi-asset run"""
    batch_id: str
    
    assets: List[str]
    timeframe: str = "1D"
    mode: SimMode = SimMode.FULL_SYSTEM
    
    # Per-asset start dates (optional)
    start_date_by_asset: Dict[str, str] = field(default_factory=dict)
    end_date: str = ""
    
    initial_capital: float = 100000.0


@dataclass
class BatchRunResult:
    """Result of batch multi-asset run"""
    batch_id: str
    
    total_assets: int = 0
    completed_assets: int = 0
    failed_assets: int = 0
    
    run_ids: Dict[str, str] = field(default_factory=dict)    # asset -> run_id
    
    # Aggregated summary
    summary_table: List[Dict[str, Any]] = field(default_factory=list)
    
    status: str = "PENDING"
    started_at: int = 0
    completed_at: int = 0


# ============================================
# Comparison Types
# ============================================

@dataclass
class CrossAssetComparison:
    """Cross-asset comparison report"""
    comparison_id: str
    
    assets: List[str]
    mode: str
    
    # Comparison matrix
    metrics_matrix: List[Dict[str, Any]] = field(default_factory=list)
    
    # Rankings
    sharpe_ranking: List[str] = field(default_factory=list)
    pf_ranking: List[str] = field(default_factory=list)
    cagr_ranking: List[str] = field(default_factory=list)
    
    # Universal edge verdict
    universal_edge: bool = False
    universal_edge_confidence: float = 0.0
    
    generated_at: int = 0
