"""
Order Management System (T2)
============================

Order lifecycle management for Trading Capsule.

Provides:
- Order creation and placement
- Order cancellation
- Order tracking
- Fill tracking
- Trade history
- Order normalization across exchanges
"""

from .order_types import (
    Order,
    OrderStatus,
    OrderType,
    Fill,
    Trade,
    OrderPrecision,
    OrderValidationResult
)

from .order_service import (
    order_service,
    OrderService,
    place_order,
    cancel_order,
    get_order,
    get_orders,
    get_fills,
    get_trades
)


__all__ = [
    # Types
    "Order",
    "OrderStatus",
    "OrderType",
    "Fill",
    "Trade",
    "OrderPrecision",
    "OrderValidationResult",
    
    # Service
    "order_service",
    "OrderService",
    "place_order",
    "cancel_order",
    "get_order",
    "get_orders",
    "get_fills",
    "get_trades"
]
