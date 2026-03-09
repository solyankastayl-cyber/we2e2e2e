"""
Autopsy Engine Routes
=====================

Phase 9.30C - API endpoints for autopsy engine.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .service import autopsy_service


router = APIRouter(prefix="/api/autopsy", tags=["autopsy-engine"])


# ============================================
# Request Models
# ============================================

class StrategyAutopsyRequest(BaseModel):
    strategy_id: str
    alpha_id: str
    name: str
    family: str
    asset_class: str = ""
    total_pnl: float = 0.0
    trades: int = 0
    winning_trades: int = 0
    regime: str = "NORMAL"
    was_paused: bool = False
    was_disabled: bool = False
    drawdown_pct: float = 0.0


class PortfolioAutopsyRequest(BaseModel):
    portfolio_id: str
    equity: float = 0.0
    initial_capital: float = 100000.0
    drawdown_pct: float = 0.0
    regime: str = "NORMAL"
    strategies: Optional[List[Dict[str, Any]]] = None
    trades: int = 0


class StressAutopsyRequest(BaseModel):
    run_id: str
    scenario_name: str
    scenario_tags: Optional[List[str]] = None
    max_drawdown_pct: float = 0.0
    capital_preserved_pct: float = 1.0
    regime: str = "NORMAL"
    strategy_results: Optional[List[Dict[str, Any]]] = None
    governance_events: int = 0
    healing_events: int = 0
    family_collapses: Optional[List[str]] = None


# ============================================
# Health
# ============================================

@router.get("/health")
async def health_check():
    return autopsy_service.get_health()


# ============================================
# Run Autopsies
# ============================================

@router.post("/run-strategy")
async def run_strategy_autopsy(request: StrategyAutopsyRequest):
    """Run autopsy on a failed strategy"""
    return autopsy_service.run_strategy_autopsy(
        strategy_id=request.strategy_id,
        alpha_id=request.alpha_id,
        name=request.name,
        family=request.family,
        asset_class=request.asset_class,
        total_pnl=request.total_pnl,
        trades=request.trades,
        winning_trades=request.winning_trades,
        regime=request.regime,
        was_paused=request.was_paused,
        was_disabled=request.was_disabled,
        drawdown_pct=request.drawdown_pct
    )


@router.post("/run-portfolio")
async def run_portfolio_autopsy(request: PortfolioAutopsyRequest):
    """Run autopsy on portfolio drawdown"""
    return autopsy_service.run_portfolio_autopsy(
        portfolio_id=request.portfolio_id,
        equity=request.equity,
        initial_capital=request.initial_capital,
        drawdown_pct=request.drawdown_pct,
        regime=request.regime,
        strategies=request.strategies,
        trades=request.trades
    )


@router.post("/run-stress")
async def run_stress_autopsy(request: StressAutopsyRequest):
    """Run autopsy on stress test results"""
    return autopsy_service.run_stress_autopsy(
        run_id=request.run_id,
        scenario_name=request.scenario_name,
        scenario_tags=request.scenario_tags,
        max_drawdown_pct=request.max_drawdown_pct,
        capital_preserved_pct=request.capital_preserved_pct,
        regime=request.regime,
        strategy_results=request.strategy_results,
        governance_events=request.governance_events,
        healing_events=request.healing_events,
        family_collapses=request.family_collapses
    )


# ============================================
# Query Reports
# ============================================

@router.get("/reports")
async def get_reports(
    entity_type: Optional[str] = None,
    family: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50
):
    """Get autopsy reports"""
    return autopsy_service.get_reports(entity_type, family, severity, limit)


@router.get("/report/{report_id}")
async def get_report(report_id: str):
    """Get single autopsy report"""
    result = autopsy_service.get_report(report_id)
    if not result:
        raise HTTPException(status_code=404, detail="Report not found")
    return result


# ============================================
# Patterns
# ============================================

@router.get("/patterns")
async def get_patterns(min_frequency: int = 1):
    """Get failure patterns"""
    return autopsy_service.get_patterns(min_frequency)


@router.get("/root-causes")
async def get_root_causes():
    """Get aggregated root cause summary"""
    return autopsy_service.get_root_causes()


@router.get("/digest")
async def get_digest():
    """Get full autopsy digest"""
    return autopsy_service.get_digest()
