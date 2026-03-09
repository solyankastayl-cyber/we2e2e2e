"""
Phase 9.3E — Alpha Combination Engine (ACE)
===========================================

Mathematically optimizes strategy weights using:
- Mean-Variance Optimization
- Covariance Matrix
- Risk Parity
- Sharpe Maximization

Key formula: maximize μᵀw - λwᵀΣw

This layer optimizes HOW alphas are combined, not WHAT alphas do.
"""

from .service import AlphaCombinationService

__all__ = ['AlphaCombinationService']
