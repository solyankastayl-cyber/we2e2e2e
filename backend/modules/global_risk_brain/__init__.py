"""
Global Risk Brain Module
========================

Phase 9.35 - Top-level risk controller.
"""

from .types import (
    RiskState, DetectorType, PolicyAction,
    RiskEnvelope, CapitalAllocation, DetectorSignal,
    RiskSnapshot, StateTransition, CrisisPolicy, GRBConfig,
    DEFAULT_ENVELOPES
)
from .engine import global_risk_brain, GlobalRiskBrain
from .routes import router

__all__ = [
    "RiskState", "DetectorType", "PolicyAction",
    "RiskEnvelope", "CapitalAllocation", "DetectorSignal",
    "RiskSnapshot", "StateTransition", "CrisisPolicy", "GRBConfig",
    "DEFAULT_ENVELOPES",
    "global_risk_brain", "GlobalRiskBrain",
    "router"
]
