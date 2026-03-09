"""
Risk Control Layer (T4)
=======================

Pre-trade and runtime risk management.

Provides:
- Pre-trade validation
- Exposure checks
- Position sizing limits
- Daily drawdown guard
- Averaging ladder constraints
- Kill switch integration
- Risk verdicts
"""

from .risk_types import (
    RiskProfile,
    RiskCheckContext,
    RiskVerdict,
    RiskSeverity,
    AveragingState
)

from .risk_service import (
    risk_service,
    RiskService
)


__all__ = [
    # Types
    "RiskProfile",
    "RiskCheckContext",
    "RiskVerdict",
    "RiskSeverity",
    "AveragingState",
    
    # Service
    "risk_service",
    "RiskService"
]
