"""
Capital Simulation Engine
=========================

Phase 9.36 - Capital-aware simulation for realistic strategy evaluation.

Simulates strategies with:
- Position sizing
- Slippage modeling
- Fee calculation
- Liquidity constraints
- Market impact
"""

import time
import uuid
import math
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from .types import (
    CapitalTier, AssetClass,
    CapitalProfile, LiquidityProfile, SlippageModel, FeeModel,
    TradeExecution, StrategySimulation, CapacityAnalysis,
    DEFAULT_CAPITAL_PROFILES, DEFAULT_LIQUIDITY
)


class CapitalSimulationEngine:
    """
    Capital Simulation Engine.
    
    Simulates strategies across different capital levels
    to find capacity limits and realistic performance.
    """
    
    def __init__(self):
        # Profiles
        self.capital_profiles = dict(DEFAULT_CAPITAL_PROFILES)
        self.liquidity_profiles = dict(DEFAULT_LIQUIDITY)
        
        # Default models
        self.default_slippage = SlippageModel()
        self.default_fees = FeeModel()
        
        # Results storage
        self.simulations: Dict[str, StrategySimulation] = {}
        self.capacity_analyses: Dict[str, CapacityAnalysis] = {}
    
    # ============================================
    # Position Sizing
    # ============================================
    
    def calculate_position_size(
        self,
        capital: float,
        risk_per_trade: float,
        stop_distance_pct: float,
        max_position_pct: float = 0.10
    ) -> float:
        """Calculate position size based on risk"""
        
        # Risk-based size
        risk_amount = capital * risk_per_trade
        position_size = risk_amount / stop_distance_pct if stop_distance_pct > 0 else 0
        
        # Cap at max position
        max_position = capital * max_position_pct
        position_size = min(position_size, max_position)
        
        return round(position_size, 2)
    
    # ============================================
    # Slippage Model
    # ============================================
    
    def calculate_slippage(
        self,
        position_size: float,
        entry_price: float,
        asset: str = "BTC",
        volatility_mult: float = 1.0
    ) -> Dict:
        """Calculate slippage for a trade"""
        
        liquidity = self.liquidity_profiles.get(asset, DEFAULT_LIQUIDITY.get("BTC"))
        slippage_model = self.default_slippage
        
        # Base spread cost
        spread_cost = position_size * (liquidity.avg_spread_bps / 10000)
        
        # Market impact (square root model)
        impact_pct = slippage_model.impact_factor * math.sqrt(position_size / 10000)
        impact_cost = position_size * impact_pct / 100
        
        # Volatility adjustment
        vol_adjustment = volatility_mult * slippage_model.vol_multiplier
        
        total_slippage = (spread_cost + impact_cost) * vol_adjustment
        slippage_bps = (total_slippage / position_size) * 10000 if position_size > 0 else 0
        
        return {
            "spread_cost": round(spread_cost, 4),
            "impact_cost": round(impact_cost, 4),
            "total_slippage": round(total_slippage, 4),
            "slippage_bps": round(slippage_bps, 2),
            "executed_price": round(entry_price * (1 + slippage_bps / 10000), 6)
        }
    
    # ============================================
    # Fee Model
    # ============================================
    
    def calculate_fees(
        self,
        position_size: float,
        is_maker: bool = False
    ) -> Dict:
        """Calculate trading fees"""
        
        fee_model = self.default_fees
        
        fee_bps = fee_model.maker_fee_bps if is_maker else fee_model.taker_fee_bps
        fee_cost = position_size * (fee_bps / 10000)
        fee_cost = max(fee_cost, fee_model.min_fee)
        
        # Platform fee
        platform_fee = position_size * fee_model.platform_fee_pct
        
        total_fee = fee_cost + platform_fee
        
        return {
            "trading_fee": round(fee_cost, 4),
            "platform_fee": round(platform_fee, 4),
            "total_fee": round(total_fee, 4),
            "fee_bps": round((total_fee / position_size) * 10000, 2) if position_size > 0 else 0
        }
    
    # ============================================
    # Liquidity Check
    # ============================================
    
    def check_liquidity(
        self,
        position_size: float,
        asset: str = "BTC"
    ) -> Dict:
        """Check if position size fits within liquidity constraints"""
        
        liquidity = self.liquidity_profiles.get(asset, DEFAULT_LIQUIDITY.get("BTC"))
        
        max_size = liquidity.avg_daily_volume * liquidity.max_participation
        fill_rate = min(1.0, max_size / position_size) if position_size > 0 else 1.0
        
        actual_size = position_size * fill_rate
        limited = fill_rate < 1.0
        
        return {
            "intended_size": position_size,
            "max_size": round(max_size, 2),
            "actual_size": round(actual_size, 2),
            "fill_rate": round(fill_rate, 4),
            "liquidity_limited": limited,
            "participation_pct": round((position_size / liquidity.avg_daily_volume) * 100, 4) if liquidity.avg_daily_volume > 0 else 0
        }
    
    # ============================================
    # Trade Execution Simulation
    # ============================================
    
    def simulate_trade(
        self,
        side: str,
        position_size: float,
        entry_price: float,
        asset: str = "BTC",
        volatility_mult: float = 1.0
    ) -> TradeExecution:
        """Simulate a single trade execution"""
        
        trade_id = f"TRADE_{uuid.uuid4().hex[:8]}"
        
        # Check liquidity
        liquidity_result = self.check_liquidity(position_size, asset)
        actual_size = liquidity_result["actual_size"]
        
        # Calculate slippage
        slippage_result = self.calculate_slippage(
            actual_size, entry_price, asset, volatility_mult
        )
        
        # Calculate fees
        fee_result = self.calculate_fees(actual_size)
        
        # Total cost
        total_cost = slippage_result["total_slippage"] + fee_result["total_fee"]
        cost_bps = (total_cost / actual_size) * 10000 if actual_size > 0 else 0
        
        return TradeExecution(
            trade_id=trade_id,
            side=side,
            intended_size=position_size,
            actual_size=actual_size,
            entry_price=entry_price,
            executed_price=slippage_result["executed_price"],
            slippage_cost=slippage_result["total_slippage"],
            fee_cost=fee_result["total_fee"],
            impact_cost=slippage_result["impact_cost"],
            total_cost=total_cost,
            cost_bps=round(cost_bps, 2),
            fill_rate=liquidity_result["fill_rate"],
            liquidity_limited=liquidity_result["liquidity_limited"],
            partial_fill=liquidity_result["fill_rate"] < 1.0,
            timestamp=int(time.time() * 1000)
        )
    
    # ============================================
    # Strategy Simulation
    # ============================================
    
    def simulate_strategy(
        self,
        strategy_id: str,
        strategy_name: str,
        trades_data: List[Dict],
        capital_tier: CapitalTier = CapitalTier.MEDIUM,
        asset: str = "BTC"
    ) -> StrategySimulation:
        """
        Simulate a strategy at a specific capital level.
        
        trades_data format:
        [{side, entry_price, exit_price, stop_distance_pct, gross_pnl_pct}, ...]
        """
        
        sim_id = f"SIM_{uuid.uuid4().hex[:10]}"
        profile = self.capital_profiles[capital_tier]
        
        # Initialize
        gross_pnl = 0.0
        slippage_costs = 0.0
        fee_costs = 0.0
        impact_costs = 0.0
        winning_trades = 0
        liquidity_limited_trades = 0
        total_fill_rate = 0.0
        
        gross_wins = 0.0
        gross_losses = 0.0
        net_wins = 0.0
        net_losses = 0.0
        
        for trade in trades_data:
            # Calculate position size
            stop_dist = trade.get("stop_distance_pct", 0.02)
            pos_size = self.calculate_position_size(
                profile.capital,
                profile.risk_per_trade,
                stop_dist,
                profile.max_position_pct
            )
            
            # Simulate entry
            entry_exec = self.simulate_trade(
                trade.get("side", "BUY"),
                pos_size,
                trade.get("entry_price", 100),
                asset
            )
            
            # Simulate exit
            exit_exec = self.simulate_trade(
                "SELL" if trade.get("side", "BUY") == "BUY" else "BUY",
                entry_exec.actual_size,
                trade.get("exit_price", 100),
                asset
            )
            
            # Calculate P&L
            trade_gross_pnl = entry_exec.actual_size * trade.get("gross_pnl_pct", 0)
            trade_costs = entry_exec.total_cost + exit_exec.total_cost
            trade_net_pnl = trade_gross_pnl - trade_costs
            
            gross_pnl += trade_gross_pnl
            slippage_costs += entry_exec.slippage_cost + exit_exec.slippage_cost
            fee_costs += entry_exec.fee_cost + exit_exec.fee_cost
            impact_costs += entry_exec.impact_cost + exit_exec.impact_cost
            
            if trade_gross_pnl > 0:
                gross_wins += trade_gross_pnl
                winning_trades += 1
            else:
                gross_losses += abs(trade_gross_pnl)
            
            if trade_net_pnl > 0:
                net_wins += trade_net_pnl
            else:
                net_losses += abs(trade_net_pnl)
            
            if entry_exec.liquidity_limited:
                liquidity_limited_trades += 1
            
            total_fill_rate += entry_exec.fill_rate
        
        n_trades = len(trades_data)
        net_pnl = gross_pnl - slippage_costs - fee_costs
        
        # Calculate metrics
        gross_pf = gross_wins / gross_losses if gross_losses > 0 else float('inf')
        net_pf = net_wins / net_losses if net_losses > 0 else float('inf')
        
        # Simplified Sharpe (using profit factor as proxy)
        gross_sharpe = min(3.0, gross_pf - 1) if gross_pf != float('inf') else 3.0
        net_sharpe = min(3.0, net_pf - 1) if net_pf != float('inf') else 3.0
        
        simulation = StrategySimulation(
            simulation_id=sim_id,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            capital_tier=capital_tier,
            capital=profile.capital,
            trades=n_trades,
            winning_trades=winning_trades,
            gross_pnl=round(gross_pnl, 2),
            slippage_costs=round(slippage_costs, 2),
            fee_costs=round(fee_costs, 2),
            impact_costs=round(impact_costs, 2),
            net_pnl=round(net_pnl, 2),
            gross_sharpe=round(gross_sharpe, 3),
            net_sharpe=round(net_sharpe, 3),
            gross_pf=round(gross_pf, 3) if gross_pf != float('inf') else 99.0,
            net_pf=round(net_pf, 3) if net_pf != float('inf') else 99.0,
            liquidity_limited_trades=liquidity_limited_trades,
            avg_fill_rate=round(total_fill_rate / n_trades, 4) if n_trades > 0 else 1.0,
            capacity_utilized=round(profile.capital / 1000000, 4),
            created_at=int(time.time() * 1000)
        )
        
        self.simulations[sim_id] = simulation
        return simulation
    
    # ============================================
    # Capacity Analysis
    # ============================================
    
    def analyze_capacity(
        self,
        strategy_id: str,
        strategy_name: str,
        trades_data: List[Dict],
        asset: str = "BTC"
    ) -> CapacityAnalysis:
        """
        Analyze strategy capacity across all capital tiers.
        
        Finds the maximum deployable capital.
        """
        
        tier_results = {}
        
        # Simulate at each tier
        for tier in CapitalTier:
            sim = self.simulate_strategy(
                strategy_id, strategy_name, trades_data, tier, asset
            )
            tier_results[tier.value] = sim
        
        # Find capacity limit
        max_capital = 0.0
        limit_reason = ""
        
        # Look for Sharpe decay
        sharpe_values = [
            (tier, sim.net_sharpe, sim.capital)
            for tier, sim in tier_results.items()
        ]
        sharpe_values.sort(key=lambda x: x[2])  # Sort by capital
        
        for i, (tier, sharpe, capital) in enumerate(sharpe_values):
            if i > 0:
                prev_sharpe = sharpe_values[i-1][1]
                if sharpe < prev_sharpe * 0.7:  # 30% Sharpe decay
                    limit_reason = f"Sharpe decay at ${capital:,.0f}"
                    max_capital = sharpe_values[i-1][2]
                    break
            
            # Check fill rate
            sim = tier_results[tier]
            if sim.avg_fill_rate < 0.9:  # 90% fill rate threshold
                limit_reason = f"Liquidity limit at ${capital:,.0f}"
                max_capital = sharpe_values[i-1][2] if i > 0 else capital
                break
            
            max_capital = capital
        
        if not limit_reason:
            limit_reason = "No capacity limit found"
        
        # Extract tier metrics
        def get_sharpe(tier_val):
            sim = tier_results.get(tier_val)
            return sim.net_sharpe if sim else 0
        
        def get_pf(tier_val):
            sim = tier_results.get(tier_val)
            return sim.net_pf if sim else 0
        
        analysis = CapacityAnalysis(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            tier_results=tier_results,
            max_deployable_capital=max_capital,
            capacity_limit_reason=limit_reason,
            sharpe_at_10k=get_sharpe(CapitalTier.MEDIUM.value),
            sharpe_at_100k=get_sharpe(CapitalTier.LARGE.value),
            sharpe_at_1m=get_sharpe(CapitalTier.FUND.value),
            pf_at_10k=get_pf(CapitalTier.MEDIUM.value),
            pf_at_100k=get_pf(CapitalTier.LARGE.value),
            pf_at_1m=get_pf(CapitalTier.FUND.value),
            optimal_tier=self._find_optimal_tier(tier_results),
            created_at=int(time.time() * 1000)
        )
        
        self.capacity_analyses[strategy_id] = analysis
        return analysis
    
    def _find_optimal_tier(self, tier_results: Dict[str, StrategySimulation]) -> CapitalTier:
        """Find optimal capital tier based on risk-adjusted returns"""
        
        best_tier = CapitalTier.MEDIUM
        best_score = 0.0
        
        for tier_name, sim in tier_results.items():
            # Score = Sharpe * fill_rate (penalize low fills)
            score = sim.net_sharpe * sim.avg_fill_rate
            if score > best_score:
                best_score = score
                best_tier = CapitalTier(tier_name)
        
        return best_tier
    
    # ============================================
    # Queries
    # ============================================
    
    def get_profiles(self) -> List[Dict]:
        """Get all capital profiles"""
        return [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "tier": p.tier.value,
                "capital": p.capital,
                "risk_per_trade": p.risk_per_trade,
                "max_position_pct": p.max_position_pct,
                "max_positions": p.max_positions
            }
            for p in self.capital_profiles.values()
        ]
    
    def get_simulation(self, sim_id: str) -> Optional[Dict]:
        """Get simulation result"""
        sim = self.simulations.get(sim_id)
        return self._simulation_to_dict(sim) if sim else None
    
    def get_capacity(self, strategy_id: str) -> Optional[Dict]:
        """Get capacity analysis"""
        analysis = self.capacity_analyses.get(strategy_id)
        return self._capacity_to_dict(analysis) if analysis else None
    
    def get_health(self) -> Dict:
        """Get engine health"""
        return {
            "enabled": True,
            "version": "phase9.36",
            "status": "ok",
            "capital_profiles": len(self.capital_profiles),
            "liquidity_profiles": len(self.liquidity_profiles),
            "total_simulations": len(self.simulations),
            "total_capacity_analyses": len(self.capacity_analyses),
            "supported_tiers": [t.value for t in CapitalTier],
            "timestamp": int(time.time() * 1000)
        }
    
    # ============================================
    # Serialization
    # ============================================
    
    def _simulation_to_dict(self, sim: StrategySimulation) -> Dict:
        return {
            "simulation_id": sim.simulation_id,
            "strategy_id": sim.strategy_id,
            "strategy_name": sim.strategy_name,
            "capital_tier": sim.capital_tier.value,
            "capital": sim.capital,
            "trades": sim.trades,
            "winning_trades": sim.winning_trades,
            "gross_pnl": sim.gross_pnl,
            "slippage_costs": sim.slippage_costs,
            "fee_costs": sim.fee_costs,
            "impact_costs": sim.impact_costs,
            "net_pnl": sim.net_pnl,
            "gross_sharpe": sim.gross_sharpe,
            "net_sharpe": sim.net_sharpe,
            "gross_pf": sim.gross_pf,
            "net_pf": sim.net_pf,
            "liquidity_limited_trades": sim.liquidity_limited_trades,
            "avg_fill_rate": sim.avg_fill_rate,
            "created_at": sim.created_at
        }
    
    def _capacity_to_dict(self, analysis: CapacityAnalysis) -> Dict:
        return {
            "strategy_id": analysis.strategy_id,
            "strategy_name": analysis.strategy_name,
            "max_deployable_capital": analysis.max_deployable_capital,
            "capacity_limit_reason": analysis.capacity_limit_reason,
            "optimal_tier": analysis.optimal_tier.value,
            "sharpe_decay": {
                "10k": analysis.sharpe_at_10k,
                "100k": analysis.sharpe_at_100k,
                "1m": analysis.sharpe_at_1m
            },
            "pf_decay": {
                "10k": analysis.pf_at_10k,
                "100k": analysis.pf_at_100k,
                "1m": analysis.pf_at_1m
            },
            "tier_results": {
                tier: self._simulation_to_dict(sim) 
                for tier, sim in analysis.tier_results.items()
            },
            "created_at": analysis.created_at
        }


# Singleton
capital_simulation_engine = CapitalSimulationEngine()
