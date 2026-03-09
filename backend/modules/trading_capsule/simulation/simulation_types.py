"""
Simulation Types (S1.1)
=======================

Type definitions for Trading Simulation Engine.

Core entities:
- SimulationRun: configuration and lifecycle of a simulation
- SimulationState: current state of a running simulation
- SimulationFingerprint: determinism guard
- FrozenSimulationConfig: immutable config snapshot

Capital Profiles:
- MICRO: $100
- SMALL: $1,000
- MEDIUM: $10,000
- LARGE: $100,000
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid
import hashlib
import json


# ===========================================
# Enums
# ===========================================

class SimulationStatus(str, Enum):
    """Simulation run status"""
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CapitalProfile(str, Enum):
    """Predefined capital profiles"""
    MICRO = "MICRO"      # $100
    SMALL = "SMALL"      # $1,000
    MEDIUM = "MEDIUM"    # $10,000
    LARGE = "LARGE"      # $100,000


class MarketType(str, Enum):
    """Market type for simulation"""
    SPOT = "SPOT"
    FUTURES = "FUTURES"


class Timeframe(str, Enum):
    """Supported timeframes"""
    D1 = "1D"
    H4 = "4H"
    H1 = "1H"


class ReplayMode(str, Enum):
    """Replay execution mode"""
    STEP = "STEP"      # Manual step-by-step
    AUTO = "AUTO"      # Automatic replay
    FAST = "FAST"      # Maximum speed


class ReplayStatus(str, Enum):
    """Replay state status"""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"


class SimulationStepStatus(str, Enum):
    """Step execution status"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ===========================================
# Capital Profile Values
# ===========================================

CAPITAL_PROFILE_VALUES: Dict[CapitalProfile, float] = {
    CapitalProfile.MICRO: 100.0,
    CapitalProfile.SMALL: 1000.0,
    CapitalProfile.MEDIUM: 10000.0,
    CapitalProfile.LARGE: 100000.0,
}


def get_capital_for_profile(profile: CapitalProfile) -> float:
    """Get capital amount for profile"""
    return CAPITAL_PROFILE_VALUES.get(profile, 1000.0)


# ===========================================
# SimulationRun
# ===========================================

@dataclass
class SimulationRun:
    """
    Configuration and lifecycle of a simulation run.
    
    A simulation run represents a single backtest/simulation
    of one strategy on one asset over a specific period.
    """
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Strategy
    strategy_id: str = ""
    strategy_version: Optional[str] = None
    
    # Asset
    asset: str = ""
    market_type: MarketType = MarketType.SPOT
    
    # Time
    timeframe: Timeframe = Timeframe.D1
    start_date: str = ""
    end_date: str = ""
    
    # Dataset
    dataset_id: Optional[str] = None
    dataset_checksum: Optional[str] = None
    
    # Capital
    initial_capital_usd: float = 1000.0
    capital_profile: CapitalProfile = CapitalProfile.SMALL
    
    # Risk profile reference
    risk_profile_id: Optional[str] = None
    risk_profile_version: Optional[str] = None
    
    # Status
    status: SimulationStatus = SimulationStatus.CREATED
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    # Result summary
    final_equity_usd: Optional[float] = None
    total_trades: int = 0
    
    # Error info
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "asset": self.asset,
            "market_type": self.market_type.value,
            "timeframe": self.timeframe.value,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "dataset_id": self.dataset_id,
            "dataset_checksum": self.dataset_checksum,
            "initial_capital_usd": round(self.initial_capital_usd, 2),
            "capital_profile": self.capital_profile.value,
            "risk_profile_id": self.risk_profile_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "final_equity_usd": round(self.final_equity_usd, 2) if self.final_equity_usd else None,
            "total_trades": self.total_trades,
            "error_message": self.error_message
        }


# ===========================================
# SimulationState
# ===========================================

@dataclass
class SimulationState:
    """
    Current runtime state of a simulation.
    
    Updated at each step of the replay.
    """
    run_id: str
    
    # Current position in replay
    current_timestamp: Optional[str] = None
    current_step_index: int = 0
    
    # Portfolio state
    equity_usd: float = 0.0
    cash_usd: float = 0.0
    
    # Positions
    open_positions: int = 0
    open_orders: int = 0
    
    # PnL
    realized_pnl_usd: float = 0.0
    unrealized_pnl_usd: float = 0.0
    
    # Drawdown tracking
    peak_equity_usd: float = 0.0
    current_drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "current_timestamp": self.current_timestamp,
            "current_step_index": self.current_step_index,
            "equity_usd": round(self.equity_usd, 2),
            "cash_usd": round(self.cash_usd, 2),
            "open_positions": self.open_positions,
            "open_orders": self.open_orders,
            "realized_pnl_usd": round(self.realized_pnl_usd, 2),
            "unrealized_pnl_usd": round(self.unrealized_pnl_usd, 2),
            "peak_equity_usd": round(self.peak_equity_usd, 2),
            "current_drawdown_pct": round(self.current_drawdown_pct, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4)
        }


# ===========================================
# SimulationFingerprint (Determinism Guard)
# ===========================================

@dataclass
class SimulationFingerprint:
    """
    Fingerprint for determinism verification.
    
    Captures all inputs that affect simulation result.
    Same fingerprint = same result (deterministic).
    """
    run_id: str
    
    # Strategy
    strategy_id: str
    strategy_version: Optional[str] = None
    
    # Asset
    asset: str = ""
    market_type: str = ""
    timeframe: str = ""
    
    # Dataset
    dataset_id: Optional[str] = None
    dataset_checksum: Optional[str] = None
    
    # Time range
    start_date: str = ""
    end_date: str = ""
    
    # Capital
    initial_capital_usd: float = 0.0
    capital_profile: str = ""
    
    # Risk
    risk_profile_id: Optional[str] = None
    risk_profile_version: Optional[str] = None
    
    # Config hash
    config_hash: str = ""
    
    # Creation
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "asset": self.asset,
            "market_type": self.market_type,
            "timeframe": self.timeframe,
            "dataset_id": self.dataset_id,
            "dataset_checksum": self.dataset_checksum,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital_usd": round(self.initial_capital_usd, 2),
            "capital_profile": self.capital_profile,
            "risk_profile_id": self.risk_profile_id,
            "config_hash": self.config_hash,
            "created_at": self.created_at.isoformat()
        }
    
    def compute_hash(self) -> str:
        """Compute hash of fingerprint for comparison"""
        data = {
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "asset": self.asset,
            "market_type": self.market_type,
            "timeframe": self.timeframe,
            "dataset_id": self.dataset_id,
            "dataset_checksum": self.dataset_checksum,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital_usd": self.initial_capital_usd,
            "capital_profile": self.capital_profile,
            "risk_profile_id": self.risk_profile_id
        }
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]


# ===========================================
# FrozenSimulationConfig
# ===========================================

@dataclass
class FrozenSimulationConfig:
    """
    Immutable snapshot of simulation configuration.
    
    Frozen at run start, cannot be modified during run.
    """
    run_id: str
    
    strategy_config: Dict[str, Any] = field(default_factory=dict)
    risk_config: Dict[str, Any] = field(default_factory=dict)
    execution_config: Dict[str, Any] = field(default_factory=dict)
    
    frozen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "strategy_config": self.strategy_config,
            "risk_config": self.risk_config,
            "execution_config": self.execution_config,
            "frozen_at": self.frozen_at.isoformat()
        }


# ===========================================
# Market Data Types
# ===========================================

@dataclass
class MarketCandle:
    """
    OHLCV candle data.
    """
    timestamp: str
    
    open: float
    high: float
    low: float
    close: float
    
    volume: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "open": round(self.open, 8),
            "high": round(self.high, 8),
            "low": round(self.low, 8),
            "close": round(self.close, 8),
            "volume": round(self.volume, 2) if self.volume else None
        }


@dataclass
class MarketDataset:
    """
    Dataset metadata.
    """
    dataset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    asset: str = ""
    timeframe: Timeframe = Timeframe.D1
    
    start_date: str = ""
    end_date: str = ""
    
    rows: int = 0
    checksum: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "asset": self.asset,
            "timeframe": self.timeframe.value,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "rows": self.rows,
            "checksum": self.checksum
        }


# ===========================================
# Replay Types
# ===========================================

@dataclass
class ReplayCursor:
    """
    Cursor tracking current position in replay.
    """
    run_id: str
    dataset_id: str
    
    current_index: int = 0
    current_timestamp: Optional[str] = None
    
    finished: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "dataset_id": self.dataset_id,
            "current_index": self.current_index,
            "current_timestamp": self.current_timestamp,
            "finished": self.finished
        }


@dataclass
class ReplayState:
    """
    Current state of replay engine.
    """
    run_id: str
    
    cursor_index: int = 0
    total_steps: int = 0
    progress: float = 0.0
    
    current_timestamp: Optional[str] = None
    
    mode: ReplayMode = ReplayMode.AUTO
    status: ReplayStatus = ReplayStatus.IDLE
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "cursor_index": self.cursor_index,
            "total_steps": self.total_steps,
            "progress": round(self.progress, 4),
            "current_timestamp": self.current_timestamp,
            "mode": self.mode.value,
            "status": self.status.value
        }


@dataclass
class SimulationStep:
    """
    Single step in simulation replay.
    
    Tracks expected and received events for determinism.
    """
    run_id: str
    step_index: int
    timestamp: str
    
    status: SimulationStepStatus = SimulationStepStatus.PENDING
    
    expected_events: List[str] = field(default_factory=list)
    received_events: List[str] = field(default_factory=list)
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "step_index": self.step_index,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "expected_events": self.expected_events,
            "received_events": self.received_events,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


# ===========================================
# Market Tick Event
# ===========================================

@dataclass
class MarketTickEvent:
    """
    Market tick event for strategy consumption.
    """
    event_type: str = "MARKET_TICK"
    
    run_id: str = ""
    step_index: int = 0
    
    asset: str = ""
    timestamp: str = ""
    
    candle: Optional[MarketCandle] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "run_id": self.run_id,
            "step_index": self.step_index,
            "asset": self.asset,
            "timestamp": self.timestamp,
            "candle": self.candle.to_dict() if self.candle else None
        }


# ===========================================
# Simulation Order/Fill Types
# ===========================================

@dataclass
class SimulationOrder:
    """
    Simulated order in simulation.
    """
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    
    asset: str = ""
    side: str = ""  # BUY, SELL
    order_type: str = "MARKET"  # MARKET, LIMIT
    
    quantity: float = 0.0
    price: Optional[float] = None
    
    status: str = "NEW"  # NEW, FILLED, PARTIAL, CANCELLED, REJECTED
    
    created_at: Optional[str] = None
    filled_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "run_id": self.run_id,
            "asset": self.asset,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": round(self.quantity, 8),
            "price": round(self.price, 8) if self.price else None,
            "status": self.status,
            "created_at": self.created_at,
            "filled_at": self.filled_at
        }


@dataclass
class SimulationFill:
    """
    Simulated fill in simulation.
    """
    fill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    run_id: str = ""
    
    asset: str = ""
    quantity: float = 0.0
    price: float = 0.0
    
    fee_usd: float = 0.0
    
    timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "run_id": self.run_id,
            "asset": self.asset,
            "quantity": round(self.quantity, 8),
            "price": round(self.price, 8),
            "fee_usd": round(self.fee_usd, 4),
            "timestamp": self.timestamp
        }


@dataclass
class SimulationPosition:
    """
    Simulated position in simulation.
    """
    run_id: str
    asset: str
    
    side: str = ""  # LONG, SHORT, FLAT
    size: float = 0.0
    entry_price: float = 0.0
    
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "asset": self.asset,
            "side": self.side,
            "size": round(self.size, 8),
            "entry_price": round(self.entry_price, 8),
            "current_price": round(self.current_price, 8),
            "unrealized_pnl": round(self.unrealized_pnl, 2)
        }
