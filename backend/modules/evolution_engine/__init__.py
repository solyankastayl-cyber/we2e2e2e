"""
Evolution Engine Module
=======================

Self-Evolving Quant Platform (SEQP).

The Evolution Engine transforms the system from a research framework
into a self-improving platform that automatically:
- Detects edge decay
- Analyzes decay reasons
- Adapts weights
- Creates mutations
- Selects winners

Usage:
    from modules.evolution_engine import evolution_engine
    
    # Run full cycle
    cycle = evolution_engine.run_cycle()
    
    # Or run phases individually
    signals = evolution_engine.observe(performances)
    analysis = evolution_engine.analyze(signals)
    mutations = evolution_engine.evolve(analysis)
    promoted = evolution_engine.select(mutations)
"""

from .types import (
    EvolutionAction,
    MutationType,
    DecayReason,
    EvolutionStatus,
    DecaySignal,
    Mutation,
    EvolutionCycle,
    EvolutionConfig,
    EvolutionMetrics
)

from .engine import EvolutionEngine, evolution_engine

from .routes import router


__all__ = [
    # Types
    "EvolutionAction",
    "MutationType",
    "DecayReason",
    "EvolutionStatus",
    "DecaySignal",
    "Mutation",
    "EvolutionCycle",
    "EvolutionConfig",
    "EvolutionMetrics",
    
    # Engine
    "EvolutionEngine",
    "evolution_engine",
    
    # Router
    "router"
]


print("[EvolutionEngine] Module loaded")
