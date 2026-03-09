"""
Hierarchical Allocator Types
============================

Types for family-based portfolio allocation.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class FamilyType(str, Enum):
    """Strategy family types"""
    TREND = "trend"
    REVERSAL = "reversal"
    BREAKOUT = "breakout"
    MOMENTUM = "momentum"
    STRUCTURE = "structure"
    HARMONIC = "harmonic"
    MEAN_REVERSION = "mean_reversion"
    EXPERIMENTAL = "experimental"


# Default family risk budgets (total = 100%)
DEFAULT_FAMILY_BUDGETS = {
    FamilyType.TREND: 0.25,
    FamilyType.BREAKOUT: 0.20,
    FamilyType.MOMENTUM: 0.15,
    FamilyType.REVERSAL: 0.15,
    FamilyType.STRUCTURE: 0.10,
    FamilyType.HARMONIC: 0.08,
    FamilyType.MEAN_REVERSION: 0.05,
    FamilyType.EXPERIMENTAL: 0.02,
}

# Strategy to family mapping
STRATEGY_FAMILY_MAP = {
    "MTF_BREAKOUT": FamilyType.BREAKOUT,
    "CHANNEL_BREAKOUT": FamilyType.BREAKOUT,
    "FLAG_BREAKOUT": FamilyType.BREAKOUT,
    "DOUBLE_BOTTOM": FamilyType.REVERSAL,
    "DOUBLE_TOP": FamilyType.REVERSAL,
    "HEAD_SHOULDERS": FamilyType.REVERSAL,
    "MOMENTUM_CONTINUATION": FamilyType.MOMENTUM,
    "TREND_PULLBACK": FamilyType.TREND,
    "EMA_CROSSOVER": FamilyType.TREND,
    "HARMONIC_ABCD": FamilyType.HARMONIC,
    "GARTLEY": FamilyType.HARMONIC,
    "WEDGE_RISING": FamilyType.STRUCTURE,
    "WEDGE_FALLING": FamilyType.STRUCTURE,
    "TRIANGLE": FamilyType.STRUCTURE,
    "RSI_DIVERGENCE": FamilyType.MEAN_REVERSION,
    "BOLLINGER_SQUEEZE": FamilyType.MEAN_REVERSION,
}


@dataclass
class FamilyConfig:
    """Configuration for a strategy family"""
    family_type: FamilyType
    risk_budget: float              # Max allocation to this family (0-1)
    max_strategies: int = 10        # Max strategies in family
    min_strategy_weight: float = 0.05   # Min weight for a strategy
    max_strategy_weight: float = 0.50   # Max weight within family
    
    # Regime adjustments
    regime_multipliers: Dict[str, float] = field(default_factory=dict)


@dataclass
class FamilyAllocation:
    """Allocation result for a single family"""
    family_type: FamilyType
    budget: float                   # Total budget allocated
    strategies: List[str]           # Strategies in this family
    weights: Dict[str, float]       # Strategy weights (within family)
    absolute_weights: Dict[str, float]  # Absolute portfolio weights
    
    family_return: float = 0.0
    family_vol: float = 0.0
    family_sharpe: float = 0.0
    
    intra_correlation: float = 0.0  # Avg correlation within family


@dataclass
class HierarchicalPortfolio:
    """Complete hierarchical portfolio"""
    timestamp: int
    
    # Family allocations
    family_allocations: Dict[FamilyType, FamilyAllocation]
    
    # Final weights (all strategies)
    final_weights: Dict[str, float]
    
    # Portfolio metrics
    expected_return: float
    expected_vol: float
    expected_sharpe: float
    
    # Diversification
    effective_families: float       # Effective number of families
    effective_strategies: float     # Effective number of strategies
    diversification_ratio: float
    
    # Risk decomposition
    family_risk_contribution: Dict[str, float] = field(default_factory=dict)


@dataclass
class AlphaInput:
    """Input for a single alpha"""
    strategy_id: str
    family: FamilyType
    returns: List[float]
    expected_return: float
    volatility: float
    sharpe: float
    health_score: float = 1.0       # From self-healing
    regime_fit: float = 1.0         # From regime detection
