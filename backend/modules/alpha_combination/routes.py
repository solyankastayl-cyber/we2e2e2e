"""
Alpha Combination API Routes
============================

Phase 9.3E — Alpha Combination Engine

Endpoints:
- GET  /api/alpha-combination/health          - Service health
- POST /api/alpha-combination/add-strategy    - Add strategy
- POST /api/alpha-combination/optimize        - Run optimization
- GET  /api/alpha-combination/weights/{id}    - Get optimal weights
- GET  /api/alpha-combination/correlations/{id} - Get correlations
- GET  /api/alpha-combination/compare/{id}    - Compare methods
- GET  /api/alpha-combination/risk/{id}       - Risk decomposition
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from .service import AlphaCombinationService


router = APIRouter(prefix="/api/alpha-combination", tags=["Alpha Combination"])

# Service instance
service = AlphaCombinationService()


class AddStrategyRequest(BaseModel):
    portfolio_id: str = Field(default="default", description="Portfolio identifier")
    strategy_id: str = Field(description="Strategy identifier")
    returns: List[float] = Field(description="Historical returns (daily)")
    expected_return: Optional[float] = Field(default=None, description="Expected annualized return")
    volatility: Optional[float] = Field(default=None, description="Annualized volatility")


class OptimizeRequest(BaseModel):
    portfolio_id: str = Field(default="default", description="Portfolio identifier")
    method: str = Field(default="max_sharpe", description="Optimization method: mean_variance, risk_parity, max_sharpe, min_variance, equal_weight")
    use_shrinkage: bool = Field(default=True, description="Apply covariance shrinkage")


@router.get("/health")
async def get_health():
    """Get alpha combination service health"""
    return service.get_health()


@router.post("/add-strategy")
async def add_strategy(request: AddStrategyRequest):
    """
    Add a strategy to the combination engine.
    
    Provide historical returns for covariance computation.
    """
    return service.add_strategy(
        portfolio_id=request.portfolio_id,
        strategy_id=request.strategy_id,
        returns=request.returns,
        expected_return=request.expected_return,
        volatility=request.volatility
    )


@router.post("/optimize")
async def optimize(request: OptimizeRequest):
    """
    Run portfolio optimization.
    
    Methods:
    - max_sharpe: Maximize Sharpe ratio
    - mean_variance: Classic Markowitz (μᵀw - λwᵀΣw)
    - risk_parity: Equal risk contribution
    - min_variance: Minimum variance portfolio
    - equal_weight: Simple 1/N
    """
    try:
        return service.optimize(
            portfolio_id=request.portfolio_id,
            method=request.method,
            use_shrinkage=request.use_shrinkage
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/weights/{portfolio_id}")
async def get_weights(portfolio_id: str):
    """Get current optimal weights"""
    return service.get_weights(portfolio_id)


@router.get("/correlations/{portfolio_id}")
async def get_correlations(portfolio_id: str):
    """Get correlation matrix between strategies"""
    return service.get_correlations(portfolio_id)


@router.get("/compare/{portfolio_id}")
async def compare_methods(portfolio_id: str):
    """
    Compare all optimization methods.
    
    Shows weights and expected metrics for each method.
    """
    return service.compare_methods(portfolio_id)


@router.get("/risk/{portfolio_id}")
async def get_risk_decomposition(portfolio_id: str):
    """
    Get risk decomposition.
    
    Shows:
    - Marginal risk contribution per strategy
    - Percentage risk contribution
    - Diversification ratio
    - Effective number of bets
    """
    return service.get_risk_decomposition(portfolio_id)


@router.post("/{portfolio_id}/reset")
async def reset(portfolio_id: str):
    """Reset alpha combination engine"""
    return service.reset(portfolio_id)


@router.get("/explain/{portfolio_id}")
async def explain(portfolio_id: str):
    """Get detailed explanation of optimization result"""
    weights_data = service.get_weights(portfolio_id)
    risk_data = service.get_risk_decomposition(portfolio_id)
    
    if risk_data.get("status") == "not_optimized":
        return {
            "portfolio_id": portfolio_id,
            "explanation": "Portfolio not optimized yet. Add strategies and call /optimize first.",
            "status": "not_optimized"
        }
    
    weights = weights_data.get("weights", {})
    risk_contrib = risk_data.get("risk_contribution", {})
    
    parts = []
    
    # Top strategies by weight
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    top_3 = sorted_weights[:3]
    
    parts.append(f"Top strategies by weight: {', '.join([f'{s}={w:.1%}' for s,w in top_3])}")
    
    # Diversification
    div_ratio = risk_data.get("diversification_ratio", 1)
    eff_n = risk_data.get("effective_n", 1)
    
    if div_ratio > 1.5:
        parts.append(f"Well diversified (ratio: {div_ratio:.1f}, effective N: {eff_n:.1f})")
    elif div_ratio > 1.2:
        parts.append(f"Moderately diversified (ratio: {div_ratio:.1f})")
    else:
        parts.append(f"Concentrated portfolio (ratio: {div_ratio:.1f})")
    
    # Risk concentration
    if risk_contrib:
        max_risk = max(risk_contrib.values())
        max_risk_strategy = max(risk_contrib.items(), key=lambda x: x[1])[0]
        
        if max_risk > 0.4:
            parts.append(f"Warning: {max_risk_strategy} contributes {max_risk:.0%} of risk")
    
    return {
        "portfolio_id": portfolio_id,
        "explanation": " | ".join(parts),
        "weights": weights,
        "risk_contribution": risk_contrib,
        "metrics": {
            "diversification_ratio": div_ratio,
            "effective_n": eff_n
        }
    }
