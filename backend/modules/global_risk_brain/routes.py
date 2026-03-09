"""
Global Risk Brain Routes
========================

Phase 9.35 - API endpoints for Global Risk Brain.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .engine import global_risk_brain
from .types import RiskState, CapitalAllocation


router = APIRouter(prefix="/api/grb", tags=["global-risk-brain"])


# ============================================
# Request Models
# ============================================

class EvaluateRequest(BaseModel):
    vol_ratio: float = 1.0
    drawdown: float = 0.0
    correlation: float = 0.3
    liquidity_ratio: float = 1.0
    regime: str = "NORMAL"


class OverrideRequest(BaseModel):
    state: str
    reason: str = "Manual override"


class AllocationRequest(BaseModel):
    equities: float = 0.40
    crypto: float = 0.30
    fx: float = 0.20
    commodities: float = 0.10
    cash: float = 0.0


# ============================================
# Health
# ============================================

@router.get("/health")
async def health_check():
    return global_risk_brain.get_health()


# ============================================
# State
# ============================================

@router.get("/state")
async def get_state():
    """Get current GRB state"""
    return global_risk_brain.get_state()


@router.get("/envelope")
async def get_envelope():
    """Get current risk envelope"""
    return global_risk_brain.get_envelope()


@router.get("/capital")
async def get_capital_allocation():
    """Get current capital allocation"""
    return global_risk_brain._allocation_to_dict(global_risk_brain.get_allocation())


# ============================================
# Detectors
# ============================================

@router.get("/detectors")
async def get_detector_values():
    """Get current detector values"""
    return {
        "detectors": global_risk_brain.detector_values,
        "last_evaluation_at": global_risk_brain.last_evaluation_at
    }


# ============================================
# Evaluation
# ============================================

@router.post("/evaluate")
async def evaluate(request: EvaluateRequest):
    """Evaluate risk and potentially transition state"""
    
    snapshot = global_risk_brain.evaluate(
        vol_ratio=request.vol_ratio,
        drawdown=request.drawdown,
        correlation=request.correlation,
        liquidity_ratio=request.liquidity_ratio,
        regime=request.regime
    )
    
    return {
        "state": snapshot.state.value,
        "envelope": global_risk_brain._envelope_to_dict(snapshot.envelope),
        "allocation": global_risk_brain._allocation_to_dict(snapshot.allocation),
        "signals": [
            {
                "detector": s.detector_type.value,
                "name": s.name,
                "value": s.value,
                "threshold": s.threshold,
                "triggered": s.triggered,
                "severity": s.severity,
                "message": s.message
            }
            for s in snapshot.signals
        ],
        "triggered_detectors": snapshot.triggered_detectors,
        "active_policies": [p.value for p in snapshot.active_policies],
        "timestamp": snapshot.timestamp
    }


# ============================================
# Override
# ============================================

@router.post("/override")
async def override_state(request: OverrideRequest):
    """Manually override risk state (admin action)"""
    
    try:
        state = RiskState(request.state)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid state: {request.state}. Valid: {[s.value for s in RiskState]}"
        )
    
    global_risk_brain.override_state(state, request.reason)
    return global_risk_brain.get_state()


@router.post("/reset")
async def reset_to_normal():
    """Reset to normal state (admin action)"""
    global_risk_brain.reset_to_normal()
    return global_risk_brain.get_state()


# ============================================
# Allocation
# ============================================

@router.post("/allocation")
async def set_allocation(request: AllocationRequest):
    """Set capital allocation (admin action)"""
    
    allocation = CapitalAllocation(
        equities=request.equities,
        crypto=request.crypto,
        fx=request.fx,
        commodities=request.commodities,
        cash=request.cash
    )
    
    if not allocation.validate():
        raise HTTPException(
            status_code=400,
            detail="Allocation must sum to 1.0 (100%)"
        )
    
    global_risk_brain.set_allocation(allocation)
    return global_risk_brain._allocation_to_dict(allocation)


@router.get("/allocation/suggest")
async def suggest_allocation(regime: str = "NORMAL"):
    """Get suggested allocation based on current state"""
    allocation = global_risk_brain.suggest_allocation(regime)
    return global_risk_brain._allocation_to_dict(allocation)


# ============================================
# History
# ============================================

@router.get("/transitions")
async def get_transitions(limit: int = 50):
    """Get state transition history"""
    return {
        "total": len(global_risk_brain.transitions),
        "transitions": global_risk_brain.get_transitions(limit)
    }


# ============================================
# Policies
# ============================================

@router.get("/policies")
async def get_policies():
    """Get registered policies"""
    return {
        "policies": [
            {
                "policy_id": p.policy_id,
                "name": p.name,
                "trigger_state": p.trigger_state.value,
                "actions": [a.value for a in p.actions],
                "auto_activate": p.auto_activate
            }
            for p in global_risk_brain.policies.values()
        ]
    }
