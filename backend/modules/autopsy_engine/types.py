"""
Autopsy Engine Types
====================

Phase 9.30C - Data structures for autopsy analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class AutopsyEntityType(str, Enum):
    STRATEGY = "STRATEGY"
    PORTFOLIO = "PORTFOLIO"
    SHADOW_RUN = "SHADOW_RUN"
    STRESS_RUN = "STRESS_RUN"


class AutopsyEventType(str, Enum):
    STRATEGY_FAILURE = "STRATEGY_FAILURE"
    PORTFOLIO_DRAWDOWN = "PORTFOLIO_DRAWDOWN"
    STRESS_COLLAPSE = "STRESS_COLLAPSE"
    TOURNAMENT_LOSS = "TOURNAMENT_LOSS"


class RootCause(str, Enum):
    REGIME_MISMATCH = "REGIME_MISMATCH"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
    CROWDING = "CROWDING"
    CORRELATION_SPIKE = "CORRELATION_SPIKE"
    OVERFITTED_ALPHA = "OVERFITTED_ALPHA"
    LATE_ENTRY = "LATE_ENTRY"
    FALSE_BREAKOUT = "FALSE_BREAKOUT"
    TREND_REVERSAL = "TREND_REVERSAL"
    RISK_POLICY_DELAY = "RISK_POLICY_DELAY"
    LOW_EDGE = "LOW_EDGE"
    FAMILY_CONCENTRATION = "FAMILY_CONCENTRATION"
    LIQUIDITY_SHOCK = "LIQUIDITY_SHOCK"
    SIGNAL_DEGRADATION = "SIGNAL_DEGRADATION"
    GOVERNANCE_DELAY = "GOVERNANCE_DELAY"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class AutopsyReport:
    """Full autopsy report for a failure event"""
    report_id: str
    entity_type: AutopsyEntityType
    entity_id: str
    event_type: AutopsyEventType

    root_causes: List[str] = field(default_factory=list)
    contributing_factors: List[str] = field(default_factory=list)
    regime_context: str = "NORMAL"

    severity: str = "MEDIUM"
    family: str = ""
    asset_class: str = ""

    summary: str = ""
    recommendations: List[str] = field(default_factory=list)

    # Metrics at time of failure
    drawdown_pct: float = 0.0
    pnl_at_failure: float = 0.0
    trades_at_failure: int = 0
    win_rate_at_failure: float = 0.0

    # Timeline
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    created_at: int = 0


@dataclass
class FailurePattern:
    """Aggregated failure pattern"""
    pattern_id: str
    root_cause: str
    family: str = ""
    asset_class: str = ""
    regime: str = ""

    frequency: int = 0
    avg_severity: float = 0.0
    affected_strategies: List[str] = field(default_factory=list)
    affected_scenarios: List[str] = field(default_factory=list)

    description: str = ""
    first_seen: int = 0
    last_seen: int = 0


@dataclass
class AutopsyDigest:
    """Summary digest of all autopsy findings"""
    total_reports: int = 0
    total_patterns: int = 0

    top_root_causes: List[Dict[str, Any]] = field(default_factory=list)
    family_vulnerability: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    regime_risk_map: Dict[str, List[str]] = field(default_factory=dict)

    most_fragile_families: List[str] = field(default_factory=list)
    most_resilient_families: List[str] = field(default_factory=list)

    computed_at: int = 0
