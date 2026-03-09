"""
Strategy Runtime Module (T6)
============================

Strategy Runtime Engine для Trading Capsule.

Отвечает за:
- Регистрацию и управление стратегиями (плагинами)
- Передачу сигналов стратегиям
- Получение решений от стратегий
- Публикацию событий в Event Bus

T6 НЕ содержит торговую логику — он только оркестрирует стратегии.

Pipeline:
    Signal/Decision → T6 Strategy Runtime → T3 Execution Layer → T4 Risk → T2 OMS → Exchange

Usage:
    from modules.trading_capsule.strategy import strategy_engine
    
    # Регистрация стратегии
    strategy_engine.register(my_strategy)
    
    # Передача сигнала
    actions = await strategy_engine.process_signal(signal, context)
"""

from .strategy_types import (
    StrategyAction,
    StrategyContext,
    StrategyPlugin,
    StrategyState,
    StrategyStatus,
    ActionType,
    SignalType
)

from .strategy_registry import (
    StrategyRegistry,
    strategy_registry
)

from .strategy_state import (
    StrategyStateManager,
    strategy_state_manager
)

from .strategy_runtime import (
    StrategyRuntime,
    strategy_runtime
)

from .strategy_engine import (
    StrategyEngine,
    strategy_engine
)

from .strategy_routes import router as strategy_router

__all__ = [
    # Types
    "StrategyAction",
    "StrategyContext", 
    "StrategyPlugin",
    "StrategyState",
    "StrategyStatus",
    "ActionType",
    "SignalType",
    
    # Registry
    "StrategyRegistry",
    "strategy_registry",
    
    # State
    "StrategyStateManager",
    "strategy_state_manager",
    
    # Runtime
    "StrategyRuntime",
    "strategy_runtime",
    
    # Engine
    "StrategyEngine",
    "strategy_engine",
    
    # Routes
    "strategy_router"
]

print("[T6 Strategy Runtime] Module loaded")
