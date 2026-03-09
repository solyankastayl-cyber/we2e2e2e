"""
Phase 8: Quant Validation Types
Core data types for quant validation layer.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import time


class FailureType(str, Enum):
    """Types of system failures/errors"""
    FALSE_BREAKOUT = "FALSE_BREAKOUT"  # Predicted breakout didn't happen
    WRONG_SCENARIO = "WRONG_SCENARIO"  # Scenario prediction was wrong
    LATE_ENTRY = "LATE_ENTRY"  # Entry was too late
    EARLY_EXIT = "EARLY_EXIT"  # Exit was premature
    MTF_CONFLICT = "MTF_CONFLICT"  # Multi-timeframe signals conflicted
    MEMORY_MISLEAD = "MEMORY_MISLEAD"  # Historical memory led to wrong decision
    REGIME_MISMATCH = "REGIME_MISMATCH"  # Wrong market regime detected
    LIQUIDITY_TRAP = "LIQUIDITY_TRAP"  # Liquidity sweep not detected
    STRUCTURE_BREAK = "STRUCTURE_BREAK"  # Market structure break missed
    OVERCONFIDENCE = "OVERCONFIDENCE"  # System was overconfident


class TradeOutcome(str, Enum):
    """Trade outcome types"""
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
    PENDING = "PENDING"


class ReplayStatus(str, Enum):
    """Replay engine status"""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class Trade:
    """Represents a single trade"""
    trade_id: str
    symbol: str
    timeframe: str
    direction: str  # LONG or SHORT
    entry_price: float
    exit_price: float = 0.0
    entry_time: int = 0
    exit_time: int = 0
    size: float = 1.0
    pnl: float = 0.0
    r_multiple: float = 0.0
    outcome: TradeOutcome = TradeOutcome.PENDING
    strategy_id: str = ""
    scenario_id: str = ""
    confidence: float = 0.0
    failure_type: Optional[FailureType] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class SimulationConfig:
    """Configuration for historical simulation"""
    symbol: str = "BTCUSDT"
    timeframe: str = "4h"
    start_date: str = "2019-01-01"
    end_date: str = "2024-01-01"
    initial_capital: float = 100000.0
    max_position_size: float = 0.05  # 5% of capital
    slippage_bps: float = 10.0
    fee_bps: float = 10.0
    use_isolation_context: bool = True
    isolation_run_id: Optional[str] = None


@dataclass
class SimulationResult:
    """Result from historical simulation"""
    run_id: str
    config: SimulationConfig
    
    # Core metrics
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_pnl: float = 0.0
    total_r: float = 0.0
    avg_r: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    
    # Advanced metrics
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_trade_duration: float = 0.0
    best_trade_r: float = 0.0
    worst_trade_r: float = 0.0
    
    # By regime
    regime_breakdown: Dict[str, Dict] = field(default_factory=dict)
    
    # By strategy
    strategy_breakdown: Dict[str, Dict] = field(default_factory=dict)
    
    # Trade list
    trade_list: List[Trade] = field(default_factory=list)
    
    # Timing
    started_at: int = 0
    completed_at: int = 0
    duration_ms: int = 0
    
    # Status
    status: str = "COMPLETED"
    error: Optional[str] = None


@dataclass
class ReplayState:
    """State during market replay"""
    run_id: str
    symbol: str
    timeframe: str
    
    # Position
    current_bar: int = 0
    total_bars: int = 0
    current_time: int = 0
    
    # Market state
    current_price: float = 0.0
    current_regime: str = "UNKNOWN"
    current_scenario: str = ""
    current_structure: str = ""
    
    # MetaBrain state
    metabrain_mode: str = "BALANCED"
    metabrain_confidence: float = 0.0
    
    # Signals
    active_signals: List[Dict] = field(default_factory=list)
    
    # Positions
    open_positions: List[Dict] = field(default_factory=list)
    
    # History
    events: List[Dict] = field(default_factory=list)
    scenario_changes: List[Dict] = field(default_factory=list)
    metabrain_changes: List[Dict] = field(default_factory=list)
    
    # Status
    status: ReplayStatus = ReplayStatus.IDLE
    progress: float = 0.0


@dataclass
class MonteCarloResult:
    """Result from Monte Carlo simulation"""
    run_id: str
    iterations: int = 1000
    
    # Distribution metrics
    median_pnl: float = 0.0
    mean_pnl: float = 0.0
    std_pnl: float = 0.0
    worst_case_pnl: float = 0.0
    best_case_pnl: float = 0.0
    
    # Percentiles
    percentile_5: float = 0.0
    percentile_25: float = 0.0
    percentile_75: float = 0.0
    percentile_95: float = 0.0
    
    # Survival
    survival_rate: float = 0.0  # % of runs that didn't blow up
    ruin_probability: float = 0.0
    
    # Robustness
    robustness_score: float = 0.0
    
    # Variations tested
    variations: Dict[str, Any] = field(default_factory=dict)
    
    timestamp: int = 0


@dataclass
class StressTestResult:
    """Result from stress testing"""
    run_id: str
    
    # Scenarios tested
    scenarios: List[str] = field(default_factory=list)
    
    # Performance under load
    load_levels: Dict[str, Dict] = field(default_factory=dict)
    # e.g., {"10_users": {"p95_latency": 50, "cpu": 0.3}, ...}
    
    # System metrics
    max_supported_users: int = 0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    cpu_peak: float = 0.0
    memory_peak_mb: float = 0.0
    ws_delay_ms: float = 0.0
    
    # Failure modes
    failure_modes: List[Dict] = field(default_factory=list)
    
    # Overall
    passed: bool = True
    score: float = 0.0
    
    timestamp: int = 0


@dataclass
class AccuracyMetrics:
    """System accuracy metrics"""
    run_id: str
    
    # Core accuracy
    direction_accuracy: float = 0.0  # % correct market direction
    scenario_accuracy: float = 0.0  # % correct scenario prediction
    structure_accuracy: float = 0.0  # % correct structure detection
    timing_accuracy: float = 0.0  # % good entry/exit timing
    
    # Extended accuracy
    regime_accuracy: float = 0.0  # % correct regime detection
    mtf_alignment_accuracy: float = 0.0  # % MTF alignment correct
    memory_recall_accuracy: float = 0.0  # % memory helped decision
    
    # Confidence calibration
    confidence_calibration: float = 0.0  # How well-calibrated is confidence
    overconfidence_rate: float = 0.0  # % of high-conf trades that failed
    underconfidence_rate: float = 0.0  # % of low-conf trades that won
    
    # Sample sizes
    total_predictions: int = 0
    direction_predictions: int = 0
    scenario_predictions: int = 0
    
    timestamp: int = 0


@dataclass
class FailureInstance:
    """A single failure instance"""
    failure_id: str
    failure_type: FailureType
    trade_id: str
    timestamp: int
    description: str
    impact_r: float = 0.0  # R-multiple impact
    root_cause: str = ""
    related_signals: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureAnalysis:
    """Analysis of system failures"""
    run_id: str
    
    # Failure counts by type
    failure_counts: Dict[str, int] = field(default_factory=dict)
    
    # Top failures
    top_failures: List[FailureType] = field(default_factory=list)
    
    # Failure rate
    total_failures: int = 0
    failure_rate: float = 0.0
    
    # Impact
    total_failure_impact_r: float = 0.0
    avg_failure_impact_r: float = 0.0
    
    # Failure instances
    failure_instances: List[FailureInstance] = field(default_factory=list)
    
    # Patterns
    failure_patterns: List[Dict] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    timestamp: int = 0


@dataclass
class ValidationReport:
    """Final aggregated validation report"""
    run_id: str
    
    # Core metrics
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    total_trades: int = 0
    
    # Accuracy
    direction_accuracy: float = 0.0
    scenario_accuracy: float = 0.0
    structure_accuracy: float = 0.0
    timing_accuracy: float = 0.0
    
    # Robustness
    monte_carlo_survival_rate: float = 0.0
    monte_carlo_worst_case: float = 0.0
    robustness_score: float = 0.0
    
    # Failures
    top_failures: List[str] = field(default_factory=list)
    failure_rate: float = 0.0
    
    # Edge assessment
    has_edge: bool = False
    edge_confidence: float = 0.0
    edge_verdict: str = "UNKNOWN"  # STRONG_EDGE, MODERATE_EDGE, WEAK_EDGE, NO_EDGE
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    # Components
    simulation_result: Optional[SimulationResult] = None
    accuracy_metrics: Optional[AccuracyMetrics] = None
    failure_analysis: Optional[FailureAnalysis] = None
    monte_carlo_result: Optional[MonteCarloResult] = None
    
    # Isolation
    validation_isolation: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    started_at: int = 0
    completed_at: int = 0
    
    timestamp: int = 0


# Configuration
VALIDATION_CONFIG = {
    "enabled": True,
    "version": "validation_v1_phase8",
    
    # Simulation defaults
    "default_timeframe": "4h",
    "default_lookback_years": 3,
    "min_trades_for_significance": 30,
    
    # Monte Carlo
    "monte_carlo_iterations": 1000,
    "monte_carlo_variations": {
        "volatility_range": [0.8, 1.2],
        "slippage_range": [5, 30],
        "wick_multiplier_range": [0.5, 2.0]
    },
    
    # Stress test levels
    "stress_levels": [10, 50, 100, 500, 1000],
    
    # Accuracy thresholds
    "accuracy_thresholds": {
        "direction": 0.55,
        "scenario": 0.50,
        "structure": 0.55,
        "timing": 0.45
    },
    
    # Edge assessment
    "edge_thresholds": {
        "strong_win_rate": 0.60,
        "strong_pf": 1.5,
        "strong_sharpe": 1.5,
        "moderate_win_rate": 0.55,
        "moderate_pf": 1.2,
        "moderate_sharpe": 1.0,
        "min_trades": 100
    },
    
    # MongoDB collections
    "collections": {
        "simulation_runs": "ta_simulation_runs",
        "replay_states": "ta_replay_states",
        "validation_reports": "ta_validation_reports",
        "failure_logs": "ta_failure_logs"
    }
}
