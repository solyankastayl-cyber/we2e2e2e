"""
Terminal Backend (T5)
=====================

Admin monitoring and control layer for Trading Capsule.

Provides:
- Account monitoring
- Position monitoring
- Order monitoring
- PnL tracking
- Execution logs
- Risk monitoring
- Averaging monitoring
- System state
- Admin actions
"""

from .terminal_types import (
    AccountOverview,
    PositionView,
    OrderView,
    PnLView,
    DailyPnLRecord,
    ExecutionLogEntry,
    RiskOverview,
    AveragingView,
    TradingSystemState,
    ActionResult,
    EventType
)

from .terminal_service import (
    terminal_service,
    TerminalService
)

from .terminal_routes import router as terminal_router


__all__ = [
    # Types
    "AccountOverview",
    "PositionView",
    "OrderView",
    "PnLView",
    "DailyPnLRecord",
    "ExecutionLogEntry",
    "RiskOverview",
    "AveragingView",
    "TradingSystemState",
    "ActionResult",
    "EventType",
    
    # Service
    "terminal_service",
    "TerminalService",
    
    # Router
    "terminal_router"
]
