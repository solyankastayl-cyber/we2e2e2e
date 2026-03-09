"""
Trading Capsule Types (T0)
==========================

Core type definitions for Trading Capsule.

Defines:
- Execution modes (TA_ONLY, MANUAL_SIGNAL_SOURCE, MBRAIN_ROUTED)
- Trading modes (SPOT, FUTURES)
- Core entities (Connection, Account, Position, Order)
- Risk profiles
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid


# ===========================================
# Enums
# ===========================================

class Exchange(str, Enum):
    """Supported exchanges"""
    BINANCE = "BINANCE"
    BYBIT = "BYBIT"
    COINBASE = "COINBASE"
    HYPERLIQUID = "HYPERLIQUID"


class MarketMode(str, Enum):
    """Trading market mode"""
    SPOT = "SPOT"
    FUTURES = "FUTURES"


class ExecutionMode(str, Enum):
    """Capsule execution mode"""
    TA_ONLY = "TA_ONLY"                      # Trade only from TA signals
    MANUAL_SIGNAL_SOURCE = "MANUAL_SIGNAL_SOURCE"  # Accept external signal payload
    MBRAIN_ROUTED = "MBRAIN_ROUTED"          # Later - receive from global M-Brain


class ConnectionStatus(str, Enum):
    """Exchange connection status"""
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    INVALID = "INVALID"
    ERROR = "ERROR"


class ConnectionHealth(str, Enum):
    """Connection health status"""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class OrderSide(str, Enum):
    """Order side"""
    BUY = "BUY"
    SELL = "SELL"


class PositionSide(str, Enum):
    """Position side"""
    LONG = "LONG"
    SHORT = "SHORT"


class OrderType(str, Enum):
    """Order type"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    """Order status"""
    PENDING = "PENDING"
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


# ===========================================
# T0: Core Entities
# ===========================================

@dataclass
class ExchangeConnection:
    """
    Exchange connection entity.
    
    Represents a registered broker connection.
    """
    connection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    exchange: Exchange = Exchange.BINANCE
    label: str = ""
    
    market_modes: List[MarketMode] = field(default_factory=lambda: [MarketMode.SPOT])
    selected_mode: MarketMode = MarketMode.SPOT
    
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    health: ConnectionHealth = ConnectionHealth.UNHEALTHY
    
    account_ref: str = ""
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "exchange": self.exchange.value,
            "label": self.label,
            "market_modes": [m.value for m in self.market_modes],
            "selected_mode": self.selected_mode.value,
            "status": self.status.value,
            "health": self.health.value,
            "account_ref": self.account_ref,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class AccountCredentialsRef:
    """
    Credentials reference (never expose raw secrets).
    
    Stores references to encrypted credentials.
    """
    connection_id: str
    provider: str
    key_ref: str  # Masked or reference ID
    secret_ref: str  # Never the actual secret
    passphrase_ref: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "provider": self.provider,
            "key_masked": self.key_ref[:4] + "****" + self.key_ref[-4:] if len(self.key_ref) > 8 else "****",
            "has_passphrase": self.passphrase_ref is not None
        }


@dataclass
class AssetBalance:
    """Single asset balance"""
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
class AccountState:
    """
    Account state from exchange.
    
    Contains balances, positions count, permissions.
    """
    connection_id: str
    exchange: str
    mode: MarketMode = MarketMode.SPOT
    
    equity_usd: float = 0.0
    balances: List[AssetBalance] = field(default_factory=list)
    
    open_positions: int = 0
    open_orders: int = 0
    
    can_read: bool = True
    can_trade: bool = False
    can_withdraw: bool = False
    
    last_sync_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "exchange": self.exchange,
            "mode": self.mode.value,
            "equity_usd": round(self.equity_usd, 2),
            "balances": [b.to_dict() for b in self.balances],
            "open_positions": self.open_positions,
            "open_orders": self.open_orders,
            "permissions": {
                "can_read": self.can_read,
                "can_trade": self.can_trade,
                "can_withdraw": self.can_withdraw
            },
            "last_sync_at": self.last_sync_at.isoformat()
        }


@dataclass
class PositionSummary:
    """Position summary"""
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    connection_id: str = ""
    
    asset: str = ""
    mode: MarketMode = MarketMode.SPOT
    side: PositionSide = PositionSide.LONG
    
    quantity: float = 0.0
    avg_entry: float = 0.0
    mark_price: float = 0.0
    
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    leverage: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "connection_id": self.connection_id,
            "asset": self.asset,
            "mode": self.mode.value,
            "side": self.side.value,
            "quantity": round(self.quantity, 8),
            "avg_entry": round(self.avg_entry, 8),
            "mark_price": round(self.mark_price, 8),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "leverage": self.leverage
        }


@dataclass
class ConnectionHealthRecord:
    """Connection health check record"""
    connection_id: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    ping_ms: Optional[float] = None
    account_fetch_ok: bool = False
    balance_fetch_ok: bool = False
    positions_fetch_ok: bool = False
    
    health: ConnectionHealth = ConnectionHealth.UNHEALTHY
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "checked_at": self.checked_at.isoformat(),
            "ping_ms": self.ping_ms,
            "account_fetch_ok": self.account_fetch_ok,
            "balance_fetch_ok": self.balance_fetch_ok,
            "positions_fetch_ok": self.positions_fetch_ok,
            "health": self.health.value,
            "reason": self.reason
        }


@dataclass
class ConnectionValidationResult:
    """Connection validation result"""
    valid: bool = False
    exchange: str = ""
    
    can_read: bool = False
    can_trade: bool = False
    can_withdraw: bool = False
    
    supported_modes: List[MarketMode] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "exchange": self.exchange,
            "can_read": self.can_read,
            "can_trade": self.can_trade,
            "can_withdraw": self.can_withdraw,
            "supported_modes": [m.value for m in self.supported_modes],
            "warnings": self.warnings,
            "errors": self.errors
        }


# ===========================================
# T0: Trading Entities
# ===========================================

@dataclass
class TradeIntent:
    """
    Trade intent from signal source.
    
    Captures WHY we want to trade, before converting to order.
    """
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_mode: ExecutionMode = ExecutionMode.TA_ONLY
    
    asset: str = ""
    side: OrderSide = OrderSide.BUY
    market_type: MarketMode = MarketMode.SPOT
    
    confidence: float = 0.0
    reason: Optional[str] = None
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "source_mode": self.source_mode.value,
            "asset": self.asset,
            "side": self.side.value,
            "market_type": self.market_type.value,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class OrderIntent:
    """
    Order intent ready for execution.
    
    The actual order to be placed.
    """
    order_intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    asset: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    
    quantity: float = 0.0
    price: Optional[float] = None
    
    reduce_only: bool = False
    client_tag: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_intent_id": self.order_intent_id,
            "asset": self.asset,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": round(self.quantity, 8),
            "price": round(self.price, 8) if self.price else None,
            "reduce_only": self.reduce_only,
            "client_tag": self.client_tag
        }


@dataclass
class TradingRiskProfile:
    """
    Trading risk profile for the capsule.
    
    Defines risk limits and trading rules.
    """
    profile_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    max_position_usd: float = 10000.0
    max_asset_exposure_pct: float = 0.20  # 20% per asset
    max_portfolio_exposure_pct: float = 0.50  # 50% total
    max_daily_drawdown_pct: float = 0.05  # 5% daily max DD
    
    averaging_enabled: bool = True
    max_averaging_steps: int = 3
    
    kill_switch_enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "max_position_usd": self.max_position_usd,
            "max_asset_exposure_pct": self.max_asset_exposure_pct,
            "max_portfolio_exposure_pct": self.max_portfolio_exposure_pct,
            "max_daily_drawdown_pct": self.max_daily_drawdown_pct,
            "averaging_enabled": self.averaging_enabled,
            "max_averaging_steps": self.max_averaging_steps,
            "kill_switch_enabled": self.kill_switch_enabled
        }


# ===========================================
# Capsule Mode State
# ===========================================

@dataclass
class CapsuleModeState:
    """Current capsule mode state"""
    execution_mode: ExecutionMode = ExecutionMode.TA_ONLY
    trading_mode: MarketMode = MarketMode.SPOT
    
    active_connection_id: Optional[str] = None
    risk_profile_id: Optional[str] = None
    
    paused: bool = False
    kill_switch_active: bool = False
    
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_mode": self.execution_mode.value,
            "trading_mode": self.trading_mode.value,
            "active_connection_id": self.active_connection_id,
            "risk_profile_id": self.risk_profile_id,
            "paused": self.paused,
            "kill_switch_active": self.kill_switch_active,
            "updated_at": self.updated_at.isoformat()
        }
