"""
Capital Simulation Engine Types
===============================

Phase 9.36 - Data structures for capital-aware simulation.

CSE simulates strategies with real money mechanics:
- Position sizing
- Slippage
- Fees
- Liquidity constraints
- Market impact
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class CapitalTier(str, Enum):
    """Capital deployment tiers"""
    MICRO = "MICRO"       # $100
    SMALL = "SMALL"       # $1,000
    MEDIUM = "MEDIUM"     # $10,000
    LARGE = "LARGE"       # $100,000
    FUND = "FUND"         # $1,000,000+


class AssetClass(str, Enum):
    """Asset classes for liquidity modeling"""
    CRYPTO = "CRYPTO"
    EQUITY = "EQUITY"
    FX = "FX"
    COMMODITY = "COMMODITY"


@dataclass
class CapitalProfile:
    """Capital deployment profile"""
    profile_id: str
    name: str
    tier: CapitalTier
    
    capital: float = 10000.0          # Total capital
    risk_per_trade: float = 0.01      # Risk per trade (1%)
    max_position_pct: float = 0.10    # Max position size (10% of capital)
    max_positions: int = 10           # Max concurrent positions


@dataclass
class LiquidityProfile:
    """Liquidity constraints for an asset"""
    asset: str
    asset_class: AssetClass
    
    avg_daily_volume: float = 1000000.0   # Average daily volume in $
    avg_spread_bps: float = 10.0          # Average spread in basis points
    max_participation: float = 0.01        # Max % of daily volume (1%)
    
    # Depth-based impact
    depth_10_pct: float = 100000.0   # $ to move price 10%
    depth_1_pct: float = 10000.0     # $ to move price 1%


@dataclass
class SlippageModel:
    """Slippage model for execution"""
    base_spread_bps: float = 5.0      # Base spread in basis points
    impact_factor: float = 0.1        # Price impact per $10k traded
    delay_ms: float = 100.0           # Execution delay in ms
    
    # Volatility-adjusted
    vol_multiplier: float = 1.0       # Multiplier during high vol


@dataclass
class FeeModel:
    """Fee structure"""
    maker_fee_bps: float = 2.0        # Maker fee in bps
    taker_fee_bps: float = 5.0        # Taker fee in bps
    funding_rate_daily: float = 0.0   # Daily funding rate (futures)
    
    # Fixed fees
    min_fee: float = 0.0              # Minimum fee per trade
    platform_fee_pct: float = 0.0     # Platform/broker fee


@dataclass
class TradeExecution:
    """Single trade execution result"""
    trade_id: str
    
    # Order details
    side: str                 # BUY or SELL
    intended_size: float      # Intended position size in $
    actual_size: float        # Actual size after liquidity check
    entry_price: float        # Intended entry price
    executed_price: float     # Actual execution price
    
    # Costs
    slippage_cost: float = 0.0
    fee_cost: float = 0.0
    impact_cost: float = 0.0
    total_cost: float = 0.0
    
    # Metrics
    cost_bps: float = 0.0     # Total cost in basis points
    fill_rate: float = 1.0    # Fraction of intended size filled
    
    # Flags
    liquidity_limited: bool = False
    partial_fill: bool = False
    
    timestamp: int = 0


@dataclass
class StrategySimulation:
    """Simulation result for a strategy at a capital level"""
    simulation_id: str
    strategy_id: str
    strategy_name: str
    
    # Capital profile
    capital_tier: CapitalTier
    capital: float
    
    # Results
    trades: int = 0
    winning_trades: int = 0
    
    # P&L
    gross_pnl: float = 0.0
    slippage_costs: float = 0.0
    fee_costs: float = 0.0
    impact_costs: float = 0.0
    net_pnl: float = 0.0
    
    # Metrics
    gross_sharpe: float = 0.0
    net_sharpe: float = 0.0
    gross_pf: float = 0.0
    net_pf: float = 0.0
    
    # Liquidity
    liquidity_limited_trades: int = 0
    avg_fill_rate: float = 1.0
    
    # Capacity
    capacity_utilized: float = 0.0
    
    created_at: int = 0


@dataclass
class CapacityAnalysis:
    """Capacity analysis for a strategy"""
    strategy_id: str
    strategy_name: str
    
    # Results by tier
    tier_results: Dict[str, StrategySimulation] = field(default_factory=dict)
    
    # Capacity metrics
    max_deployable_capital: float = 0.0
    capacity_limit_reason: str = ""
    
    # Decay curves
    sharpe_at_10k: float = 0.0
    sharpe_at_100k: float = 0.0
    sharpe_at_1m: float = 0.0
    
    pf_at_10k: float = 0.0
    pf_at_100k: float = 0.0
    pf_at_1m: float = 0.0
    
    # Recommendations
    optimal_tier: CapitalTier = CapitalTier.MEDIUM
    
    created_at: int = 0


# Default profiles
DEFAULT_CAPITAL_PROFILES = {
    CapitalTier.MICRO: CapitalProfile(
        profile_id="MICRO_100",
        name="Micro ($100)",
        tier=CapitalTier.MICRO,
        capital=100,
        risk_per_trade=0.02,
        max_position_pct=0.20,
        max_positions=3
    ),
    CapitalTier.SMALL: CapitalProfile(
        profile_id="SMALL_1K",
        name="Small ($1K)",
        tier=CapitalTier.SMALL,
        capital=1000,
        risk_per_trade=0.02,
        max_position_pct=0.15,
        max_positions=5
    ),
    CapitalTier.MEDIUM: CapitalProfile(
        profile_id="MEDIUM_10K",
        name="Medium ($10K)",
        tier=CapitalTier.MEDIUM,
        capital=10000,
        risk_per_trade=0.01,
        max_position_pct=0.10,
        max_positions=10
    ),
    CapitalTier.LARGE: CapitalProfile(
        profile_id="LARGE_100K",
        name="Large ($100K)",
        tier=CapitalTier.LARGE,
        capital=100000,
        risk_per_trade=0.01,
        max_position_pct=0.05,
        max_positions=15
    ),
    CapitalTier.FUND: CapitalProfile(
        profile_id="FUND_1M",
        name="Fund ($1M)",
        tier=CapitalTier.FUND,
        capital=1000000,
        risk_per_trade=0.005,
        max_position_pct=0.03,
        max_positions=20
    )
}


# Default liquidity profiles
DEFAULT_LIQUIDITY = {
    "BTC": LiquidityProfile(
        asset="BTC",
        asset_class=AssetClass.CRYPTO,
        avg_daily_volume=20_000_000_000,
        avg_spread_bps=5,
        max_participation=0.001,
        depth_10_pct=100_000_000,
        depth_1_pct=10_000_000
    ),
    "ETH": LiquidityProfile(
        asset="ETH",
        asset_class=AssetClass.CRYPTO,
        avg_daily_volume=10_000_000_000,
        avg_spread_bps=8,
        max_participation=0.001,
        depth_10_pct=50_000_000,
        depth_1_pct=5_000_000
    ),
    "SPX": LiquidityProfile(
        asset="SPX",
        asset_class=AssetClass.EQUITY,
        avg_daily_volume=500_000_000_000,
        avg_spread_bps=1,
        max_participation=0.0001,
        depth_10_pct=10_000_000_000,
        depth_1_pct=1_000_000_000
    )
}
