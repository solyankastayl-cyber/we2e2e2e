"""
Execution Types (T3)
====================

Type definitions for execution decision layer.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid


class ExecutionAction(str, Enum):
    """Trading action"""
    ENTER_LONG = "ENTER_LONG"
    EXIT_LONG = "EXIT_LONG"
    ENTER_SHORT = "ENTER_SHORT"
    EXIT_SHORT = "EXIT_SHORT"
    HOLD = "HOLD"
    ADD_TO_LONG = "ADD_TO_LONG"      # Averaging
    ADD_TO_SHORT = "ADD_TO_SHORT"    # Averaging


class SignalSource(str, Enum):
    """Signal source mode"""
    TA_ONLY = "TA_ONLY"
    MANUAL_SIGNAL_SOURCE = "MANUAL_SIGNAL_SOURCE"
    MBRAIN_ROUTED = "MBRAIN_ROUTED"


class Horizon(str, Enum):
    """Trading horizon"""
    SCALP = "SCALP"      # Minutes
    INTRADAY = "1D"      # Hours
    SWING = "7D"         # Days
    POSITION = "30D"     # Weeks


@dataclass
class ExecutionDecision:
    """
    Normalized execution decision from any signal source.
    
    This is the unified format for trading decisions.
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    source_mode: SignalSource = SignalSource.TA_ONLY
    source_ref: str = ""  # Reference to source (TA pattern, manual signal ID, etc.)
    
    asset: str = ""
    symbol: str = ""
    market_type: str = "SPOT"  # SPOT or FUTURES
    
    action: ExecutionAction = ExecutionAction.HOLD
    
    confidence: float = 0.0  # 0.0 to 1.0
    horizon: Horizon = Horizon.INTRADAY
    
    # Optional sizing hints from signal
    suggested_size_pct: Optional[float] = None  # % of portfolio
    suggested_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "source_mode": self.source_mode.value,
            "source_ref": self.source_ref,
            "asset": self.asset,
            "symbol": self.symbol,
            "market_type": self.market_type,
            "action": self.action.value,
            "confidence": round(self.confidence, 4),
            "horizon": self.horizon.value,
            "suggested_size_pct": self.suggested_size_pct,
            "suggested_price": self.suggested_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ExecutionContext:
    """
    Context for execution decision.
    
    Contains account state and capsule configuration.
    """
    connection_id: str = ""
    selected_mode: str = "SPOT"  # SPOT or FUTURES
    
    account_equity_usd: float = 0.0
    available_cash_usd: float = 0.0
    
    # Current position state
    has_position: bool = False
    current_position_side: Optional[str] = None  # LONG, SHORT
    current_position_size: float = 0.0
    current_position_entry: float = 0.0
    
    # Execution mode
    active_execution_mode: SignalSource = SignalSource.TA_ONLY
    
    # Control state
    paused: bool = False
    kill_switch_active: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "selected_mode": self.selected_mode,
            "account_equity_usd": round(self.account_equity_usd, 2),
            "available_cash_usd": round(self.available_cash_usd, 2),
            "has_position": self.has_position,
            "current_position_side": self.current_position_side,
            "current_position_size": round(self.current_position_size, 8),
            "current_position_entry": round(self.current_position_entry, 8),
            "active_execution_mode": self.active_execution_mode.value,
            "paused": self.paused,
            "kill_switch_active": self.kill_switch_active
        }


@dataclass
class OrderIntent:
    """
    Order intent ready for OMS.
    
    Built from ExecutionDecision + ExecutionContext.
    """
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    connection_id: str = ""
    asset: str = ""
    symbol: str = ""
    
    side: str = "BUY"  # BUY or SELL
    order_type: str = "MARKET"  # MARKET, LIMIT
    
    quantity: float = 0.0
    notional_usd: float = 0.0
    price: Optional[float] = None
    
    reduce_only: bool = False
    client_tag: Optional[str] = None
    
    source_decision_id: str = ""
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "connection_id": self.connection_id,
            "asset": self.asset,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": round(self.quantity, 8),
            "notional_usd": round(self.notional_usd, 2),
            "price": round(self.price, 8) if self.price else None,
            "reduce_only": self.reduce_only,
            "client_tag": self.client_tag,
            "source_decision_id": self.source_decision_id,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ExecutionPreview:
    """
    Preview of what execution would do.
    
    Shows decision → intent without executing.
    """
    decision: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    intent: Optional[Dict[str, Any]] = None
    
    would_execute: bool = False
    blocked: bool = False
    block_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    estimated_notional_usd: float = 0.0
    estimated_commission_usd: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "context": self.context,
            "intent": self.intent,
            "would_execute": self.would_execute,
            "blocked": self.blocked,
            "block_reasons": self.block_reasons,
            "warnings": self.warnings,
            "estimated_notional_usd": round(self.estimated_notional_usd, 2),
            "estimated_commission_usd": round(self.estimated_commission_usd, 2)
        }


@dataclass
class ExecutionResult:
    """
    Result of execution attempt.
    """
    success: bool = False
    
    decision_id: str = ""
    intent_id: Optional[str] = None
    order_id: Optional[str] = None
    
    executed: bool = False
    blocked: bool = False
    
    block_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    order_status: Optional[str] = None
    fill_price: Optional[float] = None
    fill_quantity: Optional[float] = None
    
    error: Optional[str] = None
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "decision_id": self.decision_id,
            "intent_id": self.intent_id,
            "order_id": self.order_id,
            "executed": self.executed,
            "blocked": self.blocked,
            "block_reasons": self.block_reasons,
            "warnings": self.warnings,
            "order_status": self.order_status,
            "fill_price": round(self.fill_price, 8) if self.fill_price else None,
            "fill_quantity": round(self.fill_quantity, 8) if self.fill_quantity else None,
            "error": self.error,
            "timestamp": self.timestamp.isoformat()
        }
