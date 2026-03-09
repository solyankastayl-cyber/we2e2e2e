"""
System State Machine Types
==========================

Global system states and transitions.
The system can only be in ONE state at a time.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid


class SystemState(str, Enum):
    """
    Global system states.
    Each state determines what the system can and cannot do.
    """
    INITIALIZING = "INITIALIZING"   # System loading datasets, policies, strategies
    RESEARCH = "RESEARCH"           # Feature Factory, Mutation, Research Loop active
    SIMULATION = "SIMULATION"       # Walk-forward, shadow portfolio, stress lab
    ACTIVE = "ACTIVE"               # Full system active, portfolio, risk, execution
    STRESS = "STRESS"               # Volatility spike, reduced exposure
    CRISIS = "CRISIS"               # Major drawdown, defensive mode
    PAUSED = "PAUSED"               # All processes stopped by admin
    MAINTENANCE = "MAINTENANCE"     # Dataset updates, policy changes, upgrades


# Allowed state transitions
# Key: current state, Value: set of states you can transition TO
ALLOWED_TRANSITIONS: Dict[SystemState, Set[SystemState]] = {
    SystemState.INITIALIZING: {SystemState.RESEARCH, SystemState.ACTIVE, SystemState.MAINTENANCE},
    SystemState.RESEARCH: {SystemState.SIMULATION, SystemState.ACTIVE, SystemState.PAUSED, SystemState.MAINTENANCE},
    SystemState.SIMULATION: {SystemState.ACTIVE, SystemState.RESEARCH, SystemState.PAUSED, SystemState.MAINTENANCE},
    SystemState.ACTIVE: {SystemState.STRESS, SystemState.PAUSED, SystemState.MAINTENANCE, SystemState.RESEARCH},
    SystemState.STRESS: {SystemState.CRISIS, SystemState.ACTIVE, SystemState.PAUSED},
    SystemState.CRISIS: {SystemState.STRESS, SystemState.ACTIVE, SystemState.PAUSED},
    SystemState.PAUSED: {SystemState.ACTIVE, SystemState.RESEARCH, SystemState.MAINTENANCE, SystemState.SIMULATION},
    SystemState.MAINTENANCE: {SystemState.INITIALIZING, SystemState.ACTIVE, SystemState.RESEARCH},
}


# State configurations - what's enabled in each state
STATE_CONFIG: Dict[SystemState, Dict[str, Any]] = {
    SystemState.INITIALIZING: {
        "description": "System loading, no trading",
        "research_enabled": False,
        "simulation_enabled": False,
        "trading_enabled": False,
        "portfolio_active": False,
        "risk_active": False,
        "max_exposure": 0.0,
        "allowed_actions": ["bootstrap", "load_config"]
    },
    SystemState.RESEARCH: {
        "description": "Research mode, no live trading",
        "research_enabled": True,
        "simulation_enabled": True,
        "trading_enabled": False,
        "portfolio_active": False,
        "risk_active": True,
        "max_exposure": 0.0,
        "allowed_actions": ["feature_factory", "mutation", "tournament", "backtest"]
    },
    SystemState.SIMULATION: {
        "description": "Simulation mode with shadow portfolio",
        "research_enabled": True,
        "simulation_enabled": True,
        "trading_enabled": False,
        "portfolio_active": True,
        "risk_active": True,
        "max_exposure": 0.0,
        "allowed_actions": ["walk_forward", "shadow_portfolio", "stress_lab"]
    },
    SystemState.ACTIVE: {
        "description": "Full system active",
        "research_enabled": True,
        "simulation_enabled": True,
        "trading_enabled": True,
        "portfolio_active": True,
        "risk_active": True,
        "max_exposure": 1.0,
        "max_leverage": 1.5,
        "allowed_actions": ["all"]
    },
    SystemState.STRESS: {
        "description": "Stress mode - reduced exposure",
        "research_enabled": False,
        "simulation_enabled": False,
        "trading_enabled": True,
        "portfolio_active": True,
        "risk_active": True,
        "max_exposure": 0.6,
        "max_leverage": 1.0,
        "disable_experimental": True,
        "allowed_actions": ["reduce_exposure", "close_positions"]
    },
    SystemState.CRISIS: {
        "description": "Crisis mode - defensive only",
        "research_enabled": False,
        "simulation_enabled": False,
        "trading_enabled": True,
        "portfolio_active": True,
        "risk_active": True,
        "max_exposure": 0.3,
        "max_leverage": 0.6,
        "disable_experimental": True,
        "disable_tactical": True,
        "increase_cash": True,
        "allowed_actions": ["close_positions", "hedge"]
    },
    SystemState.PAUSED: {
        "description": "All processes stopped",
        "research_enabled": False,
        "simulation_enabled": False,
        "trading_enabled": False,
        "portfolio_active": False,
        "risk_active": True,
        "max_exposure": 0.0,
        "allowed_actions": ["resume", "status"]
    },
    SystemState.MAINTENANCE: {
        "description": "System maintenance mode",
        "research_enabled": False,
        "simulation_enabled": False,
        "trading_enabled": False,
        "portfolio_active": False,
        "risk_active": False,
        "max_exposure": 0.0,
        "allowed_actions": ["update_dataset", "update_policy", "upgrade"]
    },
}


@dataclass
class StateRecord:
    """Record of a state"""
    state: str
    timestamp: int
    reason: Optional[str] = None
    triggered_by: Optional[str] = None  # Module/user that triggered
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "triggered_by": self.triggered_by
        }


@dataclass
class StateTransition:
    """Record of a state transition"""
    id: str
    from_state: str
    to_state: str
    timestamp: int
    reason: str
    triggered_by: str
    success: bool = True
    error: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        from_state: str,
        to_state: str,
        reason: str,
        triggered_by: str
    ) -> "StateTransition":
        return cls(
            id=f"trans_{uuid.uuid4().hex[:12]}",
            from_state=from_state,
            to_state=to_state,
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            reason=reason,
            triggered_by=triggered_by
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "success": self.success,
            "error": self.error
        }


def is_transition_allowed(from_state: SystemState, to_state: SystemState) -> bool:
    """Check if a state transition is allowed"""
    allowed = ALLOWED_TRANSITIONS.get(from_state, set())
    return to_state in allowed


def get_state_config(state: SystemState) -> Dict[str, Any]:
    """Get configuration for a state"""
    return STATE_CONFIG.get(state, {})
