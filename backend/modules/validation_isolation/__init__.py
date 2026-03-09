"""
Phase 8.1: Validation Isolation Layer
Prevents validation contamination by ensuring time-sealed environments.
"""

from .types import (
    ValidationRunContext,
    ValidationSnapshot,
    SnapshotType,
    IsolationMode,
    IsolationViolation,
    IsolationReport
)
from .context import ValidationContextBuilder
from .snapshots import SnapshotManager
from .guard import IsolationGuard
from .service import ValidationIsolationService

__all__ = [
    'ValidationRunContext',
    'ValidationSnapshot',
    'SnapshotType',
    'IsolationMode',
    'IsolationViolation',
    'IsolationReport',
    'ValidationContextBuilder',
    'SnapshotManager',
    'IsolationGuard',
    'ValidationIsolationService'
]
