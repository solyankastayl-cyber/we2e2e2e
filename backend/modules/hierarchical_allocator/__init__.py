"""
Phase 9.3F — Hierarchical Alpha Allocator
==========================================

Solves the Alpha Decay + Estimation Noise problem by:
1. Grouping strategies into families
2. Allocating risk budgets to families
3. Running intra-family optimization
4. Combining with cross-family allocation

This allows scaling to 50-100+ alphas without optimizer collapse.
"""

from .service import HierarchicalAllocatorService

__all__ = ['HierarchicalAllocatorService']
