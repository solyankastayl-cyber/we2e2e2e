"""
API Routes Module
================

Modular API routers for the TA Engine.
Each module has its own router file for better maintainability.
"""

from fastapi import APIRouter

# Import all routers
from .admin_cockpit import router as admin_cockpit_router
from .meta_strategy import router as meta_strategy_router

__all__ = [
    "admin_cockpit_router",
    "meta_strategy_router",
]
