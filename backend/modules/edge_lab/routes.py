"""
Edge Research Lab Routes
========================

Phase A - API endpoints for edge research and analysis.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from .engine import edge_research_engine


router = APIRouter(prefix="/api/edge", tags=["edge-research"])


# ============================================
# Health
# ============================================

@router.get("/health")
async def health_check():
    return edge_research_engine.get_health()


# ============================================
# Edge Map
# ============================================

@router.get("/map")
async def get_edge_map(
    strategy: Optional[str] = None,
    asset: Optional[str] = None,
    regime: Optional[str] = None,
    min_pf: float = 0.0
):
    """Get edge map - performance by strategy/asset/regime"""
    results = edge_research_engine.get_edge_map(strategy, asset, regime, min_pf)
    return {
        "total": len(results),
        "entries": results
    }


# ============================================
# Decade Analysis
# ============================================

@router.get("/decades")
async def get_decade_analysis(strategy: Optional[str] = None):
    """Get edge analysis by decade"""
    results = edge_research_engine.get_decade_analysis(strategy)
    return {
        "total": len(results),
        "decades": results
    }


# ============================================
# Regime Analysis
# ============================================

@router.get("/regimes")
async def get_regime_edges(strategy: Optional[str] = None):
    """Get regime-conditional edge analysis"""
    results = edge_research_engine.get_regime_edges(strategy)
    return {
        "total": len(results),
        "regime_edges": results
    }


# ============================================
# Cross-Asset Analysis
# ============================================

@router.get("/assets")
async def get_cross_asset_edges(strategy: Optional[str] = None):
    """Get cross-asset edge transferability"""
    results = edge_research_engine.get_cross_asset_edges(strategy)
    return {
        "total": len(results),
        "cross_asset_edges": results
    }


# ============================================
# Family Robustness
# ============================================

@router.get("/families")
async def get_family_robustness(family: Optional[str] = None):
    """Get strategy family robustness analysis"""
    results = edge_research_engine.get_family_robustness(family)
    return {
        "total": len(results),
        "families": results
    }


# ============================================
# Edge Decay
# ============================================

@router.get("/decay")
async def get_edge_decay(strategy: Optional[str] = None):
    """Get edge decay over time analysis"""
    results = edge_research_engine.get_edge_decay(strategy)
    return {
        "total": len(results),
        "decay_analyses": results
    }


# ============================================
# Fragility Analysis
# ============================================

@router.get("/fragility")
async def get_fragility(strategy: Optional[str] = None):
    """Get edge fragility analysis"""
    results = edge_research_engine.get_fragility(strategy)
    return {
        "total": len(results),
        "fragility_analyses": results
    }


# ============================================
# Strategy Analysis
# ============================================

@router.get("/analyze/{strategy_id}")
async def analyze_strategy(strategy_id: str):
    """Complete edge analysis for a single strategy"""
    result = edge_research_engine.analyze_strategy(strategy_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ============================================
# Reports
# ============================================

@router.post("/report")
async def generate_report():
    """Generate comprehensive edge research report"""
    report = edge_research_engine.generate_report()
    return edge_research_engine._report_to_dict(report)


@router.get("/reports")
async def list_reports():
    """List all generated reports"""
    reports = list(edge_research_engine.reports.values())
    return {
        "total": len(reports),
        "reports": [edge_research_engine._report_to_dict(r) for r in reports]
    }
