"""
Control Backend Routes (P0-3)
=============================

REST API for Control Backend Finalization.

Uses /api/control prefix to avoid conflicts with other modules.

Endpoints:

# System Monitoring (Control Backend view)
- GET  /api/control/system/health       - System health status
- GET  /api/control/system/state        - System state machine state
- GET  /api/control/system/metrics      - System metrics
- GET  /api/control/system/timeline     - Recent timeline events

# Strategy Monitoring
- GET  /api/strategies/lifecycle        - Strategy lifecycle info
- GET  /api/strategies/health           - Strategy health metrics
- GET  /api/strategies/decay            - Strategy decay info
- GET  /api/strategies/{id}             - Single strategy details

# Research Monitoring
- GET  /api/research/loops              - Research loop stats
- GET  /api/research/mutations          - Mutation stats
- GET  /api/research/success-rate       - Alpha success rate
- GET  /api/research/stats              - Combined research stats

# Risk Monitoring
- GET  /api/risk/state                  - Current risk state
- GET  /api/risk/exposure               - Risk exposure metrics
- GET  /api/risk/drawdown               - Drawdown metrics
- GET  /api/risk/alerts                 - Risk alerts

# Admin Control Actions (Protected with X-ADMIN-KEY)
- POST /api/control/system/pause        - Pause system
- POST /api/control/system/resume       - Resume system
- POST /api/risk/override               - Override risk state
- POST /api/strategy/freeze             - Freeze strategy
- POST /api/strategy/unfreeze           - Unfreeze strategy
- POST /api/lifecycle/override          - Override lifecycle state
- POST /api/control/system/maintenance  - Start maintenance mode

# Admin Audit Trail (Protected with X-ADMIN-KEY)
- GET  /api/admin/actions               - Get admin action log
- GET  /api/admin/frozen                - Get frozen strategies
"""

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import os

from .service import control_backend_service


router = APIRouter(tags=["Control Backend P0-3"])


# Admin API Key check
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "admin_secret_key_2026")


def verify_admin_key(x_admin_key: Optional[str]) -> bool:
    """Verify admin API key"""
    if not x_admin_key:
        return False
    return x_admin_key == ADMIN_API_KEY


# Request Models

class PauseRequest(BaseModel):
    reason: str


class RiskOverrideRequest(BaseModel):
    state: str
    reason: str = ""


class StrategyFreezeRequest(BaseModel):
    strategy_id: str
    reason: str = ""


class LifecycleOverrideRequest(BaseModel):
    strategy_id: str
    to_state: str
    reason: str = ""


class MaintenanceRequest(BaseModel):
    reason: str = ""


# =========================================
# System Monitoring (using /api/control prefix to avoid SSM conflicts)
# =========================================

@router.get("/api/control/system/health")
async def control_system_health():
    """
    Get system health status (Control Backend view).
    
    Returns:
        {
            "status": "healthy",
            "services": {
                "event_bus": "ok",
                "timeline": "ok",
                ...
            }
        }
    """
    return control_backend_service.get_system_health()


@router.get("/api/control/system/state")
async def control_system_state():
    """
    Get system state from State Machine (Control Backend view).
    
    Returns:
        {
            "state": "ACTIVE",
            "since": "2026-03-10T14:21:00Z"
        }
    """
    return control_backend_service.get_system_state()


@router.get("/api/control/system/metrics")
async def control_system_metrics():
    """
    Get system metrics (Control Backend view).
    
    Returns:
        {
            "event_throughput": 1040,
            "active_strategies": 28,
            "risk_state": "NORMAL",
            "research_cycles_today": 12,
            "timeline_events_today": 8432
        }
    """
    return control_backend_service.get_system_metrics()


@router.get("/api/control/system/timeline")
async def control_system_timeline(limit: int = Query(50, ge=1, le=200)):
    """
    Get recent timeline events (Control Backend view).
    
    Returns:
        {
            "events": [
                {"type": "alpha_promoted", ...},
                {"type": "risk_state_changed", ...}
            ]
        }
    """
    return control_backend_service.get_system_timeline(limit)


# =========================================
# Strategy Monitoring
# =========================================

@router.get("/api/strategies/lifecycle")
async def strategy_lifecycle():
    """
    Get strategy lifecycle info for all strategies.
    
    Returns:
        {
            "strategies": [
                {
                    "strategy": "breakout_v5",
                    "state": "CORE",
                    "age_days": 142,
                    "decay_score": 0.12
                }
            ]
        }
    """
    return control_backend_service.get_strategy_lifecycle()


@router.get("/api/strategies/health")
async def strategy_health():
    """
    Get strategy health metrics.
    
    Returns:
        {
            "health": [
                {
                    "strategy": "breakout_v5",
                    "pf": 1.31,
                    "sharpe": 1.18,
                    "drawdown": 0.09
                }
            ]
        }
    """
    return control_backend_service.get_strategy_health()


@router.get("/api/strategies/decay")
async def strategy_decay():
    """
    Get strategy decay information.
    
    Returns:
        {
            "decay": [
                {
                    "strategy": "breakout_v5",
                    "decay_score": 0.21,
                    "trend": "stable"
                }
            ]
        }
    """
    return control_backend_service.get_strategy_decay()


@router.get("/api/strategies/{strategy_id}")
async def strategy_detail(strategy_id: str):
    """
    Get single strategy details.
    
    Returns full strategy information including lifecycle state, scores, etc.
    """
    result = control_backend_service.get_strategy_detail(strategy_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# =========================================
# Research Monitoring
# =========================================

@router.get("/api/research/loops")
async def research_loops():
    """
    Get research loop stats.
    
    Returns:
        {
            "loops_today": 14,
            "loops_total": 210
        }
    """
    return control_backend_service.get_research_loops()


@router.get("/api/research/mutations")
async def research_mutations():
    """
    Get mutation stats.
    
    Returns:
        {
            "mutations_generated": 1200,
            "mutations_passed": 85
        }
    """
    return control_backend_service.get_research_mutations()


@router.get("/api/research/success-rate")
async def research_success_rate():
    """
    Get alpha success rate.
    
    Returns:
        {
            "alpha_generated": 430,
            "alpha_promoted": 17,
            "success_rate": 0.039
        }
    """
    return control_backend_service.get_research_success_rate()


@router.get("/api/research/stats")
async def research_stats():
    """
    Get combined research stats.
    
    Returns all research monitoring data in one response.
    """
    return control_backend_service.get_research_stats()


# =========================================
# Risk Monitoring
# =========================================

@router.get("/api/risk/state")
async def risk_state():
    """
    Get current risk state.
    
    Returns:
        {
            "state": "NORMAL",
            "volatility_score": 0.8,
            "correlation_score": 0.2
        }
    """
    return control_backend_service.get_risk_state()


@router.get("/api/risk/exposure")
async def risk_exposure():
    """
    Get risk exposure metrics.
    
    Returns:
        {
            "gross_exposure": 0.74,
            "net_exposure": 0.12
        }
    """
    return control_backend_service.get_risk_exposure()


@router.get("/api/risk/drawdown")
async def risk_drawdown():
    """
    Get drawdown metrics.
    
    Returns:
        {
            "current_dd": 0.04,
            "max_dd": 0.11
        }
    """
    return control_backend_service.get_risk_drawdown()


@router.get("/api/risk/alerts")
async def risk_alerts(acknowledged: Optional[bool] = Query(None)):
    """
    Get risk alerts.
    
    Args:
        acknowledged: Filter by acknowledgement status (optional)
    
    Returns:
        {
            "alerts": [...],
            "count": 5,
            "unacknowledged": 3
        }
    """
    return control_backend_service.get_risk_alerts(acknowledged)


# =========================================
# Admin Control Actions (Protected - using /api/control prefix)
# =========================================

@router.post("/api/control/system/pause")
async def control_pause_system(
    request: PauseRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-ADMIN-KEY")
):
    """
    Pause the system (Control Backend).
    
    Requires X-ADMIN-KEY header.
    
    Request body:
        {
            "reason": "maintenance"
        }
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    return control_backend_service.pause_system(request.reason)


@router.post("/api/control/system/resume")
async def control_resume_system(
    x_admin_key: Optional[str] = Header(None, alias="X-ADMIN-KEY")
):
    """
    Resume the system (Control Backend).
    
    Requires X-ADMIN-KEY header.
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    return control_backend_service.resume_system()


@router.post("/api/risk/override")
async def risk_override(
    request: RiskOverrideRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-ADMIN-KEY")
):
    """
    Override risk state.
    
    Requires X-ADMIN-KEY header.
    
    Request body:
        {
            "state": "STRESS",
            "reason": "Manual override"
        }
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    result = control_backend_service.override_risk(request.state, request.reason)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/api/strategy/freeze")
async def freeze_strategy(
    request: StrategyFreezeRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-ADMIN-KEY")
):
    """
    Freeze a strategy.
    
    Requires X-ADMIN-KEY header.
    
    Request body:
        {
            "strategy_id": "breakout_v5",
            "reason": "Performance issue"
        }
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    result = control_backend_service.freeze_strategy(request.strategy_id, request.reason)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/api/strategy/unfreeze")
async def unfreeze_strategy(
    request: StrategyFreezeRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-ADMIN-KEY")
):
    """
    Unfreeze a strategy.
    
    Requires X-ADMIN-KEY header.
    
    Request body:
        {
            "strategy_id": "breakout_v5"
        }
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    result = control_backend_service.unfreeze_strategy(request.strategy_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/api/lifecycle/override")
async def lifecycle_override(
    request: LifecycleOverrideRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-ADMIN-KEY")
):
    """
    Override strategy lifecycle state.
    
    Requires X-ADMIN-KEY header.
    
    Request body:
        {
            "strategy_id": "breakout_v5",
            "to_state": "DISABLED",
            "reason": "Manual override"
        }
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    result = control_backend_service.lifecycle_override(
        request.strategy_id, 
        request.to_state, 
        request.reason
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/api/control/system/maintenance")
async def control_start_maintenance(
    request: MaintenanceRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-ADMIN-KEY")
):
    """
    Start maintenance mode (Control Backend).
    
    Requires X-ADMIN-KEY header.
    
    Request body:
        {
            "reason": "Database upgrade"
        }
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    return control_backend_service.start_maintenance(request.reason)


@router.post("/api/control/system/maintenance/end")
async def control_end_maintenance(
    x_admin_key: Optional[str] = Header(None, alias="X-ADMIN-KEY")
):
    """
    End maintenance mode (Control Backend).
    
    Requires X-ADMIN-KEY header.
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    return control_backend_service.end_maintenance()


# =========================================
# Admin Audit Trail
# =========================================

@router.get("/api/admin/actions")
async def admin_actions(
    limit: int = Query(50, ge=1, le=200),
    action_type: Optional[str] = Query(None),
    x_admin_key: Optional[str] = Header(None, alias="X-ADMIN-KEY")
):
    """
    Get admin action audit log.
    
    Args:
        limit: Max number of actions to return
        action_type: Filter by action type (optional)
    
    Returns:
        {
            "actions": [
                {
                    "timestamp": "2026-03-10T14:22:00Z",
                    "user": "admin",
                    "action": "pause_system",
                    "target": "system",
                    "payload": {"reason": "maintenance"}
                }
            ],
            "count": 10,
            "total": 25
        }
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    return control_backend_service.get_admin_actions(limit, action_type)


@router.get("/api/admin/frozen")
async def frozen_strategies(
    x_admin_key: Optional[str] = Header(None, alias="X-ADMIN-KEY")
):
    """
    Get list of frozen strategies.
    
    Requires X-ADMIN-KEY header.
    """
    if not verify_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    
    return control_backend_service.get_frozen_strategies()


# =========================================
# Control Backend Health
# =========================================

@router.get("/api/control-backend/health")
async def control_backend_health():
    """
    Control Backend module health check.
    """
    return control_backend_service.get_health()
