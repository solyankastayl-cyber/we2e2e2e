"""
Cross-Asset Walk-Forward Engine
===============================

Phase 9.X — Universal research simulation environment.

This is not just a backtest — it's the core of the Research OS
that will later power the Alpha Factory.

Features:
- Time-sealed (no future leakage)
- Asset-agnostic core
- Policy-driven configuration
- Layer-aware simulation
- Reproducible runs with snapshots

Modules:
- types: Core data structures
- dataset_registry: Dataset metadata management
- asset_adapter: Asset-class normalization
- engine: Walk-forward core logic
- trade_simulator: Realistic trade execution
- metrics: 4-level metrics (trade, portfolio, strategy, governance)
- events: Governance event logging
- report: JSON + Markdown reports
- service: Service layer
- routes: API endpoints
"""

from .types import (
    AssetClass, SimMode, RunStatus, RebalanceFrequency,
    DatasetDescriptor, AssetAdapter, WalkForwardRun,
    SimulatedTrade, GovernanceEvent, WalkForwardReport
)
