"""
Shadow Portfolio Routes
=======================

Phase 9.30 - API endpoints for shadow portfolio system.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .service import shadow_service


router = APIRouter(prefix="/api/shadow", tags=["shadow-portfolio"])


# ============================================
# Request Models
# ============================================

class AddStrategyRequest(BaseModel):
    alpha_id: str
    name: str
    family: str = "EXPERIMENTAL"
    asset_classes: List[str] = ["CRYPTO"]
    timeframes: List[str] = ["1D"]
    tournament_run_id: str = ""
    tournament_score: float = 0.0
    confidence: float = 0.5


class RemoveStrategyRequest(BaseModel):
    reason: str = "Manual removal"


class RunCycleRequest(BaseModel):
    market_data: Optional[Dict[str, Any]] = None


class RunMultipleCyclesRequest(BaseModel):
    count: int = 10
    market_data: Optional[Dict[str, Any]] = None


class UpdateConfigRequest(BaseModel):
    initial_capital: Optional[float] = None
    max_strategies: Optional[int] = None
    max_total_exposure: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


# ============================================
# Health & Stats
# ============================================

@router.get("/health")
async def health_check():
    """Health check for shadow portfolio"""
    return shadow_service.get_health()


@router.get("/stats")
async def get_stats():
    """Get portfolio statistics summary"""
    return shadow_service.get_stats()


# ============================================
# Portfolio State
# ============================================

@router.get("/portfolio")
async def get_portfolio():
    """Get full portfolio state with strategies"""
    return shadow_service.get_portfolio()


# ============================================
# Strategy Management
# ============================================

@router.post("/add-strategy")
async def add_strategy(request: AddStrategyRequest):
    """Add a tournament winner to shadow portfolio"""
    result = shadow_service.add_strategy(
        alpha_id=request.alpha_id,
        name=request.name,
        family=request.family,
        asset_classes=request.asset_classes,
        timeframes=request.timeframes,
        tournament_run_id=request.tournament_run_id,
        tournament_score=request.tournament_score,
        confidence=request.confidence
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/remove-strategy/{strategy_id}")
async def remove_strategy(strategy_id: str, request: RemoveStrategyRequest):
    """Remove a strategy from shadow portfolio"""
    result = shadow_service.remove_strategy(strategy_id, request.reason)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# ============================================
# Cycle Execution
# ============================================

@router.post("/run-cycle")
async def run_cycle(request: RunCycleRequest):
    """Execute one portfolio cycle"""
    return shadow_service.run_cycle(request.market_data)


@router.post("/run-cycles")
async def run_multiple_cycles(request: RunMultipleCyclesRequest):
    """Run multiple portfolio cycles"""
    return shadow_service.run_multiple_cycles(request.count, request.market_data)


# ============================================
# Positions
# ============================================

@router.get("/positions")
async def get_positions(status: Optional[str] = None):
    """Get positions (open/closed/all)"""
    return shadow_service.get_positions(status)


# ============================================
# Trades
# ============================================

@router.get("/trades")
async def get_trades(strategy_id: Optional[str] = None, limit: int = 100):
    """Get trade log"""
    return shadow_service.get_trades(strategy_id, limit)


# ============================================
# Equity Curve
# ============================================

@router.get("/equity")
async def get_equity(limit: int = 500):
    """Get equity curve"""
    return shadow_service.get_equity(limit)


# ============================================
# Metrics
# ============================================

@router.get("/metrics")
async def get_metrics():
    """Compute and return portfolio metrics"""
    return shadow_service.get_metrics()


# ============================================
# Governance Events
# ============================================

@router.get("/events")
async def get_events(event_type: Optional[str] = None, limit: int = 100):
    """Get governance events"""
    return shadow_service.get_events(event_type, limit)


# ============================================
# Configuration
# ============================================

@router.get("/config")
async def get_config():
    """Get current configuration"""
    return shadow_service.get_config()


@router.put("/config")
async def update_config(request: UpdateConfigRequest):
    """Update configuration"""
    return shadow_service.update_config(
        initial_capital=request.initial_capital,
        max_strategies=request.max_strategies,
        max_total_exposure=request.max_total_exposure,
        stop_loss_pct=request.stop_loss_pct,
        take_profit_pct=request.take_profit_pct
    )


# ============================================
# Management
# ============================================

@router.post("/reset")
async def reset_portfolio():
    """Full portfolio reset"""
    return shadow_service.reset()
