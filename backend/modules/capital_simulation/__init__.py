"""
Capital Simulation Module
=========================

Phase 9.36 - Capital-aware simulation engine.
"""

from .types import (
    CapitalTier, AssetClass,
    CapitalProfile, LiquidityProfile, SlippageModel, FeeModel,
    TradeExecution, StrategySimulation, CapacityAnalysis,
    DEFAULT_CAPITAL_PROFILES, DEFAULT_LIQUIDITY
)
from .engine import capital_simulation_engine, CapitalSimulationEngine
from .routes import router

__all__ = [
    "CapitalTier", "AssetClass",
    "CapitalProfile", "LiquidityProfile", "SlippageModel", "FeeModel",
    "TradeExecution", "StrategySimulation", "CapacityAnalysis",
    "DEFAULT_CAPITAL_PROFILES", "DEFAULT_LIQUIDITY",
    "capital_simulation_engine", "CapitalSimulationEngine",
    "router"
]
