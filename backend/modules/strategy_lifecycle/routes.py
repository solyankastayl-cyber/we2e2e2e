"""
Strategy Lifecycle Engine API Routes
====================================

REST API for Strategy Lifecycle management.

Endpoints:
- GET  /api/lifecycle/health           - Health check
- POST /api/lifecycle/register         - Register new strategy
- GET  /api/lifecycle/strategies       - List all strategies
- GET  /api/lifecycle/strategy/{id}    - Get strategy by ID
- GET  /api/lifecycle/state/{state}    - Get strategies by state
- POST /api/lifecycle/transition       - Transition strategy state
- POST /api/lifecycle/promote/{id}     - Promote strategy
- POST /api/lifecycle/demote/{id}      - Demote strategy
- POST /api/lifecycle/disable/{id}     - Disable strategy
- POST /api/lifecycle/archive/{id}     - Archive strategy
- POST /api/lifecycle/recover/{id}     - Recover strategy
- GET  /api/lifecycle/history/{id}     - Get strategy history
- GET  /api/lifecycle/transitions      - Get recent transitions
- POST /api/lifecycle/evaluate/{id}    - Evaluate strategy
- POST /api/lifecycle/evaluate-all     - Evaluate all strategies
- GET  /api/lifecycle/metrics          - Get metrics
- PATCH /api/lifecycle/scores/{id}     - Update scores
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .engine import strategy_lifecycle_engine
from .types import (
    LifecycleState, DeathQuality, LifecycleScores,
    STATE_CONFIG, ALLOWED_TRANSITIONS
)


router = APIRouter(prefix="/api/lifecycle", tags=["Strategy Lifecycle"])


# Request models

class RegisterStrategyRequest(BaseModel):
    """Request to register a strategy"""
    strategy_id: str
    alpha_id: str
    name: str
    family: str
    initial_sharpe: Optional[float] = None
    initial_pf: Optional[float] = None


class TransitionRequest(BaseModel):
    """Request to transition strategy"""
    strategy_id: str
    to_state: str
    reason: str
    triggered_by: str = "api"
    force: bool = False


class DisableRequest(BaseModel):
    """Request to disable strategy"""
    reason: str
    death_quality: str = "UNKNOWN"


class UpdateScoresRequest(BaseModel):
    """Request to update scores"""
    sharpe: Optional[float] = None
    profit_factor: Optional[float] = None
    stability: Optional[float] = None
    regime_robustness: Optional[float] = None
    orthogonality: Optional[float] = None
    capital_efficiency: Optional[float] = None
    fragility_penalty: Optional[float] = None
    crowding: Optional[float] = None


# Endpoints

@router.get("/health")
async def lifecycle_health():
    """Strategy Lifecycle Engine health check"""
    return strategy_lifecycle_engine.get_health()


@router.post("/register")
async def register_strategy(request: RegisterStrategyRequest):
    """Register a new strategy in the lifecycle system"""
    
    # Check if already exists
    if strategy_lifecycle_engine.get_strategy(request.strategy_id):
        raise HTTPException(status_code=400, detail=f"Strategy {request.strategy_id} already registered")
    
    # Create initial scores
    scores = LifecycleScores()
    if request.initial_sharpe:
        scores.sharpe = request.initial_sharpe
    if request.initial_pf:
        scores.profit_factor = request.initial_pf
    
    record = strategy_lifecycle_engine.register(
        strategy_id=request.strategy_id,
        alpha_id=request.alpha_id,
        name=request.name,
        family=request.family,
        initial_scores=scores
    )
    
    return {
        "success": True,
        "strategy": record.to_dict()
    }


@router.get("/strategies")
async def list_strategies(
    limit: int = Query(100, ge=1, le=500),
    state: Optional[str] = Query(None)
):
    """List all strategies"""
    strategies = list(strategy_lifecycle_engine.strategies.values())
    
    if state:
        try:
            filter_state = LifecycleState(state)
            strategies = [s for s in strategies if s.current_state == filter_state]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid state: {state}")
    
    # Sort by created_at desc
    strategies = sorted(strategies, key=lambda s: s.created_at, reverse=True)[:limit]
    
    return {
        "strategies": [s.to_dict() for s in strategies],
        "count": len(strategies)
    }


@router.get("/strategy/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get strategy by ID"""
    strategy = strategy_lifecycle_engine.get_strategy(strategy_id)
    
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
    
    return strategy.to_dict()


@router.get("/state/{state}")
async def get_strategies_by_state(state: str):
    """Get all strategies in a specific state"""
    try:
        lifecycle_state = LifecycleState(state)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid state: {state}")
    
    strategies = strategy_lifecycle_engine.get_strategies_by_state(lifecycle_state)
    
    return {
        "state": state,
        "strategies": [s.to_dict() for s in strategies],
        "count": len(strategies)
    }


@router.post("/transition")
async def transition_strategy(request: TransitionRequest):
    """Transition strategy to a new state"""
    
    try:
        to_state = LifecycleState(request.to_state)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid state: {request.to_state}")
    
    transition = strategy_lifecycle_engine.transition(
        strategy_id=request.strategy_id,
        to_state=to_state,
        reason=request.reason,
        triggered_by=request.triggered_by,
        force=request.force
    )
    
    if not transition:
        strategy = strategy_lifecycle_engine.get_strategy(request.strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy not found: {request.strategy_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Transition from {strategy.current_state.value} to {request.to_state} not allowed"
        )
    
    return {
        "success": True,
        "transition": transition.to_dict()
    }


@router.post("/promote/{strategy_id}")
async def promote_strategy(strategy_id: str, reason: str = "Manual promotion"):
    """Promote strategy to next state"""
    transition = strategy_lifecycle_engine.promote(strategy_id, reason)
    
    if not transition:
        strategy = strategy_lifecycle_engine.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
        raise HTTPException(status_code=400, detail=f"Cannot promote from {strategy.current_state.value}")
    
    return {
        "success": True,
        "transition": transition.to_dict()
    }


@router.post("/demote/{strategy_id}")
async def demote_strategy(strategy_id: str, reason: str = "Manual demotion"):
    """Demote strategy to DEGRADED state"""
    transition = strategy_lifecycle_engine.demote(strategy_id, reason)
    
    if not transition:
        raise HTTPException(status_code=400, detail="Cannot demote strategy")
    
    return {
        "success": True,
        "transition": transition.to_dict()
    }


@router.post("/disable/{strategy_id}")
async def disable_strategy(strategy_id: str, request: DisableRequest):
    """Disable a strategy"""
    try:
        death_quality = DeathQuality(request.death_quality)
    except ValueError:
        death_quality = DeathQuality.UNKNOWN
    
    transition = strategy_lifecycle_engine.disable(
        strategy_id=strategy_id,
        reason=request.reason,
        death_quality=death_quality
    )
    
    if not transition:
        raise HTTPException(status_code=400, detail="Cannot disable strategy")
    
    return {
        "success": True,
        "transition": transition.to_dict()
    }


@router.post("/archive/{strategy_id}")
async def archive_strategy(strategy_id: str, reason: str = "Formally retired"):
    """Archive a strategy"""
    transition = strategy_lifecycle_engine.archive(strategy_id, reason)
    
    if not transition:
        raise HTTPException(status_code=400, detail="Cannot archive strategy")
    
    return {
        "success": True,
        "transition": transition.to_dict()
    }


@router.post("/recover/{strategy_id}")
async def recover_strategy(strategy_id: str, to_state: str = "SHADOW"):
    """Attempt to recover a degraded/disabled strategy"""
    try:
        target_state = LifecycleState(to_state)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid state: {to_state}")
    
    transition = strategy_lifecycle_engine.recover(strategy_id, target_state)
    
    if not transition:
        raise HTTPException(status_code=400, detail="Cannot recover strategy")
    
    return {
        "success": True,
        "transition": transition.to_dict()
    }


@router.get("/history/{strategy_id}")
async def get_strategy_history(strategy_id: str):
    """Get transition history for a strategy"""
    strategy = strategy_lifecycle_engine.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
    
    history = strategy_lifecycle_engine.get_history(strategy_id)
    
    return {
        "strategy_id": strategy_id,
        "current_state": strategy.current_state.value,
        "history": [t.to_dict() for t in history],
        "count": len(history)
    }


@router.get("/transitions")
async def get_recent_transitions(limit: int = Query(50, ge=1, le=200)):
    """Get recent transitions across all strategies"""
    transitions = strategy_lifecycle_engine.get_recent_transitions(limit)
    
    return {
        "transitions": [t.to_dict() for t in transitions],
        "count": len(transitions)
    }


@router.post("/evaluate/{strategy_id}")
async def evaluate_strategy(strategy_id: str):
    """Evaluate strategy and get recommendation"""
    result = strategy_lifecycle_engine.evaluate(strategy_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.post("/evaluate-all")
async def evaluate_all_strategies():
    """Evaluate all strategies"""
    strategy_lifecycle_engine.update_ages()
    results = strategy_lifecycle_engine.evaluate_all()
    
    return {
        "evaluations": results,
        "count": len(results)
    }


@router.get("/metrics")
async def get_metrics():
    """Get lifecycle metrics"""
    return strategy_lifecycle_engine.get_metrics().to_dict()


@router.patch("/scores/{strategy_id}")
async def update_scores(strategy_id: str, request: UpdateScoresRequest):
    """Update strategy scores"""
    strategy = strategy_lifecycle_engine.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
    
    strategy_lifecycle_engine.update_scores(
        strategy_id=strategy_id,
        sharpe=request.sharpe,
        profit_factor=request.profit_factor,
        stability=request.stability,
        regime_robustness=request.regime_robustness,
        orthogonality=request.orthogonality,
        capital_efficiency=request.capital_efficiency,
        fragility_penalty=request.fragility_penalty,
        crowding=request.crowding
    )
    
    return {
        "success": True,
        "scores": strategy.scores.to_dict()
    }


@router.get("/states")
async def list_states():
    """List all lifecycle states with configurations"""
    return {
        "states": [
            {
                "state": state.value,
                "config": STATE_CONFIG.get(state, {}),
                "allowed_transitions": [s.value for s in ALLOWED_TRANSITIONS.get(state, set())]
            }
            for state in LifecycleState
        ]
    }


@router.get("/death-qualities")
async def list_death_qualities():
    """List all death quality types"""
    return {
        "death_qualities": [dq.value for dq in DeathQuality]
    }
