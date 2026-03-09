"""
Phase 9.3D — Portfolio Overlay Layer
=====================================

Capital management layer that doesn't change signals,
but optimizes position sizing through:

1. Volatility Targeting - stable portfolio risk
2. Conviction Weighting - size based on signal quality
3. Drawdown Risk Control - reduce risk in drawdowns

This layer transforms a trading system into a portfolio engine.
"""

from .service import PortfolioOverlayService

__all__ = ['PortfolioOverlayService']
