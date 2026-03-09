"""
Risk Regime Routes
==================

Phase 9.3H - API endpoints for risk regime management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .service import risk_regime_service


router = APIRouter(prefix="/api/risk-regime", tags=["risk-regime"])


# ============================================
# Request/Response Models
# ============================================

class UpdateStateRequest(BaseModel):
    """Request to update state"""
    returns: Optional[List[float]] = None
    returns_by_asset: Optional[Dict[str, List[float]]] = None
    equity_curve: Optional[List[float]] = None
    vix_value: Optional[float] = None


class ForceStateRequest(BaseModel):
    """Request to force state"""
    state: str = Field(..., description="NORMAL, ELEVATED, STRESS, or CRISIS")
    reason: str = Field("manual override", description="Reason for override")


class UpdatePolicyRequest(BaseModel):
    """Request to update policy"""
    exposure_multiplier: Optional[float] = None
    leverage_multiplier: Optional[float] = None
    tactical_enabled: Optional[bool] = None
    experimental_enabled: Optional[bool] = None
    new_positions_enabled: Optional[bool] = None
    budget_compression: Optional[float] = None
    max_drawdown_limit: Optional[float] = None


class SimulateScenarioRequest(BaseModel):
    """Request to simulate scenario"""
    vix_value: float = Field(20.0, description="VIX value")
    volatility: float = Field(15.0, description="Realized volatility %")
    correlation: float = Field(0.4, description="Cross-asset correlation")
    drawdown: float = Field(0.05, description="Current drawdown (0.05 = 5%)")


# ============================================
# Health Check
# ============================================

@router.get("/health")
async def health_check():
    """Health check for risk regime service"""
    return risk_regime_service.get_health()


# ============================================
# State Management
# ============================================

@router.get("/state")
async def get_current_state():
    """Get current risk regime state"""
    return risk_regime_service.get_current_state()


@router.post("/state/update")
async def update_state(request: UpdateStateRequest):
    """Update risk regime state with new data"""
    return risk_regime_service.update_state(
        returns=request.returns,
        returns_by_asset=request.returns_by_asset,
        equity_curve=request.equity_curve,
        vix_value=request.vix_value
    )


@router.post("/state/force")
async def force_state(request: ForceStateRequest):
    """Force a specific risk state (manual override)"""
    result = risk_regime_service.force_state(request.state, request.reason)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ============================================
# Policy Management
# ============================================

@router.get("/policies")
async def get_policies():
    """Get all risk state policies"""
    return risk_regime_service.get_policies()


@router.put("/policies/{state_name}")
async def update_policy(state_name: str, request: UpdatePolicyRequest):
    """Update policy for a specific state"""
    result = risk_regime_service.update_policy(
        state_name=state_name,
        exposure_multiplier=request.exposure_multiplier,
        leverage_multiplier=request.leverage_multiplier,
        tactical_enabled=request.tactical_enabled,
        experimental_enabled=request.experimental_enabled,
        new_positions_enabled=request.new_positions_enabled,
        budget_compression=request.budget_compression,
        max_drawdown_limit=request.max_drawdown_limit
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ============================================
# Analysis
# ============================================

@router.get("/transitions")
async def get_transitions(limit: int = 100):
    """Get state transition history"""
    return risk_regime_service.get_transitions(limit)


@router.get("/distribution")
async def get_state_distribution():
    """Get time distribution across states"""
    return risk_regime_service.get_state_distribution()


@router.get("/indicators")
async def get_indicator_breakdown():
    """Get current indicator values breakdown"""
    return risk_regime_service.get_indicator_breakdown()


# ============================================
# Simulation
# ============================================

@router.post("/simulate")
async def simulate_scenario(request: SimulateScenarioRequest):
    """Simulate risk score for a hypothetical scenario"""
    return risk_regime_service.simulate_scenario(
        vix_value=request.vix_value,
        volatility=request.volatility,
        correlation=request.correlation,
        drawdown=request.drawdown
    )
