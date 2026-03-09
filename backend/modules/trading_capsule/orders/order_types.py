"""
Order Types (T2)
================

Order-related type definitions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid


class OrderStatus(str, Enum):
    """Order lifecycle status"""
    PENDING = "PENDING"           # Intent created, not yet submitted
    SUBMITTED = "SUBMITTED"       # Sent to exchange
    NEW = "NEW"                   # Accepted by exchange
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"             # Internal failure


class OrderType(str, Enum):
    """Order type"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderSide(str, Enum):
    """Order side"""
    BUY = "BUY"
    SELL = "SELL"


class TimeInForce(str, Enum):
    """Time in force"""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill


@dataclass
class Order:
    """
    Normalized order entity.
    
    Represents an order across any exchange in unified format.
    """
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_order_id: str = field(default_factory=lambda: f"TC_{uuid.uuid4().hex[:12]}")
    
    # Connection
    connection_id: str = ""
    exchange: str = ""
    
    # Order details
    asset: str = ""
    symbol: str = ""  # Full symbol like BTCUSDT
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    
    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False
    
    # Status
    status: OrderStatus = OrderStatus.PENDING
    broker_order_id: Optional[str] = None
    
    # Execution
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    commission_asset: str = ""
    
    # Metadata
    source_decision_id: Optional[str] = None
    source_intent_id: Optional[str] = None
    client_tag: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: Optional[datetime] = None
    
    @property
    def is_active(self) -> bool:
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]
    
    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED
    
    @property
    def fill_pct(self) -> float:
        if self.quantity == 0:
            return 0.0
        return self.filled_quantity / self.quantity
    
    @property
    def notional_usd(self) -> float:
        price = self.avg_fill_price if self.avg_fill_price > 0 else (self.price or 0)
        return self.quantity * price
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "connection_id": self.connection_id,
            "exchange": self.exchange,
            "asset": self.asset,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": round(self.quantity, 8),
            "price": round(self.price, 8) if self.price else None,
            "stop_price": round(self.stop_price, 8) if self.stop_price else None,
            "time_in_force": self.time_in_force.value,
            "reduce_only": self.reduce_only,
            "status": self.status.value,
            "broker_order_id": self.broker_order_id,
            "filled_quantity": round(self.filled_quantity, 8),
            "avg_fill_price": round(self.avg_fill_price, 8),
            "fill_pct": round(self.fill_pct, 4),
            "commission": round(self.commission, 8),
            "commission_asset": self.commission_asset,
            "notional_usd": round(self.notional_usd, 2),
            "source_decision_id": self.source_decision_id,
            "client_tag": self.client_tag,
            "created_at": self.created_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "updated_at": self.updated_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None
        }


@dataclass
class Fill:
    """
    Order fill (execution) record.
    """
    fill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    broker_trade_id: Optional[str] = None
    
    asset: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    
    quantity: float = 0.0
    price: float = 0.0
    
    commission: float = 0.0
    commission_asset: str = ""
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def notional_usd(self) -> float:
        return self.quantity * self.price
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "broker_trade_id": self.broker_trade_id,
            "asset": self.asset,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": round(self.quantity, 8),
            "price": round(self.price, 8),
            "notional_usd": round(self.notional_usd, 2),
            "commission": round(self.commission, 8),
            "commission_asset": self.commission_asset,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class Trade:
    """
    Completed trade (round trip).
    
    Represents a full trade from entry to exit.
    """
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    connection_id: str = ""
    asset: str = ""
    symbol: str = ""
    
    side: str = "LONG"  # LONG or SHORT
    
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: float = 0.0
    
    gross_pnl: float = 0.0
    commission: float = 0.0
    net_pnl: float = 0.0
    
    entry_order_id: Optional[str] = None
    exit_order_id: Optional[str] = None
    
    open_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    close_time: Optional[datetime] = None
    
    is_open: bool = True
    
    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        if self.side == "LONG":
            return (self.exit_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.exit_price) / self.entry_price
    
    @property
    def duration_minutes(self) -> float:
        if not self.close_time:
            delta = datetime.now(timezone.utc) - self.open_time
        else:
            delta = self.close_time - self.open_time
        return delta.total_seconds() / 60
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "connection_id": self.connection_id,
            "asset": self.asset,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": round(self.entry_price, 8),
            "exit_price": round(self.exit_price, 8),
            "quantity": round(self.quantity, 8),
            "gross_pnl": round(self.gross_pnl, 2),
            "commission": round(self.commission, 8),
            "net_pnl": round(self.net_pnl, 2),
            "pnl_pct": round(self.pnl_pct, 4),
            "entry_order_id": self.entry_order_id,
            "exit_order_id": self.exit_order_id,
            "open_time": self.open_time.isoformat(),
            "close_time": self.close_time.isoformat() if self.close_time else None,
            "duration_minutes": round(self.duration_minutes, 1),
            "is_open": self.is_open
        }


@dataclass
class OrderPrecision:
    """
    Order precision rules for an asset.
    """
    symbol: str
    exchange: str
    
    price_precision: int = 2          # Decimal places for price
    quantity_precision: int = 8       # Decimal places for quantity
    price_step: float = 0.01          # Minimum price increment
    quantity_step: float = 0.00001    # Minimum quantity increment
    min_quantity: float = 0.0001      # Minimum order quantity
    min_notional: float = 10.0        # Minimum order value in USD
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "price_precision": self.price_precision,
            "quantity_precision": self.quantity_precision,
            "price_step": self.price_step,
            "quantity_step": self.quantity_step,
            "min_quantity": self.min_quantity,
            "min_notional": self.min_notional
        }


@dataclass
class OrderValidationResult:
    """
    Order validation result.
    """
    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    adjusted_quantity: Optional[float] = None
    adjusted_price: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "adjusted_quantity": self.adjusted_quantity,
            "adjusted_price": self.adjusted_price
        }
