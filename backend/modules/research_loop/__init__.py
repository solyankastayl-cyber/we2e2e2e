"""
Research Loop Module
====================

Phase 9.33 - Automated research cycle engine.
"""

from .types import (
    LoopConfig, LoopCycleResult, LoopState, LoopEvent, LoopMetrics,
    LoopPhase, LoopMode, LoopStatus
)
from .engine import research_loop_engine, ResearchLoopEngine
from .routes import router

__all__ = [
    "LoopConfig",
    "LoopCycleResult",
    "LoopState",
    "LoopEvent",
    "LoopMetrics",
    "LoopPhase",
    "LoopMode",
    "LoopStatus",
    "research_loop_engine",
    "ResearchLoopEngine",
    "router"
]
