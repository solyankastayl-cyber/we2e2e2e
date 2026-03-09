"""
System State Machine API Routes
===============================

REST API for System State Machine.

Endpoints:
- GET  /api/system/state        - Get current state
- POST /api/system/transition   - Transition to new state
- GET  /api/system/history      - Get state history
- GET  /api/system/states       - List all states
- GET  /api/system/transitions  - List allowed transitions
- POST /api/system/pause        - Pause system
- POST /api/system/resume       - Resume system
- POST /api/system/force        - Force state (admin)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .types import SystemState, STATE_CONFIG, ALLOWED_TRANSITIONS
from .engine import get_state_machine


router = APIRouter(prefix="/api/system", tags=["System State Machine"])


# Request models

class TransitionRequest(BaseModel):
    """Request to transition state"""
    state: str
    reason: str
    triggered_by: str = "api"


class ForceStateRequest(BaseModel):
    """Request to force state"""
    state: str
    reason: str
    triggered_by: str = "admin"


# Endpoints

@router.get("/state")
async def get_system_state():
    """Get current system state"""
    ssm = get_state_machine()
    info = ssm.get_state_info()
    
    return {
        "state": info["state"],
        "since": info["since"],
        "since_iso": datetime.fromtimestamp(info["since"]/1000, tz=timezone.utc).isoformat(),
        "config": info["config"],
        "allowed_transitions": info["allowed_transitions"]
    }


@router.get("/states")
async def list_states():
    """List all possible states"""
    return {
        "states": [
            {
                "state": state.value,
                "config": STATE_CONFIG.get(state, {})
            }
            for state in SystemState
        ]
    }


@router.get("/transitions")
async def list_transitions():
    """List allowed state transitions"""
    return {
        "transitions": {
            from_state.value: [to_state.value for to_state in to_states]
            for from_state, to_states in ALLOWED_TRANSITIONS.items()
        }
    }


@router.post("/transition")
async def transition_state(request: TransitionRequest):
    """
    Transition to a new state.
    
    Body:
    - state: Target state
    - reason: Why this transition
    - triggered_by: Who triggered (default: api)
    """
    ssm = get_state_machine()
    
    # Validate state
    try:
        new_state = SystemState(request.state)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {request.state}. Valid: {[s.value for s in SystemState]}"
        )
    
    # Check if allowed
    if not ssm.can_transition_to(new_state):
        current = ssm.current_state.value
        allowed = [s.value for s in ALLOWED_TRANSITIONS.get(ssm.current_state, set())]
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {current} to {new_state.value}. Allowed: {allowed}"
        )
    
    # Perform transition
    transition = ssm.transition(
        new_state=new_state,
        reason=request.reason,
        triggered_by=request.triggered_by
    )
    
    return {
        "success": transition.success,
        "transition": transition.to_dict(),
        "current_state": ssm.get_state_info()
    }


@router.get("/history")
async def get_state_history(limit: int = Query(50, ge=1, le=500)):
    """Get state transition history"""
    ssm = get_state_machine()
    history = ssm.get_history(limit)
    
    return {
        "history": [t.to_dict() for t in history],
        "count": len(history)
    }


@router.post("/pause")
async def pause_system(reason: str = "Manual pause", triggered_by: str = "admin"):
    """Pause the system"""
    ssm = get_state_machine()
    
    if ssm.current_state == SystemState.PAUSED:
        return {"success": True, "message": "System already paused"}
    
    if not ssm.can_transition_to(SystemState.PAUSED):
        current = ssm.current_state.value
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause from state: {current}"
        )
    
    transition = ssm.transition(
        new_state=SystemState.PAUSED,
        reason=reason,
        triggered_by=triggered_by
    )
    
    return {
        "success": transition.success,
        "transition": transition.to_dict()
    }


@router.post("/resume")
async def resume_system(
    target_state: str = "ACTIVE",
    reason: str = "Manual resume",
    triggered_by: str = "admin"
):
    """Resume the system from paused state"""
    ssm = get_state_machine()
    
    if ssm.current_state != SystemState.PAUSED:
        return {"success": False, "message": f"System not paused, current: {ssm.current_state.value}"}
    
    try:
        new_state = SystemState(target_state)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid target state: {target_state}")
    
    transition = ssm.transition(
        new_state=new_state,
        reason=reason,
        triggered_by=triggered_by
    )
    
    return {
        "success": transition.success,
        "transition": transition.to_dict()
    }


@router.post("/force")
async def force_state(request: ForceStateRequest):
    """
    Force system to a state (admin only).
    Bypasses transition rules.
    """
    ssm = get_state_machine()
    
    try:
        new_state = SystemState(request.state)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {request.state}"
        )
    
    transition = ssm.force_state(
        new_state=new_state,
        reason=request.reason,
        triggered_by=request.triggered_by
    )
    
    return {
        "success": True,
        "transition": transition.to_dict(),
        "warning": "State was forced, transition rules bypassed"
    }


@router.get("/check-action")
async def check_action(action: str = Query(...)):
    """Check if an action is allowed in current state"""
    ssm = get_state_machine()
    allowed = ssm.is_action_allowed(action)
    config = STATE_CONFIG.get(ssm.current_state, {})
    
    return {
        "action": action,
        "allowed": allowed,
        "current_state": ssm.current_state.value,
        "allowed_actions": config.get("allowed_actions", [])
    }


@router.get("/ssm/health")
async def ssm_health():
    """System State Machine health check"""
    ssm = get_state_machine()
    
    return {
        "enabled": True,
        "version": "ssm_v1",
        "status": "ok",
        "current_state": ssm.current_state.value,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
