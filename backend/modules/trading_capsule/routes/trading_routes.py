"""
Trading Capsule Routes (T0/T1)
==============================

REST API for Trading Capsule.

Endpoints:

# Module Info
- GET  /api/trading/health               - Module health
- GET  /api/trading/mode                 - Current execution mode
- POST /api/trading/mode/select          - Select execution mode

# Connections (T1)
- GET  /api/trading/connections          - List connections
- GET  /api/trading/connections/{id}     - Get connection
- POST /api/trading/connections/register - Register new connection
- POST /api/trading/connections/validate - Validate connection
- POST /api/trading/connections/{id}/select-mode - Change mode
- POST /api/trading/connections/{id}/disable - Disable connection
- DELETE /api/trading/connections/{id}   - Remove connection

# Accounts (T1)
- GET /api/trading/accounts              - List all accounts
- GET /api/trading/accounts/{id}         - Get account state
- GET /api/trading/accounts/{id}/balances - Get balances
- GET /api/trading/accounts/{id}/positions - Get positions
- GET /api/trading/accounts/{id}/health  - Get health
- POST /api/trading/accounts/{id}/health-check - Run health check
- POST /api/trading/accounts/{id}/refresh - Refresh account state

# Risk Profile
- GET  /api/trading/risk/profile         - Get risk profile
- POST /api/trading/risk/profile         - Update risk profile
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from ..trading_types import (
    Exchange,
    MarketMode,
    ExecutionMode,
    ConnectionStatus,
    ConnectionHealth,
    CapsuleModeState,
    TradingRiskProfile
)
from ..broker import (
    broker_registry,
    get_connection,
    list_connections,
    register_connection,
    remove_connection
)


router = APIRouter(prefix="/api/trading", tags=["Trading Capsule"])


# ===========================================
# Capsule State
# ===========================================

# Global capsule state
_capsule_state = CapsuleModeState()
_risk_profile = TradingRiskProfile()


# ===========================================
# Request Models
# ===========================================

class RegisterConnectionRequest(BaseModel):
    exchange: str  # BINANCE, BYBIT, etc.
    label: str
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None
    selected_mode: str = "SPOT"  # SPOT or FUTURES


class SelectModeRequest(BaseModel):
    execution_mode: Optional[str] = None  # TA_ONLY, MANUAL_SIGNAL_SOURCE, MBRAIN_ROUTED
    trading_mode: Optional[str] = None  # SPOT, FUTURES


class RiskProfileRequest(BaseModel):
    max_position_usd: Optional[float] = None
    max_asset_exposure_pct: Optional[float] = None
    max_portfolio_exposure_pct: Optional[float] = None
    max_daily_drawdown_pct: Optional[float] = None
    averaging_enabled: Optional[bool] = None
    max_averaging_steps: Optional[int] = None
    kill_switch_enabled: Optional[bool] = None


# ===========================================
# Module Info
# ===========================================

@router.get("/health")
async def trading_health():
    """Trading Capsule health check"""
    summary = broker_registry.get_summary()
    
    return {
        "enabled": True,
        "version": "trading_capsule_t0_t1",
        "status": "ok",
        "execution_mode": _capsule_state.execution_mode.value,
        "trading_mode": _capsule_state.trading_mode.value,
        "paused": _capsule_state.paused,
        "kill_switch_active": _capsule_state.kill_switch_active,
        "connections": summary,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/mode")
async def get_mode():
    """Get current capsule mode"""
    return _capsule_state.to_dict()


@router.post("/mode/select")
async def select_mode(request: SelectModeRequest):
    """Select execution/trading mode"""
    global _capsule_state
    
    if request.execution_mode:
        try:
            _capsule_state.execution_mode = ExecutionMode(request.execution_mode)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid execution mode. Valid: {[e.value for e in ExecutionMode]}"
            )
    
    if request.trading_mode:
        try:
            _capsule_state.trading_mode = MarketMode(request.trading_mode)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid trading mode. Valid: {[m.value for m in MarketMode]}"
            )
    
    _capsule_state.updated_at = datetime.now(timezone.utc)
    
    return {
        "success": True,
        "mode": _capsule_state.to_dict()
    }


# ===========================================
# Connections
# ===========================================

@router.get("/connections")
async def list_all_connections():
    """List all broker connections"""
    connections = list_connections()
    return {
        "connections": [c.to_dict() for c in connections],
        "count": len(connections)
    }


@router.get("/connections/{connection_id}")
async def get_connection_detail(connection_id: str):
    """Get connection details"""
    connection = get_connection(connection_id)
    
    if not connection:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    
    # Get health record
    health_record = broker_registry.get_health_record(connection_id)
    
    return {
        "connection": connection.to_dict(),
        "health_record": health_record.to_dict() if health_record else None
    }


@router.post("/connections/register")
async def register_new_connection(request: RegisterConnectionRequest):
    """Register a new broker connection"""
    
    # Validate exchange
    try:
        exchange = Exchange(request.exchange.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid exchange. Valid: {[e.value for e in Exchange]}"
        )
    
    # Validate mode
    try:
        mode = MarketMode(request.selected_mode.upper())
    except ValueError:
        mode = MarketMode.SPOT
    
    # Register
    connection = register_connection(
        exchange=exchange,
        label=request.label,
        api_key=request.api_key,
        api_secret=request.api_secret,
        passphrase=request.passphrase,
        selected_mode=mode
    )
    
    return {
        "success": True,
        "connection": connection.to_dict()
    }


@router.post("/connections/validate")
async def validate_connection(connection_id: str):
    """Validate an existing connection"""
    
    adapter = await broker_registry.get_or_create_adapter(connection_id)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    
    result = await adapter.validate_connection()
    
    # Update connection status
    if result.valid:
        broker_registry.update_connection_status(
            connection_id,
            ConnectionStatus.CONNECTED,
            ConnectionHealth.HEALTHY
        )
    else:
        broker_registry.update_connection_status(
            connection_id,
            ConnectionStatus.INVALID,
            ConnectionHealth.UNHEALTHY
        )
    
    return {
        "success": result.valid,
        "validation": result.to_dict()
    }


@router.post("/connections/{connection_id}/select-mode")
async def change_connection_mode(connection_id: str, mode: str):
    """Change trading mode for a connection"""
    
    try:
        market_mode = MarketMode(mode.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Valid: {[m.value for m in MarketMode]}"
        )
    
    success = broker_registry.update_connection_mode(connection_id, market_mode)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to update mode. Mode may not be supported."
        )
    
    return {
        "success": True,
        "connection_id": connection_id,
        "new_mode": market_mode.value
    }


@router.post("/connections/{connection_id}/disable")
async def disable_connection(connection_id: str):
    """Disable a connection"""
    
    connection = get_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    
    broker_registry.update_connection_status(
        connection_id,
        ConnectionStatus.DISCONNECTED,
        ConnectionHealth.UNHEALTHY
    )
    
    return {
        "success": True,
        "connection_id": connection_id,
        "status": "DISCONNECTED"
    }


@router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: str):
    """Remove a connection"""
    
    success = remove_connection(connection_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    
    return {
        "success": True,
        "deleted": connection_id
    }


# ===========================================
# Accounts
# ===========================================

@router.get("/accounts")
async def list_accounts():
    """List all accounts with their states"""
    connections = list_connections()
    accounts = []
    
    for conn in connections:
        if conn.status == ConnectionStatus.CONNECTED:
            adapter = broker_registry.get_adapter(conn.connection_id)
            if adapter:
                try:
                    state = await adapter.fetch_account_state()
                    accounts.append(state.to_dict())
                except Exception as e:
                    accounts.append({
                        "connection_id": conn.connection_id,
                        "error": str(e)
                    })
    
    return {
        "accounts": accounts,
        "count": len(accounts)
    }


@router.get("/accounts/{connection_id}")
async def get_account_state(connection_id: str):
    """Get account state for a connection"""
    
    adapter = await broker_registry.get_or_create_adapter(connection_id)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    
    # Connect if needed
    if not adapter._connected:
        await adapter.connect()
    
    state = await adapter.fetch_account_state()
    
    return state.to_dict()


@router.get("/accounts/{connection_id}/balances")
async def get_account_balances(connection_id: str):
    """Get balances for a connection"""
    
    adapter = await broker_registry.get_or_create_adapter(connection_id)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    
    if not adapter._connected:
        await adapter.connect()
    
    balances = await adapter.fetch_balances()
    
    return {
        "connection_id": connection_id,
        "balances": [b.to_dict() for b in balances],
        "count": len(balances)
    }


@router.get("/accounts/{connection_id}/positions")
async def get_account_positions(connection_id: str):
    """Get positions for a connection"""
    
    adapter = await broker_registry.get_or_create_adapter(connection_id)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    
    if not adapter._connected:
        await adapter.connect()
    
    positions = await adapter.fetch_positions()
    
    return {
        "connection_id": connection_id,
        "positions": [p.to_dict() for p in positions],
        "count": len(positions)
    }


@router.get("/accounts/{connection_id}/health")
async def get_account_health(connection_id: str):
    """Get health record for a connection"""
    
    record = broker_registry.get_health_record(connection_id)
    
    if not record:
        return {
            "connection_id": connection_id,
            "health": "UNKNOWN",
            "message": "No health check performed yet"
        }
    
    return record.to_dict()


@router.post("/accounts/{connection_id}/health-check")
async def run_health_check(connection_id: str):
    """Run health check for a connection"""
    
    adapter = await broker_registry.get_or_create_adapter(connection_id)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    
    if not adapter._connected:
        await adapter.connect()
    
    record = await adapter.health_check()
    
    # Store record
    broker_registry.set_health_record(connection_id, record)
    
    return record.to_dict()


@router.post("/accounts/{connection_id}/refresh")
async def refresh_account(connection_id: str):
    """Refresh account state"""
    
    adapter = await broker_registry.get_or_create_adapter(connection_id)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    
    # Reconnect
    await adapter.disconnect()
    await adapter.connect()
    
    # Fetch fresh state
    state = await adapter.fetch_account_state()
    
    return {
        "success": True,
        "account": state.to_dict()
    }


# ===========================================
# Risk Profile
# ===========================================

@router.get("/risk/profile")
async def get_risk_profile():
    """Get current risk profile"""
    return _risk_profile.to_dict()


@router.post("/risk/profile")
async def update_risk_profile(request: RiskProfileRequest):
    """Update risk profile"""
    global _risk_profile
    
    if request.max_position_usd is not None:
        _risk_profile.max_position_usd = request.max_position_usd
    
    if request.max_asset_exposure_pct is not None:
        _risk_profile.max_asset_exposure_pct = request.max_asset_exposure_pct
    
    if request.max_portfolio_exposure_pct is not None:
        _risk_profile.max_portfolio_exposure_pct = request.max_portfolio_exposure_pct
    
    if request.max_daily_drawdown_pct is not None:
        _risk_profile.max_daily_drawdown_pct = request.max_daily_drawdown_pct
    
    if request.averaging_enabled is not None:
        _risk_profile.averaging_enabled = request.averaging_enabled
    
    if request.max_averaging_steps is not None:
        _risk_profile.max_averaging_steps = request.max_averaging_steps
    
    if request.kill_switch_enabled is not None:
        _risk_profile.kill_switch_enabled = request.kill_switch_enabled
    
    return {
        "success": True,
        "profile": _risk_profile.to_dict()
    }


# ===========================================
# Capsule Control
# ===========================================

@router.post("/pause")
async def pause_capsule():
    """Pause trading capsule"""
    global _capsule_state
    _capsule_state.paused = True
    _capsule_state.updated_at = datetime.now(timezone.utc)
    
    return {
        "success": True,
        "paused": True
    }


@router.post("/resume")
async def resume_capsule():
    """Resume trading capsule"""
    global _capsule_state
    _capsule_state.paused = False
    _capsule_state.updated_at = datetime.now(timezone.utc)
    
    return {
        "success": True,
        "paused": False
    }


@router.post("/kill-switch/activate")
async def activate_kill_switch():
    """Activate kill switch - stops all trading"""
    global _capsule_state
    _capsule_state.kill_switch_active = True
    _capsule_state.paused = True
    _capsule_state.updated_at = datetime.now(timezone.utc)
    
    return {
        "success": True,
        "kill_switch_active": True,
        "message": "Kill switch activated. All trading stopped."
    }


@router.post("/kill-switch/deactivate")
async def deactivate_kill_switch():
    """Deactivate kill switch"""
    global _capsule_state
    _capsule_state.kill_switch_active = False
    _capsule_state.updated_at = datetime.now(timezone.utc)
    
    return {
        "success": True,
        "kill_switch_active": False,
        "message": "Kill switch deactivated. Manual resume required."
    }



# ===========================================
# Orders (T2 OMS)
# ===========================================

class PlaceOrderRequest(BaseModel):
    connection_id: str
    symbol: str
    side: str  # BUY or SELL
    order_type: str = "MARKET"  # MARKET, LIMIT
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"
    reduce_only: bool = False
    client_tag: Optional[str] = None


class CancelOrderRequest(BaseModel):
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None


@router.get("/orders/health")
async def orders_health():
    """OMS health check"""
    from ..orders import order_service
    return order_service.get_health()


@router.post("/orders/place")
async def place_order_endpoint(request: PlaceOrderRequest):
    """
    Place a new order.
    
    Request body:
        {
            "connection_id": "...",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 0.01
        }
    """
    from ..orders import order_service
    from ..orders.order_types import OrderSide, OrderType, TimeInForce
    
    # Check kill switch
    if _capsule_state.kill_switch_active:
        raise HTTPException(
            status_code=400,
            detail="Kill switch is active. Cannot place orders."
        )
    
    if _capsule_state.paused:
        raise HTTPException(
            status_code=400,
            detail="Trading is paused. Cannot place orders."
        )
    
    try:
        side = OrderSide(request.side.upper())
        order_type = OrderType(request.order_type.upper())
        tif = TimeInForce(request.time_in_force.upper())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    order = await order_service.place_order(
        connection_id=request.connection_id,
        symbol=request.symbol,
        side=side,
        order_type=order_type,
        quantity=request.quantity,
        price=request.price,
        stop_price=request.stop_price,
        time_in_force=tif,
        reduce_only=request.reduce_only,
        client_tag=request.client_tag
    )
    
    return {
        "success": order.status.value not in ["REJECTED", "FAILED"],
        "order": order.to_dict()
    }


@router.post("/orders/cancel")
async def cancel_order_endpoint(request: CancelOrderRequest):
    """Cancel an order"""
    from ..orders import order_service
    
    if not request.order_id and not request.client_order_id:
        raise HTTPException(
            status_code=400,
            detail="Either order_id or client_order_id required"
        )
    
    try:
        order = await order_service.cancel_order(
            order_id=request.order_id,
            client_order_id=request.client_order_id
        )
        return {
            "success": True,
            "order": order.to_dict()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/orders/cancel-all")
async def cancel_all_orders_endpoint(
    connection_id: Optional[str] = None,
    symbol: Optional[str] = None
):
    """Cancel all active orders"""
    from ..orders import order_service
    
    cancelled = await order_service.cancel_all_orders(connection_id, symbol)
    
    return {
        "success": True,
        "cancelled": [o.to_dict() for o in cancelled],
        "count": len(cancelled)
    }


@router.get("/orders")
async def get_orders_endpoint(
    connection_id: Optional[str] = None,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """Get orders with filters"""
    from ..orders import order_service
    from ..orders.order_types import OrderStatus
    
    order_status = None
    if status:
        try:
            order_status = OrderStatus(status.upper())
        except ValueError:
            pass
    
    orders = order_service.get_orders(
        connection_id=connection_id,
        symbol=symbol,
        status=order_status,
        limit=limit
    )
    
    return {
        "orders": [o.to_dict() for o in orders],
        "count": len(orders)
    }


@router.get("/orders/active")
async def get_active_orders_endpoint(connection_id: Optional[str] = None):
    """Get all active orders"""
    from ..orders import order_service
    
    orders = order_service.get_active_orders(connection_id)
    
    return {
        "orders": [o.to_dict() for o in orders],
        "count": len(orders)
    }


@router.get("/orders/{order_id}")
async def get_order_endpoint(order_id: str):
    """Get order by ID"""
    from ..orders import order_service
    
    order = order_service.get_order(order_id=order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return order.to_dict()


# ===========================================
# Fills (T2 OMS)
# ===========================================

@router.get("/fills")
async def get_fills_endpoint(
    order_id: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """Get fills with filters"""
    from ..orders import order_service
    
    fills = order_service.get_fills(
        order_id=order_id,
        symbol=symbol,
        limit=limit
    )
    
    return {
        "fills": [f.to_dict() for f in fills],
        "count": len(fills)
    }


# ===========================================
# Trades (T2 OMS)
# ===========================================

@router.get("/trades")
async def get_trades_endpoint(
    connection_id: Optional[str] = None,
    symbol: Optional[str] = None,
    is_open: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """Get trades with filters"""
    from ..orders import order_service
    
    trades = order_service.get_trades(
        connection_id=connection_id,
        symbol=symbol,
        is_open=is_open,
        limit=limit
    )
    
    return {
        "trades": [t.to_dict() for t in trades],
        "count": len(trades)
    }


@router.get("/trades/open")
async def get_open_trades_endpoint():
    """Get all open trades"""
    from ..orders import order_service
    
    trades = order_service.get_open_trades()
    
    return {
        "trades": [t.to_dict() for t in trades],
        "count": len(trades)
    }


@router.get("/trades/{trade_id}")
async def get_trade_endpoint(trade_id: str):
    """Get trade by ID"""
    from ..orders import order_service
    
    trade = order_service.get_trade(trade_id)
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    return trade.to_dict()


@router.get("/stats")
async def get_trading_stats():
    """Get trading statistics"""
    from ..orders import order_service
    
    return {
        "oms": order_service.get_stats(),
        "capsule": _capsule_state.to_dict(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ===========================================
# Execution Layer (T3)
# ===========================================

class TASignalRequest(BaseModel):
    """TA signal payload"""
    asset: str
    bias: str  # BULLISH, BEARISH, NEUTRAL
    confidence: float = 0.5
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    patterns: Optional[List[str]] = None


class ManualSignalRequest(BaseModel):
    """Manual signal payload"""
    asset: str
    action: str  # ENTER_LONG, EXIT_LONG, ENTER_SHORT, EXIT_SHORT, ADD_TO_LONG, ADD_TO_SHORT, HOLD
    confidence: float = 1.0
    size_pct: Optional[float] = None
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: Optional[str] = None
    market_type: str = "SPOT"
    horizon: str = "1D"


class ExecuteDecisionRequest(BaseModel):
    """Execute decision request"""
    connection_id: str
    decision_id: Optional[str] = None
    ta_signal: Optional[TASignalRequest] = None
    manual_signal: Optional[ManualSignalRequest] = None
    skip_risk_check: bool = False


class PreviewDecisionRequest(BaseModel):
    """Preview decision request"""
    connection_id: str
    ta_signal: Optional[TASignalRequest] = None
    manual_signal: Optional[ManualSignalRequest] = None


@router.get("/execution/health")
async def execution_health():
    """Execution layer health check"""
    from ..execution import execution_service
    return execution_service.get_health()


@router.post("/execution/signal/ta")
async def submit_ta_signal(request: TASignalRequest):
    """
    Submit TA signal for normalization.
    
    Returns normalized ExecutionDecision.
    """
    from ..execution import execution_service
    
    payload = {
        "asset": request.asset,
        "bias": request.bias,
        "confidence": request.confidence,
        "entry_price": request.entry_price,
        "stop_loss": request.stop_loss,
        "take_profit": request.take_profit,
        "patterns": request.patterns or []
    }
    
    decision = execution_service.normalize_ta_signal(payload)
    
    return {
        "success": True,
        "decision": decision.to_dict()
    }


@router.post("/execution/signal/manual")
async def submit_manual_signal(request: ManualSignalRequest):
    """
    Submit manual signal for normalization.
    
    Returns normalized ExecutionDecision.
    """
    from ..execution import execution_service
    
    payload = {
        "asset": request.asset,
        "action": request.action,
        "confidence": request.confidence,
        "size_pct": request.size_pct,
        "price": request.price,
        "stop_loss": request.stop_loss,
        "take_profit": request.take_profit,
        "reason": request.reason,
        "market_type": request.market_type,
        "horizon": request.horizon
    }
    
    decision = execution_service.normalize_manual_signal(payload)
    
    return {
        "success": True,
        "decision": decision.to_dict()
    }


@router.post("/execution/preview")
async def preview_execution(request: PreviewDecisionRequest):
    """
    Preview execution without actually executing.
    
    Shows what would happen: decision → intent → risk checks.
    """
    from ..execution import execution_service
    
    # Normalize signal
    if request.ta_signal:
        payload = {
            "asset": request.ta_signal.asset,
            "bias": request.ta_signal.bias,
            "confidence": request.ta_signal.confidence,
            "entry_price": request.ta_signal.entry_price,
            "stop_loss": request.ta_signal.stop_loss,
            "take_profit": request.ta_signal.take_profit,
            "patterns": request.ta_signal.patterns or []
        }
        decision = execution_service.normalize_ta_signal(payload)
    elif request.manual_signal:
        payload = {
            "asset": request.manual_signal.asset,
            "action": request.manual_signal.action,
            "confidence": request.manual_signal.confidence,
            "size_pct": request.manual_signal.size_pct,
            "price": request.manual_signal.price,
            "stop_loss": request.manual_signal.stop_loss,
            "take_profit": request.manual_signal.take_profit,
            "reason": request.manual_signal.reason,
            "market_type": request.manual_signal.market_type,
            "horizon": request.manual_signal.horizon
        }
        decision = execution_service.normalize_manual_signal(payload)
    else:
        raise HTTPException(status_code=400, detail="Either ta_signal or manual_signal required")
    
    # Preview
    preview = await execution_service.preview(decision, request.connection_id)
    
    return preview.to_dict()


@router.post("/execution/execute")
async def execute_decision(request: ExecuteDecisionRequest):
    """
    Execute a trading decision.
    
    Full pipeline: decision → risk check → intent → OMS.
    """
    from ..execution import execution_service
    
    # Check kill switch
    if _capsule_state.kill_switch_active:
        raise HTTPException(
            status_code=400,
            detail="Kill switch is active. Cannot execute."
        )
    
    if _capsule_state.paused:
        raise HTTPException(
            status_code=400,
            detail="Trading is paused. Cannot execute."
        )
    
    # Get or create decision
    if request.decision_id:
        decision = execution_service.get_decision(request.decision_id)
        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")
    elif request.ta_signal:
        payload = {
            "asset": request.ta_signal.asset,
            "bias": request.ta_signal.bias,
            "confidence": request.ta_signal.confidence,
            "entry_price": request.ta_signal.entry_price,
            "stop_loss": request.ta_signal.stop_loss,
            "take_profit": request.ta_signal.take_profit,
            "patterns": request.ta_signal.patterns or []
        }
        decision = execution_service.normalize_ta_signal(payload)
    elif request.manual_signal:
        payload = {
            "asset": request.manual_signal.asset,
            "action": request.manual_signal.action,
            "confidence": request.manual_signal.confidence,
            "size_pct": request.manual_signal.size_pct,
            "price": request.manual_signal.price,
            "stop_loss": request.manual_signal.stop_loss,
            "take_profit": request.manual_signal.take_profit,
            "reason": request.manual_signal.reason,
            "market_type": request.manual_signal.market_type,
            "horizon": request.manual_signal.horizon
        }
        decision = execution_service.normalize_manual_signal(payload)
    else:
        raise HTTPException(
            status_code=400,
            detail="Either decision_id, ta_signal, or manual_signal required"
        )
    
    # Execute
    result = await execution_service.execute(
        decision,
        request.connection_id,
        skip_risk_check=request.skip_risk_check
    )
    
    return result.to_dict()


@router.get("/execution/decisions")
async def get_decisions(limit: int = Query(50, ge=1, le=200)):
    """Get recent execution decisions"""
    from ..execution import execution_service
    
    decisions = execution_service.get_decisions(limit)
    
    return {
        "decisions": [d.to_dict() for d in decisions],
        "count": len(decisions)
    }


@router.get("/execution/decisions/{decision_id}")
async def get_decision(decision_id: str):
    """Get decision by ID"""
    from ..execution import execution_service
    
    decision = execution_service.get_decision(decision_id)
    
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    return decision.to_dict()


@router.get("/execution/results")
async def get_execution_results(limit: int = Query(50, ge=1, le=200)):
    """Get recent execution results"""
    from ..execution import execution_service
    
    results = execution_service.get_results(limit)
    
    return {
        "results": [r.to_dict() for r in results],
        "count": len(results)
    }


# ===========================================
# Risk Layer (T4)
# ===========================================

class RiskProfileUpdateRequest(BaseModel):
    """Risk profile update request"""
    max_position_usd: Optional[float] = None
    max_asset_exposure_pct: Optional[float] = None
    max_portfolio_exposure_pct: Optional[float] = None
    max_open_positions: Optional[int] = None
    max_orders_per_asset: Optional[int] = None
    max_daily_drawdown_pct: Optional[float] = None
    spot_enabled: Optional[bool] = None
    futures_enabled: Optional[bool] = None
    short_allowed: Optional[bool] = None
    leverage_allowed: Optional[bool] = None
    max_leverage: Optional[float] = None
    averaging_enabled: Optional[bool] = None
    max_averaging_steps: Optional[int] = None
    max_averaging_capital_pct: Optional[float] = None
    averaging_step_multiplier: Optional[float] = None
    averaging_min_price_drop_pct: Optional[float] = None
    emergency_stop_enabled: Optional[bool] = None


class RiskCheckRequest(BaseModel):
    """Risk check request"""
    connection_id: str
    asset: str
    side: str  # BUY or SELL
    notional_usd: float
    quantity: float = 0.0
    price: Optional[float] = None
    reduce_only: bool = False
    market_type: str = "SPOT"


class AveragingEntryRequest(BaseModel):
    """Add averaging entry"""
    connection_id: str
    asset: str
    entry_price: float
    quantity: float
    notional_usd: float


class UpdatePriceRequest(BaseModel):
    """Update current price for averaging"""
    connection_id: str
    asset: str
    price: float


class RecordPnLRequest(BaseModel):
    """Record PnL"""
    connection_id: str
    pnl: float


@router.get("/risk/health")
async def risk_health():
    """Risk layer health check"""
    from ..risk import risk_service
    return risk_service.get_health()


@router.get("/risk/profile/full")
async def get_full_risk_profile():
    """Get full risk profile with all parameters"""
    from ..risk import risk_service
    return risk_service.get_profile().to_dict()


@router.post("/risk/profile/update")
async def update_full_risk_profile(request: RiskProfileUpdateRequest):
    """Update risk profile parameters"""
    from ..risk import risk_service
    
    updates = request.model_dump(exclude_none=True)
    profile = risk_service.update_profile(updates)
    
    return {
        "success": True,
        "profile": profile.to_dict()
    }


@router.post("/risk/check")
async def check_risk(request: RiskCheckRequest):
    """
    Run pre-trade risk check.
    
    Returns risk verdict with allowed/blocked status.
    """
    from ..risk import risk_service
    from ..execution.execution_types import OrderIntent
    
    # Build order intent for risk check
    intent = OrderIntent(
        connection_id=request.connection_id,
        asset=request.asset,
        symbol=f"{request.asset}USDT",
        side=request.side,
        order_type="MARKET",
        quantity=request.quantity,
        notional_usd=request.notional_usd,
        price=request.price,
        reduce_only=request.reduce_only
    )
    
    # Build context
    context = await risk_service.build_context(
        request.connection_id,
        request.asset,
        request.market_type
    )
    
    # Evaluate
    verdict = await risk_service.evaluate(intent, context)
    
    return {
        "verdict": verdict.to_dict(),
        "context": context.to_dict()
    }


@router.get("/risk/context/{connection_id}")
async def get_risk_context(connection_id: str, asset: str = "BTC"):
    """Get current risk context"""
    from ..risk import risk_service
    
    context = await risk_service.build_context(connection_id, asset)
    
    return context.to_dict()


@router.get("/risk/events")
async def get_risk_events(limit: int = Query(100, ge=1, le=500)):
    """Get recent risk events"""
    from ..risk import risk_service
    
    events = risk_service.get_risk_events(limit)
    
    return {
        "events": events,
        "count": len(events)
    }


# ===========================================
# Averaging Management (T4)
# ===========================================

@router.get("/risk/averaging/{connection_id}/{asset}")
async def get_averaging_state(connection_id: str, asset: str):
    """Get averaging state for asset"""
    from ..risk import risk_service
    
    state = risk_service.get_averaging_state(connection_id, asset)
    
    if not state:
        return {
            "asset": asset,
            "connection_id": connection_id,
            "active": False,
            "message": "No averaging state"
        }
    
    return state.to_dict()


@router.post("/risk/averaging/start")
async def start_averaging_ladder(request: AveragingEntryRequest):
    """Start averaging ladder for asset"""
    from ..risk import risk_service
    
    state = risk_service.start_averaging(
        request.connection_id,
        request.asset,
        request.entry_price,
        request.quantity,
        request.notional_usd
    )
    
    return {
        "success": True,
        "state": state.to_dict()
    }


@router.post("/risk/averaging/add")
async def add_averaging_entry(request: AveragingEntryRequest):
    """Add entry to averaging ladder"""
    from ..risk import risk_service
    
    state = risk_service.add_averaging_entry(
        request.connection_id,
        request.asset,
        request.entry_price,
        request.quantity,
        request.notional_usd
    )
    
    if not state:
        raise HTTPException(status_code=400, detail="Failed to add averaging entry")
    
    return {
        "success": True,
        "state": state.to_dict()
    }


@router.post("/risk/averaging/reset")
async def reset_averaging_ladder(connection_id: str, asset: str):
    """Reset averaging state"""
    from ..risk import risk_service
    
    risk_service.reset_averaging(connection_id, asset)
    
    return {
        "success": True,
        "message": f"Averaging reset for {asset}"
    }


@router.post("/risk/averaging/update-price")
async def update_averaging_price(request: UpdatePriceRequest):
    """Update current price for averaging calculations"""
    from ..risk import risk_service
    
    risk_service.update_current_price(
        request.connection_id,
        request.asset,
        request.price
    )
    
    return {
        "success": True,
        "message": f"Price updated for {request.asset}"
    }


# ===========================================
# Daily PnL Tracking (T4)
# ===========================================

@router.get("/risk/pnl/{connection_id}")
async def get_daily_pnl(connection_id: str):
    """Get daily PnL for connection"""
    from ..risk import risk_service
    
    pnl = risk_service.get_daily_pnl(connection_id)
    
    return {
        "connection_id": connection_id,
        "daily_pnl_usd": round(pnl, 2),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
    }


@router.post("/risk/pnl/record")
async def record_pnl(request: RecordPnLRequest):
    """Record PnL for daily tracking"""
    from ..risk import risk_service
    
    risk_service.record_pnl(request.connection_id, request.pnl)
    
    return {
        "success": True,
        "message": f"Recorded PnL: {request.pnl}"
    }


# ===========================================
# Include Terminal Router (T5)
# ===========================================

from ..terminal.terminal_routes import router as terminal_router
router.include_router(terminal_router)


# ===========================================
# Include Strategy Router (T6)
# ===========================================

from ..strategy.strategy_routes import router as strategy_router
router.include_router(strategy_router)


# ===========================================
# Include Simulation Router (S1)
# ===========================================

from ..simulation.simulation_routes import router as simulation_router
router.include_router(simulation_router)
