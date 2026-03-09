"""
Evolution Engine API Routes
===========================

REST API for the Evolution Engine.

Endpoints:
- GET  /api/evolution/health    - Health check
- POST /api/evolution/run       - Run evolution cycle
- GET  /api/evolution/cycles    - List cycles
- GET  /api/evolution/cycle/{id} - Get cycle by ID
- GET  /api/evolution/metrics   - Get metrics
- GET  /api/evolution/decay     - Get decay signals
- POST /api/evolution/observe   - Run observation only
- POST /api/evolution/analyze   - Run analysis
- GET  /api/evolution/config    - Get config
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .engine import evolution_engine
from .types import EvolutionConfig, MutationType


router = APIRouter(prefix="/api/evolution", tags=["Evolution Engine"])


# Request models

class RunCycleRequest(BaseModel):
    """Request to run evolution cycle"""
    alpha_performances: Optional[Dict[str, Dict[str, float]]] = None


class ConfigUpdateRequest(BaseModel):
    """Request to update config"""
    decay_threshold: Optional[float] = None
    max_mutations_per_cycle: Optional[int] = None
    promotion_threshold: Optional[float] = None
    min_sharpe: Optional[float] = None


# Endpoints

@router.get("/health")
async def evolution_health():
    """Evolution Engine health check"""
    return evolution_engine.get_health()


@router.post("/run")
async def run_evolution_cycle(request: RunCycleRequest = None):
    """
    Run a complete evolution cycle.
    
    Pipeline: observe → analyze → adapt → evolve → select
    """
    performances = request.alpha_performances if request else None
    cycle = evolution_engine.run_cycle(performances)
    
    return {
        "success": cycle.status.value == "COMPLETED",
        "cycle": cycle.to_dict()
    }


@router.get("/cycles")
async def list_cycles(limit: int = Query(20, ge=1, le=100)):
    """List recent evolution cycles"""
    cycles = evolution_engine.get_recent_cycles(limit)
    
    return {
        "cycles": [c.to_dict() for c in cycles],
        "count": len(cycles)
    }


@router.get("/cycle/{cycle_id}")
async def get_cycle(cycle_id: str):
    """Get evolution cycle by ID"""
    cycle = evolution_engine.get_cycle(cycle_id)
    
    if not cycle:
        raise HTTPException(status_code=404, detail=f"Cycle not found: {cycle_id}")
    
    return cycle.to_dict()


@router.get("/metrics")
async def get_metrics():
    """Get evolution metrics"""
    return evolution_engine.get_metrics().to_dict()


@router.get("/decay")
async def get_decay_signals(limit: int = Query(50, ge=1, le=200)):
    """Get recent decay signals"""
    signals = evolution_engine.get_decay_signals(limit)
    
    return {
        "signals": [s.to_dict() for s in signals],
        "count": len(signals)
    }


@router.post("/observe")
async def run_observation(request: RunCycleRequest = None):
    """
    Run observation phase only.
    
    Detects decay in alpha performance.
    """
    performances = request.alpha_performances if request else None
    signals = evolution_engine.observe(performances)
    
    return {
        "signals": [s.to_dict() for s in signals],
        "count": len(signals),
        "decay_detected": len(signals) > 0
    }


@router.post("/analyze")
async def run_analysis():
    """
    Run analysis on recent decay signals.
    """
    recent_signals = evolution_engine.get_decay_signals(20)
    analysis = evolution_engine.analyze(recent_signals)
    
    return analysis


@router.get("/config")
async def get_config():
    """Get current configuration"""
    return evolution_engine.config.to_dict()


@router.patch("/config")
async def update_config(request: ConfigUpdateRequest):
    """Update configuration"""
    config = evolution_engine.config
    
    if request.decay_threshold is not None:
        config.decay_threshold = request.decay_threshold
    if request.max_mutations_per_cycle is not None:
        config.max_mutations_per_cycle = request.max_mutations_per_cycle
    if request.promotion_threshold is not None:
        config.promotion_threshold = request.promotion_threshold
    if request.min_sharpe is not None:
        config.min_sharpe = request.min_sharpe
    
    return {
        "success": True,
        "config": config.to_dict()
    }


@router.get("/mutations")
async def list_mutations(limit: int = Query(50, ge=1, le=200)):
    """List recent mutations"""
    mutations = list(evolution_engine.mutations.values())
    mutations = sorted(mutations, key=lambda m: m.created_at, reverse=True)[:limit]
    
    return {
        "mutations": [m.to_dict() for m in mutations],
        "count": len(mutations)
    }


@router.get("/baselines")
async def get_alpha_baselines():
    """Get alpha baseline sharpes"""
    return {
        "baselines": evolution_engine.alpha_baselines,
        "count": len(evolution_engine.alpha_baselines)
    }


@router.post("/baseline/{alpha_id}")
async def set_baseline(alpha_id: str, sharpe: float = Query(...)):
    """Set baseline sharpe for an alpha"""
    evolution_engine.alpha_baselines[alpha_id] = sharpe
    
    return {
        "success": True,
        "alpha_id": alpha_id,
        "baseline_sharpe": sharpe
    }
