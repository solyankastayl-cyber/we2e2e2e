"""
Microstructure Lab Module
=========================

Phase B - Realistic market simulation.
"""

from .types import *
from .engine import microstructure_engine, MicrostructureEngine
from .routes import router

__all__ = [
    "microstructure_engine",
    "MicrostructureEngine",
    "router"
]
