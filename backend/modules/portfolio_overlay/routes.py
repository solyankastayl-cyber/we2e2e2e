"""
Portfolio Overlay API Routes
============================

Phase 9.3D — Portfolio Overlay Layer

Endpoints:
- GET  /api/portfolio-overlay/health           - Service health
- GET  /api/portfolio-overlay/{portfolio_id}   - Get current state
- POST /api/portfolio-overlay/update           - Update state
- POST /api/portfolio-overlay/size             - Get adjusted size
- POST /api/portfolio-overlay/configure        - Update config
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from .service import PortfolioOverlayService


router = APIRouter(prefix="/api/portfolio-overlay", tags=["Portfolio Overlay"])

# Service instance
service = PortfolioOverlayService()


class UpdateRequest(BaseModel):
    portfolio_id: str = Field(default="default", description="Portfolio identifier")
    equity: float = Field(description="Current portfolio equity")
    daily_return: float = Field(default=0.0, description="Today's return")
    strategy_score: float = Field(default=0.5, description="Strategy validation score")
    regime_confidence: float = Field(default=0.5, description="Regime detection confidence")
    health_score: float = Field(default=1.0, description="Self-healing health score")
    signal_confidence: float = Field(default=0.5, description="Signal confidence")


class SizeRequest(BaseModel):
    portfolio_id: str = Field(default="default", description="Portfolio identifier")
    base_size: float = Field(description="Base position size")


class ConfigureRequest(BaseModel):
    portfolio_id: str = Field(default="default", description="Portfolio identifier")
    target_volatility: Optional[float] = Field(default=None, description="Target annual volatility")
    dd_threshold_critical: Optional[float] = Field(default=None, description="Critical drawdown threshold")


@router.get("/health")
async def get_health():
    """Get portfolio overlay service health"""
    return service.get_health()


@router.get("/{portfolio_id}")
async def get_state(portfolio_id: str):
    """Get current overlay state for portfolio"""
    return service.get_current_state(portfolio_id)


@router.post("/update")
async def update_state(request: UpdateRequest):
    """
    Update overlay state with new data.
    
    Call this on each bar to update volatility, conviction, and drawdown states.
    """
    return service.update(
        portfolio_id=request.portfolio_id,
        equity=request.equity,
        daily_return=request.daily_return,
        strategy_score=request.strategy_score,
        regime_confidence=request.regime_confidence,
        health_score=request.health_score,
        signal_confidence=request.signal_confidence
    )


@router.post("/size")
async def size_position(request: SizeRequest):
    """
    Get overlay-adjusted position size.
    
    Returns position size after applying:
    - Volatility targeting
    - Conviction weighting
    - Drawdown control
    """
    return service.size_position(
        portfolio_id=request.portfolio_id,
        base_size=request.base_size
    )


@router.post("/configure")
async def configure(request: ConfigureRequest):
    """Update overlay configuration"""
    return service.configure(
        portfolio_id=request.portfolio_id,
        target_volatility=request.target_volatility,
        dd_threshold_critical=request.dd_threshold_critical
    )


@router.post("/{portfolio_id}/reset")
async def reset(portfolio_id: str):
    """Reset overlay engine for portfolio"""
    return service.reset(portfolio_id)


@router.get("/{portfolio_id}/explain")
async def explain(portfolio_id: str):
    """Get detailed explanation of current overlay state"""
    state = service.get_current_state(portfolio_id)
    
    if state.get("status") == "not_initialized":
        return {
            "portfolio_id": portfolio_id,
            "explanation": "Overlay not initialized. Call /update first.",
            "final_multiplier": 1.0
        }
    
    parts = []
    
    # Volatility explanation
    vol = state.get("volatility", {})
    target = vol.get("target", 0.12)
    realized = vol.get("realized", 0.12)
    
    if realized > target * 1.5:
        parts.append(f"High volatility ({realized:.1%} vs {target:.1%} target) - reducing position sizes")
    elif realized < target * 0.7:
        parts.append(f"Low volatility ({realized:.1%} vs {target:.1%} target) - increasing position sizes")
    else:
        parts.append(f"Volatility near target ({realized:.1%})")
    
    # Conviction explanation
    conv = state.get("conviction", {})
    level = conv.get("level", "MEDIUM")
    parts.append(f"Conviction level: {level}")
    
    # Drawdown explanation
    dd = state.get("drawdown", {})
    dd_pct = dd.get("current", 0)
    dd_state = dd.get("state", "NORMAL")
    
    if dd_pct > 0.10:
        parts.append(f"In {dd_state} drawdown ({dd_pct:.1%}) - reducing risk")
    elif dd_pct > 0.05:
        parts.append(f"Elevated drawdown ({dd_pct:.1%}) - slightly reduced risk")
    
    final = state.get("final_multiplier", 1.0)
    parts.append(f"Final position multiplier: {final}x")
    
    return {
        "portfolio_id": portfolio_id,
        "explanation": " | ".join(parts),
        "final_multiplier": final,
        "components": {
            "volatility_mult": vol.get("multiplier", 1.0),
            "conviction_mult": conv.get("multiplier", 1.0),
            "drawdown_mult": dd.get("multiplier", 1.0)
        }
    }
