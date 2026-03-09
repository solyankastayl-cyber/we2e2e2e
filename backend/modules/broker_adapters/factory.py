"""
Broker Factory
==============

Factory pattern for creating broker adapters.
"""

from typing import Dict, Any, Optional, Type

from .base_adapter import BaseBrokerAdapter, BrokerCredentials
from .mock_adapter import MockAdapter
from .binance_adapter import BinanceAdapter
from .bybit_adapter import BybitAdapter


# Registry of available adapters
ADAPTER_REGISTRY: Dict[str, Type[BaseBrokerAdapter]] = {
    "mock": MockAdapter,
    "binance": BinanceAdapter,
    "binance_spot": BinanceAdapter,
    "binance_futures": BinanceAdapter,
    "bybit": BybitAdapter,
    "bybit_spot": BybitAdapter,
    "bybit_linear": BybitAdapter,
    "bybit_inverse": BybitAdapter
}


class BrokerFactory:
    """
    Factory for creating broker adapters.
    
    Usage:
        adapter = BrokerFactory.create("binance", {
            "api_key": "...",
            "api_secret": "...",
            "testnet": True
        })
    """
    
    @staticmethod
    def create(
        broker: str,
        credentials: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> BaseBrokerAdapter:
        """
        Create a broker adapter.
        
        Args:
            broker: Broker identifier (e.g., "binance", "bybit", "mock")
            credentials: Dict with api_key, api_secret, etc.
            **kwargs: Additional adapter-specific arguments
            
        Returns:
            Configured broker adapter
            
        Raises:
            ValueError: If broker is not supported
        """
        broker_lower = broker.lower()
        
        if broker_lower not in ADAPTER_REGISTRY:
            raise ValueError(
                f"Unsupported broker: {broker}. "
                f"Available: {list(ADAPTER_REGISTRY.keys())}"
            )
        
        # Build credentials
        credentials = credentials or {}
        creds = BrokerCredentials(
            api_key=credentials.get("api_key", "mock_key"),
            api_secret=credentials.get("api_secret", "mock_secret"),
            passphrase=credentials.get("passphrase"),
            testnet=credentials.get("testnet", False)
        )
        
        adapter_class = ADAPTER_REGISTRY[broker_lower]
        
        # Handle broker-specific options
        if broker_lower == "mock":
            initial_balance = kwargs.get("initial_balance", 100000.0)
            return MockAdapter(creds, initial_balance=initial_balance)
        
        elif broker_lower in ["binance", "binance_spot"]:
            return BinanceAdapter(creds, use_futures=False)
        
        elif broker_lower == "binance_futures":
            return BinanceAdapter(creds, use_futures=True)
        
        elif broker_lower in ["bybit", "bybit_linear"]:
            return BybitAdapter(creds, category="linear")
        
        elif broker_lower == "bybit_spot":
            return BybitAdapter(creds, category="spot")
        
        elif broker_lower == "bybit_inverse":
            return BybitAdapter(creds, category="inverse")
        
        # Default instantiation
        return adapter_class(creds, **kwargs)
    
    @staticmethod
    def list_brokers() -> Dict[str, Dict[str, Any]]:
        """
        List available brokers and their capabilities.
        
        Returns:
            Dict of broker info
        """
        return {
            "mock": {
                "description": "Mock adapter for testing",
                "supports_futures": True,
                "supports_margin": True,
                "testnet_available": False,
                "requires_credentials": False
            },
            "binance_spot": {
                "description": "Binance Spot trading",
                "supports_futures": False,
                "supports_margin": True,
                "testnet_available": True,
                "requires_credentials": True
            },
            "binance_futures": {
                "description": "Binance USDT-M Futures",
                "supports_futures": True,
                "supports_margin": True,
                "testnet_available": True,
                "requires_credentials": True
            },
            "bybit_spot": {
                "description": "Bybit Spot trading",
                "supports_futures": False,
                "supports_margin": True,
                "testnet_available": True,
                "requires_credentials": True
            },
            "bybit_linear": {
                "description": "Bybit Linear Perpetuals (USDT)",
                "supports_futures": True,
                "supports_margin": True,
                "testnet_available": True,
                "requires_credentials": True
            },
            "bybit_inverse": {
                "description": "Bybit Inverse Perpetuals",
                "supports_futures": True,
                "supports_margin": True,
                "testnet_available": True,
                "requires_credentials": True
            }
        }


# Singleton adapter instances
_active_adapters: Dict[str, BaseBrokerAdapter] = {}


def get_adapter(broker: str) -> Optional[BaseBrokerAdapter]:
    """
    Get an existing adapter instance.
    
    Args:
        broker: Broker identifier
        
    Returns:
        Adapter instance or None if not initialized
    """
    return _active_adapters.get(broker.lower())


def set_adapter(broker: str, adapter: BaseBrokerAdapter):
    """
    Register an adapter instance.
    
    Args:
        broker: Broker identifier
        adapter: Adapter instance
    """
    _active_adapters[broker.lower()] = adapter


def remove_adapter(broker: str):
    """
    Remove an adapter instance.
    
    Args:
        broker: Broker identifier
    """
    if broker.lower() in _active_adapters:
        del _active_adapters[broker.lower()]


def list_active_adapters() -> Dict[str, Dict[str, Any]]:
    """
    List all active adapter instances.
    
    Returns:
        Dict of adapter statuses
    """
    return {
        broker: adapter.get_status()
        for broker, adapter in _active_adapters.items()
    }
