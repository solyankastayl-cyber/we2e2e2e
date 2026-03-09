"""
Control Backend Module (P0-3)
=============================

Final control layer for the Quant Research OS.

Provides:
- System monitoring
- Strategy monitoring
- Research monitoring
- Risk monitoring
- Admin control actions
- Admin audit trail

All endpoints in one unified module.
"""

from .types import (
    AdminAction,
    AdminActionType,
    SystemHealthStatus,
    SystemMetrics,
    StrategyHealth,
    StrategyDecay,
    RiskExposure,
    RiskAlert
)

from .service import control_backend_service, ControlBackendService

from .routes import router


__all__ = [
    # Types
    "AdminAction",
    "AdminActionType",
    "SystemHealthStatus",
    "SystemMetrics",
    "StrategyHealth",
    "StrategyDecay",
    "RiskExposure",
    "RiskAlert",
    
    # Service
    "control_backend_service",
    "ControlBackendService",
    
    # Router
    "router"
]


print("[ControlBackend] P0-3 Module loaded")
