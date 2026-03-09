"""
Market Reality Layer Module
===========================

Realistic market simulation for strategy validation.

This layer models:
- Order book dynamics
- Slippage (volume-based, volatility-based, impact model)
- Latency simulation
- Partial fills and rejections
- Market impact
- Gap events

This is what separates backtest results from live trading reality.

Usage:
    from modules.market_reality import market_reality_engine, SimulatedOrder, OrderSide, OrderType
    
    # Execute an order
    order = SimulatedOrder.create(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        size=1.0
    )
    
    fill = market_reality_engine.simulate_execution(
        order=order,
        current_price=50000,
        current_volume=1000,
        volatility=0.02
    )
    
    print(f"Filled at {fill.filled_price} with {fill.slippage_bps} bps slippage")
"""

from .types import (
    OrderType,
    OrderSide,
    FillStatus,
    SlippageModel,
    OrderBookLevel,
    OrderBook,
    SimulatedOrder,
    Fill,
    MarketImpactResult,
    GapEvent,
    RealityConfig,
    RealityMetrics
)

from .engine import MarketRealityEngine, market_reality_engine

from .routes import router


__all__ = [
    # Types
    "OrderType",
    "OrderSide",
    "FillStatus",
    "SlippageModel",
    "OrderBookLevel",
    "OrderBook",
    "SimulatedOrder",
    "Fill",
    "MarketImpactResult",
    "GapEvent",
    "RealityConfig",
    "RealityMetrics",
    
    # Engine
    "MarketRealityEngine",
    "market_reality_engine",
    
    # Router
    "router"
]


print("[MarketReality] Module loaded")
