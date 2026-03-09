"""
Capital Simulation Routes
=========================

Phase 9.36 - API endpoints for capital-aware simulation.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .engine import capital_simulation_engine
from .types import CapitalTier


router = APIRouter(prefix="/api/capital", tags=["capital-simulation"])


# ============================================
# Request Models
# ============================================

class PositionSizeRequest(BaseModel):
    capital: float = 10000.0
    risk_per_trade: float = 0.01
    stop_distance_pct: float = 0.02
    max_position_pct: float = 0.10


class SlippageRequest(BaseModel):
    position_size: float
    entry_price: float
    asset: str = "BTC"
    volatility_mult: float = 1.0


class TradeSimRequest(BaseModel):
    side: str = "BUY"
    position_size: float
    entry_price: float
    asset: str = "BTC"
    volatility_mult: float = 1.0


class TradeData(BaseModel):
    side: str = "BUY"
    entry_price: float = 100.0
    exit_price: float = 102.0
    stop_distance_pct: float = 0.02
    gross_pnl_pct: float = 0.02


class StrategySimRequest(BaseModel):
    strategy_id: str
    strategy_name: str
    trades: List[TradeData]
    capital_tier: str = "MEDIUM"
    asset: str = "BTC"


class CapacityRequest(BaseModel):
    strategy_id: str
    strategy_name: str
    trades: List[TradeData]
    asset: str = "BTC"


# ============================================
# Health
# ============================================

@router.get("/health")
async def health_check():
    return capital_simulation_engine.get_health()


# ============================================
# Profiles
# ============================================

@router.get("/profiles")
async def get_profiles():
    """Get all capital profiles"""
    return {"profiles": capital_simulation_engine.get_profiles()}


# ============================================
# Position Sizing
# ============================================

@router.post("/position-size")
async def calculate_position_size(request: PositionSizeRequest):
    """Calculate position size based on risk"""
    
    size = capital_simulation_engine.calculate_position_size(
        capital=request.capital,
        risk_per_trade=request.risk_per_trade,
        stop_distance_pct=request.stop_distance_pct,
        max_position_pct=request.max_position_pct
    )
    
    return {
        "capital": request.capital,
        "risk_per_trade": request.risk_per_trade,
        "stop_distance_pct": request.stop_distance_pct,
        "position_size": size,
        "position_pct": round(size / request.capital * 100, 2)
    }


# ============================================
# Cost Models
# ============================================

@router.post("/slippage")
async def calculate_slippage(request: SlippageRequest):
    """Calculate slippage for a trade"""
    return capital_simulation_engine.calculate_slippage(
        position_size=request.position_size,
        entry_price=request.entry_price,
        asset=request.asset,
        volatility_mult=request.volatility_mult
    )


@router.post("/fees")
async def calculate_fees(position_size: float, is_maker: bool = False):
    """Calculate trading fees"""
    return capital_simulation_engine.calculate_fees(
        position_size=position_size,
        is_maker=is_maker
    )


@router.post("/liquidity-check")
async def check_liquidity(position_size: float, asset: str = "BTC"):
    """Check liquidity constraints"""
    return capital_simulation_engine.check_liquidity(
        position_size=position_size,
        asset=asset
    )


# ============================================
# Trade Simulation
# ============================================

@router.post("/simulate-trade")
async def simulate_trade(request: TradeSimRequest):
    """Simulate a single trade execution"""
    
    execution = capital_simulation_engine.simulate_trade(
        side=request.side,
        position_size=request.position_size,
        entry_price=request.entry_price,
        asset=request.asset,
        volatility_mult=request.volatility_mult
    )
    
    return {
        "trade_id": execution.trade_id,
        "side": execution.side,
        "intended_size": execution.intended_size,
        "actual_size": execution.actual_size,
        "entry_price": execution.entry_price,
        "executed_price": execution.executed_price,
        "slippage_cost": execution.slippage_cost,
        "fee_cost": execution.fee_cost,
        "total_cost": execution.total_cost,
        "cost_bps": execution.cost_bps,
        "fill_rate": execution.fill_rate,
        "liquidity_limited": execution.liquidity_limited
    }


# ============================================
# Strategy Simulation
# ============================================

@router.post("/run")
async def run_simulation(request: StrategySimRequest):
    """Run strategy simulation at specific capital tier"""
    
    try:
        tier = CapitalTier(request.capital_tier)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier: {request.capital_tier}. Valid: {[t.value for t in CapitalTier]}"
        )
    
    trades_data = [
        {
            "side": t.side,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "stop_distance_pct": t.stop_distance_pct,
            "gross_pnl_pct": t.gross_pnl_pct
        }
        for t in request.trades
    ]
    
    simulation = capital_simulation_engine.simulate_strategy(
        strategy_id=request.strategy_id,
        strategy_name=request.strategy_name,
        trades_data=trades_data,
        capital_tier=tier,
        asset=request.asset
    )
    
    return capital_simulation_engine._simulation_to_dict(simulation)


@router.get("/results")
async def list_simulations(limit: int = 50):
    """List simulation results"""
    
    sims = list(capital_simulation_engine.simulations.values())
    sims.sort(key=lambda s: s.created_at, reverse=True)
    
    return {
        "total": len(sims),
        "simulations": [
            capital_simulation_engine._simulation_to_dict(s) 
            for s in sims[:limit]
        ]
    }


@router.get("/results/{sim_id}")
async def get_simulation(sim_id: str):
    """Get simulation result"""
    result = capital_simulation_engine.get_simulation(sim_id)
    if not result:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return result


# ============================================
# Capacity Analysis
# ============================================

@router.post("/capacity")
async def analyze_capacity(request: CapacityRequest):
    """Analyze strategy capacity across all tiers"""
    
    trades_data = [
        {
            "side": t.side,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "stop_distance_pct": t.stop_distance_pct,
            "gross_pnl_pct": t.gross_pnl_pct
        }
        for t in request.trades
    ]
    
    analysis = capital_simulation_engine.analyze_capacity(
        strategy_id=request.strategy_id,
        strategy_name=request.strategy_name,
        trades_data=trades_data,
        asset=request.asset
    )
    
    return capital_simulation_engine._capacity_to_dict(analysis)


@router.get("/capacity/{strategy_id}")
async def get_capacity(strategy_id: str):
    """Get capacity analysis for a strategy"""
    result = capital_simulation_engine.get_capacity(strategy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Capacity analysis not found")
    return result
