"""
Broker Base Adapter (T1)
========================

Abstract base class for all broker adapters.
Each exchange must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime, timezone
import time

from ..trading_types import (
    Exchange,
    MarketMode,
    ConnectionStatus,
    ConnectionHealth,
    ExchangeConnection,
    AccountState,
    AssetBalance,
    PositionSummary,
    ConnectionHealthRecord,
    ConnectionValidationResult
)


class BrokerAdapter(ABC):
    """
    Abstract broker adapter interface.
    
    All exchange adapters must implement these methods.
    Separates account/trading concerns from market data.
    """
    
    def __init__(self, connection: ExchangeConnection, api_key: str, api_secret: str, passphrase: str = None):
        self.connection = connection
        self._api_key = api_key
        self._api_secret = api_secret
        self._passphrase = passphrase
        
        self._connected = False
        self._last_request_at: Optional[datetime] = None
        self._request_count = 0
    
    @property
    @abstractmethod
    def exchange(self) -> Exchange:
        """Exchange identifier"""
        pass
    
    @property
    @abstractmethod
    def supported_modes(self) -> List[MarketMode]:
        """Supported trading modes"""
        pass
    
    # ===========================================
    # Connection Validation
    # ===========================================
    
    @abstractmethod
    async def validate_connection(self) -> ConnectionValidationResult:
        """
        Validate API credentials and permissions.
        
        Returns:
            ConnectionValidationResult with permissions and supported modes
        """
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to exchange.
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Close connection.
        
        Returns:
            True if successful
        """
        pass
    
    # ===========================================
    # Account State
    # ===========================================
    
    @abstractmethod
    async def fetch_account_state(self) -> AccountState:
        """
        Fetch full account state.
        
        Returns:
            AccountState with balances, positions count, etc.
        """
        pass
    
    @abstractmethod
    async def fetch_balances(self) -> List[AssetBalance]:
        """
        Fetch account balances.
        
        Returns:
            List of AssetBalance
        """
        pass
    
    @abstractmethod
    async def fetch_positions(self) -> List[PositionSummary]:
        """
        Fetch open positions.
        
        Returns:
            List of PositionSummary
        """
        pass
    
    @abstractmethod
    async def fetch_open_orders_count(self) -> int:
        """
        Get count of open orders.
        
        Returns:
            Number of open orders
        """
        pass
    
    # ===========================================
    # Health Check
    # ===========================================
    
    @abstractmethod
    async def health_check(self) -> ConnectionHealthRecord:
        """
        Perform health check on connection.
        
        Returns:
            ConnectionHealthRecord with status
        """
        pass
    
    # ===========================================
    # Utility
    # ===========================================
    
    def _increment_request(self):
        """Track request count"""
        self._request_count += 1
        self._last_request_at = datetime.now(timezone.utc)
    
    def get_status(self) -> dict:
        """Get adapter status"""
        return {
            "connection_id": self.connection.connection_id,
            "exchange": self.exchange.value,
            "connected": self._connected,
            "request_count": self._request_count,
            "last_request_at": self._last_request_at.isoformat() if self._last_request_at else None,
            "selected_mode": self.connection.selected_mode.value
        }
