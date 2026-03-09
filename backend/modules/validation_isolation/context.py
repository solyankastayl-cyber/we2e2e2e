"""
Phase 8.1: Validation Context Builder
Builds and manages ValidationRunContext for isolated validation runs.
"""
import time
from typing import Dict, List, Optional, Any

from .types import (
    ValidationRunContext,
    ValidationSnapshot,
    SnapshotType,
    IsolationMode,
    ISOLATION_CONFIG
)
from .snapshots import SnapshotManager


class ValidationContextBuilder:
    """
    Builds ValidationRunContext with frozen snapshots.
    
    Ensures all validation runs operate in isolated environments
    with no access to future data or live system state.
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or ISOLATION_CONFIG
        self.snapshot_manager = SnapshotManager(db, config)
        self._active_contexts: Dict[str, ValidationRunContext] = {}
    
    def build_context(
        self,
        symbol: str,
        timeframe: str,
        cutoff_time: int,
        mode: IsolationMode = IsolationMode.HISTORICAL_FAITHFUL,
        strategies: Optional[List[Dict]] = None,
        memory_state: Optional[Dict] = None,
        metabrain_config: Optional[Dict] = None,
        thresholds: Optional[Dict] = None,
        discovery_state: Optional[Dict] = None,
        system_config: Optional[Dict] = None
    ) -> ValidationRunContext:
        """
        Build a complete validation context with all required snapshots.
        
        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            timeframe: Timeframe (e.g., 4h)
            cutoff_time: Unix timestamp ms - no data beyond this point
            mode: Isolation mode (historical_faithful or frozen_config)
            strategies: Current strategies to snapshot
            memory_state: Current memory state to snapshot
            metabrain_config: Current metabrain config to snapshot
            thresholds: Current thresholds to snapshot
            discovery_state: Current discovery state to snapshot
            system_config: Current system config to snapshot
            
        Returns:
            Fully initialized ValidationRunContext
        """
        now = int(time.time() * 1000)
        run_id = self._generate_run_id(symbol, timeframe, cutoff_time)
        
        # Create snapshots for all dependencies
        strategy_snapshot = self.snapshot_manager.create_snapshot(
            SnapshotType.STRATEGY,
            strategies or self._get_mock_strategies(),
            cutoff_time,
            {"symbol": symbol, "timeframe": timeframe}
        )
        
        memory_snapshot = self.snapshot_manager.create_snapshot(
            SnapshotType.MEMORY,
            memory_state or self._get_mock_memory_state(),
            cutoff_time,
            {"symbol": symbol, "timeframe": timeframe}
        )
        
        metabrain_snapshot = self.snapshot_manager.create_snapshot(
            SnapshotType.METABRAIN,
            metabrain_config or self._get_mock_metabrain_config(),
            cutoff_time,
            {"mode": mode.value}
        )
        
        threshold_snapshot = self.snapshot_manager.create_snapshot(
            SnapshotType.THRESHOLD,
            thresholds or self._get_mock_thresholds(),
            cutoff_time
        )
        
        discovery_snapshot = self.snapshot_manager.create_snapshot(
            SnapshotType.DISCOVERY,
            discovery_state or self._get_mock_discovery_state(),
            cutoff_time
        )
        
        config_snapshot = self.snapshot_manager.create_snapshot(
            SnapshotType.CONFIG,
            system_config or self._get_mock_config(),
            cutoff_time
        )
        
        # Build context
        context = ValidationRunContext(
            run_id=run_id,
            symbol=symbol,
            timeframe=timeframe,
            cutoff_time=cutoff_time,
            strategy_snapshot_id=strategy_snapshot.snapshot_id,
            memory_snapshot_id=memory_snapshot.snapshot_id,
            metabrain_snapshot_id=metabrain_snapshot.snapshot_id,
            config_snapshot_id=config_snapshot.snapshot_id,
            threshold_snapshot_id=threshold_snapshot.snapshot_id,
            discovery_snapshot_id=discovery_snapshot.snapshot_id,
            mode=mode,
            isolation_passed=False,  # Will be set by IsolationGuard
            violations=[],
            created_at=now,
            metadata={
                "builder_version": "v1",
                "snapshot_count": 6
            }
        )
        
        # Store context
        if self.db:
            self._store_context(context)
        
        # Cache locally
        self._active_contexts[run_id] = context
        
        return context
    
    def get_context(self, run_id: str) -> Optional[ValidationRunContext]:
        """Retrieve a validation context by run ID"""
        if run_id in self._active_contexts:
            return self._active_contexts[run_id]
        
        if self.db:
            return self._load_context(run_id)
        
        return None
    
    def get_snapshot_for_context(
        self,
        context: ValidationRunContext,
        snapshot_type: SnapshotType
    ) -> Optional[ValidationSnapshot]:
        """
        Get a specific snapshot for a validation context.
        
        Args:
            context: The validation context
            snapshot_type: Type of snapshot to retrieve
            
        Returns:
            The requested snapshot or None
        """
        snapshot_id_map = {
            SnapshotType.STRATEGY: context.strategy_snapshot_id,
            SnapshotType.MEMORY: context.memory_snapshot_id,
            SnapshotType.METABRAIN: context.metabrain_snapshot_id,
            SnapshotType.CONFIG: context.config_snapshot_id,
            SnapshotType.THRESHOLD: context.threshold_snapshot_id,
            SnapshotType.DISCOVERY: context.discovery_snapshot_id
        }
        
        snapshot_id = snapshot_id_map.get(snapshot_type)
        if not snapshot_id:
            return None
        
        return self.snapshot_manager.get_snapshot(snapshot_id)
    
    def mark_started(self, run_id: str) -> bool:
        """Mark a validation run as started"""
        context = self.get_context(run_id)
        if not context:
            return False
        
        context.started_at = int(time.time() * 1000)
        
        if self.db:
            self._update_context(context)
        
        return True
    
    def mark_completed(
        self,
        run_id: str,
        passed: bool,
        violations: List = None
    ) -> bool:
        """Mark a validation run as completed"""
        context = self.get_context(run_id)
        if not context:
            return False
        
        context.completed_at = int(time.time() * 1000)
        context.isolation_passed = passed
        if violations:
            context.violations = violations
        
        if self.db:
            self._update_context(context)
        
        return True
    
    def list_contexts(
        self,
        symbol: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List recent validation contexts.
        
        Args:
            symbol: Filter by symbol (optional)
            limit: Maximum number to return
            
        Returns:
            List of context summaries
        """
        if not self.db:
            contexts = list(self._active_contexts.values())
            if symbol:
                contexts = [c for c in contexts if c.symbol == symbol]
            contexts = sorted(contexts, key=lambda c: c.created_at, reverse=True)[:limit]
            return [
                {
                    "runId": c.run_id,
                    "symbol": c.symbol,
                    "timeframe": c.timeframe,
                    "cutoffTime": c.cutoff_time,
                    "mode": c.mode.value,
                    "isolationPassed": c.isolation_passed,
                    "createdAt": c.created_at
                }
                for c in contexts
            ]
        
        collection = self.config.get("collections", {}).get("contexts", "ta_validation_context")
        query = {}
        if symbol:
            query["symbol"] = symbol
        
        docs = self.db[collection].find(query).sort("created_at", -1).limit(limit)
        
        return [
            {
                "runId": doc.get("run_id"),
                "symbol": doc.get("symbol"),
                "timeframe": doc.get("timeframe"),
                "cutoffTime": doc.get("cutoff_time"),
                "mode": doc.get("mode"),
                "isolationPassed": doc.get("isolation_passed"),
                "createdAt": doc.get("created_at")
            }
            for doc in docs
        ]
    
    # ==================
    # Private methods
    # ==================
    
    def _generate_run_id(self, symbol: str, timeframe: str, cutoff_time: int) -> str:
        """Generate unique validation run ID"""
        return f"val_{symbol}_{timeframe}_{cutoff_time}_{int(time.time() * 1000) % 10000}"
    
    def _store_context(self, context: ValidationRunContext):
        """Store context in MongoDB"""
        collection = self.config.get("collections", {}).get("contexts", "ta_validation_context")
        doc = {
            "run_id": context.run_id,
            "symbol": context.symbol,
            "timeframe": context.timeframe,
            "cutoff_time": context.cutoff_time,
            "strategy_snapshot_id": context.strategy_snapshot_id,
            "memory_snapshot_id": context.memory_snapshot_id,
            "metabrain_snapshot_id": context.metabrain_snapshot_id,
            "config_snapshot_id": context.config_snapshot_id,
            "threshold_snapshot_id": context.threshold_snapshot_id,
            "discovery_snapshot_id": context.discovery_snapshot_id,
            "mode": context.mode.value,
            "isolation_passed": context.isolation_passed,
            "violations": [],  # Will be serialized separately if needed
            "created_at": context.created_at,
            "started_at": context.started_at,
            "completed_at": context.completed_at,
            "metadata": context.metadata
        }
        self.db[collection].insert_one(doc)
    
    def _update_context(self, context: ValidationRunContext):
        """Update context in MongoDB"""
        collection = self.config.get("collections", {}).get("contexts", "ta_validation_context")
        self.db[collection].update_one(
            {"run_id": context.run_id},
            {
                "$set": {
                    "isolation_passed": context.isolation_passed,
                    "started_at": context.started_at,
                    "completed_at": context.completed_at
                }
            }
        )
    
    def _load_context(self, run_id: str) -> Optional[ValidationRunContext]:
        """Load context from MongoDB"""
        collection = self.config.get("collections", {}).get("contexts", "ta_validation_context")
        doc = self.db[collection].find_one({"run_id": run_id})
        
        if not doc:
            return None
        
        return ValidationRunContext(
            run_id=doc.get("run_id"),
            symbol=doc.get("symbol", "BTCUSDT"),
            timeframe=doc.get("timeframe", "4h"),
            cutoff_time=doc.get("cutoff_time", 0),
            strategy_snapshot_id=doc.get("strategy_snapshot_id", ""),
            memory_snapshot_id=doc.get("memory_snapshot_id", ""),
            metabrain_snapshot_id=doc.get("metabrain_snapshot_id", ""),
            config_snapshot_id=doc.get("config_snapshot_id", ""),
            threshold_snapshot_id=doc.get("threshold_snapshot_id", ""),
            discovery_snapshot_id=doc.get("discovery_snapshot_id", ""),
            mode=IsolationMode(doc.get("mode", "historical_faithful")),
            isolation_passed=doc.get("isolation_passed", False),
            violations=[],
            created_at=doc.get("created_at", 0),
            started_at=doc.get("started_at", 0),
            completed_at=doc.get("completed_at", 0),
            metadata=doc.get("metadata", {})
        )
    
    def _get_mock_strategies(self) -> Dict[str, Any]:
        """Get mock strategies data for snapshot"""
        return {
            "strategies": [
                {"id": "MTF_BREAKOUT", "status": "APPROVED", "winRate": 0.62},
                {"id": "LIQUIDITY_SWEEP", "status": "APPROVED", "winRate": 0.58},
                {"id": "RANGE_REVERSAL", "status": "TESTING", "winRate": 0.55}
            ],
            "frozen_at": int(time.time() * 1000),
            "count": 3
        }
    
    def _get_mock_memory_state(self) -> Dict[str, Any]:
        """Get mock memory state for snapshot"""
        return {
            "patterns_indexed": 1500,
            "scenarios_indexed": 450,
            "last_rebuild": int(time.time() * 1000) - 86400000,
            "memory_version": "v2"
        }
    
    def _get_mock_metabrain_config(self) -> Dict[str, Any]:
        """Get mock metabrain config for snapshot"""
        return {
            "weights": {
                "scenario": 0.25,
                "memory": 0.20,
                "mtf": 0.15,
                "structure": 0.15,
                "edge": 0.15,
                "regime": 0.10
            },
            "thresholds": {
                "min_confidence": 0.6,
                "min_ev": 0.15
            },
            "mode": "balanced"
        }
    
    def _get_mock_thresholds(self) -> Dict[str, Any]:
        """Get mock thresholds for snapshot"""
        return {
            "confidence": {"strong": 0.75, "moderate": 0.55, "weak": 0.40},
            "ev": {"high": 0.30, "medium": 0.15, "low": 0.05},
            "sizing": {"max": 0.05, "default": 0.02}
        }
    
    def _get_mock_discovery_state(self) -> Dict[str, Any]:
        """Get mock discovery state for snapshot"""
        return {
            "strategies_discovered": 12,
            "strategies_approved": 3,
            "strategies_testing": 5,
            "last_discovery_run": int(time.time() * 1000) - 3600000
        }
    
    def _get_mock_config(self) -> Dict[str, Any]:
        """Get mock system config for snapshot"""
        return {
            "version": "2.0.0",
            "features": {
                "mtf_enabled": True,
                "structure_ai_enabled": True,
                "memory_enabled": True,
                "discovery_enabled": True
            },
            "params": {
                "default_timeframe": "4h",
                "lookback_bars": 100
            }
        }
