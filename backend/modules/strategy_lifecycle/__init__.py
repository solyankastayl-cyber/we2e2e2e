"""
Strategy Lifecycle Engine Module
================================

Manages the complete lifecycle of strategies from birth to death.

States:
- CANDIDATE: Just created
- SANDBOX: Local testing
- VALIDATED: Passed validation
- SHADOW: Quasi-production
- LIMITED: Limited exposure
- CORE: Main battle-tested
- MATURE: Long-term proven
- DEGRADED: Edge weakening
- DISABLED: Turned off
- ARCHIVED: Retired

Usage:
    from modules.strategy_lifecycle import strategy_lifecycle_engine
    
    # Register strategy
    record = strategy_lifecycle_engine.register(
        strategy_id="strat_001",
        alpha_id="alpha_momentum_v1",
        name="Momentum V1",
        family="MOMENTUM"
    )
    
    # Promote
    strategy_lifecycle_engine.promote("strat_001", "Tournament winner")
    
    # Evaluate
    result = strategy_lifecycle_engine.evaluate("strat_001")
"""

from .types import (
    LifecycleState,
    StrategyAge,
    DeathQuality,
    ALLOWED_TRANSITIONS,
    STATE_CONFIG,
    LifecycleScores,
    LifecycleTransition,
    StrategyLifecycleRecord,
    LifecycleMetrics,
    is_transition_allowed,
    get_state_config,
    calculate_age_category
)

from .engine import StrategyLifecycleEngine, strategy_lifecycle_engine

from .routes import router


__all__ = [
    # Types
    "LifecycleState",
    "StrategyAge",
    "DeathQuality",
    "ALLOWED_TRANSITIONS",
    "STATE_CONFIG",
    "LifecycleScores",
    "LifecycleTransition",
    "StrategyLifecycleRecord",
    "LifecycleMetrics",
    "is_transition_allowed",
    "get_state_config",
    "calculate_age_category",
    
    # Engine
    "StrategyLifecycleEngine",
    "strategy_lifecycle_engine",
    
    # Router
    "router"
]


print("[StrategyLifecycle] Module loaded")
