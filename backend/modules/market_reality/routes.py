"""
Market Reality Layer API Routes
===============================

REST API for Market Reality simulation.

Endpoints:
- GET  /api/reality/health         - Health check
- POST /api/reality/execute        - Execute single order
- POST /api/reality/batch          - Execute batch of orders
- GET  /api/reality/fills          - List fills
- GET  /api/reality/fill/{id}      - Get fill by ID
- GET  /api/reality/metrics        - Get metrics
- POST /api/reality/orderbook      - Generate order book
- GET  /api/reality/orderbook/{symbol} - Get order book
- GET  /api/reality/gaps           - Get gap events
- GET  /api/reality/config         - Get config
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .engine import market_reality_engine
from .types import (
    OrderType, OrderSide, SimulatedOrder,
    SlippageModel, RealityConfig
)


router = APIRouter(prefix="/api/reality", tags=["Market Reality"])


# Request models

class ExecuteOrderRequest(BaseModel):
    """Request to execute an order"""
    symbol: str = "BTCUSDT"
    side: str = "BUY"
    order_type: str = "MARKET"
    size: float = 1.0
    price: Optional[float] = None
    current_price: float
    current_volume: float = 1000.0
    volatility: float = 0.02


class BatchExecuteRequest(BaseModel):
    """Request to execute batch of orders"""
    trades: List[Dict[str, Any]]
    prices: List[float]
    volumes: List[float]


class GenerateOrderBookRequest(BaseModel):
    """Request to generate order book"""
    symbol: str
    mid_price: float
    spread_bps: float = 5.0
    depth_levels: int = 10


class ConfigUpdateRequest(BaseModel):
    """Request to update config"""
    slippage_model: Optional[str] = None
    base_slippage_bps: Optional[float] = None
    base_latency_ms: Optional[float] = None
    limit_fill_probability: Optional[float] = None
    gap_probability: Optional[float] = None


# Endpoints

@router.get("/health")
async def reality_health():
    """Market Reality Layer health check"""
    return market_reality_engine.get_health()


@router.post("/execute")
async def execute_order(request: ExecuteOrderRequest):
    """
    Execute a single order with realistic simulation.
    
    Returns fill with slippage, latency, and impact.
    """
    order = SimulatedOrder.create(
        symbol=request.symbol,
        side=OrderSide(request.side),
        order_type=OrderType(request.order_type),
        size=request.size,
        price=request.price
    )
    
    fill = market_reality_engine.simulate_execution(
        order=order,
        current_price=request.current_price,
        current_volume=request.current_volume,
        volatility=request.volatility
    )
    
    return {
        "success": fill.status.value != "REJECTED",
        "order": order.to_dict(),
        "fill": fill.to_dict()
    }


@router.post("/batch")
async def execute_batch(request: BatchExecuteRequest):
    """
    Execute a batch of orders.
    
    Returns summary of all executions.
    """
    result = market_reality_engine.simulate_trade_series(
        trades=request.trades,
        prices=request.prices,
        volumes=request.volumes
    )
    
    return result


@router.get("/fills")
async def list_fills(limit: int = Query(50, ge=1, le=200)):
    """List recent fills"""
    fills = market_reality_engine.get_recent_fills(limit)
    
    return {
        "fills": [f.to_dict() for f in fills],
        "count": len(fills)
    }


@router.get("/fill/{fill_id}")
async def get_fill(fill_id: str):
    """Get fill by ID"""
    fill = market_reality_engine.get_fill(fill_id)
    
    if not fill:
        raise HTTPException(status_code=404, detail=f"Fill not found: {fill_id}")
    
    return fill.to_dict()


@router.get("/metrics")
async def get_metrics():
    """Get execution metrics"""
    return market_reality_engine.get_metrics().to_dict()


@router.post("/metrics/reset")
async def reset_metrics():
    """Reset metrics"""
    market_reality_engine.reset_metrics()
    return {"success": True, "message": "Metrics reset"}


@router.post("/orderbook")
async def generate_orderbook(request: GenerateOrderBookRequest):
    """Generate a simulated order book"""
    order_book = market_reality_engine.generate_order_book(
        symbol=request.symbol,
        mid_price=request.mid_price,
        spread_bps=request.spread_bps,
        depth_levels=request.depth_levels
    )
    
    return order_book.to_dict()


@router.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str):
    """Get order book for symbol"""
    order_book = market_reality_engine.get_order_book(symbol)
    
    if not order_book:
        raise HTTPException(status_code=404, detail=f"Order book not found: {symbol}")
    
    return order_book.to_dict()


@router.get("/gaps")
async def get_gap_events(limit: int = Query(20, ge=1, le=100)):
    """Get recent gap events"""
    gaps = market_reality_engine.get_gap_events(limit)
    
    return {
        "gaps": [g.to_dict() for g in gaps],
        "count": len(gaps)
    }


@router.post("/gap/simulate")
async def simulate_gap(symbol: str = "BTCUSDT", current_price: float = 50000):
    """Simulate a random gap event"""
    gap = market_reality_engine.simulate_gap(symbol, current_price)
    
    if gap:
        return {"gap_occurred": True, "gap": gap.to_dict()}
    return {"gap_occurred": False}


@router.get("/config")
async def get_config():
    """Get current configuration"""
    return market_reality_engine.config.to_dict()


@router.patch("/config")
async def update_config(request: ConfigUpdateRequest):
    """Update configuration"""
    config = market_reality_engine.config
    
    if request.slippage_model:
        config.slippage_model = SlippageModel(request.slippage_model)
    if request.base_slippage_bps is not None:
        config.base_slippage_bps = request.base_slippage_bps
    if request.base_latency_ms is not None:
        config.base_latency_ms = request.base_latency_ms
    if request.limit_fill_probability is not None:
        config.limit_fill_probability = request.limit_fill_probability
    if request.gap_probability is not None:
        config.gap_probability = request.gap_probability
    
    return {
        "success": True,
        "config": config.to_dict()
    }


@router.get("/slippage-models")
async def list_slippage_models():
    """List available slippage models"""
    return {
        "models": [
            {
                "id": model.value,
                "description": {
                    "FIXED": "Fixed percentage slippage",
                    "VOLUME_BASED": "Slippage increases with order size vs volume",
                    "VOLATILITY_BASED": "Slippage increases with volatility",
                    "IMPACT_MODEL": "Square root market impact model"
                }.get(model.value, "")
            }
            for model in SlippageModel
        ]
    }
