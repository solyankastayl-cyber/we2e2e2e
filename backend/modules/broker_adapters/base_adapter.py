"""
Base Broker Adapter
===================

Abstract base class for all broker adapters.
Defines the unified interface for broker operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid


# ===========================================
# Enums
# ===========================================

class BrokerStatus(str, Enum):
    """Broker connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


class OrderSide(str, Enum):
    """Order side"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LIMIT = "STOP_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"


class OrderStatus(str, Enum):
    """Order status"""
    PENDING = "PENDING"
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TimeInForce(str, Enum):
    """Time in force"""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    GTD = "GTD"  # Good Till Date
    DAY = "DAY"  # Day order


# ===========================================
# Data Classes
# ===========================================

@dataclass
class BrokerCredentials:
    """Broker credentials"""
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None  # For some brokers like Coinbase
    testnet: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_key": self.api_key[:8] + "...",  # Masked
            "testnet": self.testnet
        }


@dataclass
class Balance:
    """Account balance"""
    asset: str
    free: float
    locked: float
    total: float = 0.0
    usd_value: float = 0.0
    
    def __post_init__(self):
        if self.total == 0.0:
            self.total = self.free + self.locked
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "free": round(self.free, 8),
            "locked": round(self.locked, 8),
            "total": round(self.total, 8),
            "usd_value": round(self.usd_value, 2)
        }


@dataclass
class Position:
    """Trading position"""
    symbol: str
    side: str  # LONG or SHORT
    size: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    leverage: float = 1.0
    margin: float = 0.0
    liquidation_price: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "size": round(self.size, 8),
            "entry_price": round(self.entry_price, 8),
            "current_price": round(self.current_price, 8),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "leverage": self.leverage,
            "margin": round(self.margin, 2),
            "liquidation_price": round(self.liquidation_price, 8) if self.liquidation_price else None,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Order:
    """Order details"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    broker_order_id: Optional[str] = None
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    commission_asset: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "broker_order_id": self.broker_order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": round(self.quantity, 8),
            "price": round(self.price, 8) if self.price else None,
            "stop_price": round(self.stop_price, 8) if self.stop_price else None,
            "time_in_force": self.time_in_force.value,
            "status": self.status.value,
            "filled_quantity": round(self.filled_quantity, 8),
            "avg_fill_price": round(self.avg_fill_price, 8),
            "commission": round(self.commission, 8),
            "commission_asset": self.commission_asset,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Ticker:
    """Market ticker"""
    symbol: str
    bid: float
    ask: float
    last: float
    volume_24h: float = 0.0
    change_24h: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid
    
    @property
    def spread_bps(self) -> float:
        if self.mid == 0:
            return 0
        return (self.spread / self.mid) * 10000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "bid": round(self.bid, 8),
            "ask": round(self.ask, 8),
            "last": round(self.last, 8),
            "mid": round(self.mid, 8),
            "spread": round(self.spread, 8),
            "spread_bps": round(self.spread_bps, 2),
            "volume_24h": round(self.volume_24h, 2),
            "change_24h": round(self.change_24h, 4),
            "high_24h": round(self.high_24h, 8),
            "low_24h": round(self.low_24h, 8),
            "timestamp": self.timestamp.isoformat()
        }


# ===========================================
# Exceptions
# ===========================================

class BrokerError(Exception):
    """Base broker exception"""
    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code
        super().__init__(message)


class ConnectionError(BrokerError):
    """Connection failed"""
    pass


class AuthenticationError(BrokerError):
    """Authentication failed"""
    pass


class OrderError(BrokerError):
    """Order operation failed"""
    pass


class InsufficientFundsError(BrokerError):
    """Insufficient funds"""
    pass


class RateLimitError(BrokerError):
    """Rate limit exceeded"""
    pass


# ===========================================
# Base Adapter
# ===========================================

class BaseBrokerAdapter(ABC):
    """
    Abstract base class for broker adapters.
    
    All broker adapters must implement these methods.
    """
    
    def __init__(self, credentials: BrokerCredentials):
        self.credentials = credentials
        self.status = BrokerStatus.DISCONNECTED
        self.connected_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self._request_count = 0
        self._last_request_at: Optional[datetime] = None
    
    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Broker identifier"""
        pass
    
    @property
    @abstractmethod
    def supports_futures(self) -> bool:
        """Whether broker supports futures/derivatives"""
        pass
    
    @property
    @abstractmethod
    def supports_margin(self) -> bool:
        """Whether broker supports margin trading"""
        pass
    
    # ===========================================
    # Connection
    # ===========================================
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to broker.
        
        Returns:
            True if connection successful
            
        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If authentication fails
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Close connection to broker.
        
        Returns:
            True if disconnected successfully
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to broker.
        
        Returns:
            True if connected
        """
        pass
    
    # ===========================================
    # Account
    # ===========================================
    
    @abstractmethod
    async def get_balance(self, asset: Optional[str] = None) -> List[Balance]:
        """
        Get account balances.
        
        Args:
            asset: Specific asset to query (None for all)
            
        Returns:
            List of Balance objects
        """
        pass
    
    @abstractmethod
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        Get open positions.
        
        Args:
            symbol: Specific symbol to query (None for all)
            
        Returns:
            List of Position objects
        """
        pass
    
    # ===========================================
    # Market Data
    # ===========================================
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """
        Get current ticker for symbol.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            
        Returns:
            Ticker object
        """
        pass
    
    @abstractmethod
    async def get_tickers(self, symbols: Optional[List[str]] = None) -> List[Ticker]:
        """
        Get tickers for multiple symbols.
        
        Args:
            symbols: List of symbols (None for all)
            
        Returns:
            List of Ticker objects
        """
        pass
    
    # ===========================================
    # Orders
    # ===========================================
    
    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_order_id: Optional[str] = None
    ) -> Order:
        """
        Place a new order.
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            order_type: MARKET, LIMIT, etc.
            quantity: Order quantity
            price: Limit price (required for LIMIT orders)
            stop_price: Stop price (for stop orders)
            time_in_force: GTC, IOC, FOK
            client_order_id: Custom order ID
            
        Returns:
            Order object
            
        Raises:
            OrderError: If order placement fails
            InsufficientFundsError: If insufficient balance
        """
        pass
    
    @abstractmethod
    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """
        Cancel an existing order.
        
        Args:
            symbol: Trading symbol
            order_id: Broker order ID
            client_order_id: Custom order ID
            
        Returns:
            Cancelled Order object
            
        Raises:
            OrderError: If cancellation fails
        """
        pass
    
    @abstractmethod
    async def get_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """
        Get order details.
        
        Args:
            symbol: Trading symbol
            order_id: Broker order ID
            client_order_id: Custom order ID
            
        Returns:
            Order object
        """
        pass
    
    @abstractmethod
    async def get_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100
    ) -> List[Order]:
        """
        Get list of orders.
        
        Args:
            symbol: Filter by symbol (None for all)
            status: Filter by status (None for all)
            limit: Max number of orders
            
        Returns:
            List of Order objects
        """
        pass
    
    @abstractmethod
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Cancel all open orders.
        
        Args:
            symbol: Cancel orders for specific symbol (None for all)
            
        Returns:
            List of cancelled Order objects
        """
        pass
    
    # ===========================================
    # Utility
    # ===========================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get adapter status"""
        return {
            "broker": self.broker_name,
            "status": self.status.value,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_error": self.last_error,
            "request_count": self._request_count,
            "testnet": self.credentials.testnet,
            "supports_futures": self.supports_futures,
            "supports_margin": self.supports_margin
        }
    
    def _increment_request_count(self):
        """Track request count for rate limiting"""
        self._request_count += 1
        self._last_request_at = datetime.now(timezone.utc)
