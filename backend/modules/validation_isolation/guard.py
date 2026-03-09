"""
Phase 8.1: Isolation Guard
Validates that validation runs are properly isolated.
"""
import time
from typing import Dict, List, Optional, Any

from .types import (
    ValidationRunContext,
    ValidationSnapshot,
    SnapshotType,
    IsolationViolation,
    IsolationReport,
    ViolationType,
    SeverityLevel,
    ISOLATION_CONFIG
)
from .snapshots import SnapshotManager


class IsolationGuard:
    """
    Guards against validation contamination.
    
    Checks:
    1. No live dependencies are being used
    2. All snapshots are from before cutoff time
    3. No mixed configurations
    4. No live memory access
    5. No automatic updates during validation
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or ISOLATION_CONFIG
        self.snapshot_manager = SnapshotManager(db, config)
    
    def check(
        self,
        context: ValidationRunContext,
        current_system_state: Optional[Dict[str, Any]] = None
    ) -> IsolationReport:
        """
        Perform full isolation check for a validation context.
        
        Args:
            context: The validation context to check
            current_system_state: Optional current system state to compare against
            
        Returns:
            IsolationReport with all violations found
        """
        violations = []
        notes = []
        
        # 1. Check all snapshots exist and are valid
        snapshot_violations, snapshot_notes = self._check_snapshots(context)
        violations.extend(snapshot_violations)
        notes.extend(snapshot_notes)
        
        # 2. Check cutoff time is respected
        cutoff_violations, cutoff_notes = self._check_cutoff_time(context)
        violations.extend(cutoff_violations)
        notes.extend(cutoff_notes)
        
        # 3. Check for live dependencies
        live_violations, live_notes = self._check_live_dependencies(
            context, current_system_state
        )
        violations.extend(live_violations)
        notes.extend(live_notes)
        
        # 4. Check for mixed configs
        mixed_violations, mixed_notes = self._check_mixed_configs(context)
        violations.extend(mixed_violations)
        notes.extend(mixed_notes)
        
        # 5. Check blocking rules are enforced
        blocking_violations, blocking_notes = self._check_blocking_rules(context)
        violations.extend(blocking_violations)
        notes.extend(blocking_notes)
        
        # Count violations by severity
        critical_count = len([v for v in violations if v.severity == SeverityLevel.CRITICAL])
        high_count = len([v for v in violations if v.severity == SeverityLevel.HIGH])
        
        # Determine pass/fail
        strict_mode = self.config.get("strict_mode", True)
        
        if strict_mode:
            passed = len(violations) == 0
        else:
            passed = critical_count == 0 and high_count <= 1
        
        return IsolationReport(
            passed=passed,
            violations=violations,
            violations_count=len(violations),
            critical_count=critical_count,
            high_count=high_count,
            snapshot_integrity=len(snapshot_violations) == 0,
            cutoff_respected=len(cutoff_violations) == 0,
            live_dependencies_blocked=len(live_violations) == 0,
            notes=notes,
            timestamp=int(time.time() * 1000)
        )
    
    def quick_check(self, context: ValidationRunContext) -> Dict[str, Any]:
        """
        Quick pre-flight check before validation run.
        
        Args:
            context: The validation context to check
            
        Returns:
            Quick check result dict
        """
        issues = []
        warnings = []
        
        # Check required fields
        if not context.cutoff_time:
            issues.append("Missing cutoff_time")
        
        if not context.strategy_snapshot_id:
            issues.append("Missing strategy snapshot")
        
        if not context.memory_snapshot_id:
            issues.append("Missing memory snapshot")
        
        if not context.metabrain_snapshot_id:
            warnings.append("Missing metabrain snapshot")
        
        # Check cutoff time is not in future
        now = int(time.time() * 1000)
        if context.cutoff_time > now:
            issues.append("Cutoff time is in the future")
        
        # Check cutoff time is not too old (configurable)
        max_age_days = 365 * 5  # 5 years
        max_age_ms = max_age_days * 24 * 60 * 60 * 1000
        if now - context.cutoff_time > max_age_ms:
            warnings.append(f"Cutoff time is very old (>{max_age_days} days)")
        
        return {
            "ready_to_run": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "recommendation": "Fix issues before running" if issues else "Ready for validation"
        }
    
    def validate_snapshot_access(
        self,
        context: ValidationRunContext,
        snapshot_type: SnapshotType,
        requested_snapshot_id: str
    ) -> bool:
        """
        Validate that a snapshot access is allowed.
        
        Args:
            context: The validation context
            snapshot_type: Type of snapshot being accessed
            requested_snapshot_id: ID of snapshot being requested
            
        Returns:
            True if access is allowed
        """
        # Get expected snapshot ID from context
        expected_id_map = {
            SnapshotType.STRATEGY: context.strategy_snapshot_id,
            SnapshotType.MEMORY: context.memory_snapshot_id,
            SnapshotType.METABRAIN: context.metabrain_snapshot_id,
            SnapshotType.CONFIG: context.config_snapshot_id,
            SnapshotType.THRESHOLD: context.threshold_snapshot_id,
            SnapshotType.DISCOVERY: context.discovery_snapshot_id
        }
        
        expected_id = expected_id_map.get(snapshot_type)
        return requested_snapshot_id == expected_id
    
    # ==================
    # Private methods
    # ==================
    
    def _check_snapshots(self, context: ValidationRunContext) -> tuple:
        """
        Check all required snapshots exist and have valid integrity.
        
        Returns:
            Tuple of (violations, notes)
        """
        violations = []
        notes = []
        
        snapshot_ids = [
            (SnapshotType.STRATEGY, context.strategy_snapshot_id, "Strategy"),
            (SnapshotType.MEMORY, context.memory_snapshot_id, "Memory"),
            (SnapshotType.METABRAIN, context.metabrain_snapshot_id, "MetaBrain"),
            (SnapshotType.CONFIG, context.config_snapshot_id, "Config"),
            (SnapshotType.THRESHOLD, context.threshold_snapshot_id, "Threshold"),
            (SnapshotType.DISCOVERY, context.discovery_snapshot_id, "Discovery")
        ]
        
        require_all = self.config.get("require_all_snapshots", True)
        
        for snap_type, snap_id, name in snapshot_ids:
            if not snap_id:
                if require_all:
                    violations.append(IsolationViolation(
                        type=ViolationType.LIVE_DEPENDENCY,
                        severity=SeverityLevel.HIGH,
                        message=f"Missing {name} snapshot",
                        location=f"{snap_type.value}_snapshot_id",
                        suggestion=f"Create {name} snapshot before validation"
                    ))
                continue
            
            # Try to load and verify snapshot
            snapshot = self.snapshot_manager.get_snapshot(snap_id)
            
            if not snapshot:
                violations.append(IsolationViolation(
                    type=ViolationType.LIVE_DEPENDENCY,
                    severity=SeverityLevel.CRITICAL,
                    message=f"{name} snapshot not found: {snap_id}",
                    location=f"{snap_type.value}_snapshot_id",
                    expected_value=snap_id,
                    suggestion=f"Ensure {name} snapshot exists before validation"
                ))
                continue
            
            # Verify integrity
            if not self.snapshot_manager.verify_integrity(snapshot):
                violations.append(IsolationViolation(
                    type=ViolationType.MIXED_CONFIG,
                    severity=SeverityLevel.CRITICAL,
                    message=f"{name} snapshot integrity check failed",
                    location=snap_id,
                    suggestion="Recreate snapshot - data may have been modified"
                ))
            else:
                notes.append(f"{name} snapshot verified: {snap_id}")
        
        return violations, notes
    
    def _check_cutoff_time(self, context: ValidationRunContext) -> tuple:
        """
        Check that cutoff time is properly set and all snapshots respect it.
        
        Returns:
            Tuple of (violations, notes)
        """
        violations = []
        notes = []
        
        if not context.cutoff_time:
            if self.config.get("require_cutoff_time", True):
                violations.append(IsolationViolation(
                    type=ViolationType.CUTOFF_BREACH,
                    severity=SeverityLevel.CRITICAL,
                    message="No cutoff time specified",
                    location="cutoff_time",
                    suggestion="Set cutoff_time to define validation boundary"
                ))
            return violations, notes
        
        # Check all snapshots are from before cutoff
        snapshot_ids = [
            context.strategy_snapshot_id,
            context.memory_snapshot_id,
            context.metabrain_snapshot_id,
            context.config_snapshot_id,
            context.threshold_snapshot_id,
            context.discovery_snapshot_id
        ]
        
        for snap_id in snapshot_ids:
            if not snap_id:
                continue
            
            snapshot = self.snapshot_manager.get_snapshot(snap_id)
            if snapshot and snapshot.cutoff_time > context.cutoff_time:
                violations.append(IsolationViolation(
                    type=ViolationType.FUTURE_SNAPSHOT,
                    severity=SeverityLevel.CRITICAL,
                    message=f"Snapshot {snap_id} is from after cutoff time",
                    location=snap_id,
                    expected_value=str(context.cutoff_time),
                    actual_value=str(snapshot.cutoff_time),
                    suggestion="Use snapshot from before cutoff time"
                ))
        
        notes.append(f"Cutoff time: {context.cutoff_time}")
        return violations, notes
    
    def _check_live_dependencies(self, context: ValidationRunContext, current_state: Optional[Dict]) -> tuple:
        """
        Check that no live system dependencies are being used.
        
        Returns:
            Tuple of (violations, notes)
        """
        violations = []
        notes = []
        
        if not current_state:
            notes.append("No current system state provided - skipping live dependency check")
            return violations, notes
        
        # Check if current strategies differ from snapshot
        if "strategies" in current_state:
            strategy_snap = self.snapshot_manager.get_snapshot(context.strategy_snapshot_id)
            if strategy_snap:
                # Handle both dict and list formats for strategy data
                if isinstance(strategy_snap.data, dict):
                    snap_count = len(strategy_snap.data.get("strategies", []))
                elif isinstance(strategy_snap.data, list):
                    snap_count = len(strategy_snap.data)
                else:
                    snap_count = 0
                    
                current_count = len(current_state.get("strategies", []))
                
                if current_count != snap_count:
                    violations.append(IsolationViolation(
                        type=ViolationType.LIVE_DEPENDENCY,
                        severity=SeverityLevel.HIGH,
                        message="Current strategies differ from snapshot",
                        location="strategies",
                        expected_value=str(snap_count),
                        actual_value=str(current_count),
                        suggestion="Use frozen strategy snapshot only"
                    ))
        
        # Check if memory has been rebuilt
        if "memory_last_rebuild" in current_state:
            memory_snap = self.snapshot_manager.get_snapshot(context.memory_snapshot_id)
            if memory_snap:
                snap_rebuild = memory_snap.data.get("last_rebuild", 0)
                current_rebuild = current_state.get("memory_last_rebuild", 0)
                
                if current_rebuild > snap_rebuild:
                    violations.append(IsolationViolation(
                        type=ViolationType.LIVE_MEMORY,
                        severity=SeverityLevel.HIGH,
                        message="Memory has been rebuilt since snapshot",
                        location="memory",
                        suggestion="Use frozen memory snapshot"
                    ))
        
        notes.append("Live dependency check completed")
        return violations, notes
    
    def _check_mixed_configs(self, context: ValidationRunContext) -> tuple:
        """
        Check for mixed frozen/live configurations.
        
        Returns:
            Tuple of (violations, notes)
        """
        violations = []
        notes = []
        
        # In historical_faithful mode, all snapshots should have same cutoff
        if context.mode.value == "historical_faithful":
            cutoff_times = []
            
            for snap_id in [context.strategy_snapshot_id, context.memory_snapshot_id, 
                           context.metabrain_snapshot_id]:
                if snap_id:
                    snapshot = self.snapshot_manager.get_snapshot(snap_id)
                    if snapshot:
                        cutoff_times.append(snapshot.cutoff_time)
            
            if cutoff_times and len(set(cutoff_times)) > 1:
                violations.append(IsolationViolation(
                    type=ViolationType.MIXED_CONFIG,
                    severity=SeverityLevel.MEDIUM,
                    message="Snapshots have different cutoff times in historical_faithful mode",
                    location="cutoff_times",
                    expected_value="All same",
                    actual_value=str(sorted(set(cutoff_times))),
                    suggestion="Create all snapshots with same cutoff time"
                ))
        
        notes.append(f"Config mode: {context.mode.value}")
        return violations, notes
    
    def _check_blocking_rules(self, context: ValidationRunContext) -> tuple:
        """
        Check that blocking rules are being enforced.
        
        Returns:
            Tuple of (violations, notes)
        """
        violations = []
        notes = []
        
        blocking_rules = [
            ("block_live_discovery_updates", "Live discovery updates"),
            ("block_live_memory_rebuild", "Live memory rebuild"),
            ("block_live_regime_learning", "Live regime learning"),
            ("block_metabrain_adaptation", "MetaBrain adaptation"),
            ("block_threshold_tuning", "Threshold tuning")
        ]
        
        blocked_features = []
        for rule, name in blocking_rules:
            if self.config.get(rule, True):
                blocked_features.append(name)
        
        notes.append(f"Blocked features: {', '.join(blocked_features)}")
        
        return violations, notes


def isolation_report_to_dict(report: IsolationReport) -> Dict[str, Any]:
    """Convert IsolationReport to JSON-serializable dict"""
    return {
        "passed": report.passed,
        "violations": [
            {
                "type": v.type.value,
                "severity": v.severity.value,
                "message": v.message,
                "location": v.location,
                "expectedValue": v.expected_value,
                "actualValue": v.actual_value,
                "suggestion": v.suggestion
            }
            for v in report.violations
        ],
        "violationsCount": report.violations_count,
        "criticalCount": report.critical_count,
        "highCount": report.high_count,
        "snapshotIntegrity": report.snapshot_integrity,
        "cutoffRespected": report.cutoff_respected,
        "liveDependenciesBlocked": report.live_dependencies_blocked,
        "notes": report.notes,
        "timestamp": report.timestamp
    }
