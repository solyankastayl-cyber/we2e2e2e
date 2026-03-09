"""
Strategy Types (T6)
===================

Type definitions for Strategy Runtime Engine.

Defines:
- StrategyAction: действие, которое возвращает стратегия
- StrategyContext: контекст, который получает стратегия
- StrategyPlugin: интерфейс плагина стратегии
- StrategyState: состояние стратегии
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Protocol, runtime_checkable
from enum import Enum
from abc import ABC, abstractmethod
import uuid


# ===========================================
# Enums
# ===========================================

class ActionType(str, Enum):
    """Strategy action types"""
    ENTER_LONG = "ENTER_LONG"
    EXIT_LONG = "EXIT_LONG"
    ENTER_SHORT = "ENTER_SHORT"
    EXIT_SHORT = "EXIT_SHORT"
    AVERAGE = "AVERAGE"           # Add to position
    HOLD = "HOLD"                 # Do nothing
    SCALE_IN = "SCALE_IN"         # Partial entry
    SCALE_OUT = "SCALE_OUT"       # Partial exit
    FLIP = "FLIP"                 # Reverse position


class SignalType(str, Enum):
    """Signal source types"""
    TA_SIGNAL = "TA_SIGNAL"                  # From TA Engine
    MANUAL_SIGNAL = "MANUAL_SIGNAL"          # Manual input
    MBRAIN_SIGNAL = "MBRAIN_SIGNAL"          # From M-Brain
    MARKET_UPDATE = "MARKET_UPDATE"          # Price/volume update
    POSITION_UPDATE = "POSITION_UPDATE"      # Position changed
    RISK_UPDATE = "RISK_UPDATE"              # Risk state changed
    TIME_TRIGGER = "TIME_TRIGGER"            # Scheduled trigger


class StrategyStatus(str, Enum):
    """Strategy status"""
    ACTIVE = "ACTIVE"             # Running, processing signals
    PAUSED = "PAUSED"             # Temporarily paused
    DISABLED = "DISABLED"         # Disabled, not processing
    ERROR = "ERROR"               # In error state


# ===========================================
# Strategy Action
# ===========================================

@dataclass
class StrategyAction:
    """
    Action returned by a strategy.
    
    Represents what the strategy wants to do.
    """
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Core fields
    action: ActionType = ActionType.HOLD
    asset: str = ""
    
    # Sizing
    size: Optional[float] = None           # Quantity
    size_pct: Optional[float] = None       # % of portfolio
    notional_usd: Optional[float] = None   # USD value
    
    # Confidence
    confidence: float = 0.0                # 0.0 to 1.0
    
    # Risk management
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Metadata
    strategy_id: str = ""
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action": self.action.value,
            "asset": self.asset,
            "size": self.size,
            "size_pct": self.size_pct,
            "notional_usd": self.notional_usd,
            "confidence": round(self.confidence, 4),
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "strategy_id": self.strategy_id,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


# ===========================================
# Strategy Context
# ===========================================

@dataclass
class StrategyContext:
    """
    Context provided to strategy for evaluation.
    
    Contains all data the strategy needs to make a decision.
    """
    # Signal data
    signal_type: SignalType = SignalType.TA_SIGNAL
    signal_data: Dict[str, Any] = field(default_factory=dict)
    
    # Market data
    asset: str = ""
    current_price: float = 0.0
    market_data: Dict[str, Any] = field(default_factory=dict)
    
    # Account state
    account_equity_usd: float = 0.0
    available_cash_usd: float = 0.0
    
    # Position state
    has_position: bool = False
    position_side: Optional[str] = None    # LONG, SHORT
    position_size: float = 0.0
    position_entry: float = 0.0
    position_pnl: float = 0.0
    
    # Risk state
    risk_state: Dict[str, Any] = field(default_factory=dict)
    daily_pnl: float = 0.0
    max_drawdown_pct: float = 0.0
    
    # Capsule state
    paused: bool = False
    kill_switch_active: bool = False
    
    # Timestamp
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type.value,
            "signal_data": self.signal_data,
            "asset": self.asset,
            "current_price": round(self.current_price, 8),
            "market_data": self.market_data,
            "account_equity_usd": round(self.account_equity_usd, 2),
            "available_cash_usd": round(self.available_cash_usd, 2),
            "has_position": self.has_position,
            "position_side": self.position_side,
            "position_size": round(self.position_size, 8),
            "position_entry": round(self.position_entry, 8),
            "position_pnl": round(self.position_pnl, 2),
            "risk_state": self.risk_state,
            "daily_pnl": round(self.daily_pnl, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "paused": self.paused,
            "kill_switch_active": self.kill_switch_active,
            "timestamp": self.timestamp.isoformat()
        }


# ===========================================
# Strategy State
# ===========================================

@dataclass
class StrategyState:
    """
    Runtime state of a strategy.
    """
    strategy_id: str
    status: StrategyStatus = StrategyStatus.DISABLED
    
    # Metrics
    signals_received: int = 0
    actions_generated: int = 0
    last_signal_at: Optional[datetime] = None
    last_action_at: Optional[datetime] = None
    
    # Error tracking
    errors: int = 0
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    
    # Performance
    total_pnl: float = 0.0
    win_rate: float = 0.0
    
    # Timestamps
    enabled_at: Optional[datetime] = None
    disabled_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "status": self.status.value,
            "signals_received": self.signals_received,
            "actions_generated": self.actions_generated,
            "last_signal_at": self.last_signal_at.isoformat() if self.last_signal_at else None,
            "last_action_at": self.last_action_at.isoformat() if self.last_action_at else None,
            "errors": self.errors,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "total_pnl": round(self.total_pnl, 2),
            "win_rate": round(self.win_rate, 4),
            "enabled_at": self.enabled_at.isoformat() if self.enabled_at else None,
            "disabled_at": self.disabled_at.isoformat() if self.disabled_at else None,
            "paused_at": self.paused_at.isoformat() if self.paused_at else None
        }


# ===========================================
# Strategy Plugin Interface
# ===========================================

@runtime_checkable
class StrategyPlugin(Protocol):
    """
    Interface that all strategy plugins must implement.
    
    Strategy is a plugin that:
    - Receives signals
    - Evaluates market context
    - Returns trading actions
    """
    
    @property
    def strategy_id(self) -> str:
        """Unique strategy identifier"""
        ...
    
    @property
    def name(self) -> str:
        """Human-readable strategy name"""
        ...
    
    @property
    def description(self) -> str:
        """Strategy description"""
        ...
    
    @property
    def version(self) -> str:
        """Strategy version"""
        ...
    
    def on_signal(self, signal_type: SignalType, signal_data: Dict[str, Any]) -> None:
        """
        Called when a signal is received.
        
        Use for signal preprocessing/storage.
        """
        ...
    
    def on_market_update(self, market_data: Dict[str, Any]) -> None:
        """
        Called when market data is updated.
        
        Use for real-time data processing.
        """
        ...
    
    def on_position_update(self, position_data: Dict[str, Any]) -> None:
        """
        Called when position changes.
        
        Use for position tracking.
        """
        ...
    
    def evaluate(self, context: StrategyContext) -> StrategyAction:
        """
        Main evaluation method.
        
        Called after signal/update to get action.
        Must return StrategyAction.
        """
        ...


# ===========================================
# Base Strategy Implementation
# ===========================================

class BaseStrategy(ABC):
    """
    Abstract base class for strategies.
    
    Provides default implementations and utilities.
    """
    
    def __init__(
        self,
        strategy_id: str,
        name: str,
        description: str = "",
        version: str = "1.0.0"
    ):
        self._strategy_id = strategy_id
        self._name = name
        self._description = description
        self._version = version
        
        # Internal state
        self._last_signal: Optional[Dict[str, Any]] = None
        self._last_market_data: Optional[Dict[str, Any]] = None
        self._last_position: Optional[Dict[str, Any]] = None
    
    @property
    def strategy_id(self) -> str:
        return self._strategy_id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def version(self) -> str:
        return self._version
    
    def on_signal(self, signal_type: SignalType, signal_data: Dict[str, Any]) -> None:
        """Store last signal"""
        self._last_signal = {
            "type": signal_type.value,
            "data": signal_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def on_market_update(self, market_data: Dict[str, Any]) -> None:
        """Store last market data"""
        self._last_market_data = market_data
    
    def on_position_update(self, position_data: Dict[str, Any]) -> None:
        """Store last position"""
        self._last_position = position_data
    
    @abstractmethod
    def evaluate(self, context: StrategyContext) -> StrategyAction:
        """Must be implemented by subclasses"""
        pass
    
    def _create_action(
        self,
        action: ActionType,
        asset: str,
        confidence: float = 0.5,
        reason: str = "",
        **kwargs
    ) -> StrategyAction:
        """Helper to create action"""
        return StrategyAction(
            action=action,
            asset=asset,
            confidence=confidence,
            strategy_id=self.strategy_id,
            reason=reason,
            **kwargs
        )
    
    def _hold(self, asset: str = "", reason: str = "No action") -> StrategyAction:
        """Return HOLD action"""
        return self._create_action(ActionType.HOLD, asset, 0.0, reason)
