"""
Research Memory Module
======================

Phase 9.32 - Knowledge base for tracking research failures.
"""

from .types import (
    MemoryEntry, MemoryPattern, MemorySummary, MemoryMatch,
    MemoryCategory, MemoryOutcome, MemoryImportance
)
from .engine import research_memory, ResearchMemoryEngine
from .service import research_memory_service, ResearchMemoryService
from .routes import router

__all__ = [
    "MemoryEntry",
    "MemoryPattern",
    "MemorySummary",
    "MemoryMatch",
    "MemoryCategory",
    "MemoryOutcome",
    "MemoryImportance",
    "research_memory",
    "ResearchMemoryEngine",
    "research_memory_service",
    "ResearchMemoryService",
    "router"
]
