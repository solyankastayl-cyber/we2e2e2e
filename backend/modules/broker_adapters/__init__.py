"""
Broker Adapters Module (Phase 9.37)
===================================

Unified interface for broker connections.

Supported Brokers:
- Binance (Spot + Futures)
- Bybit (Spot + Derivatives)
- Alpaca (US Equities)
- IBKR (Multi-asset)

Usage:
    from modules.broker_adapters import BinanceAdapter, BrokerFactory
    
    # Direct instantiation
    adapter = BinanceAdapter(api_key="...", api_secret="...")
    await adapter.connect()
    balance = await adapter.get_balance()
    
    # Factory pattern
    adapter = BrokerFactory.create("binance", credentials={...})
"""

from .base_adapter import (
    BaseBrokerAdapter,
    BrokerCredentials,
    BrokerStatus,
    OrderSide,
    OrderType,
    OrderStatus,
    TimeInForce,
    Order,
    Position,
    Balance,
    Ticker,
    BrokerError,
    ConnectionError,
    AuthenticationError,
    OrderError,
    InsufficientFundsError
)

from .binance_adapter import BinanceAdapter
from .bybit_adapter import BybitAdapter
from .mock_adapter import MockAdapter
from .factory import BrokerFactory, get_adapter

from .routes import router


__all__ = [
    # Base
    "BaseBrokerAdapter",
    "BrokerCredentials",
    "BrokerStatus",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "TimeInForce",
    "Order",
    "Position",
    "Balance",
    "Ticker",
    
    # Errors
    "BrokerError",
    "ConnectionError",
    "AuthenticationError",
    "OrderError",
    "InsufficientFundsError",
    
    # Adapters
    "BinanceAdapter",
    "BybitAdapter",
    "MockAdapter",
    
    # Factory
    "BrokerFactory",
    "get_adapter",
    
    # Router
    "router"
]


print("[BrokerAdapters] Phase 9.37 Module loaded")
