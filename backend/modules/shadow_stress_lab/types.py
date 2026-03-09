"""
Stress Lab Types
================

Phase 9.30B - Data structures for stress testing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class StressAssetClass(str, Enum):
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    FX = "FX"
    COMMODITY = "COMMODITY"
    MULTI_ASSET = "MULTI_ASSET"


class StressRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StressRunMode(str, Enum):
    CORE_ONLY = "CORE_ONLY"
    FULL_SYSTEM = "FULL_SYSTEM"
    FULL_STRESS_POLICIES = "FULL_STRESS_POLICIES"


@dataclass
class CrisisProfile:
    """Defines the characteristics of a market crisis"""
    peak_drawdown: float = 0.30
    drawdown_duration_bars: int = 20
    recovery_duration_bars: int = 40
    volatility_multiplier: float = 3.0
    correlation_spike: float = 0.85
    trend_direction: float = -1.0  # -1 = bearish, +1 = bullish
    volatility_clustering: float = 0.7
    liquidity_shock: float = 0.5  # 0=normal, 1=complete freeze
    mean_reversion_after: bool = True


@dataclass
class StressScenario:
    """Pre-defined crisis scenario"""
    scenario_id: str
    name: str
    description: str
    asset_class: StressAssetClass
    tags: List[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    crisis_profile: CrisisProfile = field(default_factory=CrisisProfile)
    total_bars: int = 60
    affected_assets: List[str] = field(default_factory=list)


@dataclass
class StressTimelineEvent:
    """Event in the stress timeline"""
    bar: int
    timestamp: int
    event_type: str  # VOLATILITY_SPIKE, REGIME_SWITCH, STRATEGY_DEMOTED, etc.
    description: str
    severity: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyStressResult:
    """Per-strategy results from stress test"""
    strategy_id: str
    alpha_id: str
    name: str
    family: str
    survived: bool = True
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    trades: int = 0
    winning_trades: int = 0
    was_paused: bool = False
    was_disabled: bool = False
    bars_active: int = 0
    regime_at_failure: str = ""


@dataclass
class StressPortfolioMetrics:
    """Portfolio-level stress metrics"""
    # Performance
    total_return: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    recovery_bars: int = 0
    tail_loss: float = 0.0
    stress_sharpe: float = 0.0
    calmar: float = 0.0

    # Governance
    regime_switches: int = 0
    healing_events: int = 0
    demotions: int = 0
    overlay_reductions: int = 0
    blocked_signals: int = 0

    # Survival
    strategies_survived: int = 0
    strategies_disabled: int = 0
    strategies_paused: int = 0
    capital_preserved_pct: float = 0.0
    family_collapses: List[str] = field(default_factory=list)

    # System
    total_cycles: int = 0
    total_trades: int = 0
    total_governance_events: int = 0


@dataclass
class StressRun:
    """Complete stress test run"""
    run_id: str
    scenario_id: str
    scenario_name: str
    mode: StressRunMode = StressRunMode.FULL_SYSTEM
    status: StressRunStatus = StressRunStatus.PENDING

    # Snapshots
    initial_equity: float = 100000.0
    final_equity: float = 0.0

    # Results
    metrics: StressPortfolioMetrics = field(default_factory=StressPortfolioMetrics)
    strategy_results: List[StrategyStressResult] = field(default_factory=list)
    timeline: List[StressTimelineEvent] = field(default_factory=list)
    equity_curve: List[Dict] = field(default_factory=list)

    # Verdict
    survived: bool = False
    verdict: str = ""
    verdict_details: List[str] = field(default_factory=list)

    # Timestamps
    started_at: int = 0
    completed_at: int = 0
    duration_ms: int = 0


@dataclass
class StressBatchResult:
    """Result of running multiple scenarios"""
    batch_id: str
    mode: str = "FULL_SYSTEM"
    total_scenarios: int = 0
    scenarios_survived: int = 0
    scenarios_failed: int = 0
    runs: List[str] = field(default_factory=list)  # run_ids
    weakest_scenario: str = ""
    strongest_scenario: str = ""
    avg_drawdown: float = 0.0
    avg_recovery: int = 0
    family_vulnerability: Dict[str, int] = field(default_factory=dict)
    started_at: int = 0
    completed_at: int = 0
