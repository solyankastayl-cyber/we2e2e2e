"""
Edge Research Lab Module
========================

Phase A - Deep edge research and analysis.
"""

from .types import *
from .engine import edge_research_engine, EdgeResearchEngine
from .routes import router

__all__ = [
    "edge_research_engine",
    "EdgeResearchEngine",
    "router"
]
