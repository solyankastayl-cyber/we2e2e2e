"""
Structural Bias Types
=====================

Defines bias states and multipliers for different market conditions.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class BiasDirection(str, Enum):
    """Structural bias permission levels"""
    LONG_ONLY = "LONG_ONLY"           # Shorts blocked completely
    LONG_PREFERRED = "LONG_PREFERRED" # Longs 1.0x, Shorts 0.4x
    NEUTRAL = "NEUTRAL"               # Both directions equal
    SHORT_PREFERRED = "SHORT_PREFERRED" # Shorts 1.0x, Longs 0.5x
    SHORT_ONLY = "SHORT_ONLY"         # Longs blocked completely


class TrendState(str, Enum):
    """Long-term trend classification"""
    STRONG_UP = "STRONG_UP"
    UP = "UP"
    FLAT = "FLAT"
    DOWN = "DOWN"
    STRONG_DOWN = "STRONG_DOWN"


class VolatilityRegime(str, Enum):
    """Volatility state classification"""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class DrawdownState(str, Enum):
    """Drawdown severity state"""
    NORMAL = "NORMAL"       # < 5%
    ELEVATED = "ELEVATED"   # 5-10%
    STRESSED = "STRESSED"   # 10-20%
    CRISIS = "CRISIS"       # > 20%


# Asset class configurations
ASSET_CLASS_CONFIG = {
    # Equities - strong structural long bias
    "SPX": {
        "class": "equity_index",
        "default_bias": BiasDirection.LONG_PREFERRED,
        "long_multiplier_default": 1.0,
        "short_multiplier_default": 0.4,
        "enable_crisis_override": True
    },
    "NDX": {
        "class": "equity_index",
        "default_bias": BiasDirection.LONG_PREFERRED,
        "long_multiplier_default": 1.0,
        "short_multiplier_default": 0.35,
        "enable_crisis_override": True
    },
    
    # Crypto - more symmetric, slight long bias
    "BTC": {
        "class": "crypto",
        "default_bias": BiasDirection.NEUTRAL,
        "long_multiplier_default": 1.0,
        "short_multiplier_default": 0.8,
        "enable_crisis_override": True
    },
    "ETH": {
        "class": "crypto",
        "default_bias": BiasDirection.NEUTRAL,
        "long_multiplier_default": 1.0,
        "short_multiplier_default": 0.8,
        "enable_crisis_override": True
    },
    
    # FX - neutral/symmetric
    "DXY": {
        "class": "fx",
        "default_bias": BiasDirection.NEUTRAL,
        "long_multiplier_default": 1.0,
        "short_multiplier_default": 1.0,
        "enable_crisis_override": False
    },
    
    # Commodities - depends on asset
    "GOLD": {
        "class": "commodity",
        "default_bias": BiasDirection.NEUTRAL,
        "long_multiplier_default": 1.0,
        "short_multiplier_default": 0.9,
        "enable_crisis_override": False
    }
}


# Bias direction to multipliers mapping
BIAS_MULTIPLIERS = {
    BiasDirection.LONG_ONLY: {"long": 1.0, "short": 0.0},
    BiasDirection.LONG_PREFERRED: {"long": 1.0, "short": 0.4},
    BiasDirection.NEUTRAL: {"long": 1.0, "short": 1.0},
    BiasDirection.SHORT_PREFERRED: {"long": 0.5, "short": 1.0},
    BiasDirection.SHORT_ONLY: {"long": 0.0, "short": 1.0}
}


@dataclass
class StructuralBiasState:
    """Current structural bias state for an asset"""
    asset: str
    timeframe: str
    timestamp: int
    
    # Market structure assessment
    long_term_trend: TrendState = TrendState.FLAT
    volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    drawdown_state: DrawdownState = DrawdownState.NORMAL
    
    # EMA data
    price: float = 0.0
    ema_50: float = 0.0
    ema_200: float = 0.0
    ema_200_slope: float = 0.0
    
    # Volatility data
    current_vol: float = 0.0
    avg_vol: float = 0.0
    vol_ratio: float = 1.0
    
    # Drawdown data
    current_drawdown: float = 0.0
    peak_price: float = 0.0
    
    # Final bias determination
    bias: BiasDirection = BiasDirection.NEUTRAL
    long_multiplier: float = 1.0
    short_multiplier: float = 1.0
    
    # Override flags
    crisis_override_active: bool = False
    manual_override: Optional[BiasDirection] = None
    
    # Metadata
    reasons: List[str] = field(default_factory=list)


@dataclass 
class BiasAdjustedSignal:
    """Signal after bias adjustment"""
    original_weight: float
    bias_multiplier: float
    adjusted_weight: float
    direction: str
    bias_state: BiasDirection
    allowed: bool
    rejection_reason: Optional[str] = None
