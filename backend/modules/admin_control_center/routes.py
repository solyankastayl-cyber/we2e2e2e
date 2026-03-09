"""
Admin Control Center Routes
===========================

Phase C - Unified dashboard and control API.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from .engine import admin_control_center


router = APIRouter(prefix="/api/control-center", tags=["admin-control-center"])


class RiskOverrideRequest(BaseModel):
    state: str
    reason: str = ""


class CreateExperimentRequest(BaseModel):
    name: str
    dataset_version: str = ""
    strategies: list = []
    assets: list = []
    tags: list = []


# ============================================
# Health
# ============================================

@router.get("/health")
async def health_check():
    return admin_control_center.get_health()


# ============================================
# Dashboards
# ============================================

@router.get("/dashboard")
async def get_full_dashboard():
    """Get complete system dashboard"""
    return admin_control_center.get_full_dashboard()


@router.get("/dashboard/edge")
async def get_edge_dashboard():
    """Get edge intelligence dashboard"""
    return admin_control_center.get_edge_dashboard()


@router.get("/dashboard/execution")
async def get_execution_dashboard():
    """Get execution/microstructure dashboard"""
    return admin_control_center.get_execution_dashboard()


@router.get("/dashboard/alpha")
async def get_alpha_dashboard():
    """Get alpha factory dashboard"""
    return admin_control_center.get_alpha_dashboard()


@router.get("/dashboard/risk")
async def get_risk_dashboard():
    """Get risk/governance dashboard"""
    return admin_control_center.get_risk_dashboard()


@router.get("/dashboard/research")
async def get_research_dashboard():
    """Get research loop dashboard"""
    return admin_control_center.get_research_dashboard()


@router.get("/dashboard/shadow")
async def get_shadow_dashboard():
    """Get shadow portfolio dashboard"""
    return admin_control_center.get_shadow_dashboard()


@router.get("/dashboard/system")
async def get_system_dashboard():
    """Get system telemetry dashboard"""
    return admin_control_center.get_system_dashboard()


# ============================================
# Control Actions
# ============================================

@router.post("/research/run")
async def trigger_research_cycle(loop_id: str = "LOOP_DEFAULT"):
    """Trigger a research loop cycle"""
    return admin_control_center.trigger_research_cycle(loop_id)


@router.post("/risk/override")
async def override_risk_state(request: RiskOverrideRequest):
    """Override risk state (admin action)"""
    return admin_control_center.override_risk_state(request.state, request.reason)


@router.post("/experiments")
async def create_experiment(request: CreateExperimentRequest):
    """Create a new experiment"""
    return admin_control_center.create_experiment(
        name=request.name,
        dataset_version=request.dataset_version,
        strategies=request.strategies,
        assets=request.assets,
        tags=request.tags
    )
