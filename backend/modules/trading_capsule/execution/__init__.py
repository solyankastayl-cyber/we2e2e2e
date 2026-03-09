"""
Execution Decision Layer (T3)
=============================

Signal to Order Intent routing.

Provides:
- Signal source abstraction
- Decision normalization
- Mode routing
- Intent building
- Preview mode
- Handoff to OMS
"""

from .execution_types import (
    ExecutionDecision,
    ExecutionContext,
    ExecutionAction,
    SignalSource,
    ExecutionPreview,
    ExecutionResult
)

from .execution_service import (
    execution_service,
    ExecutionService
)


__all__ = [
    # Types
    "ExecutionDecision",
    "ExecutionContext",
    "ExecutionAction",
    "SignalSource",
    "ExecutionPreview",
    "ExecutionResult",
    
    # Service
    "execution_service",
    "ExecutionService"
]
