"""
Risk Regime Engine Types
========================

Phase 9.3H - Data structures for global tactical risk management.

Risk States:
- NORMAL: Full allocation, all strategies enabled
- ELEVATED: Reduced exposure, extra scrutiny
- STRESS: Defensive mode, limited tactical
- CRISIS: Capital preservation, minimal exposure
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class RiskState(str, Enum):
    """Global risk regime states"""
    NORMAL = "NORMAL"           # Green - Full allocation
    ELEVATED = "ELEVATED"       # Yellow - Reduced exposure
    STRESS = "STRESS"           # Orange - Defensive mode
    CRISIS = "CRISIS"           # Red - Capital preservation


class RiskIndicator(str, Enum):
    """Risk indicators used for regime detection"""
    VIX = "VIX"                          # Volatility Index
    VIX_TERM_STRUCTURE = "VIX_TERM"      # VIX contango/backwardation
    CREDIT_SPREAD = "CREDIT_SPREAD"      # High yield spreads
    CORRELATION = "CORRELATION"          # Cross-asset correlation
    DRAWDOWN = "DRAWDOWN"                # Portfolio drawdown
    VOLATILITY = "VOLATILITY"            # Realized volatility
    VOLUME_SPIKE = "VOLUME_SPIKE"        # Abnormal volume
    LIQUIDITY = "LIQUIDITY"              # Market liquidity
    MOMENTUM_CRASH = "MOMENTUM_CRASH"    # Factor crash detection


class TransitionTrigger(str, Enum):
    """What triggered the state transition"""
    VOLATILITY_SPIKE = "volatility_spike"
    CORRELATION_EXPLOSION = "correlation_explosion"
    DRAWDOWN_BREACH = "drawdown_breach"
    CREDIT_STRESS = "credit_stress"
    LIQUIDITY_CRUNCH = "liquidity_crunch"
    MANUAL_OVERRIDE = "manual_override"
    RECOVERY = "recovery"
    TIME_BASED = "time_based"


@dataclass
class RiskIndicatorValue:
    """Single risk indicator reading"""
    indicator: RiskIndicator
    value: float = 0.0
    z_score: float = 0.0              # Standard deviations from mean
    percentile: float = 50.0          # Historical percentile
    signal: str = "neutral"           # bullish/neutral/bearish
    weight: float = 1.0               # Weight in composite score
    timestamp: int = 0


@dataclass
class RiskRegimeState:
    """Current state of risk regime"""
    state: RiskState = RiskState.NORMAL
    previous_state: RiskState = RiskState.NORMAL
    
    # Composite risk score (0-100)
    risk_score: float = 0.0
    
    # Thresholds
    elevated_threshold: float = 40.0
    stress_threshold: float = 60.0
    crisis_threshold: float = 80.0
    
    # State duration
    bars_in_state: int = 0
    state_start_timestamp: int = 0
    
    # Transition info
    last_transition: Optional[TransitionTrigger] = None
    last_transition_timestamp: int = 0
    
    # Indicator breakdown
    indicators: Dict[str, RiskIndicatorValue] = field(default_factory=dict)


@dataclass
class RiskPolicy:
    """
    Policy adjustments for each risk state.
    
    Controls how the system behaves in different risk environments.
    """
    state: RiskState
    
    # Exposure multipliers
    exposure_multiplier: float = 1.0      # Global exposure cap
    leverage_multiplier: float = 1.0      # Leverage limit
    
    # Strategy controls
    tactical_enabled: bool = True         # Allow tactical strategies
    experimental_enabled: bool = True     # Allow experimental strategies
    new_positions_enabled: bool = True    # Allow opening new positions
    
    # Family budget compression
    budget_compression: float = 1.0       # Compress all family budgets
    
    # Risk limits
    max_drawdown_limit: float = 0.20      # Max DD before forced reduction
    position_size_cap: float = 1.0        # Cap on individual position sizes
    
    # Stop management
    tighten_stops: bool = False           # Use tighter stops
    stop_multiplier: float = 1.0          # Stop distance multiplier
    
    # Correlation
    max_correlation_allowed: float = 0.70  # Max pairwise correlation


@dataclass
class StateTransition:
    """Record of a risk state transition"""
    transition_id: str
    
    from_state: RiskState
    to_state: RiskState
    
    trigger: TransitionTrigger
    risk_score: float
    
    # Indicators at transition
    indicator_values: Dict[str, float] = field(default_factory=dict)
    
    # Actions taken
    actions_taken: List[str] = field(default_factory=list)
    
    timestamp: int = 0


@dataclass
class RiskRegimeConfig:
    """Configuration for risk regime engine"""
    
    # Thresholds for state transitions
    normal_to_elevated: float = 40.0
    elevated_to_stress: float = 60.0
    stress_to_crisis: float = 80.0
    
    # Recovery thresholds (hysteresis)
    crisis_to_stress: float = 70.0
    stress_to_elevated: float = 50.0
    elevated_to_normal: float = 30.0
    
    # Minimum bars in state before transition allowed
    min_bars_for_upgrade: int = 5         # To higher risk state
    min_bars_for_downgrade: int = 10      # To lower risk state
    
    # Indicator weights
    indicator_weights: Dict[str, float] = field(default_factory=lambda: {
        "VIX": 0.25,
        "VOLATILITY": 0.20,
        "CORRELATION": 0.20,
        "DRAWDOWN": 0.15,
        "CREDIT_SPREAD": 0.10,
        "LIQUIDITY": 0.10
    })
    
    # Lookback periods
    volatility_lookback: int = 20
    correlation_lookback: int = 60
    drawdown_lookback: int = 252


# Default policies for each state
DEFAULT_POLICIES = {
    RiskState.NORMAL: RiskPolicy(
        state=RiskState.NORMAL,
        exposure_multiplier=1.0,
        leverage_multiplier=1.0,
        tactical_enabled=True,
        experimental_enabled=True,
        new_positions_enabled=True,
        budget_compression=1.0,
        max_drawdown_limit=0.20,
        position_size_cap=1.0,
        tighten_stops=False,
        stop_multiplier=1.0,
        max_correlation_allowed=0.70
    ),
    RiskState.ELEVATED: RiskPolicy(
        state=RiskState.ELEVATED,
        exposure_multiplier=0.75,
        leverage_multiplier=0.80,
        tactical_enabled=True,
        experimental_enabled=False,
        new_positions_enabled=True,
        budget_compression=0.85,
        max_drawdown_limit=0.15,
        position_size_cap=0.80,
        tighten_stops=False,
        stop_multiplier=0.90,
        max_correlation_allowed=0.60
    ),
    RiskState.STRESS: RiskPolicy(
        state=RiskState.STRESS,
        exposure_multiplier=0.50,
        leverage_multiplier=0.50,
        tactical_enabled=False,
        experimental_enabled=False,
        new_positions_enabled=False,
        budget_compression=0.60,
        max_drawdown_limit=0.10,
        position_size_cap=0.50,
        tighten_stops=True,
        stop_multiplier=0.75,
        max_correlation_allowed=0.50
    ),
    RiskState.CRISIS: RiskPolicy(
        state=RiskState.CRISIS,
        exposure_multiplier=0.20,
        leverage_multiplier=0.25,
        tactical_enabled=False,
        experimental_enabled=False,
        new_positions_enabled=False,
        budget_compression=0.30,
        max_drawdown_limit=0.05,
        position_size_cap=0.25,
        tighten_stops=True,
        stop_multiplier=0.50,
        max_correlation_allowed=0.40
    )
}
