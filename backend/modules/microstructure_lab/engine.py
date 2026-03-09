"""
Market Microstructure Lab Engine
================================

Phase B - Realistic market simulation engine.

Models real market mechanics:
- Spread dynamics by asset/regime
- Slippage curves
- Execution delays
- Gap/overnight risk
- Liquidity stress
- Fill quality
"""

import time
import uuid
import math
import random
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from .types import (
    MarketCondition, FillQuality, AssetClass,
    SpreadProfile, SlippageProfile, DelayModel, GapProfile, LiquidityProfile,
    FillResult, MicrostructureScenario, ExecutionFragility, AssetClassProfile,
    DEFAULT_SCENARIOS
)


class MicrostructureEngine:
    """
    Market Microstructure Simulation Engine.
    
    Simulates realistic execution with all market frictions.
    """
    
    def __init__(self):
        # Profiles
        self.spread_profiles: Dict[str, SpreadProfile] = {}
        self.slippage_profiles: Dict[str, SlippageProfile] = {}
        self.delay_models: Dict[str, DelayModel] = {}
        self.gap_profiles: Dict[str, GapProfile] = {}
        self.liquidity_profiles: Dict[str, LiquidityProfile] = {}
        
        # Scenarios
        self.scenarios = dict(DEFAULT_SCENARIOS)
        
        # Results
        self.fill_results: List[FillResult] = []
        self.fragility_analyses: Dict[str, ExecutionFragility] = {}
        
        # Initialize default profiles
        self._init_default_profiles()
    
    def _init_default_profiles(self):
        """Initialize default asset class profiles"""
        
        # EQUITY profile
        self._create_asset_profile(
            asset="SPX",
            asset_class=AssetClass.EQUITY,
            spread_bps=2.0,
            slippage_bps=3.0,
            delay_ms=100,
            gap_freq=0.15,
            gap_size=0.015,
            daily_volume=500_000_000_000
        )
        
        # CRYPTO profile
        self._create_asset_profile(
            asset="BTC",
            asset_class=AssetClass.CRYPTO,
            spread_bps=5.0,
            slippage_bps=5.0,
            delay_ms=50,
            gap_freq=0.02,  # 24/7 trading
            gap_size=0.03,
            daily_volume=20_000_000_000
        )
        
        self._create_asset_profile(
            asset="ETH",
            asset_class=AssetClass.CRYPTO,
            spread_bps=8.0,
            slippage_bps=7.0,
            delay_ms=50,
            gap_freq=0.02,
            gap_size=0.04,
            daily_volume=10_000_000_000
        )
        
        # FX profile
        self._create_asset_profile(
            asset="EURUSD",
            asset_class=AssetClass.FX,
            spread_bps=1.0,
            slippage_bps=1.5,
            delay_ms=30,
            gap_freq=0.05,  # Weekend gaps
            gap_size=0.008,
            daily_volume=100_000_000_000
        )
        
        # COMMODITY profile
        self._create_asset_profile(
            asset="GOLD",
            asset_class=AssetClass.COMMODITY,
            spread_bps=3.0,
            slippage_bps=4.0,
            delay_ms=80,
            gap_freq=0.10,
            gap_size=0.012,
            daily_volume=50_000_000_000
        )
    
    def _create_asset_profile(
        self,
        asset: str,
        asset_class: AssetClass,
        spread_bps: float,
        slippage_bps: float,
        delay_ms: float,
        gap_freq: float,
        gap_size: float,
        daily_volume: float
    ):
        """Create profiles for an asset"""
        
        self.spread_profiles[asset] = SpreadProfile(
            asset=asset,
            asset_class=asset_class,
            baseline_spread_bps=spread_bps,
            stress_multiplier=2.0 if asset_class == AssetClass.CRYPTO else 2.5,
            crisis_multiplier=4.0 if asset_class == AssetClass.CRYPTO else 5.0
        )
        
        self.slippage_profiles[asset] = SlippageProfile(
            asset=asset,
            asset_class=asset_class,
            base_slippage_bps=slippage_bps,
            impact_coefficient=0.15 if asset_class == AssetClass.CRYPTO else 0.1
        )
        
        self.delay_models[asset] = DelayModel(
            asset=asset,
            asset_class=asset_class,
            total_delay_ms=delay_ms
        )
        
        self.gap_profiles[asset] = GapProfile(
            asset=asset,
            asset_class=asset_class,
            avg_gap_frequency=gap_freq,
            avg_gap_size_pct=gap_size,
            max_gap_size_pct=gap_size * 5
        )
        
        self.liquidity_profiles[asset] = LiquidityProfile(
            asset=asset,
            asset_class=asset_class,
            avg_daily_volume=daily_volume,
            max_participation_pct=0.01 if asset_class == AssetClass.CRYPTO else 0.001
        )
    
    # ============================================
    # Spread Model
    # ============================================
    
    def calculate_spread(
        self,
        asset: str,
        condition: MarketCondition = MarketCondition.NORMAL,
        is_open: bool = False,
        is_close: bool = False
    ) -> Dict:
        """Calculate effective spread"""
        
        profile = self.spread_profiles.get(asset)
        if not profile:
            profile = SpreadProfile(asset=asset, asset_class=AssetClass.EQUITY)
        
        # Base spread
        spread = profile.baseline_spread_bps
        
        # Condition multiplier
        if condition == MarketCondition.ELEVATED:
            spread *= 1.5
        elif condition == MarketCondition.STRESS:
            spread *= profile.stress_multiplier
        elif condition == MarketCondition.CRISIS:
            spread *= profile.crisis_multiplier
        
        # Session effects
        if is_open:
            spread *= profile.open_spread_multiplier
        elif is_close:
            spread *= profile.close_spread_multiplier
        
        return {
            "asset": asset,
            "base_spread_bps": profile.baseline_spread_bps,
            "effective_spread_bps": round(spread, 2),
            "condition": condition.value,
            "multiplier_applied": round(spread / profile.baseline_spread_bps, 2)
        }
    
    # ============================================
    # Slippage Model
    # ============================================
    
    def calculate_slippage(
        self,
        asset: str,
        order_size: float,
        condition: MarketCondition = MarketCondition.NORMAL,
        volatility_mult: float = 1.0
    ) -> Dict:
        """Calculate slippage with square-root impact model"""
        
        profile = self.slippage_profiles.get(asset)
        if not profile:
            profile = SlippageProfile(asset=asset, asset_class=AssetClass.EQUITY)
        
        liquidity = self.liquidity_profiles.get(asset)
        if not liquidity:
            liquidity = LiquidityProfile(asset=asset, asset_class=AssetClass.EQUITY)
        
        # Base slippage
        slippage = profile.base_slippage_bps
        
        # Size impact (square root model)
        if order_size > profile.small_order_threshold:
            size_factor = math.sqrt(order_size / 10000)
            slippage += profile.impact_coefficient * size_factor
        
        # Large order penalty
        if order_size > profile.large_order_threshold:
            large_factor = (order_size / profile.large_order_threshold) ** 0.5
            slippage *= large_factor
        
        # Volatility adjustment
        slippage *= volatility_mult * profile.volatility_multiplier
        
        # Condition multiplier
        scenario = self.scenarios.get(condition)
        if scenario:
            slippage *= scenario.slippage_multiplier
        
        return {
            "asset": asset,
            "order_size": order_size,
            "base_slippage_bps": profile.base_slippage_bps,
            "effective_slippage_bps": round(slippage, 2),
            "size_impact_bps": round(slippage - profile.base_slippage_bps, 2),
            "condition": condition.value
        }
    
    # ============================================
    # Delay Model
    # ============================================
    
    def calculate_delay_cost(
        self,
        asset: str,
        condition: MarketCondition = MarketCondition.NORMAL,
        volatility: float = 0.02  # Daily vol
    ) -> Dict:
        """Calculate cost of execution delay"""
        
        delay_model = self.delay_models.get(asset)
        if not delay_model:
            delay_model = DelayModel(asset=asset, asset_class=AssetClass.EQUITY)
        
        scenario = self.scenarios.get(condition)
        
        # Effective delay
        delay_ms = delay_model.total_delay_ms
        if scenario:
            delay_ms *= scenario.delay_multiplier
        
        # Price impact of delay
        # Higher vol = more price movement during delay
        delay_seconds = delay_ms / 1000
        price_impact_bps = delay_model.delay_price_impact_bps * delay_seconds * volatility * 100
        
        return {
            "asset": asset,
            "base_delay_ms": delay_model.total_delay_ms,
            "effective_delay_ms": round(delay_ms, 1),
            "price_impact_bps": round(price_impact_bps, 2),
            "condition": condition.value
        }
    
    # ============================================
    # Gap Model
    # ============================================
    
    def simulate_gap_risk(
        self,
        asset: str,
        position_size: float,
        stop_distance_pct: float,
        condition: MarketCondition = MarketCondition.NORMAL
    ) -> Dict:
        """Simulate overnight gap risk"""
        
        gap_profile = self.gap_profiles.get(asset)
        if not gap_profile:
            gap_profile = GapProfile(asset=asset, asset_class=AssetClass.EQUITY)
        
        scenario = self.scenarios.get(condition)
        gap_prob_mult = scenario.gap_probability_multiplier if scenario else 1.0
        
        # Gap occurrence probability
        gap_probability = gap_profile.avg_gap_frequency * gap_prob_mult
        
        # Expected gap size
        expected_gap = gap_profile.avg_gap_size_pct
        
        # Stop-through probability
        # If gap > stop distance, stop is ineffective
        stop_through_prob = 0.0
        if expected_gap > stop_distance_pct:
            stop_through_prob = gap_profile.stop_through_frequency
        
        # Expected additional loss from gap-through
        gap_through_loss_pct = max(0, expected_gap - stop_distance_pct)
        expected_gap_cost = gap_probability * gap_through_loss_pct * position_size
        
        return {
            "asset": asset,
            "gap_probability": round(gap_probability, 4),
            "expected_gap_pct": round(expected_gap * 100, 2),
            "stop_distance_pct": round(stop_distance_pct * 100, 2),
            "stop_through_probability": round(stop_through_prob, 4),
            "gap_through_loss_pct": round(gap_through_loss_pct * 100, 2),
            "expected_gap_cost": round(expected_gap_cost, 2),
            "condition": condition.value
        }
    
    # ============================================
    # Liquidity Model
    # ============================================
    
    def check_liquidity(
        self,
        asset: str,
        order_size: float,
        condition: MarketCondition = MarketCondition.NORMAL
    ) -> Dict:
        """Check liquidity constraints"""
        
        liquidity = self.liquidity_profiles.get(asset)
        if not liquidity:
            liquidity = LiquidityProfile(asset=asset, asset_class=AssetClass.EQUITY)
        
        scenario = self.scenarios.get(condition)
        
        # Adjusted volume
        volume = liquidity.avg_daily_volume
        if scenario:
            volume *= scenario.liquidity_multiplier
        
        # Max order size
        max_order = volume * liquidity.max_participation_pct
        
        # Participation rate
        participation = order_size / volume if volume > 0 else 1.0
        
        # Fill rate
        fill_rate = min(1.0, max_order / order_size) if order_size > 0 else 1.0
        
        # Liquidity warning
        warning = None
        if fill_rate < 0.5:
            warning = "SEVERE: Order size exceeds 50% of max participation"
        elif fill_rate < 0.8:
            warning = "WARNING: Order may experience partial fills"
        elif participation > liquidity.max_participation_pct * 0.5:
            warning = "CAUTION: High market participation"
        
        return {
            "asset": asset,
            "order_size": order_size,
            "adjusted_daily_volume": round(volume, 0),
            "max_order_size": round(max_order, 0),
            "participation_pct": round(participation * 100, 4),
            "expected_fill_rate": round(fill_rate, 4),
            "warning": warning,
            "condition": condition.value
        }
    
    # ============================================
    # Fill Simulation
    # ============================================
    
    def simulate_fill(
        self,
        asset: str,
        side: str,
        order_size: float,
        intended_price: float,
        condition: MarketCondition = MarketCondition.NORMAL,
        volatility: float = 0.02,
        is_overnight: bool = False
    ) -> FillResult:
        """Simulate complete order fill with all frictions"""
        
        order_id = f"ORD_{uuid.uuid4().hex[:8]}"
        now = int(time.time() * 1000)
        
        # Calculate all costs
        spread = self.calculate_spread(asset, condition)
        slippage = self.calculate_slippage(asset, order_size, condition, 1 + volatility * 10)
        delay = self.calculate_delay_cost(asset, condition, volatility)
        liquidity = self.check_liquidity(asset, order_size, condition)
        
        # Gap risk if overnight
        gap_cost = 0.0
        had_gap = False
        if is_overnight:
            gap_result = self.simulate_gap_risk(asset, order_size, 0.02, condition)
            if random.random() < gap_result["gap_probability"]:
                gap_cost = gap_result["expected_gap_pct"] * 100  # to bps
                had_gap = True
        
        # Total cost
        spread_cost = spread["effective_spread_bps"] / 2  # Half spread per side
        slippage_cost = slippage["effective_slippage_bps"]
        delay_cost = delay["price_impact_bps"]
        total_cost = spread_cost + slippage_cost + delay_cost + gap_cost
        
        # Fill rate and quality
        fill_rate = liquidity["expected_fill_rate"]
        filled_size = order_size * fill_rate
        
        # Determine fill quality
        if fill_rate >= 0.99:
            quality = FillQuality.FULL
        elif fill_rate >= 0.8:
            quality = FillQuality.PARTIAL
        elif fill_rate >= 0.5:
            quality = FillQuality.DELAYED
        elif fill_rate > 0:
            quality = FillQuality.BAD
        else:
            quality = FillQuality.REJECTED
        
        # Executed price
        direction = 1 if side == "BUY" else -1
        price_impact = intended_price * (total_cost / 10000) * direction
        avg_fill_price = intended_price + price_impact
        
        result = FillResult(
            order_id=order_id,
            asset=asset,
            side=side,
            requested_size=order_size,
            filled_size=round(filled_size, 2),
            avg_fill_price=round(avg_fill_price, 6),
            intended_price=intended_price,
            fill_quality=quality,
            fill_rate=round(fill_rate, 4),
            spread_cost_bps=round(spread_cost, 2),
            slippage_cost_bps=round(slippage_cost, 2),
            delay_cost_bps=round(delay_cost, 2),
            gap_cost_bps=round(gap_cost, 2),
            total_cost_bps=round(total_cost, 2),
            was_delayed=delay["effective_delay_ms"] > 200,
            was_partial=fill_rate < 0.99,
            had_gap_through=had_gap,
            timestamp=now
        )
        
        self.fill_results.append(result)
        return result
    
    # ============================================
    # Scenario Simulation
    # ============================================
    
    def run_scenario(
        self,
        scenario_id: str,
        trades: List[Dict]
    ) -> Dict:
        """Run multiple trades through a scenario"""
        
        scenario = self.scenarios.get(MarketCondition(scenario_id))
        if not scenario:
            scenario = self.scenarios[MarketCondition.NORMAL]
        
        results = []
        total_cost = 0.0
        partial_fills = 0
        gap_throughs = 0
        
        for trade in trades:
            result = self.simulate_fill(
                asset=trade.get("asset", "BTC"),
                side=trade.get("side", "BUY"),
                order_size=trade.get("size", 10000),
                intended_price=trade.get("price", 100),
                condition=scenario.condition,
                volatility=trade.get("volatility", 0.02),
                is_overnight=trade.get("is_overnight", False)
            )
            results.append(result)
            total_cost += result.total_cost_bps
            if result.was_partial:
                partial_fills += 1
            if result.had_gap_through:
                gap_throughs += 1
        
        avg_cost = total_cost / len(trades) if trades else 0
        
        return {
            "scenario_id": scenario_id,
            "scenario_name": scenario.name,
            "trades_simulated": len(trades),
            "total_cost_bps": round(total_cost, 2),
            "avg_cost_per_trade_bps": round(avg_cost, 2),
            "partial_fills": partial_fills,
            "gap_throughs": gap_throughs,
            "partial_fill_rate": round(partial_fills / len(trades), 4) if trades else 0,
            "results": [self._fill_to_dict(r) for r in results]
        }
    
    # ============================================
    # Fragility Analysis
    # ============================================
    
    def analyze_fragility(
        self,
        strategy_id: str,
        typical_order_size: float,
        typical_trades_per_day: int,
        primary_asset: str = "BTC"
    ) -> ExecutionFragility:
        """Analyze execution fragility for a strategy"""
        
        # Get profiles
        spread = self.spread_profiles.get(primary_asset)
        slippage = self.slippage_profiles.get(primary_asset)
        gap = self.gap_profiles.get(primary_asset)
        liquidity = self.liquidity_profiles.get(primary_asset)
        
        # Calculate sensitivities
        spread_sens = 0.0
        if spread:
            # Higher spread = more sensitive
            spread_sens = min(1.0, spread.baseline_spread_bps / 20)
        
        slippage_sens = 0.0
        if slippage:
            # Size-dependent
            slippage_data = self.calculate_slippage(primary_asset, typical_order_size)
            slippage_sens = min(1.0, slippage_data["effective_slippage_bps"] / 30)
        
        gap_sens = 0.0
        if gap:
            gap_sens = min(1.0, gap.avg_gap_frequency * 5)
        
        liquidity_sens = 0.0
        if liquidity:
            liq_data = self.check_liquidity(primary_asset, typical_order_size)
            liquidity_sens = 1.0 - liq_data["expected_fill_rate"]
        
        delay_sens = 0.3  # Default moderate sensitivity
        
        # Overall fragility
        overall = (spread_sens + slippage_sens + gap_sens + liquidity_sens + delay_sens) / 5
        
        # Classification
        if overall < 0.2:
            level = "LOW"
        elif overall < 0.4:
            level = "MEDIUM"
        elif overall < 0.6:
            level = "HIGH"
        else:
            level = "CRITICAL"
        
        # Max recommended capital
        if liquidity:
            max_capital = liquidity.avg_daily_volume * liquidity.max_participation_pct * 10
        else:
            max_capital = 100000
        
        fragility = ExecutionFragility(
            strategy=strategy_id,
            spread_sensitivity=round(spread_sens, 3),
            slippage_sensitivity=round(slippage_sens, 3),
            delay_sensitivity=round(delay_sens, 3),
            gap_sensitivity=round(gap_sens, 3),
            liquidity_sensitivity=round(liquidity_sens, 3),
            overall_fragility=round(overall, 3),
            fragility_level=level,
            max_recommended_capital=round(max_capital, 0)
        )
        
        self.fragility_analyses[strategy_id] = fragility
        return fragility
    
    # ============================================
    # Queries
    # ============================================
    
    def get_asset_profile(self, asset: str) -> Dict:
        """Get complete microstructure profile for asset"""
        return {
            "asset": asset,
            "spread": self._spread_to_dict(self.spread_profiles.get(asset)) if asset in self.spread_profiles else None,
            "slippage": self._slippage_to_dict(self.slippage_profiles.get(asset)) if asset in self.slippage_profiles else None,
            "delay": self._delay_to_dict(self.delay_models.get(asset)) if asset in self.delay_models else None,
            "gap": self._gap_to_dict(self.gap_profiles.get(asset)) if asset in self.gap_profiles else None,
            "liquidity": self._liquidity_to_dict(self.liquidity_profiles.get(asset)) if asset in self.liquidity_profiles else None
        }
    
    def get_health(self) -> Dict:
        """Get engine health"""
        return {
            "enabled": True,
            "version": "phaseB",
            "status": "ok",
            "spread_profiles": len(self.spread_profiles),
            "slippage_profiles": len(self.slippage_profiles),
            "delay_models": len(self.delay_models),
            "gap_profiles": len(self.gap_profiles),
            "liquidity_profiles": len(self.liquidity_profiles),
            "scenarios": len(self.scenarios),
            "fill_results_cached": len(self.fill_results),
            "fragility_analyses": len(self.fragility_analyses),
            "timestamp": int(time.time() * 1000)
        }
    
    # ============================================
    # Serialization
    # ============================================
    
    def _spread_to_dict(self, p: SpreadProfile) -> Dict:
        if not p: return None
        return {
            "asset": p.asset,
            "asset_class": p.asset_class.value,
            "baseline_bps": p.baseline_spread_bps,
            "stress_mult": p.stress_multiplier,
            "crisis_mult": p.crisis_multiplier
        }
    
    def _slippage_to_dict(self, p: SlippageProfile) -> Dict:
        if not p: return None
        return {
            "asset": p.asset,
            "base_bps": p.base_slippage_bps,
            "impact_coefficient": p.impact_coefficient
        }
    
    def _delay_to_dict(self, d: DelayModel) -> Dict:
        if not d: return None
        return {
            "asset": d.asset,
            "total_delay_ms": d.total_delay_ms,
            "price_impact_bps": d.delay_price_impact_bps
        }
    
    def _gap_to_dict(self, g: GapProfile) -> Dict:
        if not g: return None
        return {
            "asset": g.asset,
            "avg_frequency": g.avg_gap_frequency,
            "avg_size_pct": g.avg_gap_size_pct,
            "stop_through_freq": g.stop_through_frequency
        }
    
    def _liquidity_to_dict(self, l: LiquidityProfile) -> Dict:
        if not l: return None
        return {
            "asset": l.asset,
            "avg_daily_volume": l.avg_daily_volume,
            "max_participation_pct": l.max_participation_pct
        }
    
    def _fill_to_dict(self, f: FillResult) -> Dict:
        return {
            "order_id": f.order_id,
            "asset": f.asset,
            "side": f.side,
            "requested_size": f.requested_size,
            "filled_size": f.filled_size,
            "intended_price": f.intended_price,
            "avg_fill_price": f.avg_fill_price,
            "fill_quality": f.fill_quality.value,
            "fill_rate": f.fill_rate,
            "spread_cost_bps": f.spread_cost_bps,
            "slippage_cost_bps": f.slippage_cost_bps,
            "delay_cost_bps": f.delay_cost_bps,
            "gap_cost_bps": f.gap_cost_bps,
            "total_cost_bps": f.total_cost_bps,
            "was_partial": f.was_partial,
            "had_gap_through": f.had_gap_through
        }
    
    def _fragility_to_dict(self, f: ExecutionFragility) -> Dict:
        return {
            "strategy": f.strategy,
            "spread_sensitivity": f.spread_sensitivity,
            "slippage_sensitivity": f.slippage_sensitivity,
            "delay_sensitivity": f.delay_sensitivity,
            "gap_sensitivity": f.gap_sensitivity,
            "liquidity_sensitivity": f.liquidity_sensitivity,
            "overall_fragility": f.overall_fragility,
            "fragility_level": f.fragility_level,
            "max_recommended_capital": f.max_recommended_capital
        }


# Singleton
microstructure_engine = MicrostructureEngine()
