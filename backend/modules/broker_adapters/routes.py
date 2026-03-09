"""
Broker Adapters API Routes
==========================

REST API for broker operations.

Endpoints:
- GET  /api/broker/health              - Module health
- GET  /api/broker/list                - List available brokers
- GET  /api/broker/active              - List active connections
- POST /api/broker/connect             - Connect to broker
- POST /api/broker/disconnect          - Disconnect from broker
- GET  /api/broker/status              - Get connection status
- GET  /api/broker/balance             - Get account balance
- GET  /api/broker/positions           - Get open positions
- GET  /api/broker/ticker/{symbol}     - Get ticker
- GET  /api/broker/tickers             - Get multiple tickers
- POST /api/broker/order               - Place order
- DELETE /api/broker/order             - Cancel order
- GET  /api/broker/orders              - Get orders
- DELETE /api/broker/orders            - Cancel all orders
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from .factory import (
    BrokerFactory,
    get_adapter,
    set_adapter,
    remove_adapter,
    list_active_adapters
)
from .base_adapter import (
    BrokerCredentials,
    OrderSide,
    OrderType,
    OrderStatus,
    TimeInForce,
    BrokerError,
    ConnectionError as BrokerConnectionError,
    AuthenticationError,
    OrderError,
    InsufficientFundsError
)


router = APIRouter(prefix="/api/broker", tags=["Broker Adapters"])


# ===========================================
# Request Models
# ===========================================

class ConnectRequest(BaseModel):
    broker: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    passphrase: Optional[str] = None
    testnet: bool = True
    initial_balance: float = 100000.0  # For mock


class OrderRequest(BaseModel):
    broker: str
    symbol: str
    side: str  # BUY or SELL
    order_type: str = "MARKET"  # MARKET, LIMIT
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"
    client_order_id: Optional[str] = None


class CancelOrderRequest(BaseModel):
    broker: str
    symbol: str
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None


# ===========================================
# Health & Info
# ===========================================

@router.get("/health")
async def broker_health():
    """Module health check"""
    active = list_active_adapters()
    connected = sum(1 for a in active.values() if a.get("status") == "connected")
    
    return {
        "enabled": True,
        "version": "phase9.37",
        "status": "ok",
        "active_connections": len(active),
        "connected_count": connected,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/list")
async def list_brokers():
    """List available brokers and capabilities"""
    return {
        "brokers": BrokerFactory.list_brokers()
    }


@router.get("/active")
async def list_active():
    """List active broker connections"""
    return {
        "adapters": list_active_adapters()
    }


# ===========================================
# Connection Management
# ===========================================

@router.post("/connect")
async def connect_broker(request: ConnectRequest):
    """
    Connect to a broker.
    
    For testing, use mock broker with no credentials.
    For real brokers, provide api_key and api_secret.
    """
    try:
        # Check if already connected
        existing = get_adapter(request.broker)
        if existing and await existing.is_connected():
            return {
                "success": True,
                "message": f"Already connected to {request.broker}",
                "status": existing.get_status()
            }
        
        # Create adapter
        credentials = {
            "api_key": request.api_key or "mock_key",
            "api_secret": request.api_secret or "mock_secret",
            "passphrase": request.passphrase,
            "testnet": request.testnet
        }
        
        adapter = BrokerFactory.create(
            request.broker,
            credentials,
            initial_balance=request.initial_balance
        )
        
        # Connect
        await adapter.connect()
        
        # Register
        set_adapter(request.broker, adapter)
        
        return {
            "success": True,
            "message": f"Connected to {request.broker}",
            "status": adapter.get_status()
        }
        
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e.message}")
    except BrokerConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Connection failed: {e.message}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/disconnect")
async def disconnect_broker(broker: str):
    """Disconnect from a broker"""
    adapter = get_adapter(broker)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Broker not found: {broker}")
    
    await adapter.disconnect()
    remove_adapter(broker)
    
    return {
        "success": True,
        "message": f"Disconnected from {broker}"
    }


@router.get("/status")
async def broker_status(broker: str):
    """Get broker connection status"""
    adapter = get_adapter(broker)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Broker not found: {broker}")
    
    return adapter.get_status()


# ===========================================
# Account
# ===========================================

@router.get("/balance")
async def get_balance(broker: str, asset: Optional[str] = None):
    """Get account balance"""
    adapter = get_adapter(broker)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Broker not found: {broker}")
    
    if not await adapter.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    try:
        balances = await adapter.get_balance(asset)
        return {
            "broker": broker,
            "balances": [b.to_dict() for b in balances],
            "count": len(balances)
        }
    except BrokerError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/positions")
async def get_positions(broker: str, symbol: Optional[str] = None):
    """Get open positions"""
    adapter = get_adapter(broker)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Broker not found: {broker}")
    
    if not await adapter.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    try:
        positions = await adapter.get_positions(symbol)
        return {
            "broker": broker,
            "positions": [p.to_dict() for p in positions],
            "count": len(positions)
        }
    except BrokerError as e:
        raise HTTPException(status_code=400, detail=e.message)


# ===========================================
# Market Data
# ===========================================

@router.get("/ticker/{symbol}")
async def get_ticker(broker: str, symbol: str):
    """Get ticker for symbol"""
    adapter = get_adapter(broker)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Broker not found: {broker}")
    
    if not await adapter.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    try:
        ticker = await adapter.get_ticker(symbol)
        return ticker.to_dict()
    except BrokerError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/tickers")
async def get_tickers(
    broker: str,
    symbols: Optional[str] = Query(None, description="Comma-separated symbols")
):
    """Get multiple tickers"""
    adapter = get_adapter(broker)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Broker not found: {broker}")
    
    if not await adapter.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    try:
        symbol_list = symbols.split(",") if symbols else None
        tickers = await adapter.get_tickers(symbol_list)
        return {
            "broker": broker,
            "tickers": [t.to_dict() for t in tickers],
            "count": len(tickers)
        }
    except BrokerError as e:
        raise HTTPException(status_code=400, detail=e.message)


# ===========================================
# Orders
# ===========================================

@router.post("/order")
async def place_order(request: OrderRequest):
    """Place a new order"""
    adapter = get_adapter(request.broker)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Broker not found: {request.broker}")
    
    if not await adapter.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    try:
        # Parse enums
        side = OrderSide(request.side.upper())
        order_type = OrderType(request.order_type.upper())
        tif = TimeInForce(request.time_in_force.upper())
        
        order = await adapter.place_order(
            symbol=request.symbol,
            side=side,
            order_type=order_type,
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price,
            time_in_force=tif,
            client_order_id=request.client_order_id
        )
        
        return {
            "success": True,
            "order": order.to_dict()
        }
        
    except InsufficientFundsError as e:
        raise HTTPException(status_code=400, detail=f"Insufficient funds: {e.message}")
    except OrderError as e:
        raise HTTPException(status_code=400, detail=f"Order error: {e.message}")
    except BrokerError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.delete("/order")
async def cancel_order(request: CancelOrderRequest):
    """Cancel an order"""
    adapter = get_adapter(request.broker)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Broker not found: {request.broker}")
    
    if not await adapter.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    try:
        order = await adapter.cancel_order(
            symbol=request.symbol,
            order_id=request.order_id,
            client_order_id=request.client_order_id
        )
        
        return {
            "success": True,
            "order": order.to_dict()
        }
        
    except OrderError as e:
        raise HTTPException(status_code=400, detail=f"Cancel error: {e.message}")
    except BrokerError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/orders")
async def get_orders(
    broker: str,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """Get orders"""
    adapter = get_adapter(broker)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Broker not found: {broker}")
    
    if not await adapter.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    try:
        order_status = OrderStatus(status.upper()) if status else None
        orders = await adapter.get_orders(symbol, order_status, limit)
        
        return {
            "broker": broker,
            "orders": [o.to_dict() for o in orders],
            "count": len(orders)
        }
        
    except BrokerError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.delete("/orders")
async def cancel_all_orders(broker: str, symbol: Optional[str] = None):
    """Cancel all open orders"""
    adapter = get_adapter(broker)
    
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Broker not found: {broker}")
    
    if not await adapter.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    
    try:
        cancelled = await adapter.cancel_all_orders(symbol)
        
        return {
            "success": True,
            "cancelled": [o.to_dict() for o in cancelled],
            "count": len(cancelled)
        }
        
    except OrderError as e:
        raise HTTPException(status_code=400, detail=f"Cancel error: {e.message}")
    except BrokerError as e:
        raise HTTPException(status_code=400, detail=e.message)
