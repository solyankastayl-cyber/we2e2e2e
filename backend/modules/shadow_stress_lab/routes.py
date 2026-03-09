"""
Stress Lab Routes
=================

Phase 9.30B - API endpoints for stress testing.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .service import stress_service


router = APIRouter(prefix="/api/stress", tags=["stress-lab"])


# ============================================
# Request Models
# ============================================

class RunScenarioRequest(BaseModel):
    scenario_id: str
    mode: str = "FULL_SYSTEM"  # CORE_ONLY, FULL_SYSTEM, FULL_STRESS_POLICIES
    initial_capital: float = 100000.0


class RunBatchRequest(BaseModel):
    scenario_ids: Optional[List[str]] = None  # None = all scenarios
    mode: str = "FULL_SYSTEM"
    initial_capital: float = 100000.0


# ============================================
# Health
# ============================================

@router.get("/health")
async def health_check():
    """Health check for stress lab"""
    return stress_service.get_health()


# ============================================
# Scenarios
# ============================================

@router.get("/scenarios")
async def get_scenarios(asset_class: Optional[str] = None):
    """Get available stress scenarios"""
    return stress_service.get_scenarios(asset_class)


# ============================================
# Run Stress Tests
# ============================================

@router.post("/run")
async def run_scenario(request: RunScenarioRequest):
    """Run a single stress scenario"""
    return stress_service.run_scenario(
        scenario_id=request.scenario_id,
        mode=request.mode,
        initial_capital=request.initial_capital
    )


@router.post("/run-batch")
async def run_batch(request: RunBatchRequest):
    """Run multiple stress scenarios (batch)"""
    return stress_service.run_batch(
        scenario_ids=request.scenario_ids,
        mode=request.mode,
        initial_capital=request.initial_capital
    )


# ============================================
# Query Results
# ============================================

@router.get("/runs")
async def list_runs(limit: int = 20):
    """List all stress runs"""
    return stress_service.list_runs(limit)


@router.get("/run/{run_id}")
async def get_run(run_id: str):
    """Get full stress run details"""
    result = stress_service.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/report/{run_id}")
async def get_report(run_id: str):
    """Get condensed stress report"""
    result = stress_service.get_report(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/events/{run_id}")
async def get_events(run_id: str):
    """Get timeline events for a stress run"""
    result = stress_service.get_events(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/metrics/{run_id}")
async def get_metrics(run_id: str):
    """Get detailed metrics for a stress run"""
    result = stress_service.get_metrics(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result
