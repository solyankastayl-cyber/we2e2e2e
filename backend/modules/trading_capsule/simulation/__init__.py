"""
Trading Simulation Module (S1)
==============================

Trading Simulation Engine for research-grade backtesting.

S1.1 - Simulation Core:
- Run Manager
- State Manager  
- Determinism Guard

S1.2 - Market Replay Engine:
- Dataset Service
- Cursor Service
- Step Orchestrator
- Replay Driver

Architecture:
    Market Replay → Strategy Runtime (T6) → Execution (T3) → Risk (T4) → OMS (T2) → Simulated Broker
"""

from .simulation_types import (
    # Enums
    SimulationStatus,
    CapitalProfile,
    MarketType,
    Timeframe,
    ReplayMode,
    ReplayStatus,
    SimulationStepStatus,
    
    # Capital
    CAPITAL_PROFILE_VALUES,
    get_capital_for_profile,
    
    # Entities
    SimulationRun,
    SimulationState,
    SimulationFingerprint,
    FrozenSimulationConfig,
    MarketCandle,
    MarketDataset,
    ReplayCursor,
    ReplayState,
    SimulationStep,
    MarketTickEvent,
    SimulationOrder,
    SimulationFill,
    SimulationPosition
)

from .simulation_run_service import (
    SimulationRunService,
    simulation_run_service
)

from .simulation_state_service import (
    SimulationStateService,
    simulation_state_service
)

from .simulation_determinism_service import (
    SimulationDeterminismService,
    simulation_determinism_service
)

from .replay import (
    market_dataset_service,
    replay_cursor_service,
    step_orchestrator_service,
    replay_driver_service
)

from .simulation_engine import (
    SimulationEngine,
    simulation_engine
)

from .simulation_routes import router as simulation_router


__all__ = [
    # Enums
    "SimulationStatus",
    "CapitalProfile",
    "MarketType",
    "Timeframe",
    "ReplayMode",
    "ReplayStatus",
    "SimulationStepStatus",
    
    # Capital
    "CAPITAL_PROFILE_VALUES",
    "get_capital_for_profile",
    
    # Entities
    "SimulationRun",
    "SimulationState",
    "SimulationFingerprint",
    "FrozenSimulationConfig",
    "MarketCandle",
    "MarketDataset",
    "ReplayCursor",
    "ReplayState",
    "SimulationStep",
    "MarketTickEvent",
    "SimulationOrder",
    "SimulationFill",
    "SimulationPosition",
    
    # Services (S1.1)
    "SimulationRunService",
    "simulation_run_service",
    "SimulationStateService",
    "simulation_state_service",
    "SimulationDeterminismService",
    "simulation_determinism_service",
    
    # Replay Services (S1.2)
    "market_dataset_service",
    "replay_cursor_service",
    "step_orchestrator_service",
    "replay_driver_service",
    
    # Engine
    "SimulationEngine",
    "simulation_engine",
    
    # Routes
    "simulation_router"
]


print("[Simulation] Module loaded - S1.1/S1.2 Ready")
