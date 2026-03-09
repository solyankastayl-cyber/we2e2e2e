"""
Trading Capsule Module
======================

Isolated trading capsule ready for merge into master platform.

Phase T0: Capsule Contract & Boundaries
Phase T1: Broker / Account Layer
Phase T2: Order Management System
Phase T3: Execution Decision Layer
Phase T4: Risk Control Layer
Phase T5: Terminal Backend for Admin
Phase T6: Strategy Logic Layer
Phase T7: Merge-Ready Integration Contracts

Execution Modes:
- TA_ONLY: Trade based on TA signals only
- MANUAL_SIGNAL_SOURCE: Accept external signal payload
- MBRAIN_ROUTED: Later - receive decisions from global M-Brain

Trading Modes:
- SPOT: Primary mode
- FUTURES: Optional, secondary mode

IMPORTANT: This capsule does NOT include:
- User-facing analytics
- Global UI
- 5-module orchestration logic
- Global M-Brain
- Public user layer
"""

from .trading_types import (
    # Enums
    Exchange,
    MarketMode,
    ExecutionMode,
    ConnectionStatus,
    ConnectionHealth,
    OrderSide,
    PositionSide,
    
    # Core entities
    ExchangeConnection,
    AccountCredentialsRef,
    AccountState,
    AssetBalance,
    PositionSummary,
    ConnectionHealthRecord,
    ConnectionValidationResult,
    
    # Trading entities
    TradeIntent,
    OrderIntent,
    TradingRiskProfile
)

from .broker import (
    BrokerAdapter,
    BrokerRegistry,
    broker_registry,
    get_connection,
    list_connections
)

from .routes.trading_routes import router


__all__ = [
    # Enums
    "Exchange",
    "MarketMode",
    "ExecutionMode",
    "ConnectionStatus",
    "ConnectionHealth",
    "OrderSide",
    "PositionSide",
    
    # Core entities
    "ExchangeConnection",
    "AccountCredentialsRef",
    "AccountState",
    "AssetBalance",
    "PositionSummary",
    "ConnectionHealthRecord",
    "ConnectionValidationResult",
    "TradeIntent",
    "OrderIntent",
    "TradingRiskProfile",
    
    # Broker
    "BrokerAdapter",
    "BrokerRegistry",
    "broker_registry",
    "get_connection",
    "list_connections",
    
    # Router
    "router"
]


print("[TradingCapsule] Module loaded - T0/T1 Ready")
