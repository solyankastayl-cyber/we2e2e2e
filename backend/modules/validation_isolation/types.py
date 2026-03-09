"""
Phase 8.1: Validation Isolation Types
Core data types for validation isolation layer.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class SnapshotType(str, Enum):
    """Types of snapshots for validation isolation"""
    STRATEGY = "strategy"
    MEMORY = "memory"
    METABRAIN = "metabrain"
    CONFIG = "config"
    THRESHOLD = "threshold"
    DISCOVERY = "discovery"


class IsolationMode(str, Enum):
    """Validation isolation modes"""
    HISTORICAL_FAITHFUL = "historical_faithful"  # Uses only data available at cutoff time
    FROZEN_CONFIG = "frozen_config"  # Uses frozen configuration snapshot


class ViolationType(str, Enum):
    """Types of isolation violations"""
    LIVE_DEPENDENCY = "live_dependency"  # Using live module instead of snapshot
    FUTURE_SNAPSHOT = "future_snapshot"  # Snapshot from after cutoff time
    MIXED_CONFIG = "mixed_config"  # Mixed frozen/live configurations
    LIVE_MEMORY = "live_memory"  # Using live memory instead of snapshot
    CUTOFF_BREACH = "cutoff_breach"  # Data from after cutoff time
    AUTO_UPDATE = "auto_update"  # Automatic strategy updates during validation


class SeverityLevel(str, Enum):
    """Severity levels for violations"""
    CRITICAL = "critical"  # Validation is invalid
    HIGH = "high"  # Results may be contaminated
    MEDIUM = "medium"  # Potential contamination risk
    LOW = "low"  # Minor issue, results still usable


@dataclass
class IsolationViolation:
    """Represents a single isolation violation"""
    type: ViolationType
    severity: SeverityLevel
    message: str
    location: str = ""
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    suggestion: str = ""


@dataclass
class ValidationSnapshot:
    """Represents a frozen snapshot of system state"""
    snapshot_id: str
    snapshot_type: SnapshotType
    cutoff_time: int  # Unix timestamp milliseconds
    created_at: int
    data: Dict[str, Any]
    checksum: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationRunContext:
    """
    Context for a single validation run.
    Ensures all components use time-sealed snapshots.
    """
    run_id: str
    symbol: str = "BTCUSDT"
    timeframe: str = "4h"
    
    # Time boundary
    cutoff_time: int = 0  # Unix timestamp milliseconds
    
    # Snapshot references
    strategy_snapshot_id: str = ""
    memory_snapshot_id: str = ""
    metabrain_snapshot_id: str = ""
    config_snapshot_id: str = ""
    threshold_snapshot_id: str = ""
    discovery_snapshot_id: str = ""
    
    # Mode
    mode: IsolationMode = IsolationMode.HISTORICAL_FAITHFUL
    
    # Validation state
    isolation_passed: bool = False
    violations: List[IsolationViolation] = field(default_factory=list)
    
    # Timestamps
    created_at: int = 0
    started_at: int = 0
    completed_at: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IsolationReport:
    """Report from isolation guard check"""
    passed: bool
    violations: List[IsolationViolation]
    violations_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    snapshot_integrity: bool = True
    cutoff_respected: bool = True
    live_dependencies_blocked: bool = True
    notes: List[str] = field(default_factory=list)
    timestamp: int = 0


# Configuration defaults
ISOLATION_CONFIG = {
    "enabled": True,
    "version": "isolation_v1_phase8.1",
    
    # Snapshot retention
    "snapshot_retention_days": 90,
    "max_snapshots_per_type": 100,
    
    # Validation requirements
    "require_all_snapshots": True,
    "require_cutoff_time": True,
    "strict_mode": True,  # Fail on any violation
    
    # Blocking rules
    "block_live_discovery_updates": True,
    "block_live_memory_rebuild": True,
    "block_live_regime_learning": True,
    "block_metabrain_adaptation": True,
    "block_threshold_tuning": True,
    
    # MongoDB collections
    "collections": {
        "contexts": "ta_validation_context",
        "strategy_snapshots": "ta_strategy_snapshots",
        "memory_snapshots": "ta_memory_snapshots",
        "metabrain_snapshots": "ta_metabrain_snapshots",
        "threshold_snapshots": "ta_threshold_snapshots",
        "discovery_snapshots": "ta_discovery_snapshots",
        "config_snapshots": "ta_config_snapshots"
    }
}
