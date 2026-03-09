"""
Microstructure Lab Routes
=========================

Phase B - API endpoints for market microstructure simulation.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from .engine import microstructure_engine
from .types import MarketCondition


router = APIRouter(prefix="/api/microstructure", tags=["microstructure"])


# ============================================
# Request Models
# ============================================

class SpreadRequest(BaseModel):
    asset: str = "BTC"
    condition: str = "NORMAL"
    is_open: bool = False
    is_close: bool = False


class SlippageRequest(BaseModel):
    asset: str = "BTC"
    order_size: float = 10000.0
    condition: str = "NORMAL"
    volatility_mult: float = 1.0


class GapRiskRequest(BaseModel):
    asset: str = "BTC"
    position_size: float = 10000.0
    stop_distance_pct: float = 0.02
    condition: str = "NORMAL"


class LiquidityRequest(BaseModel):
    asset: str = "BTC"
    order_size: float = 10000.0
    condition: str = "NORMAL"


class FillSimRequest(BaseModel):
    asset: str = "BTC"
    side: str = "BUY"
    order_size: float = 10000.0
    intended_price: float = 40000.0
    condition: str = "NORMAL"
    volatility: float = 0.02
    is_overnight: bool = False


class TradeData(BaseModel):
    asset: str = "BTC"
    side: str = "BUY"
    size: float = 10000.0
    price: float = 40000.0
    volatility: float = 0.02
    is_overnight: bool = False


class ScenarioRequest(BaseModel):
    scenario_id: str = "NORMAL"
    trades: List[TradeData]


class FragilityRequest(BaseModel):
    strategy_id: str
    typical_order_size: float = 10000.0
    typical_trades_per_day: int = 5
    primary_asset: str = "BTC"


# ============================================
# Health
# ============================================

@router.get("/health")
async def health_check():
    return microstructure_engine.get_health()


# ============================================
# Asset Profiles
# ============================================

@router.get("/profiles")
async def list_asset_profiles():
    """List all asset microstructure profiles"""
    assets = list(microstructure_engine.spread_profiles.keys())
    return {
        "total": len(assets),
        "profiles": [microstructure_engine.get_asset_profile(a) for a in assets]
    }


@router.get("/profiles/{asset}")
async def get_asset_profile(asset: str):
    """Get microstructure profile for an asset"""
    profile = microstructure_engine.get_asset_profile(asset)
    if not any(profile.values()):
        raise HTTPException(status_code=404, detail=f"Asset {asset} not found")
    return profile


# ============================================
# Spread
# ============================================

@router.post("/spread")
async def calculate_spread(request: SpreadRequest):
    """Calculate effective spread"""
    try:
        condition = MarketCondition(request.condition)
    except ValueError:
        condition = MarketCondition.NORMAL
    
    return microstructure_engine.calculate_spread(
        asset=request.asset,
        condition=condition,
        is_open=request.is_open,
        is_close=request.is_close
    )


# ============================================
# Slippage
# ============================================

@router.post("/slippage")
async def calculate_slippage(request: SlippageRequest):
    """Calculate slippage with impact model"""
    try:
        condition = MarketCondition(request.condition)
    except ValueError:
        condition = MarketCondition.NORMAL
    
    return microstructure_engine.calculate_slippage(
        asset=request.asset,
        order_size=request.order_size,
        condition=condition,
        volatility_mult=request.volatility_mult
    )


# ============================================
# Gap Risk
# ============================================

@router.post("/gaps")
async def simulate_gap_risk(request: GapRiskRequest):
    """Simulate overnight gap risk"""
    try:
        condition = MarketCondition(request.condition)
    except ValueError:
        condition = MarketCondition.NORMAL
    
    return microstructure_engine.simulate_gap_risk(
        asset=request.asset,
        position_size=request.position_size,
        stop_distance_pct=request.stop_distance_pct,
        condition=condition
    )


# ============================================
# Liquidity
# ============================================

@router.post("/liquidity")
async def check_liquidity(request: LiquidityRequest):
    """Check liquidity constraints"""
    try:
        condition = MarketCondition(request.condition)
    except ValueError:
        condition = MarketCondition.NORMAL
    
    return microstructure_engine.check_liquidity(
        asset=request.asset,
        order_size=request.order_size,
        condition=condition
    )


# ============================================
# Fill Simulation
# ============================================

@router.post("/fills")
async def simulate_fill(request: FillSimRequest):
    """Simulate complete order fill"""
    try:
        condition = MarketCondition(request.condition)
    except ValueError:
        condition = MarketCondition.NORMAL
    
    result = microstructure_engine.simulate_fill(
        asset=request.asset,
        side=request.side,
        order_size=request.order_size,
        intended_price=request.intended_price,
        condition=condition,
        volatility=request.volatility,
        is_overnight=request.is_overnight
    )
    
    return microstructure_engine._fill_to_dict(result)


# ============================================
# Scenario Simulation
# ============================================

@router.post("/simulate")
async def run_scenario(request: ScenarioRequest):
    """Run trades through a scenario"""
    
    trades = [
        {
            "asset": t.asset,
            "side": t.side,
            "size": t.size,
            "price": t.price,
            "volatility": t.volatility,
            "is_overnight": t.is_overnight
        }
        for t in request.trades
    ]
    
    return microstructure_engine.run_scenario(request.scenario_id, trades)


@router.get("/scenarios")
async def list_scenarios():
    """List available scenarios"""
    return {
        "scenarios": [
            {
                "id": s.scenario_id,
                "name": s.name,
                "condition": s.condition.value,
                "spread_mult": s.spread_multiplier,
                "slippage_mult": s.slippage_multiplier,
                "liquidity_mult": s.liquidity_multiplier,
                "description": s.description
            }
            for s in microstructure_engine.scenarios.values()
        ]
    }


# ============================================
# Fragility Analysis
# ============================================

@router.post("/fragility")
async def analyze_fragility(request: FragilityRequest):
    """Analyze execution fragility for a strategy"""
    
    result = microstructure_engine.analyze_fragility(
        strategy_id=request.strategy_id,
        typical_order_size=request.typical_order_size,
        typical_trades_per_day=request.typical_trades_per_day,
        primary_asset=request.primary_asset
    )
    
    return microstructure_engine._fragility_to_dict(result)


@router.get("/fragility/{strategy_id}")
async def get_fragility(strategy_id: str):
    """Get fragility analysis for a strategy"""
    result = microstructure_engine.fragility_analyses.get(strategy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Fragility analysis not found")
    return microstructure_engine._fragility_to_dict(result)


# ============================================
# Reports
# ============================================

@router.get("/reports")
async def get_execution_report():
    """Get execution quality report"""
    fills = microstructure_engine.fill_results[-100:]  # Last 100
    
    if not fills:
        return {"message": "No fills to report"}
    
    total_cost = sum(f.total_cost_bps for f in fills)
    partial_fills = sum(1 for f in fills if f.was_partial)
    gap_throughs = sum(1 for f in fills if f.had_gap_through)
    
    return {
        "fills_analyzed": len(fills),
        "avg_cost_bps": round(total_cost / len(fills), 2),
        "partial_fill_rate": round(partial_fills / len(fills), 4),
        "gap_through_rate": round(gap_throughs / len(fills), 4),
        "by_quality": {
            quality.value: sum(1 for f in fills if f.fill_quality == quality)
            for quality in [
                microstructure_engine.fill_results[0].fill_quality.__class__.FULL,
                microstructure_engine.fill_results[0].fill_quality.__class__.PARTIAL,
                microstructure_engine.fill_results[0].fill_quality.__class__.DELAYED,
                microstructure_engine.fill_results[0].fill_quality.__class__.BAD
            ]
        } if fills else {}
    }
