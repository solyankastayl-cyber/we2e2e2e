"""
Phase 9.3A — Structural Bias Layer
===================================

Recognizes fundamental market asymmetry on equities.
SPX historically has structural long bias - this layer adjusts 
trade permissions accordingly.

Key concept: Don't change strategies, change PERMISSION to trade direction.
"""

from .service import StructuralBiasService

__all__ = ['StructuralBiasService']
