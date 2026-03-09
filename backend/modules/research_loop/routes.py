"""
Research Loop Routes
====================

Phase 9.33 - API endpoints for research loop engine.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .engine import research_loop_engine
from .types import LoopConfig, LoopMode


router = APIRouter(prefix="/api/research-loop", tags=["research-loop"])


# ============================================
# Request Models
# ============================================

class CreateLoopRequest(BaseModel):
    name: str = "Research Loop"
    mode: str = "MANUAL"
    max_mutations_per_cycle: int = 20
    mutation_categories: List[str] = ["ARITHMETIC", "TEMPORAL"]
    max_alphas_per_cycle: int = 10
    alpha_families: List[str] = ["MOMENTUM", "MEAN_REVERSION", "BREAKOUT"]
    min_feature_quality: float = 0.6
    min_alpha_sharpe: float = 0.5
    max_crowding: float = 0.85
    tournament_rounds: int = 3
    min_tournament_score: float = 0.4
    cooldown_seconds: int = 3600
    max_cycles_per_day: int = 24
    target_assets: List[str] = ["BTC", "SPX"]
    target_timeframes: List[str] = ["1D", "4H"]


class UpdateConfigRequest(BaseModel):
    updates: Dict[str, Any]


# ============================================
# Health
# ============================================

@router.get("/health")
async def health_check():
    return research_loop_engine.get_health()


# ============================================
# Loop Management
# ============================================

@router.post("/loops")
async def create_loop(request: CreateLoopRequest):
    """Create a new research loop"""
    
    try:
        mode = LoopMode(request.mode)
    except ValueError:
        mode = LoopMode.MANUAL
    
    config = LoopConfig(
        name=request.name,
        mode=mode,
        max_mutations_per_cycle=request.max_mutations_per_cycle,
        mutation_categories=request.mutation_categories,
        max_alphas_per_cycle=request.max_alphas_per_cycle,
        alpha_families=request.alpha_families,
        min_feature_quality=request.min_feature_quality,
        min_alpha_sharpe=request.min_alpha_sharpe,
        max_crowding=request.max_crowding,
        tournament_rounds=request.tournament_rounds,
        min_tournament_score=request.min_tournament_score,
        cooldown_seconds=request.cooldown_seconds,
        max_cycles_per_day=request.max_cycles_per_day,
        target_assets=request.target_assets,
        target_timeframes=request.target_timeframes
    )
    
    state = research_loop_engine.create_loop(config)
    return research_loop_engine._state_to_dict(state)


@router.get("/loops")
async def list_loops():
    """List all research loops"""
    return {"loops": research_loop_engine.list_loops()}


@router.get("/loops/{loop_id}")
async def get_loop(loop_id: str):
    """Get loop state"""
    state = research_loop_engine.get_loop(loop_id)
    if not state:
        raise HTTPException(status_code=404, detail="Loop not found")
    return research_loop_engine._state_to_dict(state)


@router.get("/loops/{loop_id}/config")
async def get_loop_config(loop_id: str):
    """Get loop configuration"""
    config = research_loop_engine.configs.get(loop_id)
    if not config:
        raise HTTPException(status_code=404, detail="Loop not found")
    return research_loop_engine._config_to_dict(config)


@router.patch("/loops/{loop_id}/config")
async def update_loop_config(loop_id: str, request: UpdateConfigRequest):
    """Update loop configuration"""
    config = research_loop_engine.update_config(loop_id, request.updates)
    if not config:
        raise HTTPException(status_code=404, detail="Loop not found")
    return research_loop_engine._config_to_dict(config)


# ============================================
# Cycle Execution
# ============================================

@router.post("/run")
async def run_cycle(loop_id: str = "LOOP_DEFAULT"):
    """Run a single research cycle"""
    result = research_loop_engine.run_cycle(loop_id)
    return research_loop_engine._cycle_to_dict(result)


@router.post("/loops/{loop_id}/run")
async def run_loop_cycle(loop_id: str):
    """Run a cycle for specific loop"""
    result = research_loop_engine.run_cycle(loop_id)
    return research_loop_engine._cycle_to_dict(result)


# ============================================
# Cycles
# ============================================

@router.get("/cycles")
async def list_cycles(loop_id: Optional[str] = None, limit: int = 50):
    """List cycles"""
    return {
        "total": len(research_loop_engine.cycles),
        "cycles": research_loop_engine.list_cycles(loop_id, limit)
    }


@router.get("/cycles/{cycle_id}")
async def get_cycle(cycle_id: str):
    """Get cycle result"""
    result = research_loop_engine.get_cycle(cycle_id)
    if not result:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return result


# ============================================
# Events
# ============================================

@router.get("/events")
async def get_events(cycle_id: Optional[str] = None, limit: int = 100):
    """Get loop events"""
    return {
        "total": len(research_loop_engine.events),
        "events": research_loop_engine.get_events(cycle_id, limit)
    }


# ============================================
# Metrics
# ============================================

@router.get("/metrics")
async def get_metrics(loop_id: str = "LOOP_DEFAULT"):
    """Get loop metrics"""
    metrics = research_loop_engine.get_metrics(loop_id)
    return {
        "loop_id": metrics.loop_id,
        "feature_pass_rate": metrics.feature_pass_rate,
        "alpha_admission_rate": metrics.alpha_admission_rate,
        "tournament_win_rate": metrics.tournament_win_rate,
        "memory_block_rate": metrics.memory_block_rate,
        "avg_feature_quality": metrics.avg_feature_quality,
        "avg_alpha_sharpe": metrics.avg_alpha_sharpe,
        "features_per_cycle": metrics.features_per_cycle,
        "alphas_per_cycle": metrics.alphas_per_cycle,
        "admissions_per_cycle": metrics.admissions_per_cycle,
        "unique_patterns_found": metrics.unique_patterns_found,
        "compute_saved_by_memory": metrics.compute_saved_by_memory,
        "computed_at": metrics.computed_at
    }


@router.get("/loops/{loop_id}/metrics")
async def get_loop_metrics(loop_id: str):
    """Get metrics for specific loop"""
    metrics = research_loop_engine.get_metrics(loop_id)
    return {
        "loop_id": metrics.loop_id,
        "feature_pass_rate": metrics.feature_pass_rate,
        "alpha_admission_rate": metrics.alpha_admission_rate,
        "tournament_win_rate": metrics.tournament_win_rate,
        "avg_feature_quality": metrics.avg_feature_quality,
        "avg_alpha_sharpe": metrics.avg_alpha_sharpe,
        "features_per_cycle": metrics.features_per_cycle,
        "alphas_per_cycle": metrics.alphas_per_cycle,
        "computed_at": metrics.computed_at
    }
