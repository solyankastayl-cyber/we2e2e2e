"""
Global Risk Brain Types
=======================

Phase 9.35 - Data structures for global risk management.

GRB is the top-level risk controller for the entire system.
It manages:
- Global exposure limits
- Capital allocation across asset classes
- Crisis detection and response
- Risk state machine
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class RiskState(str, Enum):
    """Global risk states"""
    NORMAL = "NORMAL"       # Full exposure, normal operations
    ELEVATED = "ELEVATED"   # Reduced exposure, heightened monitoring
    STRESS = "STRESS"       # Significant reduction, defensive posture
    CRISIS = "CRISIS"       # Minimal exposure, survival mode
    SURVIVAL = "SURVIVAL"   # Emergency mode, capital preservation only


class DetectorType(str, Enum):
    """Types of risk detectors"""
    VOLATILITY = "VOLATILITY"
    DRAWDOWN = "DRAWDOWN"
    CORRELATION = "CORRELATION"
    LIQUIDITY = "LIQUIDITY"
    REGIME = "REGIME"


class PolicyAction(str, Enum):
    """Actions that GRB can take"""
    REDUCE_EXPOSURE = "REDUCE_EXPOSURE"
    DISABLE_EXPERIMENTAL = "DISABLE_EXPERIMENTAL"
    FREEZE_TACTICAL = "FREEZE_TACTICAL"
    INCREASE_STOPS = "INCREASE_STOPS"
    SHIFT_ALLOCATION = "SHIFT_ALLOCATION"
    FULL_FREEZE = "FULL_FREEZE"


@dataclass
class RiskEnvelope:
    """Risk limits for a given state"""
    state: RiskState
    max_exposure: float = 1.0       # Max total exposure (1.0 = 100%)
    max_leverage: float = 1.5       # Max leverage allowed
    max_drawdown: float = 0.20      # Max acceptable drawdown
    stop_multiplier: float = 1.0    # Stop-loss multiplier
    experimental_allowed: bool = True
    tactical_allowed: bool = True


@dataclass
class CapitalAllocation:
    """Capital allocation across asset classes"""
    equities: float = 0.40
    crypto: float = 0.30
    fx: float = 0.20
    commodities: float = 0.10
    cash: float = 0.0
    
    def validate(self) -> bool:
        total = self.equities + self.crypto + self.fx + self.commodities + self.cash
        return abs(total - 1.0) < 0.01


@dataclass
class DetectorSignal:
    """Signal from a risk detector"""
    detector_type: DetectorType
    name: str
    value: float = 0.0
    threshold: float = 0.0
    triggered: bool = False
    severity: float = 0.0  # 0-1 scale
    message: str = ""
    timestamp: int = 0


@dataclass
class RiskSnapshot:
    """Current risk snapshot"""
    state: RiskState
    envelope: RiskEnvelope
    allocation: CapitalAllocation
    
    # Detector signals
    signals: List[DetectorSignal] = field(default_factory=list)
    triggered_detectors: List[str] = field(default_factory=list)
    
    # Portfolio metrics
    current_exposure: float = 0.0
    current_leverage: float = 0.0
    current_drawdown: float = 0.0
    portfolio_correlation: float = 0.0
    
    # Actions
    active_policies: List[PolicyAction] = field(default_factory=list)
    
    timestamp: int = 0


@dataclass
class StateTransition:
    """Record of state transition"""
    transition_id: str
    from_state: RiskState
    to_state: RiskState
    
    trigger_detectors: List[str] = field(default_factory=list)
    trigger_values: Dict[str, float] = field(default_factory=dict)
    
    actions_taken: List[PolicyAction] = field(default_factory=list)
    
    timestamp: int = 0


@dataclass 
class CrisisPolicy:
    """Policy for crisis handling"""
    policy_id: str
    name: str
    trigger_state: RiskState
    
    actions: List[PolicyAction] = field(default_factory=list)
    allocation_override: Optional[CapitalAllocation] = None
    envelope_override: Optional[RiskEnvelope] = None
    
    auto_activate: bool = True
    requires_confirmation: bool = False


@dataclass
class GRBConfig:
    """Configuration for Global Risk Brain"""
    # Detector thresholds
    vol_spike_threshold: float = 2.0      # Vol / avg vol
    drawdown_threshold: float = 0.10      # 10% drawdown triggers elevation
    correlation_threshold: float = 0.80   # Avg correlation spike
    liquidity_threshold: float = 3.0      # ATR multiplier
    
    # State transition thresholds
    elevated_trigger_score: float = 0.3
    stress_trigger_score: float = 0.5
    crisis_trigger_score: float = 0.7
    survival_trigger_score: float = 0.9
    
    # Recovery settings
    recovery_cooldown_seconds: int = 3600  # 1 hour minimum in each state
    require_all_clear: bool = True
    
    # Default allocations per state
    normal_allocation: CapitalAllocation = field(default_factory=CapitalAllocation)
    crisis_allocation: CapitalAllocation = field(default_factory=lambda: CapitalAllocation(
        equities=0.10, crypto=0.05, fx=0.15, commodities=0.10, cash=0.60
    ))


# Default envelopes per state
DEFAULT_ENVELOPES = {
    RiskState.NORMAL: RiskEnvelope(
        state=RiskState.NORMAL,
        max_exposure=1.0,
        max_leverage=1.5,
        max_drawdown=0.20,
        stop_multiplier=1.0,
        experimental_allowed=True,
        tactical_allowed=True
    ),
    RiskState.ELEVATED: RiskEnvelope(
        state=RiskState.ELEVATED,
        max_exposure=0.8,
        max_leverage=1.2,
        max_drawdown=0.15,
        stop_multiplier=1.2,
        experimental_allowed=True,
        tactical_allowed=True
    ),
    RiskState.STRESS: RiskEnvelope(
        state=RiskState.STRESS,
        max_exposure=0.6,
        max_leverage=1.0,
        max_drawdown=0.10,
        stop_multiplier=1.5,
        experimental_allowed=False,
        tactical_allowed=True
    ),
    RiskState.CRISIS: RiskEnvelope(
        state=RiskState.CRISIS,
        max_exposure=0.3,
        max_leverage=0.6,
        max_drawdown=0.05,
        stop_multiplier=2.0,
        experimental_allowed=False,
        tactical_allowed=False
    ),
    RiskState.SURVIVAL: RiskEnvelope(
        state=RiskState.SURVIVAL,
        max_exposure=0.1,
        max_leverage=0.3,
        max_drawdown=0.03,
        stop_multiplier=3.0,
        experimental_allowed=False,
        tactical_allowed=False
    )
}
