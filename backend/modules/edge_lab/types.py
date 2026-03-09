"""
Edge Research Lab Types
=======================

Phase A - Data structures for edge research and analysis.

Edge Lab answers fundamental questions:
1. Where does edge exist?
2. Where does it break?
3. How stable is it across regimes?
4. How does it transfer across assets?
5. How does it decay over time?
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class EdgeStrength(str, Enum):
    """Edge strength classification"""
    STRONG = "STRONG"       # PF > 1.3, Sharpe > 1.0
    MEDIUM = "MEDIUM"       # PF 1.1-1.3, Sharpe 0.5-1.0
    WEAK = "WEAK"           # PF 1.0-1.1, Sharpe 0.3-0.5
    NONE = "NONE"           # PF < 1.0, Sharpe < 0.3
    NEGATIVE = "NEGATIVE"   # PF < 0.9, losing edge


class RegimeType(str, Enum):
    """Market regime types"""
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    EXPANSION = "EXPANSION"
    CONTRACTION = "CONTRACTION"
    CRISIS = "CRISIS"


class AssetClass(str, Enum):
    """Asset classes"""
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    FX = "FX"
    COMMODITY = "COMMODITY"


class StrategyFamily(str, Enum):
    """Strategy families"""
    TREND = "TREND"
    BREAKOUT = "BREAKOUT"
    MOMENTUM = "MOMENTUM"
    MEAN_REVERSION = "MEAN_REVERSION"
    VOLATILITY = "VOLATILITY"
    CARRY = "CARRY"


@dataclass
class EdgeMapEntry:
    """Single entry in the edge map"""
    strategy: str
    asset: str
    asset_class: AssetClass
    regime: RegimeType
    
    # Core metrics
    trades: int = 0
    pf: float = 0.0
    sharpe: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    
    # Edge classification
    edge_strength: EdgeStrength = EdgeStrength.NONE
    
    # Confidence
    sample_size_score: float = 0.0  # Higher = more trades
    consistency_score: float = 0.0   # Higher = more stable


@dataclass
class DecadeAnalysis:
    """Edge analysis by decade"""
    strategy: str
    family: StrategyFamily
    
    decade: str  # "1990s", "2000s", etc.
    start_year: int = 0
    end_year: int = 0
    
    # Metrics
    trades: int = 0
    pf: float = 0.0
    sharpe: float = 0.0
    win_rate: float = 0.0
    
    # Comparison
    vs_previous_decade_pf: float = 0.0
    vs_previous_decade_sharpe: float = 0.0
    
    edge_strength: EdgeStrength = EdgeStrength.NONE


@dataclass
class RegimeEdge:
    """Edge stability by regime"""
    strategy: str
    family: StrategyFamily
    
    # Performance by regime
    trend_up_pf: float = 0.0
    trend_up_sharpe: float = 0.0
    trend_down_pf: float = 0.0
    trend_down_sharpe: float = 0.0
    range_pf: float = 0.0
    range_sharpe: float = 0.0
    expansion_pf: float = 0.0
    expansion_sharpe: float = 0.0
    crisis_pf: float = 0.0
    crisis_sharpe: float = 0.0
    
    # Classification by regime
    best_regime: RegimeType = RegimeType.TREND_UP
    worst_regime: RegimeType = RegimeType.CRISIS
    
    # Fragility
    regime_spread: float = 0.0  # Difference between best and worst
    is_regime_dependent: bool = False


@dataclass
class CrossAssetEdge:
    """Edge transferability across assets"""
    strategy: str
    family: StrategyFamily
    
    # Performance by asset
    equity_pf: float = 0.0
    equity_sharpe: float = 0.0
    crypto_pf: float = 0.0
    crypto_sharpe: float = 0.0
    fx_pf: float = 0.0
    fx_sharpe: float = 0.0
    commodity_pf: float = 0.0
    commodity_sharpe: float = 0.0
    
    # Transferability
    best_asset_class: AssetClass = AssetClass.EQUITY
    worst_asset_class: AssetClass = AssetClass.COMMODITY
    
    # Robustness
    cross_asset_consistency: float = 0.0  # 0-1, higher = more consistent
    is_asset_specific: bool = False


@dataclass
class FamilyRobustness:
    """Robustness analysis for strategy family"""
    family: StrategyFamily
    
    # Overall metrics
    avg_pf: float = 0.0
    avg_sharpe: float = 0.0
    strategy_count: int = 0
    
    # Stability
    pf_std: float = 0.0
    sharpe_std: float = 0.0
    stability_score: float = 0.0  # 0-1
    
    # Regime robustness
    all_regime_positive: bool = False
    worst_regime_pf: float = 0.0
    
    # Asset robustness
    all_asset_positive: bool = False
    worst_asset_pf: float = 0.0
    
    # Classification
    robustness_level: str = "MEDIUM"  # FRAGILE, MEDIUM, ROBUST, ANTIFRAGILE


@dataclass
class EdgeDecay:
    """Edge decay over time"""
    strategy: str
    family: StrategyFamily
    
    # Current vs historical
    current_pf: float = 0.0
    historical_pf: float = 0.0
    current_sharpe: float = 0.0
    historical_sharpe: float = 0.0
    
    # Decay rates
    pf_decay_rate: float = 0.0      # Negative = decay
    sharpe_decay_rate: float = 0.0
    win_rate_decay_rate: float = 0.0
    
    # Time periods
    lookback_years: int = 10
    recent_years: int = 3
    
    # Classification
    is_decaying: bool = False
    decay_severity: str = "NONE"  # NONE, MILD, MODERATE, SEVERE


@dataclass
class FragilityAnalysis:
    """Edge fragility assessment"""
    strategy: str
    family: StrategyFamily
    
    # Dependencies
    requires_specific_regime: bool = False
    required_regimes: List[RegimeType] = field(default_factory=list)
    
    requires_specific_asset: bool = False
    required_assets: List[str] = field(default_factory=list)
    
    requires_specific_decade: bool = False
    
    # Fragility score
    fragility_score: float = 0.0  # 0 = robust, 1 = fragile
    
    # Working conditions
    working_conditions: int = 0  # Count of regime/asset combos where edge exists
    total_conditions: int = 0
    
    # Classification
    fragility_level: str = "MEDIUM"  # ROBUST, MEDIUM, FRAGILE, VERY_FRAGILE


@dataclass
class EdgeReport:
    """Complete edge research report"""
    report_id: str
    
    # Summary
    total_strategies: int = 0
    strategies_with_edge: int = 0
    strategies_decaying: int = 0
    
    # Best performers
    strongest_strategy: str = ""
    strongest_family: StrategyFamily = StrategyFamily.TREND
    best_regime: RegimeType = RegimeType.TREND_UP
    best_asset_class: AssetClass = AssetClass.EQUITY
    
    # Weakest
    weakest_strategy: str = ""
    most_fragile_family: StrategyFamily = StrategyFamily.BREAKOUT
    worst_regime: RegimeType = RegimeType.CRISIS
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    created_at: int = 0
