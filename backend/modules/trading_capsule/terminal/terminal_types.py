"""
Terminal Types (T5)
===================

Type definitions for Terminal Backend.

Provides views and entities for admin monitoring and control.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid


# ===========================================
# Enums
# ===========================================

class EventType(str, Enum):
    """Execution log event types"""
    DECISION = "DECISION"
    INTENT_CREATED = "INTENT_CREATED"
    RISK_CHECKED = "RISK_CHECKED"
    RISK_BLOCKED = "RISK_BLOCKED"
    RISK_ADJUSTED = "RISK_ADJUSTED"
    ORDER_SENT = "ORDER_SENT"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    AVERAGING_STARTED = "AVERAGING_STARTED"
    AVERAGING_STEP = "AVERAGING_STEP"
    KILL_SWITCH_ACTIVATED = "KILL_SWITCH_ACTIVATED"
    SYSTEM_PAUSED = "SYSTEM_PAUSED"
    SYSTEM_RESUMED = "SYSTEM_RESUMED"


# ===========================================
# Account Monitor
# ===========================================

@dataclass
class AccountOverview:
    """Account overview for terminal display"""
    connection_id: str = ""
    exchange: str = ""
    label: str = ""
    
    total_equity_usd: float = 0.0
    available_cash_usd: float = 0.0
    
    spot_equity_usd: float = 0.0
    futures_equity_usd: float = 0.0
    
    margin_used_pct: float = 0.0
    
    status: str = "DISCONNECTED"
    health: str = "UNKNOWN"
    
    open_positions: int = 0
    open_orders: int = 0
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "exchange": self.exchange,
            "label": self.label,
            "total_equity_usd": round(self.total_equity_usd, 2),
            "available_cash_usd": round(self.available_cash_usd, 2),
            "spot_equity_usd": round(self.spot_equity_usd, 2),
            "futures_equity_usd": round(self.futures_equity_usd, 2),
            "margin_used_pct": round(self.margin_used_pct, 4),
            "status": self.status,
            "health": self.health,
            "open_positions": self.open_positions,
            "open_orders": self.open_orders,
            "timestamp": self.timestamp.isoformat()
        }


# ===========================================
# Positions Monitor
# ===========================================

@dataclass
class PositionView:
    """Position view for terminal display"""
    position_id: str = ""
    connection_id: str = ""
    asset: str = ""
    symbol: str = ""
    
    side: str = "LONG"  # LONG or SHORT
    market_type: str = "SPOT"  # SPOT or FUTURES
    
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    
    unrealized_pnl_usd: float = 0.0
    unrealized_pnl_pct: float = 0.0
    
    exposure_usd: float = 0.0
    exposure_pct: float = 0.0  # % of portfolio
    
    leverage: float = 1.0
    
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_minutes: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "connection_id": self.connection_id,
            "asset": self.asset,
            "symbol": self.symbol,
            "side": self.side,
            "market_type": self.market_type,
            "quantity": round(self.quantity, 8),
            "avg_entry_price": round(self.avg_entry_price, 8),
            "current_price": round(self.current_price, 8),
            "unrealized_pnl_usd": round(self.unrealized_pnl_usd, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 4),
            "exposure_usd": round(self.exposure_usd, 2),
            "exposure_pct": round(self.exposure_pct, 4),
            "leverage": self.leverage,
            "opened_at": self.opened_at.isoformat(),
            "duration_minutes": round(self.duration_minutes, 1)
        }


# ===========================================
# Orders Monitor
# ===========================================

@dataclass
class OrderView:
    """Order view for terminal display"""
    order_id: str = ""
    client_order_id: str = ""
    exchange_order_id: Optional[str] = None
    
    connection_id: str = ""
    asset: str = ""
    symbol: str = ""
    
    side: str = "BUY"  # BUY or SELL
    order_type: str = "MARKET"  # MARKET, LIMIT
    
    quantity: float = 0.0
    filled_quantity: float = 0.0
    fill_pct: float = 0.0
    
    price: Optional[float] = None
    avg_fill_price: Optional[float] = None
    
    status: str = "NEW"  # NEW, PARTIAL, FILLED, CANCELLED
    
    notional_usd: float = 0.0
    commission_usd: float = 0.0
    
    source: Optional[str] = None  # TA_ONLY, MANUAL, etc.
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "connection_id": self.connection_id,
            "asset": self.asset,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": round(self.quantity, 8),
            "filled_quantity": round(self.filled_quantity, 8),
            "fill_pct": round(self.fill_pct, 4),
            "price": round(self.price, 8) if self.price else None,
            "avg_fill_price": round(self.avg_fill_price, 8) if self.avg_fill_price else None,
            "status": self.status,
            "notional_usd": round(self.notional_usd, 2),
            "commission_usd": round(self.commission_usd, 4),
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None
        }


# ===========================================
# PnL Engine
# ===========================================

@dataclass
class PnLView:
    """PnL overview for terminal display"""
    connection_id: str = ""
    
    realized_pnl_usd: float = 0.0
    unrealized_pnl_usd: float = 0.0
    total_pnl_usd: float = 0.0
    
    daily_pnl_usd: float = 0.0
    daily_pnl_pct: float = 0.0
    
    weekly_pnl_usd: float = 0.0
    monthly_pnl_usd: float = 0.0
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    win_rate: float = 0.0
    
    avg_win_usd: float = 0.0
    avg_loss_usd: float = 0.0
    
    profit_factor: float = 0.0  # gross profit / gross loss
    
    max_drawdown_usd: float = 0.0
    max_drawdown_pct: float = 0.0
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "realized_pnl_usd": round(self.realized_pnl_usd, 2),
            "unrealized_pnl_usd": round(self.unrealized_pnl_usd, 2),
            "total_pnl_usd": round(self.total_pnl_usd, 2),
            "daily_pnl_usd": round(self.daily_pnl_usd, 2),
            "daily_pnl_pct": round(self.daily_pnl_pct, 4),
            "weekly_pnl_usd": round(self.weekly_pnl_usd, 2),
            "monthly_pnl_usd": round(self.monthly_pnl_usd, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "avg_win_usd": round(self.avg_win_usd, 2),
            "avg_loss_usd": round(self.avg_loss_usd, 2),
            "profit_factor": round(self.profit_factor, 2),
            "max_drawdown_usd": round(self.max_drawdown_usd, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class DailyPnLRecord:
    """Daily PnL record"""
    date: str = ""
    connection_id: str = ""
    
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    
    trades_count: int = 0
    volume_usd: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "connection_id": self.connection_id,
            "pnl_usd": round(self.pnl_usd, 2),
            "pnl_pct": round(self.pnl_pct, 4),
            "trades_count": self.trades_count,
            "volume_usd": round(self.volume_usd, 2)
        }


# ===========================================
# Execution Log
# ===========================================

@dataclass
class ExecutionLogEntry:
    """Execution log entry for terminal display"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    event_type: EventType = EventType.DECISION
    
    connection_id: Optional[str] = None
    asset: Optional[str] = None
    
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    severity: str = "INFO"  # INFO, WARNING, ERROR
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "connection_id": self.connection_id,
            "asset": self.asset,
            "message": self.message,
            "details": self.details,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat()
        }


# ===========================================
# Risk Monitor
# ===========================================

@dataclass
class RiskOverview:
    """Risk overview for terminal display"""
    profile_id: str = ""
    
    kill_switch_active: bool = False
    paused: bool = False
    emergency_stop_triggered: bool = False
    
    current_exposure_usd: float = 0.0
    current_exposure_pct: float = 0.0
    max_exposure_pct: float = 0.5
    
    daily_pnl_usd: float = 0.0
    daily_drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.05
    
    open_positions: int = 0
    max_positions: int = 5
    
    averaging_active_assets: int = 0
    
    blocked_trades_24h: int = 0
    adjusted_trades_24h: int = 0
    
    last_risk_event: Optional[str] = None
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "kill_switch_active": self.kill_switch_active,
            "paused": self.paused,
            "emergency_stop_triggered": self.emergency_stop_triggered,
            "current_exposure_usd": round(self.current_exposure_usd, 2),
            "current_exposure_pct": round(self.current_exposure_pct, 4),
            "max_exposure_pct": self.max_exposure_pct,
            "daily_pnl_usd": round(self.daily_pnl_usd, 2),
            "daily_drawdown_pct": round(self.daily_drawdown_pct, 4),
            "max_drawdown_pct": self.max_drawdown_pct,
            "open_positions": self.open_positions,
            "max_positions": self.max_positions,
            "averaging_active_assets": self.averaging_active_assets,
            "blocked_trades_24h": self.blocked_trades_24h,
            "adjusted_trades_24h": self.adjusted_trades_24h,
            "last_risk_event": self.last_risk_event,
            "timestamp": self.timestamp.isoformat()
        }


# ===========================================
# Averaging Monitor
# ===========================================

@dataclass
class AveragingView:
    """Averaging state view for terminal display"""
    connection_id: str = ""
    asset: str = ""
    
    active: bool = False
    
    steps_used: int = 0
    max_steps: int = 3
    
    capital_committed_usd: float = 0.0
    max_capital_usd: float = 0.0
    capital_used_pct: float = 0.0
    
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    price_distance_pct: float = 0.0
    
    last_entry_price: float = 0.0
    next_entry_trigger_price: float = 0.0
    
    unrealized_pnl_usd: float = 0.0
    
    started_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "asset": self.asset,
            "active": self.active,
            "steps_used": self.steps_used,
            "max_steps": self.max_steps,
            "capital_committed_usd": round(self.capital_committed_usd, 2),
            "max_capital_usd": round(self.max_capital_usd, 2),
            "capital_used_pct": round(self.capital_used_pct, 4),
            "avg_entry_price": round(self.avg_entry_price, 8),
            "current_price": round(self.current_price, 8),
            "price_distance_pct": round(self.price_distance_pct, 4),
            "last_entry_price": round(self.last_entry_price, 8),
            "next_entry_trigger_price": round(self.next_entry_trigger_price, 8),
            "unrealized_pnl_usd": round(self.unrealized_pnl_usd, 2),
            "started_at": self.started_at.isoformat() if self.started_at else None
        }


# ===========================================
# System State
# ===========================================

@dataclass
class TradingSystemState:
    """Trading system state for terminal display"""
    execution_mode: str = "TA_ONLY"  # TA_ONLY, MANUAL_SIGNAL_SOURCE, MBRAIN_ROUTED
    trading_mode: str = "SPOT"  # SPOT, FUTURES
    
    paused: bool = False
    kill_switch_active: bool = False
    
    active_connections: int = 0
    healthy_connections: int = 0
    
    open_positions: int = 0
    open_orders: int = 0
    
    daily_trades: int = 0
    daily_volume_usd: float = 0.0
    daily_pnl_usd: float = 0.0
    
    uptime_minutes: float = 0.0
    last_trade_at: Optional[datetime] = None
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_mode": self.execution_mode,
            "trading_mode": self.trading_mode,
            "paused": self.paused,
            "kill_switch_active": self.kill_switch_active,
            "active_connections": self.active_connections,
            "healthy_connections": self.healthy_connections,
            "open_positions": self.open_positions,
            "open_orders": self.open_orders,
            "daily_trades": self.daily_trades,
            "daily_volume_usd": round(self.daily_volume_usd, 2),
            "daily_pnl_usd": round(self.daily_pnl_usd, 2),
            "uptime_minutes": round(self.uptime_minutes, 1),
            "last_trade_at": self.last_trade_at.isoformat() if self.last_trade_at else None,
            "timestamp": self.timestamp.isoformat()
        }


# ===========================================
# Action Results
# ===========================================

@dataclass
class ActionResult:
    """Result of terminal action"""
    success: bool = False
    action: str = ""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action": self.action,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }
