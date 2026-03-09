"""
Broker Registry (T1)
====================

Registry for managing broker connections.

Provides:
- Connection registration
- Connection lifecycle management
- Adapter instantiation
"""

from typing import Dict, Optional, List, Any
from datetime import datetime, timezone
import asyncio

from ..trading_types import (
    Exchange,
    MarketMode,
    ConnectionStatus,
    ConnectionHealth,
    ExchangeConnection,
    AccountState,
    ConnectionValidationResult,
    ConnectionHealthRecord
)
from .broker_base import BrokerAdapter


class BrokerRegistry:
    """
    Registry for broker connections.
    
    Manages:
    - Connection registration
    - Adapter lifecycle
    - Connection state
    """
    
    def __init__(self):
        # Connection storage
        self._connections: Dict[str, ExchangeConnection] = {}
        
        # Active adapters
        self._adapters: Dict[str, BrokerAdapter] = {}
        
        # Credentials (stored separately, never exposed)
        self._credentials: Dict[str, Dict[str, str]] = {}
        
        # Health records
        self._health_records: Dict[str, ConnectionHealthRecord] = {}
        
        print("[BrokerRegistry] Initialized")
    
    # ===========================================
    # Connection Management
    # ===========================================
    
    def register_connection(
        self,
        exchange: Exchange,
        label: str,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str] = None,
        selected_mode: MarketMode = MarketMode.SPOT
    ) -> ExchangeConnection:
        """
        Register a new broker connection.
        
        Args:
            exchange: Exchange type
            label: User-friendly label
            api_key: API key
            api_secret: API secret
            passphrase: Optional passphrase (for some exchanges)
            selected_mode: Initial trading mode
            
        Returns:
            ExchangeConnection object
        """
        # Determine supported modes based on exchange
        supported_modes = self._get_supported_modes(exchange)
        
        # Ensure selected mode is supported
        if selected_mode not in supported_modes:
            selected_mode = supported_modes[0]
        
        # Create connection
        connection = ExchangeConnection(
            exchange=exchange,
            label=label,
            market_modes=supported_modes,
            selected_mode=selected_mode,
            status=ConnectionStatus.DISCONNECTED,
            health=ConnectionHealth.UNHEALTHY,
            account_ref=f"{exchange.value}_{label}"
        )
        
        # Store connection
        self._connections[connection.connection_id] = connection
        
        # Store credentials (never expose)
        self._credentials[connection.connection_id] = {
            "api_key": api_key,
            "api_secret": api_secret,
            "passphrase": passphrase or ""
        }
        
        return connection
    
    def get_connection(self, connection_id: str) -> Optional[ExchangeConnection]:
        """Get connection by ID"""
        return self._connections.get(connection_id)
    
    def list_connections(self) -> List[ExchangeConnection]:
        """List all connections"""
        return list(self._connections.values())
    
    def remove_connection(self, connection_id: str) -> bool:
        """Remove a connection"""
        if connection_id in self._connections:
            # Disconnect adapter if active
            if connection_id in self._adapters:
                asyncio.create_task(self._adapters[connection_id].disconnect())
                del self._adapters[connection_id]
            
            del self._connections[connection_id]
            
            if connection_id in self._credentials:
                del self._credentials[connection_id]
            
            if connection_id in self._health_records:
                del self._health_records[connection_id]
            
            return True
        return False
    
    def update_connection_mode(self, connection_id: str, mode: MarketMode) -> bool:
        """Update selected trading mode"""
        connection = self._connections.get(connection_id)
        if connection and mode in connection.market_modes:
            connection.selected_mode = mode
            connection.updated_at = datetime.now(timezone.utc)
            return True
        return False
    
    def update_connection_status(
        self,
        connection_id: str,
        status: ConnectionStatus,
        health: Optional[ConnectionHealth] = None
    ):
        """Update connection status"""
        connection = self._connections.get(connection_id)
        if connection:
            connection.status = status
            if health:
                connection.health = health
            connection.updated_at = datetime.now(timezone.utc)
    
    # ===========================================
    # Adapter Management
    # ===========================================
    
    async def get_or_create_adapter(self, connection_id: str) -> Optional[BrokerAdapter]:
        """Get or create adapter for connection"""
        if connection_id in self._adapters:
            return self._adapters[connection_id]
        
        connection = self._connections.get(connection_id)
        if not connection:
            return None
        
        creds = self._credentials.get(connection_id)
        if not creds:
            return None
        
        # Create appropriate adapter
        adapter = self._create_adapter(
            connection,
            creds["api_key"],
            creds["api_secret"],
            creds.get("passphrase")
        )
        
        if adapter:
            self._adapters[connection_id] = adapter
        
        return adapter
    
    def get_adapter(self, connection_id: str) -> Optional[BrokerAdapter]:
        """Get existing adapter (sync)"""
        return self._adapters.get(connection_id)
    
    def _create_adapter(
        self,
        connection: ExchangeConnection,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str]
    ) -> Optional[BrokerAdapter]:
        """Create adapter based on exchange type"""
        from .broker_adapters import (
            MockBrokerAdapter,
            BinanceBrokerAdapter,
            BybitBrokerAdapter
        )
        
        # Use mock adapter for mock keys
        if "mock" in api_key.lower() or api_key == "" or api_secret == "":
            return MockBrokerAdapter(connection, api_key, api_secret)
        
        if connection.exchange == Exchange.BINANCE:
            return BinanceBrokerAdapter(
                connection, api_key, api_secret,
                use_futures=(connection.selected_mode == MarketMode.FUTURES)
            )
        elif connection.exchange == Exchange.BYBIT:
            return BybitBrokerAdapter(
                connection, api_key, api_secret,
                category="linear" if connection.selected_mode == MarketMode.FUTURES else "spot"
            )
        else:
            # Default to mock for unsupported exchanges
            return MockBrokerAdapter(connection, api_key, api_secret)
    
    def _get_supported_modes(self, exchange: Exchange) -> List[MarketMode]:
        """Get supported modes for exchange"""
        mode_map = {
            Exchange.BINANCE: [MarketMode.SPOT, MarketMode.FUTURES],
            Exchange.BYBIT: [MarketMode.SPOT, MarketMode.FUTURES],
            Exchange.COINBASE: [MarketMode.SPOT],
            Exchange.HYPERLIQUID: [MarketMode.FUTURES]
        }
        return mode_map.get(exchange, [MarketMode.SPOT])
    
    # ===========================================
    # Health Management
    # ===========================================
    
    def get_health_record(self, connection_id: str) -> Optional[ConnectionHealthRecord]:
        """Get latest health record"""
        return self._health_records.get(connection_id)
    
    def set_health_record(self, connection_id: str, record: ConnectionHealthRecord):
        """Store health record"""
        self._health_records[connection_id] = record
        
        # Update connection health
        connection = self._connections.get(connection_id)
        if connection:
            connection.health = record.health
            connection.updated_at = datetime.now(timezone.utc)
    
    # ===========================================
    # Summary
    # ===========================================
    
    def get_summary(self) -> Dict[str, Any]:
        """Get registry summary"""
        connected = sum(
            1 for c in self._connections.values()
            if c.status == ConnectionStatus.CONNECTED
        )
        healthy = sum(
            1 for c in self._connections.values()
            if c.health == ConnectionHealth.HEALTHY
        )
        
        return {
            "total_connections": len(self._connections),
            "connected": connected,
            "healthy": healthy,
            "active_adapters": len(self._adapters),
            "by_exchange": {
                exchange.value: sum(
                    1 for c in self._connections.values()
                    if c.exchange == exchange
                )
                for exchange in Exchange
            }
        }


# ===========================================
# Global Instance
# ===========================================

broker_registry = BrokerRegistry()


def get_connection(connection_id: str) -> Optional[ExchangeConnection]:
    """Get connection from global registry"""
    return broker_registry.get_connection(connection_id)


def list_connections() -> List[ExchangeConnection]:
    """List all connections from global registry"""
    return broker_registry.list_connections()


def register_connection(
    exchange: Exchange,
    label: str,
    api_key: str,
    api_secret: str,
    passphrase: Optional[str] = None,
    selected_mode: MarketMode = MarketMode.SPOT
) -> ExchangeConnection:
    """Register connection in global registry"""
    return broker_registry.register_connection(
        exchange, label, api_key, api_secret, passphrase, selected_mode
    )


def remove_connection(connection_id: str) -> bool:
    """Remove connection from global registry"""
    return broker_registry.remove_connection(connection_id)
