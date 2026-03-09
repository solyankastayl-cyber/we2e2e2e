"""
Event Bus Types
===============

Core data structures for the Event Bus system.
Provides loosely-coupled communication between modules.

Event Categories:
- RESEARCH: research_cycle_*, feature_*, alpha_*
- PORTFOLIO: portfolio_*, strategy_weight_*, family_budget_*
- RISK: risk_state_*, drawdown_*, exposure_*
- EXECUTION: trade_*, slippage_*, gap_*
- GOVERNANCE: policy_*, dataset_*, experiment_*
- SYSTEM: system_*, bootstrap_*, shutdown_*
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


class EventCategory(str, Enum):
    """Event categories for taxonomy"""
    RESEARCH = "RESEARCH"
    PORTFOLIO = "PORTFOLIO"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    GOVERNANCE = "GOVERNANCE"
    SYSTEM = "SYSTEM"


class EventType(str, Enum):
    """Standard event types in the system"""
    # Research events
    RESEARCH_CYCLE_STARTED = "research_cycle_started"
    RESEARCH_CYCLE_COMPLETED = "research_cycle_completed"
    FEATURE_GENERATED = "feature_generated"
    FEATURE_REJECTED = "feature_rejected"
    ALPHA_GENERATED = "alpha_generated"
    ALPHA_PROMOTED = "alpha_promoted"
    ALPHA_REJECTED = "alpha_rejected"
    ALPHA_DEMOTED = "alpha_demoted"
    
    # Portfolio events
    PORTFOLIO_REBALANCED = "portfolio_rebalanced"
    STRATEGY_WEIGHT_CHANGED = "strategy_weight_changed"
    FAMILY_BUDGET_ADJUSTED = "family_budget_adjusted"
    SHADOW_PORTFOLIO_UPDATED = "shadow_portfolio_updated"
    
    # Risk events
    RISK_STATE_CHANGED = "risk_state_changed"
    DRAWDOWN_THRESHOLD_HIT = "drawdown_threshold_hit"
    EXPOSURE_REDUCED = "exposure_reduced"
    VOLATILITY_SPIKE_DETECTED = "volatility_spike_detected"
    CORRELATION_SPIKE_DETECTED = "correlation_spike_detected"
    
    # Execution events
    TRADE_OPENED = "trade_opened"
    TRADE_CLOSED = "trade_closed"
    SLIPPAGE_DETECTED = "slippage_detected"
    GAP_EVENT_DETECTED = "gap_event_detected"
    FILL_REJECTED = "fill_rejected"
    
    # Strategy events (T6)
    STRATEGY_REGISTERED = "strategy_registered"
    STRATEGY_UNREGISTERED = "strategy_unregistered"
    STRATEGY_ENABLED = "strategy_enabled"
    STRATEGY_DISABLED = "strategy_disabled"
    STRATEGY_PAUSED = "strategy_paused"
    STRATEGY_RESUMED = "strategy_resumed"
    STRATEGY_ACTION_GENERATED = "strategy_action_generated"
    STRATEGY_ERROR = "strategy_error"
    
    # Governance events
    POLICY_UPDATED = "policy_updated"
    DATASET_REGISTERED = "dataset_registered"
    EXPERIMENT_STARTED = "experiment_started"
    EXPERIMENT_COMPLETED = "experiment_completed"
    EXPERIMENT_FAILED = "experiment_failed"
    
    # Simulation events (S1)
    SIMULATION_RUN_CREATED = "simulation_run_created"
    SIMULATION_RUN_STARTED = "simulation_run_started"
    SIMULATION_RUN_PAUSED = "simulation_run_paused"
    SIMULATION_RUN_RESUMED = "simulation_run_resumed"
    SIMULATION_RUN_COMPLETED = "simulation_run_completed"
    SIMULATION_RUN_FAILED = "simulation_run_failed"
    SIMULATION_REPLAY_STARTED = "simulation_replay_started"
    SIMULATION_REPLAY_STEP = "simulation_replay_step"
    SIMULATION_REPLAY_PAUSED = "simulation_replay_paused"
    SIMULATION_REPLAY_FINISHED = "simulation_replay_finished"
    
    # System events
    SYSTEM_STARTED = "system_started"
    SYSTEM_SHUTDOWN = "system_shutdown"
    MODULE_LOADED = "module_loaded"
    MODULE_ERROR = "module_error"
    BOOTSTRAP_COMPLETED = "bootstrap_completed"


# Map event types to categories
EVENT_CATEGORY_MAP: Dict[EventType, EventCategory] = {
    # Research
    EventType.RESEARCH_CYCLE_STARTED: EventCategory.RESEARCH,
    EventType.RESEARCH_CYCLE_COMPLETED: EventCategory.RESEARCH,
    EventType.FEATURE_GENERATED: EventCategory.RESEARCH,
    EventType.FEATURE_REJECTED: EventCategory.RESEARCH,
    EventType.ALPHA_GENERATED: EventCategory.RESEARCH,
    EventType.ALPHA_PROMOTED: EventCategory.RESEARCH,
    EventType.ALPHA_REJECTED: EventCategory.RESEARCH,
    EventType.ALPHA_DEMOTED: EventCategory.RESEARCH,
    
    # Portfolio
    EventType.PORTFOLIO_REBALANCED: EventCategory.PORTFOLIO,
    EventType.STRATEGY_WEIGHT_CHANGED: EventCategory.PORTFOLIO,
    EventType.FAMILY_BUDGET_ADJUSTED: EventCategory.PORTFOLIO,
    EventType.SHADOW_PORTFOLIO_UPDATED: EventCategory.PORTFOLIO,
    
    # Risk
    EventType.RISK_STATE_CHANGED: EventCategory.RISK,
    EventType.DRAWDOWN_THRESHOLD_HIT: EventCategory.RISK,
    EventType.EXPOSURE_REDUCED: EventCategory.RISK,
    EventType.VOLATILITY_SPIKE_DETECTED: EventCategory.RISK,
    EventType.CORRELATION_SPIKE_DETECTED: EventCategory.RISK,
    
    # Execution
    EventType.TRADE_OPENED: EventCategory.EXECUTION,
    EventType.TRADE_CLOSED: EventCategory.EXECUTION,
    EventType.SLIPPAGE_DETECTED: EventCategory.EXECUTION,
    EventType.GAP_EVENT_DETECTED: EventCategory.EXECUTION,
    EventType.FILL_REJECTED: EventCategory.EXECUTION,
    
    # Strategy (T6)
    EventType.STRATEGY_REGISTERED: EventCategory.EXECUTION,
    EventType.STRATEGY_UNREGISTERED: EventCategory.EXECUTION,
    EventType.STRATEGY_ENABLED: EventCategory.EXECUTION,
    EventType.STRATEGY_DISABLED: EventCategory.EXECUTION,
    EventType.STRATEGY_PAUSED: EventCategory.EXECUTION,
    EventType.STRATEGY_RESUMED: EventCategory.EXECUTION,
    EventType.STRATEGY_ACTION_GENERATED: EventCategory.EXECUTION,
    EventType.STRATEGY_ERROR: EventCategory.EXECUTION,
    
    # Governance
    EventType.POLICY_UPDATED: EventCategory.GOVERNANCE,
    EventType.DATASET_REGISTERED: EventCategory.GOVERNANCE,
    EventType.EXPERIMENT_STARTED: EventCategory.GOVERNANCE,
    EventType.EXPERIMENT_COMPLETED: EventCategory.GOVERNANCE,
    EventType.EXPERIMENT_FAILED: EventCategory.GOVERNANCE,
    
    # System
    EventType.SYSTEM_STARTED: EventCategory.SYSTEM,
    EventType.SYSTEM_SHUTDOWN: EventCategory.SYSTEM,
    EventType.MODULE_LOADED: EventCategory.SYSTEM,
    EventType.MODULE_ERROR: EventCategory.SYSTEM,
    EventType.BOOTSTRAP_COMPLETED: EventCategory.SYSTEM,
}


@dataclass
class SystemEvent:
    """
    Core event structure.
    All events in the system follow this format.
    """
    id: str
    type: str
    source: str
    timestamp: int  # Unix timestamp in milliseconds
    payload: Dict[str, Any]
    category: str = ""
    correlation_id: Optional[str] = None  # For tracking related events
    
    def __post_init__(self):
        """Set category if not provided"""
        if not self.category:
            try:
                event_type = EventType(self.type)
                self.category = EVENT_CATEGORY_MAP.get(event_type, EventCategory.SYSTEM).value
            except ValueError:
                self.category = EventCategory.SYSTEM.value
    
    @classmethod
    def create(
        cls,
        event_type: str,
        source: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> "SystemEvent":
        """Factory method to create a new event"""
        return cls(
            id=f"evt_{uuid.uuid4().hex[:16]}",
            type=event_type,
            source=source,
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            payload=payload,
            correlation_id=correlation_id
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/transmission"""
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "category": self.category,
            "correlation_id": self.correlation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemEvent":
        """Create from dictionary"""
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            source=data.get("source", ""),
            timestamp=data.get("timestamp", 0),
            payload=data.get("payload", {}),
            category=data.get("category", ""),
            correlation_id=data.get("correlation_id")
        )


@dataclass
class EventSubscription:
    """Subscription to event types"""
    id: str
    event_types: List[str]  # Event types to subscribe to
    handler_name: str  # Name of the handler module
    created_at: int
    active: bool = True
    
    @classmethod
    def create(cls, event_types: List[str], handler_name: str) -> "EventSubscription":
        return cls(
            id=f"sub_{uuid.uuid4().hex[:12]}",
            event_types=event_types,
            handler_name=handler_name,
            created_at=int(datetime.now(timezone.utc).timestamp() * 1000)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_types": self.event_types,
            "handler_name": self.handler_name,
            "created_at": self.created_at,
            "active": self.active
        }


@dataclass
class EventStats:
    """Statistics about event processing"""
    total_published: int = 0
    total_dispatched: int = 0
    events_by_category: Dict[str, int] = field(default_factory=dict)
    events_by_type: Dict[str, int] = field(default_factory=dict)
    last_event_at: Optional[int] = None
    errors: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_published": self.total_published,
            "total_dispatched": self.total_dispatched,
            "events_by_category": self.events_by_category,
            "events_by_type": self.events_by_type,
            "last_event_at": self.last_event_at,
            "errors": self.errors
        }


# Handler type for event callbacks
EventHandler = Callable[[SystemEvent], None]
