"""
Market Microstructure Lab Types
===============================

Phase B - Data structures for realistic market simulation.

Microstructure Lab models real market mechanics:
- Spread dynamics
- Slippage curves
- Execution delays
- Gap/overnight risk
- Liquidity stress
- Fill quality
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class MarketCondition(str, Enum):
    """Market condition states"""
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    STRESS = "STRESS"
    CRISIS = "CRISIS"


class FillQuality(str, Enum):
    """Fill quality types"""
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    DELAYED = "DELAYED"
    BAD = "BAD"
    REJECTED = "REJECTED"


class AssetClass(str, Enum):
    """Asset classes with different microstructure"""
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    FX = "FX"
    COMMODITY = "COMMODITY"


@dataclass
class SpreadProfile:
    """Spread characteristics for an asset"""
    asset: str
    asset_class: AssetClass
    
    baseline_spread_bps: float = 5.0    # Normal spread
    stress_multiplier: float = 2.0       # Spread in stress
    crisis_multiplier: float = 4.0       # Spread in crisis
    
    # Session effects
    open_spread_multiplier: float = 1.5  # First 30 min
    close_spread_multiplier: float = 1.3 # Last 30 min
    overnight_spread_multiplier: float = 2.0


@dataclass
class SlippageProfile:
    """Slippage model for an asset"""
    asset: str
    asset_class: AssetClass
    
    base_slippage_bps: float = 3.0
    impact_coefficient: float = 0.1      # Price impact per $10k
    volatility_multiplier: float = 1.0   # Adjustment for vol
    
    # Size-dependent
    small_order_threshold: float = 1000.0   # $ below this = minimal slippage
    large_order_threshold: float = 100000.0 # $ above this = heavy slippage


@dataclass
class DelayModel:
    """Execution delay model"""
    asset: str
    asset_class: AssetClass
    
    # Delays in milliseconds
    decision_delay_ms: float = 100.0
    routing_delay_ms: float = 50.0
    exchange_delay_ms: float = 20.0
    
    # Total typical delay
    total_delay_ms: float = 170.0
    
    # Delay impact on price (bps per second delay)
    delay_price_impact_bps: float = 0.5


@dataclass
class GapProfile:
    """Gap/overnight risk profile"""
    asset: str
    asset_class: AssetClass
    
    # Gap frequency
    avg_gap_frequency: float = 0.1      # % of days with significant gap
    avg_gap_size_pct: float = 0.02      # Average gap size
    max_gap_size_pct: float = 0.10      # Maximum observed
    
    # Gap distribution
    gap_up_probability: float = 0.5
    gap_down_probability: float = 0.5
    
    # Stop-through risk
    stop_through_frequency: float = 0.05  # % of stops that gap through


@dataclass
class LiquidityProfile:
    """Liquidity characteristics"""
    asset: str
    asset_class: AssetClass
    
    avg_daily_volume: float = 1000000.0
    max_participation_pct: float = 0.01   # Max % of volume
    
    # Stress behavior
    stress_volume_multiplier: float = 0.5  # Volume drops in stress
    crisis_volume_multiplier: float = 0.3
    
    # Depth
    depth_10bps: float = 100000.0   # $ to move price 10bps
    depth_50bps: float = 500000.0   # $ to move price 50bps


@dataclass
class FillResult:
    """Result of a fill simulation"""
    order_id: str
    asset: str
    
    # Order details
    side: str  # BUY or SELL
    requested_size: float
    
    # Fill details
    filled_size: float
    avg_fill_price: float
    intended_price: float
    
    # Quality
    fill_quality: FillQuality
    fill_rate: float  # Fraction filled
    
    # Costs
    spread_cost_bps: float = 0.0
    slippage_cost_bps: float = 0.0
    delay_cost_bps: float = 0.0
    gap_cost_bps: float = 0.0
    total_cost_bps: float = 0.0
    
    # Flags
    was_delayed: bool = False
    was_partial: bool = False
    had_gap_through: bool = False
    
    timestamp: int = 0


@dataclass
class MicrostructureScenario:
    """Scenario for microstructure testing"""
    scenario_id: str
    name: str
    condition: MarketCondition
    
    # Modifiers
    spread_multiplier: float = 1.0
    slippage_multiplier: float = 1.0
    delay_multiplier: float = 1.0
    liquidity_multiplier: float = 1.0
    gap_probability_multiplier: float = 1.0
    
    # Behaviors
    allow_partial_fills: bool = True
    allow_rejections: bool = False
    
    description: str = ""


@dataclass
class ExecutionFragility:
    """Execution fragility analysis for a strategy"""
    strategy: str
    
    # Sensitivity scores (0-1, higher = more sensitive)
    spread_sensitivity: float = 0.0
    slippage_sensitivity: float = 0.0
    delay_sensitivity: float = 0.0
    gap_sensitivity: float = 0.0
    liquidity_sensitivity: float = 0.0
    
    # Overall fragility
    overall_fragility: float = 0.0
    fragility_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Recommendations
    max_recommended_capital: float = 0.0
    recommended_asset_classes: List[AssetClass] = field(default_factory=list)


@dataclass
class AssetClassProfile:
    """Complete microstructure profile for asset class"""
    asset_class: AssetClass
    name: str
    
    spread: SpreadProfile = None
    slippage: SlippageProfile = None
    delay: DelayModel = None
    gap: GapProfile = None
    liquidity: LiquidityProfile = None
    
    # Summary characteristics
    typical_cost_bps: float = 0.0
    stress_cost_bps: float = 0.0
    overnight_risk: str = "LOW"  # LOW, MEDIUM, HIGH
    
    notes: List[str] = field(default_factory=list)


# Default scenarios
DEFAULT_SCENARIOS = {
    MarketCondition.NORMAL: MicrostructureScenario(
        scenario_id="NORMAL",
        name="Normal Market",
        condition=MarketCondition.NORMAL,
        spread_multiplier=1.0,
        slippage_multiplier=1.0,
        delay_multiplier=1.0,
        liquidity_multiplier=1.0,
        description="Standard market conditions"
    ),
    MarketCondition.ELEVATED: MicrostructureScenario(
        scenario_id="ELEVATED",
        name="Elevated Stress",
        condition=MarketCondition.ELEVATED,
        spread_multiplier=1.5,
        slippage_multiplier=1.5,
        delay_multiplier=1.3,
        liquidity_multiplier=0.8,
        description="Heightened market stress"
    ),
    MarketCondition.STRESS: MicrostructureScenario(
        scenario_id="STRESS",
        name="Market Stress",
        condition=MarketCondition.STRESS,
        spread_multiplier=2.5,
        slippage_multiplier=2.0,
        delay_multiplier=2.0,
        liquidity_multiplier=0.5,
        allow_partial_fills=True,
        description="Significant market stress"
    ),
    MarketCondition.CRISIS: MicrostructureScenario(
        scenario_id="CRISIS",
        name="Market Crisis",
        condition=MarketCondition.CRISIS,
        spread_multiplier=4.0,
        slippage_multiplier=3.0,
        delay_multiplier=3.0,
        liquidity_multiplier=0.3,
        gap_probability_multiplier=3.0,
        allow_partial_fills=True,
        allow_rejections=True,
        description="Severe market crisis"
    )
}
