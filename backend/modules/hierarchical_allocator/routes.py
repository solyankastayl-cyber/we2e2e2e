"""
Hierarchical Allocator API Routes
=================================

Phase 9.3F — Hierarchical Alpha Allocator

Endpoints:
- GET  /api/hierarchical-allocator/health        - Service health
- POST /api/hierarchical-allocator/add-alpha     - Add single alpha
- POST /api/hierarchical-allocator/add-batch     - Add multiple alphas
- POST /api/hierarchical-allocator/set-regime    - Set regime
- POST /api/hierarchical-allocator/allocate      - Run allocation
- GET  /api/hierarchical-allocator/weights/{id}  - Get final weights
- GET  /api/hierarchical-allocator/families/{id} - Get family breakdown
- GET  /api/hierarchical-allocator/crowding/{id} - Get crowding report
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from .service import HierarchicalAllocatorService


router = APIRouter(prefix="/api/hierarchical-allocator", tags=["Hierarchical Allocator"])

# Service instance
service = HierarchicalAllocatorService()


class AddAlphaRequest(BaseModel):
    portfolio_id: str = Field(default="default")
    strategy_id: str = Field(description="Strategy identifier")
    family: str = Field(description="Family type: trend, reversal, breakout, momentum, structure, harmonic, mean_reversion, experimental")
    returns: List[float] = Field(description="Historical returns")
    expected_return: Optional[float] = None
    volatility: Optional[float] = None
    health_score: float = Field(default=1.0)
    regime_fit: float = Field(default=1.0)


class AddBatchRequest(BaseModel):
    portfolio_id: str = Field(default="default")
    alphas: List[Dict[str, Any]] = Field(description="List of alpha configs")


class SetRegimeRequest(BaseModel):
    portfolio_id: str = Field(default="default")
    regime: str = Field(description="Current regime: TREND_UP, TREND_DOWN, RANGE, EXPANSION, CRISIS")


class AllocateRequest(BaseModel):
    portfolio_id: str = Field(default="default")
    method: str = Field(default="max_sharpe")


class UpdateBudgetsRequest(BaseModel):
    portfolio_id: str = Field(default="default")
    budgets: Dict[str, float] = Field(description="Family budgets")


@router.get("/health")
async def get_health():
    """Get hierarchical allocator service health"""
    return service.get_health()


@router.post("/add-alpha")
async def add_alpha(request: AddAlphaRequest):
    """
    Add a single alpha to the allocator.
    
    Alpha will be grouped into specified family.
    """
    return service.add_alpha(
        portfolio_id=request.portfolio_id,
        strategy_id=request.strategy_id,
        family=request.family,
        returns=request.returns,
        expected_return=request.expected_return,
        volatility=request.volatility,
        health_score=request.health_score,
        regime_fit=request.regime_fit
    )


@router.post("/add-batch")
async def add_batch(request: AddBatchRequest):
    """Add multiple alphas in batch"""
    return service.add_alphas_batch(
        portfolio_id=request.portfolio_id,
        alphas=request.alphas
    )


@router.post("/set-regime")
async def set_regime(request: SetRegimeRequest):
    """
    Set current market regime.
    
    This adjusts family budgets based on regime.
    For example, TREND_UP increases trend/breakout budgets.
    """
    return service.set_regime(
        portfolio_id=request.portfolio_id,
        regime=request.regime
    )


@router.post("/allocate")
async def allocate(request: AllocateRequest):
    """
    Run hierarchical allocation.
    
    Steps:
    1. Get regime-adjusted family budgets
    2. Optimize within each family (intra-family)
    3. Combine into final portfolio weights
    
    This prevents optimizer from concentrating on noise.
    """
    return service.allocate(
        portfolio_id=request.portfolio_id,
        method=request.method
    )


@router.get("/weights/{portfolio_id}")
async def get_weights(portfolio_id: str):
    """Get final portfolio weights"""
    return service.get_final_weights(portfolio_id)


@router.get("/families/{portfolio_id}")
async def get_families(portfolio_id: str):
    """Get allocation breakdown by family"""
    return service.get_family_breakdown(portfolio_id)


@router.get("/crowding/{portfolio_id}")
async def get_crowding(portfolio_id: str):
    """
    Get crowding analysis by family.
    
    Shows:
    - Average correlation within each family
    - High-correlation pairs (crowding risk)
    - Crowding risk level (LOW/MEDIUM/HIGH)
    """
    return service.get_crowding_report(portfolio_id)


@router.post("/budgets")
async def update_budgets(request: UpdateBudgetsRequest):
    """Update family risk budgets"""
    return service.update_family_budgets(
        portfolio_id=request.portfolio_id,
        budgets=request.budgets
    )


@router.post("/{portfolio_id}/reset")
async def reset(portfolio_id: str):
    """Reset allocator"""
    return service.reset(portfolio_id)


@router.get("/explain/{portfolio_id}")
async def explain(portfolio_id: str):
    """Get detailed explanation of allocation"""
    weights = service.get_final_weights(portfolio_id)
    families = service.get_family_breakdown(portfolio_id)
    
    if weights.get("status") == "not_allocated":
        return {
            "portfolio_id": portfolio_id,
            "explanation": "Portfolio not allocated. Add alphas and call /allocate first.",
            "status": "not_allocated"
        }
    
    parts = []
    
    # Total strategies
    total = weights.get("total_strategies", 0)
    effective = weights.get("effective_strategies", 0)
    parts.append(f"{total} strategies → {effective:.1f} effective bets")
    
    # Families
    fam_data = families.get("families", {})
    active_families = [f for f, d in fam_data.items() if d.get("budget", 0) > 0.05]
    parts.append(f"Active families: {', '.join(active_families)}")
    
    # Top allocations
    final_weights = weights.get("weights", {})
    if final_weights:
        sorted_w = sorted(final_weights.items(), key=lambda x: x[1], reverse=True)[:3]
        top_str = ", ".join([f"{s}={w:.1%}" for s, w in sorted_w])
        parts.append(f"Top allocations: {top_str}")
    
    # Regime
    regime = families.get("regime", "RANGE")
    parts.append(f"Regime: {regime}")
    
    return {
        "portfolio_id": portfolio_id,
        "explanation": " | ".join(parts),
        "total_strategies": total,
        "effective_strategies": effective,
        "effective_families": weights.get("effective_families", 0),
        "regime": regime
    }
