"""
Terminal Routes (T5)
====================

REST API for Terminal Backend.

Provides endpoints for:
- Account monitoring
- Position monitoring
- Order monitoring
- PnL tracking
- Execution logs
- Risk monitoring
- Averaging monitoring
- System state
- Admin actions
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from .terminal_service import terminal_service
from .terminal_types import EventType


router = APIRouter(prefix="/terminal", tags=["Terminal Backend"])


# ===========================================
# Request Models
# ===========================================

class ClosePositionRequest(BaseModel):
    connection_id: str
    asset: str


class CancelOrderRequest(BaseModel):
    order_id: str


class UpdatePriceRequest(BaseModel):
    asset: str
    price: float


# ===========================================
# Health
# ===========================================

@router.get("/health")
async def terminal_health():
    """Terminal backend health check"""
    return terminal_service.get_health()


# ===========================================
# Account Monitor
# ===========================================

@router.get("/accounts")
async def get_accounts():
    """Get overview of all accounts"""
    accounts = await terminal_service.get_accounts_overview()
    return {
        "accounts": [a.to_dict() for a in accounts],
        "count": len(accounts)
    }


@router.get("/accounts/{connection_id}")
async def get_account(connection_id: str):
    """Get account overview"""
    account = await terminal_service.get_account_overview(connection_id)
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return account.to_dict()


# ===========================================
# Positions Monitor
# ===========================================

@router.get("/positions")
async def get_positions(connection_id: Optional[str] = None):
    """Get all open positions"""
    positions = await terminal_service.get_positions(connection_id)
    return {
        "positions": [p.to_dict() for p in positions],
        "count": len(positions),
        "total_exposure_usd": sum(p.exposure_usd for p in positions),
        "total_unrealized_pnl_usd": sum(p.unrealized_pnl_usd for p in positions)
    }


@router.get("/positions/{asset}")
async def get_position(asset: str, connection_id: Optional[str] = None):
    """Get position for specific asset"""
    position = await terminal_service.get_position(asset.upper(), connection_id)
    
    if not position:
        raise HTTPException(status_code=404, detail=f"No position found for {asset}")
    
    return position.to_dict()


# ===========================================
# Orders Monitor
# ===========================================

@router.get("/orders")
async def get_orders(
    connection_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """Get orders with filters"""
    orders = terminal_service.get_orders(connection_id, status, limit)
    return {
        "orders": [o.to_dict() for o in orders],
        "count": len(orders)
    }


@router.get("/orders/open")
async def get_open_orders(connection_id: Optional[str] = None):
    """Get all open orders"""
    orders = terminal_service.get_open_orders(connection_id)
    return {
        "orders": [o.to_dict() for o in orders],
        "count": len(orders)
    }


@router.get("/orders/history")
async def get_order_history(
    connection_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """Get order history (filled/cancelled)"""
    orders = terminal_service.get_order_history(connection_id, limit)
    return {
        "orders": [o.to_dict() for o in orders],
        "count": len(orders)
    }


# ===========================================
# PnL Engine
# ===========================================

@router.get("/pnl")
async def get_pnl(connection_id: Optional[str] = None):
    """Get PnL overview"""
    pnl = await terminal_service.get_pnl(connection_id)
    return pnl.to_dict()


@router.get("/pnl/daily")
async def get_daily_pnl(connection_id: str):
    """Get today's PnL"""
    pnl = terminal_service.get_daily_pnl(connection_id)
    return pnl.to_dict()


@router.get("/pnl/history")
async def get_pnl_history(
    connection_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365)
):
    """Get PnL history"""
    history = terminal_service.get_pnl_history(connection_id, days)
    return {
        "history": [r.to_dict() for r in history],
        "count": len(history)
    }


# ===========================================
# Execution Log
# ===========================================

@router.get("/logs")
async def get_execution_logs(
    connection_id: Optional[str] = None,
    asset: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """Get execution log entries"""
    et = None
    if event_type:
        try:
            et = EventType(event_type.upper())
        except ValueError:
            pass
    
    logs = terminal_service.get_execution_log(connection_id, asset, et, limit)
    return {
        "logs": [l.to_dict() for l in logs],
        "count": len(logs)
    }


@router.get("/logs/{asset}")
async def get_asset_logs(
    asset: str,
    connection_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """Get execution logs for specific asset"""
    logs = terminal_service.get_execution_log(connection_id, asset.upper(), None, limit)
    return {
        "asset": asset.upper(),
        "logs": [l.to_dict() for l in logs],
        "count": len(logs)
    }


# ===========================================
# Risk Monitor
# ===========================================

@router.get("/risk")
async def get_risk_overview(connection_id: Optional[str] = None):
    """Get risk overview"""
    risk = await terminal_service.get_risk_overview(connection_id)
    return risk.to_dict()


@router.get("/risk/exposure")
async def get_exposure(connection_id: Optional[str] = None):
    """Get exposure details"""
    risk = await terminal_service.get_risk_overview(connection_id)
    positions = await terminal_service.get_positions(connection_id)
    
    # Group exposure by asset
    by_asset = {}
    for pos in positions:
        if pos.asset not in by_asset:
            by_asset[pos.asset] = 0.0
        by_asset[pos.asset] += pos.exposure_usd
    
    return {
        "total_exposure_usd": risk.current_exposure_usd,
        "total_exposure_pct": risk.current_exposure_pct,
        "max_exposure_pct": risk.max_exposure_pct,
        "by_asset": by_asset,
        "positions_count": len(positions)
    }


@router.get("/risk/drawdown")
async def get_drawdown(connection_id: Optional[str] = None):
    """Get drawdown details"""
    risk = await terminal_service.get_risk_overview(connection_id)
    
    return {
        "daily_pnl_usd": risk.daily_pnl_usd,
        "daily_drawdown_pct": risk.daily_drawdown_pct,
        "max_drawdown_pct": risk.max_drawdown_pct,
        "emergency_stop_triggered": risk.emergency_stop_triggered,
        "blocked_trades_24h": risk.blocked_trades_24h
    }


# ===========================================
# Averaging Monitor
# ===========================================

@router.get("/averaging")
async def get_averaging_overview(connection_id: Optional[str] = None):
    """Get all averaging states"""
    states = await terminal_service.get_averaging_overview(connection_id)
    return {
        "averaging_states": [s.to_dict() for s in states],
        "active_count": len(states),
        "total_capital_committed_usd": sum(s.capital_committed_usd for s in states)
    }


@router.get("/averaging/{asset}")
async def get_averaging_state(asset: str, connection_id: Optional[str] = None):
    """Get averaging state for specific asset"""
    # If connection_id not provided, try to find any
    states = await terminal_service.get_averaging_overview(connection_id)
    
    for state in states:
        if state.asset == asset.upper():
            return state.to_dict()
    
    return {
        "asset": asset.upper(),
        "active": False,
        "message": "No active averaging for this asset"
    }


# ===========================================
# System State
# ===========================================

@router.get("/state")
async def get_system_state():
    """Get trading system state"""
    state = await terminal_service.get_system_state()
    return state.to_dict()


# ===========================================
# Terminal Actions
# ===========================================

@router.post("/actions/pause")
async def action_pause():
    """Pause trading"""
    result = await terminal_service.action_pause()
    return result.to_dict()


@router.post("/actions/resume")
async def action_resume():
    """Resume trading"""
    result = await terminal_service.action_resume()
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return result.to_dict()


@router.post("/actions/kill-switch")
async def action_kill_switch():
    """Activate kill switch"""
    result = await terminal_service.action_activate_kill_switch()
    return result.to_dict()


@router.post("/actions/deactivate-kill-switch")
async def action_deactivate_kill_switch():
    """Deactivate kill switch"""
    result = await terminal_service.action_deactivate_kill_switch()
    return result.to_dict()


@router.post("/actions/close-position")
async def action_close_position(request: ClosePositionRequest):
    """Close position for asset"""
    result = await terminal_service.action_close_position(
        request.connection_id,
        request.asset.upper()
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return result.to_dict()


@router.post("/actions/cancel-order")
async def action_cancel_order(request: CancelOrderRequest):
    """Cancel specific order"""
    result = await terminal_service.action_cancel_order(request.order_id)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return result.to_dict()


@router.post("/actions/cancel-all-orders")
async def action_cancel_all_orders(connection_id: Optional[str] = None):
    """Cancel all orders"""
    result = await terminal_service.action_cancel_all_orders(connection_id)
    return result.to_dict()


# ===========================================
# Utility
# ===========================================

@router.post("/prices/update")
async def update_price(request: UpdatePriceRequest):
    """Update price for asset (for valuation)"""
    terminal_service.update_price(request.asset.upper(), request.price)
    return {
        "success": True,
        "asset": request.asset.upper(),
        "price": request.price
    }


# ===========================================
# Dashboard Summary
# ===========================================

@router.get("/dashboard")
async def get_dashboard(connection_id: Optional[str] = None):
    """
    Get complete dashboard summary.
    
    Aggregates all terminal data for admin UI.
    """
    state = await terminal_service.get_system_state()
    accounts = await terminal_service.get_accounts_overview()
    positions = await terminal_service.get_positions(connection_id)
    risk = await terminal_service.get_risk_overview(connection_id)
    pnl = await terminal_service.get_pnl(connection_id)
    averaging = await terminal_service.get_averaging_overview(connection_id)
    open_orders = terminal_service.get_open_orders(connection_id)
    recent_logs = terminal_service.get_execution_log(connection_id, limit=10)
    
    return {
        "system": state.to_dict(),
        "accounts": {
            "list": [a.to_dict() for a in accounts],
            "total_equity_usd": sum(a.total_equity_usd for a in accounts)
        },
        "positions": {
            "list": [p.to_dict() for p in positions],
            "count": len(positions),
            "total_exposure_usd": sum(p.exposure_usd for p in positions),
            "total_unrealized_pnl_usd": sum(p.unrealized_pnl_usd for p in positions)
        },
        "orders": {
            "open": [o.to_dict() for o in open_orders],
            "open_count": len(open_orders)
        },
        "risk": risk.to_dict(),
        "pnl": pnl.to_dict(),
        "averaging": {
            "states": [a.to_dict() for a in averaging],
            "active_count": len(averaging)
        },
        "recent_logs": [l.to_dict() for l in recent_logs],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
