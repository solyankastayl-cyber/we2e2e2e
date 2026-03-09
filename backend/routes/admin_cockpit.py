"""
Phase 9.25E: Admin Cockpit API Routes
=====================================

Policy-based Admin Cockpit for system governance.

Endpoints:
- GET  /api/admin/health         - Health check
- GET  /api/admin/dashboard      - Admin dashboard
- GET  /api/admin/policies       - Get all policies
- GET  /api/admin/policies/{type} - Get specific policy type
- POST /api/admin/policies/update - Update policy
- GET  /api/admin/policies/versions - Get policy versions
- POST /api/admin/policies/snapshot - Create snapshot
- POST /api/admin/policies/rollback - Rollback to version
- POST /api/admin/control/strategy - Control strategy
- GET  /api/admin/control/overrides - Get all overrides
- GET  /api/admin/control/history - Control history
- GET  /api/admin/governance/history - Governance history
"""

import time
from fastapi import APIRouter, HTTPException, Request
from typing import Optional

# Import service
try:
    from modules.admin_cockpit.service import (
        AdminCockpitService,
        dashboard_to_dict,
        PolicyType
    )
    
    admin_cockpit_service = AdminCockpitService()
    ADMIN_COCKPIT_AVAILABLE = True
    print("[Phase 9.25E] Admin Cockpit module loaded successfully")
except ImportError as e:
    ADMIN_COCKPIT_AVAILABLE = False
    admin_cockpit_service = None
    print(f"[Phase 9.25E] Module not available: {e}")


router = APIRouter(prefix="/api/admin", tags=["Admin Cockpit"])


# ============================================
# Health & Dashboard
# ============================================

@router.get("/health")
async def admin_health():
    """Admin Cockpit health check"""
    if not ADMIN_COCKPIT_AVAILABLE:
        return {
            "enabled": False,
            "version": "phase9.25E",
            "status": "unavailable",
            "error": "Module not loaded"
        }
    
    return admin_cockpit_service.get_health()


@router.get("/dashboard")
async def admin_dashboard():
    """Get admin dashboard summary"""
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    dashboard = admin_cockpit_service.get_dashboard()
    return dashboard_to_dict(dashboard)


# ============================================
# Policy Management
# ============================================

@router.get("/policies")
async def get_policies(policy_type: Optional[str] = None):
    """
    Get all policies or specific policy type.
    
    Query params:
    - policy_type: Optional filter (strategy_policies, self_healing_policies, etc.)
    """
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    return admin_cockpit_service.get_policies(policy_type)


@router.get("/policies/{policy_type}")
async def get_policy_by_type(policy_type: str):
    """Get specific policy type"""
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    # Validate policy type
    valid_types = [t.value for t in PolicyType]
    if policy_type not in valid_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid policy type: {policy_type}. Valid types: {valid_types}"
        )
    
    policies = admin_cockpit_service.get_policies(policy_type)
    
    if not policies:
        raise HTTPException(status_code=404, detail=f"Policy type not found: {policy_type}")
    
    return {
        "policyType": policy_type,
        "policies": policies,
        "version": admin_cockpit_service.policy_manager._current_version
    }


@router.post("/policies/update")
async def update_policy(request: Request):
    """
    Update a policy section.
    
    Request body:
    {
        "policyType": "self_healing_policies",
        "updates": {
            "health_thresholds": {
                "warning": 0.65
            }
        },
        "author": "admin",
        "reason": "Adjusting warning threshold"
    }
    """
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    body = await request.json()
    
    policy_type = body.get("policyType")
    updates = body.get("updates")
    author = body.get("author", "admin")
    reason = body.get("reason", "")
    
    if not policy_type or not updates:
        raise HTTPException(status_code=400, detail="policyType and updates are required")
    
    result = admin_cockpit_service.update_policy(policy_type, updates, author, reason)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or result.get("errors"))
    
    return result


@router.get("/policies/versions")
async def get_policy_versions():
    """Get all policy version snapshots"""
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    versions = admin_cockpit_service.policy_manager.get_versions()
    
    return {
        "currentVersion": admin_cockpit_service.policy_manager._current_version,
        "versions": versions,
        "count": len(versions)
    }


@router.post("/policies/snapshot")
async def create_policy_snapshot(request: Request):
    """
    Create a versioned snapshot of current policies.
    
    Request body:
    {
        "author": "admin",
        "notes": "Pre-production snapshot"
    }
    """
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    body = await request.json()
    author = body.get("author", "admin")
    notes = body.get("notes", "")
    
    result = admin_cockpit_service.create_snapshot(author, notes)
    
    return result


@router.post("/policies/rollback")
async def rollback_policy(request: Request):
    """
    Rollback policies to a previous version.
    
    Request body:
    {
        "versionId": "v1_1709856000",
        "author": "admin"
    }
    """
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    body = await request.json()
    version_id = body.get("versionId")
    author = body.get("author", "admin")
    
    if not version_id:
        raise HTTPException(status_code=400, detail="versionId is required")
    
    result = admin_cockpit_service.rollback(version_id, author)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    return result


# ============================================
# Strategy Control
# ============================================

@router.post("/control/strategy")
async def control_strategy(request: Request):
    """
    Execute a strategy control action.
    
    Request body:
    {
        "action": "FREEZE" | "UNFREEZE" | "PROMOTE" | "DEMOTE" | "DISABLE" | "ENABLE" | 
                  "FORCE_RECOVERY" | "FORCE_DEMOTION" | "SET_WEIGHT" | "SET_BUDGET",
        "strategyId": "MTF_BREAKOUT",
        "params": {
            "to_status": "APPROVED",  // For PROMOTE/DEMOTE
            "reason": "Manual override",  // For DEMOTE/DISABLE
            "weight": 0.8,  // For SET_WEIGHT
            "budget": {...}  // For SET_BUDGET
        },
        "author": "admin"
    }
    """
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    body = await request.json()
    
    action = body.get("action")
    strategy_id = body.get("strategyId")
    params = body.get("params", {})
    author = body.get("author", "admin")
    
    if not action or not strategy_id:
        raise HTTPException(status_code=400, detail="action and strategyId are required")
    
    result = admin_cockpit_service.control_strategy(action, strategy_id, params, author)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.get("/control/overrides")
async def get_control_overrides():
    """Get all strategy overrides"""
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    overrides = admin_cockpit_service.strategy_controller.get_all_overrides()
    frozen = list(admin_cockpit_service.strategy_controller._frozen_strategies)
    
    return {
        "overrides": overrides,
        "frozenStrategies": frozen,
        "count": len(overrides),
        "timestamp": int(time.time() * 1000)
    }


@router.get("/control/override/{strategy_id}")
async def get_strategy_override(strategy_id: str):
    """Get override for specific strategy"""
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    override = admin_cockpit_service.strategy_controller.get_override(strategy_id)
    is_frozen = admin_cockpit_service.strategy_controller.is_frozen(strategy_id)
    
    return {
        "strategyId": strategy_id,
        "override": override,
        "isFrozen": is_frozen,
        "timestamp": int(time.time() * 1000)
    }


@router.get("/control/history")
async def get_control_history(limit: int = 50):
    """Get control action history"""
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    history = admin_cockpit_service.strategy_controller.get_control_history(limit)
    
    return {
        "history": [
            {
                "action": h.action.value,
                "target": h.target,
                "oldState": h.old_state,
                "newState": h.new_state,
                "message": h.message,
                "timestamp": h.timestamp
            }
            for h in history
        ],
        "count": len(history)
    }


# ============================================
# Governance History
# ============================================

@router.get("/governance/history")
async def get_governance_history(limit: int = 50):
    """Get full governance history"""
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    history = admin_cockpit_service.get_governance_history(limit)
    
    return {
        "history": history,
        "count": len(history)
    }


@router.get("/governance/stats")
async def get_governance_stats():
    """Get governance statistics"""
    if not ADMIN_COCKPIT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Admin Cockpit module not available")
    
    history = admin_cockpit_service.governance_history.get_history()
    
    # Count by type
    by_type = {}
    for change in history:
        change_type = change.change_type.value
        by_type[change_type] = by_type.get(change_type, 0) + 1
    
    # Count by author
    by_author = {}
    for change in history:
        author = change.author
        by_author[author] = by_author.get(author, 0) + 1
    
    # Recent activity
    now = int(time.time() * 1000)
    day_ago = now - 86400000
    week_ago = now - 604800000
    
    changes_24h = len([c for c in history if c.timestamp > day_ago])
    changes_7d = len([c for c in history if c.timestamp > week_ago])
    
    return {
        "totalChanges": len(history),
        "byType": by_type,
        "byAuthor": by_author,
        "activity": {
            "last24h": changes_24h,
            "last7d": changes_7d
        },
        "currentPolicyVersion": admin_cockpit_service.policy_manager._current_version
    }
