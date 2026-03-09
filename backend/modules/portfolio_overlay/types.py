"""
Portfolio Overlay Types
=======================

Defines overlay state, config and multipliers.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class DrawdownState(str, Enum):
    """Drawdown severity levels"""
    NORMAL = "NORMAL"       # < 5%
    ELEVATED = "ELEVATED"   # 5-10%
    WARNING = "WARNING"     # 10-15%
    DANGER = "DANGER"       # 15-20%
    CRITICAL = "CRITICAL"   # > 20%


class ConvictionLevel(str, Enum):
    """Signal conviction levels"""
    HIGH = "HIGH"           # > 0.7
    MEDIUM = "MEDIUM"       # 0.4-0.7
    LOW = "LOW"             # < 0.4


# Drawdown multipliers
DRAWDOWN_MULTIPLIERS = {
    DrawdownState.NORMAL: 1.0,
    DrawdownState.ELEVATED: 0.85,
    DrawdownState.WARNING: 0.70,
    DrawdownState.DANGER: 0.50,
    DrawdownState.CRITICAL: 0.30
}

# Conviction multipliers
CONVICTION_MULTIPLIERS = {
    ConvictionLevel.HIGH: 1.4,
    ConvictionLevel.MEDIUM: 1.0,
    ConvictionLevel.LOW: 0.6
}


@dataclass
class OverlayConfig:
    """Configuration for Portfolio Overlay"""
    # Volatility targeting
    target_volatility: float = 0.12  # 12% annual vol target
    vol_lookback_days: int = 20
    min_vol_multiplier: float = 0.5
    max_vol_multiplier: float = 2.0
    
    # Conviction weighting
    high_conviction_threshold: float = 0.7
    low_conviction_threshold: float = 0.4
    use_strategy_score: bool = True
    use_regime_confidence: bool = True
    use_health_score: bool = True
    
    # Drawdown control
    dd_threshold_elevated: float = 0.05
    dd_threshold_warning: float = 0.10
    dd_threshold_danger: float = 0.15
    dd_threshold_critical: float = 0.20
    
    # Position limits
    max_position_multiplier: float = 2.0
    min_position_multiplier: float = 0.2


@dataclass
class OverlayState:
    """Current state of the overlay layer"""
    timestamp: int
    
    # Volatility
    target_volatility: float = 0.12
    realized_volatility: float = 0.12
    volatility_multiplier: float = 1.0
    
    # Conviction (aggregated)
    strategy_score: float = 0.5
    regime_confidence: float = 0.5
    health_score: float = 1.0
    conviction_level: ConvictionLevel = ConvictionLevel.MEDIUM
    conviction_multiplier: float = 1.0
    
    # Drawdown
    current_drawdown: float = 0.0
    peak_equity: float = 0.0
    drawdown_state: DrawdownState = DrawdownState.NORMAL
    drawdown_multiplier: float = 1.0
    
    # Final
    final_multiplier: float = 1.0
    
    # Reasons for current state
    reasons: List[str] = field(default_factory=list)


@dataclass
class SizedPosition:
    """Position with overlay-adjusted size"""
    original_size: float
    volatility_adjusted: float
    conviction_adjusted: float
    drawdown_adjusted: float
    final_size: float
    multipliers: Dict[str, float] = field(default_factory=dict)
