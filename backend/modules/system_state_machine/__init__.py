"""
System State Machine Module
===========================

Global state control for the Quant Research OS.

States:
- INITIALIZING: System loading
- RESEARCH: Research mode, no trading
- SIMULATION: Simulation with shadow portfolio
- ACTIVE: Full system active
- STRESS: Reduced exposure due to volatility
- CRISIS: Defensive mode due to drawdown
- PAUSED: All processes stopped
- MAINTENANCE: System maintenance

Usage:
    from modules.system_state_machine import get_state_machine, SystemState
    
    ssm = get_state_machine()
    
    # Get current state
    state = ssm.current_state
    
    # Transition
    ssm.transition(SystemState.ACTIVE, reason="Starting live trading", triggered_by="admin")
    
    # Check if action allowed
    if ssm.is_action_allowed("feature_factory"):
        # Do feature factory
        pass
"""

from .types import (
    SystemState,
    StateRecord,
    StateTransition,
    ALLOWED_TRANSITIONS,
    STATE_CONFIG,
    is_transition_allowed,
    get_state_config
)

from .engine import SystemStateMachine, get_state_machine

from .routes import router


__all__ = [
    # Types
    "SystemState",
    "StateRecord",
    "StateTransition",
    "ALLOWED_TRANSITIONS",
    "STATE_CONFIG",
    "is_transition_allowed",
    "get_state_config",
    
    # Engine
    "SystemStateMachine",
    "get_state_machine",
    
    # Router
    "router"
]


print("[SystemStateMachine] Module loaded")
