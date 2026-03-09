"""
Simulation Routes (S1)
======================

REST API for Trading Simulation Engine.

Endpoints:

# Health
GET  /api/trading/simulation/health

# Run Management
POST /api/trading/simulation/runs                  - Create simulation
GET  /api/trading/simulation/runs                  - List simulations  
GET  /api/trading/simulation/runs/{runId}          - Get simulation
POST /api/trading/simulation/runs/{runId}/start    - Start simulation
POST /api/trading/simulation/runs/{runId}/run      - Run full simulation
POST /api/trading/simulation/runs/{runId}/pause    - Pause simulation
POST /api/trading/simulation/runs/{runId}/resume   - Resume simulation
POST /api/trading/simulation/runs/{runId}/stop     - Stop simulation

# Step Control
POST /api/trading/simulation/runs/{runId}/step     - Execute single step

# State
GET  /api/trading/simulation/runs/{runId}/state    - Get state
GET  /api/trading/simulation/runs/{runId}/positions - Get positions
GET  /api/trading/simulation/runs/{runId}/equity   - Get equity history

# Determinism
GET  /api/trading/simulation/runs/{runId}/fingerprint - Get fingerprint
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from .simulation_types import (
    CapitalProfile,
    MarketType,
    Timeframe,
    SimulationStatus
)

from .simulation_engine import simulation_engine


router = APIRouter(prefix="/simulation", tags=["Trading Simulation (S1)"])


# ===========================================
# Request Models
# ===========================================

class CreateSimulationRequest(BaseModel):
    """Request to create simulation"""
    strategy_id: str
    asset: str = "BTCUSDT"
    start_date: str = "2022-01-01"
    end_date: str = "2023-01-01"
    capital_profile: str = "SMALL"  # MICRO, SMALL, MEDIUM, LARGE
    initial_capital_usd: Optional[float] = None
    market_type: str = "SPOT"  # SPOT, FUTURES
    timeframe: str = "1D"  # 1D, 4H, 1H
    strategy_version: Optional[str] = None
    risk_profile_id: Optional[str] = None
    strategy_config: Optional[Dict[str, Any]] = None
    risk_config: Optional[Dict[str, Any]] = None


class StartSimulationRequest(BaseModel):
    """Request to start simulation"""
    strategy_config: Optional[Dict[str, Any]] = None
    risk_config: Optional[Dict[str, Any]] = None


# ===========================================
# Health
# ===========================================

@router.get("/health")
async def simulation_health():
    """Simulation engine health check"""
    return simulation_engine.get_health()


# ===========================================
# Run Management
# ===========================================

@router.post("/runs")
async def create_simulation(request: CreateSimulationRequest):
    """
    Create a new simulation run.
    
    Does not start the simulation - use /start endpoint to begin.
    """
    try:
        capital_profile = CapitalProfile(request.capital_profile)
    except ValueError:
        capital_profile = CapitalProfile.SMALL
    
    try:
        market_type = MarketType(request.market_type)
    except ValueError:
        market_type = MarketType.SPOT
    
    try:
        timeframe = Timeframe(request.timeframe)
    except ValueError:
        timeframe = Timeframe.D1
    
    result = await simulation_engine.create_simulation(
        strategy_id=request.strategy_id,
        asset=request.asset,
        start_date=request.start_date,
        end_date=request.end_date,
        capital_profile=capital_profile,
        initial_capital_usd=request.initial_capital_usd,
        market_type=market_type,
        timeframe=timeframe,
        strategy_version=request.strategy_version,
        risk_profile_id=request.risk_profile_id,
        strategy_config=request.strategy_config,
        risk_config=request.risk_config
    )
    
    return result


@router.get("/runs")
async def list_simulations(
    status: Optional[str] = Query(None),
    strategy_id: Optional[str] = Query(None),
    limit: int = Query(100)
):
    """List all simulations"""
    status_enum = None
    if status:
        try:
            status_enum = SimulationStatus(status)
        except ValueError:
            pass
    
    runs = simulation_engine.list_simulations(
        status=status_enum,
        strategy_id=strategy_id,
        limit=limit
    )
    
    return {
        "runs": runs,
        "count": len(runs)
    }


@router.get("/runs/{run_id}")
async def get_simulation(run_id: str):
    """Get simulation details"""
    result = simulation_engine.get_simulation(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    return result


@router.post("/runs/{run_id}/start")
async def start_simulation(run_id: str, request: Optional[StartSimulationRequest] = None):
    """
    Start simulation (freeze config, begin replay).
    
    After starting, config cannot be changed.
    """
    config = request or StartSimulationRequest()
    
    result = await simulation_engine.start_simulation(
        run_id,
        strategy_config=config.strategy_config,
        risk_config=config.risk_config
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to start"))
    
    return result


@router.post("/runs/{run_id}/run")
async def run_simulation(run_id: str, request: Optional[StartSimulationRequest] = None):
    """
    Run complete simulation.
    
    Combines start + full replay execution.
    Returns final results.
    """
    config = request or StartSimulationRequest()
    
    result = await simulation_engine.run_simulation(
        run_id,
        strategy_config=config.strategy_config,
        risk_config=config.risk_config
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Simulation failed"))
    
    return result


@router.post("/runs/{run_id}/pause")
async def pause_simulation(run_id: str):
    """Pause running simulation"""
    result = await simulation_engine.pause_simulation(run_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail="Failed to pause")
    
    return result


@router.post("/runs/{run_id}/resume")
async def resume_simulation(run_id: str):
    """Resume paused simulation"""
    result = await simulation_engine.resume_simulation(run_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail="Failed to resume")
    
    return result


@router.post("/runs/{run_id}/stop")
async def stop_simulation(run_id: str):
    """Stop and complete simulation"""
    result = await simulation_engine.stop_simulation(run_id)
    return result


# ===========================================
# Step Control
# ===========================================

@router.post("/runs/{run_id}/step")
async def step_simulation(run_id: str):
    """
    Execute single replay step.
    
    Use for STEP mode or debugging.
    """
    result = await simulation_engine.step_simulation(run_id)
    return result


# ===========================================
# State
# ===========================================

@router.get("/runs/{run_id}/state")
async def get_simulation_state(run_id: str):
    """Get current simulation state"""
    state = simulation_engine.get_state(run_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    
    return state


@router.get("/runs/{run_id}/positions")
async def get_simulation_positions(run_id: str):
    """Get simulation positions"""
    positions = simulation_engine.get_positions(run_id)
    
    return {
        "positions": positions,
        "count": len(positions)
    }


@router.get("/runs/{run_id}/equity")
async def get_equity_history(run_id: str):
    """Get equity curve"""
    history = simulation_engine.get_equity_history(run_id)
    
    return {
        "equity_history": history,
        "points": len(history)
    }


@router.get("/runs/{run_id}/fills")
async def get_simulation_fills(run_id: str):
    """Get simulation fills (orders that were executed)"""
    fills = simulation_engine.get_fills(run_id)
    
    return {
        "fills": fills,
        "count": len(fills)
    }


@router.get("/runs/{run_id}/orders")
async def get_simulation_orders(run_id: str):
    """Get simulation orders (open and closed)"""
    orders = simulation_engine.get_orders(run_id)
    
    return orders


# ===========================================
# Determinism
# ===========================================

@router.get("/runs/{run_id}/fingerprint")
async def get_fingerprint(run_id: str):
    """
    Get simulation fingerprint.
    
    Useful for verifying determinism and comparing runs.
    """
    fingerprint = simulation_engine.get_fingerprint(run_id)
    
    if not fingerprint:
        raise HTTPException(status_code=404, detail="Fingerprint not found")
    
    return fingerprint


# ===========================================
# Include Metrics Router (S1.4)
# ===========================================

from .metrics.metrics_routes import router as metrics_router
router.include_router(metrics_router)
