"""
Metrics Module (S1.4)
=====================

Post-simulation metrics and trade analysis.

S1.4A - Trade Normalization:
- Trade Builder (fills → trades)
- Trade Normalizer Service
- Trade Statistics

S1.4B - Performance Metrics (coming)
S1.4C - Risk Metrics (coming)
S1.4D - Metrics API (coming)
"""

from .trade_types import (
    TradeSide,
    TradeStatus,
    ClosedTrade,
    OpenPosition,
    TradeStats
)

from .trade_builder import (
    TradeBuilder,
    compute_trade_stats
)

from .trade_normalizer_service import (
    TradeNormalizerService,
    trade_normalizer_service
)

from .metrics_routes import router as metrics_router


__all__ = [
    # Types
    "TradeSide",
    "TradeStatus",
    "ClosedTrade",
    "OpenPosition",
    "TradeStats",
    
    # Builder
    "TradeBuilder",
    "compute_trade_stats",
    
    # Service
    "TradeNormalizerService",
    "trade_normalizer_service",
    
    # Routes
    "metrics_router"
]


print("[Metrics] Module loaded - S1.4A Trade Normalization Ready")
