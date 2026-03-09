"""
Broker Layer (T1)
=================

Broker adapter abstraction and registry.

Provides:
- Unified BrokerAdapter interface
- Connection registry
- Account state management
- Health checks
"""

from .broker_base import BrokerAdapter
from .broker_registry import (
    BrokerRegistry,
    broker_registry,
    get_connection,
    list_connections,
    register_connection,
    remove_connection
)
from .broker_adapters import (
    MockBrokerAdapter,
    BinanceBrokerAdapter,
    BybitBrokerAdapter
)


__all__ = [
    "BrokerAdapter",
    "BrokerRegistry",
    "broker_registry",
    "get_connection",
    "list_connections",
    "register_connection",
    "remove_connection",
    "MockBrokerAdapter",
    "BinanceBrokerAdapter",
    "BybitBrokerAdapter"
]
