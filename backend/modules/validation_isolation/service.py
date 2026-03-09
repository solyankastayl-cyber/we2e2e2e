"""
Phase 8.1: Validation Isolation Service
Main service orchestrating validation isolation.
"""
import time
from typing import Dict, List, Optional, Any

from .types import (
    ValidationRunContext,
    ValidationSnapshot,
    SnapshotType,
    IsolationMode,
    IsolationReport,
    ISOLATION_CONFIG
)
from .context import ValidationContextBuilder
from .snapshots import SnapshotManager
from .guard import IsolationGuard, isolation_report_to_dict


class ValidationIsolationService:
    """
    Main service for validation isolation.
    
    Orchestrates:
    1. Context building with frozen snapshots
    2. Snapshot management
    3. Isolation guard checks
    4. Validation run lifecycle
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or ISOLATION_CONFIG
        
        # Initialize shared snapshot manager for all components
        self.snapshot_manager = SnapshotManager(db, config)
        
        # Initialize components with shared snapshot manager
        self.context_builder = ValidationContextBuilder(db, config)
        # Share snapshot manager between context builder and guard
        self.context_builder.snapshot_manager = self.snapshot_manager
        
        self.isolation_guard = IsolationGuard(db, config)
        # Share snapshot manager with guard
        self.isolation_guard.snapshot_manager = self.snapshot_manager
    
    def create_validation_context(
        self,
        symbol: str,
        timeframe: str,
        cutoff_time: int,
        mode: str = "historical_faithful",
        strategies: Optional[List[Dict]] = None,
        memory_state: Optional[Dict] = None,
        metabrain_config: Optional[Dict] = None,
        thresholds: Optional[Dict] = None,
        discovery_state: Optional[Dict] = None,
        system_config: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a new validation context with all required snapshots.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            cutoff_time: Unix timestamp ms - no data beyond this point
            mode: "historical_faithful" or "frozen_config"
            strategies: Strategies to snapshot (optional)
            memory_state: Memory state to snapshot (optional)
            metabrain_config: MetaBrain config to snapshot (optional)
            thresholds: Thresholds to snapshot (optional)
            discovery_state: Discovery state to snapshot (optional)
            system_config: System config to snapshot (optional)
            
        Returns:
            Context creation result
        """
        try:
            isolation_mode = IsolationMode(mode)
        except ValueError:
            isolation_mode = IsolationMode.HISTORICAL_FAITHFUL
        
        context = self.context_builder.build_context(
            symbol=symbol,
            timeframe=timeframe,
            cutoff_time=cutoff_time,
            mode=isolation_mode,
            strategies=strategies,
            memory_state=memory_state,
            metabrain_config=metabrain_config,
            thresholds=thresholds,
            discovery_state=discovery_state,
            system_config=system_config
        )
        
        return self._context_to_dict(context)
    
    def check_isolation(
        self,
        run_id: str,
        current_system_state: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Run isolation check for a validation context.
        
        Args:
            run_id: Validation run ID
            current_system_state: Optional current system state to compare
            
        Returns:
            Isolation check result
        """
        context = self.context_builder.get_context(run_id)
        
        if not context:
            return {
                "passed": False,
                "error": f"Context not found: {run_id}"
            }
        
        report = self.isolation_guard.check(context, current_system_state)
        
        # Update context with results
        self.context_builder.mark_completed(
            run_id,
            passed=report.passed,
            violations=report.violations
        )
        
        return isolation_report_to_dict(report)
    
    def quick_check(
        self,
        run_id: str
    ) -> Dict[str, Any]:
        """
        Quick pre-flight check before running validation.
        
        Args:
            run_id: Validation run ID
            
        Returns:
            Quick check result
        """
        context = self.context_builder.get_context(run_id)
        
        if not context:
            return {
                "ready_to_run": False,
                "issues": [f"Context not found: {run_id}"],
                "warnings": [],
                "recommendation": "Create context first"
            }
        
        return self.isolation_guard.quick_check(context)
    
    def get_context(
        self,
        run_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a validation context by run ID.
        
        Args:
            run_id: Validation run ID
            
        Returns:
            Context dict or None
        """
        context = self.context_builder.get_context(run_id)
        
        if not context:
            return None
        
        return self._context_to_dict(context)
    
    def get_snapshot(
        self,
        snapshot_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a snapshot by ID.
        
        Args:
            snapshot_id: Snapshot ID
            
        Returns:
            Snapshot dict or None
        """
        snapshot = self.snapshot_manager.get_snapshot(snapshot_id)
        
        if not snapshot:
            return None
        
        return {
            "snapshotId": snapshot.snapshot_id,
            "type": snapshot.snapshot_type.value,
            "cutoffTime": snapshot.cutoff_time,
            "createdAt": snapshot.created_at,
            "data": snapshot.data,
            "checksum": snapshot.checksum,
            "metadata": snapshot.metadata
        }
    
    def list_contexts(
        self,
        symbol: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List validation contexts.
        
        Args:
            symbol: Filter by symbol (optional)
            limit: Maximum number to return
            
        Returns:
            List of context summaries
        """
        return self.context_builder.list_contexts(symbol, limit)
    
    def list_snapshots(
        self,
        snapshot_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List available snapshots.
        
        Args:
            snapshot_type: Filter by type (optional)
            limit: Maximum number to return
            
        Returns:
            List of snapshot summaries
        """
        snap_type = None
        if snapshot_type:
            try:
                snap_type = SnapshotType(snapshot_type)
            except ValueError:
                pass
        
        return self.snapshot_manager.list_snapshots(snap_type, limit)
    
    def start_validation_run(
        self,
        run_id: str
    ) -> Dict[str, Any]:
        """
        Mark a validation run as started.
        
        Args:
            run_id: Validation run ID
            
        Returns:
            Start result
        """
        success = self.context_builder.mark_started(run_id)
        
        return {
            "success": success,
            "runId": run_id,
            "startedAt": int(time.time() * 1000) if success else None,
            "message": "Validation run started" if success else "Context not found"
        }
    
    def complete_validation_run(
        self,
        run_id: str,
        passed: bool,
        violations: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Mark a validation run as completed.
        
        Args:
            run_id: Validation run ID
            passed: Whether isolation passed
            violations: List of violations (optional)
            
        Returns:
            Completion result
        """
        # Convert violations to proper objects if provided
        # (simplified for now - just use empty list)
        success = self.context_builder.mark_completed(run_id, passed, [])
        
        return {
            "success": success,
            "runId": run_id,
            "passed": passed if success else None,
            "completedAt": int(time.time() * 1000) if success else None,
            "message": "Validation run completed" if success else "Context not found"
        }
    
    def cleanup_old_snapshots(
        self,
        keep_count: int = 50
    ) -> Dict[str, Any]:
        """
        Clean up old snapshots beyond retention limit.
        
        Args:
            keep_count: Number of snapshots to keep per type
            
        Returns:
            Cleanup result
        """
        results = {}
        
        for snap_type in SnapshotType:
            deleted = self.snapshot_manager.cleanup_old_snapshots(snap_type, keep_count)
            results[snap_type.value] = deleted
        
        total_deleted = sum(results.values())
        
        return {
            "success": True,
            "totalDeleted": total_deleted,
            "byType": results,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    def get_health(self) -> Dict[str, Any]:
        """
        Get service health status.
        """
        return {
            "enabled": self.config.get("enabled", True),
            "version": self.config.get("version", "isolation_v1_phase8.1"),
            "status": "ok",
            "components": {
                "context_builder": "ok",
                "snapshot_manager": "ok",
                "isolation_guard": "ok"
            },
            "config": {
                "strictMode": self.config.get("strict_mode", True),
                "requireAllSnapshots": self.config.get("require_all_snapshots", True),
                "blockLiveDiscovery": self.config.get("block_live_discovery_updates", True),
                "blockLiveMemory": self.config.get("block_live_memory_rebuild", True),
                "blockMetabrainAdaptation": self.config.get("block_metabrain_adaptation", True)
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    # ==================
    # Private methods
    # ==================
    
    def _context_to_dict(self, context: ValidationRunContext) -> Dict[str, Any]:
        """Convert ValidationRunContext to JSON-serializable dict"""
        return {
            "runId": context.run_id,
            "symbol": context.symbol,
            "timeframe": context.timeframe,
            "cutoffTime": context.cutoff_time,
            "strategySnapshotId": context.strategy_snapshot_id,
            "memorySnapshotId": context.memory_snapshot_id,
            "metabrainSnapshotId": context.metabrain_snapshot_id,
            "configSnapshotId": context.config_snapshot_id,
            "thresholdSnapshotId": context.threshold_snapshot_id,
            "discoverySnapshotId": context.discovery_snapshot_id,
            "mode": context.mode.value,
            "isolationPassed": context.isolation_passed,
            "createdAt": context.created_at,
            "startedAt": context.started_at,
            "completedAt": context.completed_at,
            "metadata": context.metadata
        }


def context_to_validation_isolation_block(context: ValidationRunContext) -> Dict[str, Any]:
    """
    Generate the validationIsolation block for validation reports.
    This block should be included in every validation report.
    """
    return {
        "cutoffTime": context.cutoff_time,
        "strategySnapshotId": context.strategy_snapshot_id,
        "memorySnapshotId": context.memory_snapshot_id,
        "metabrainSnapshotId": context.metabrain_snapshot_id,
        "mode": context.mode.value,
        "isolationPassed": context.isolation_passed
    }
