"""
Research Memory Types
=====================

Phase 9.32 - Data structures for research memory system.

Research Memory stores:
- Failed features
- Failed alphas
- Failed mutation branches
- Regime failures
- Tournament losses
- Stress failures

This prevents:
- Retesting dead ideas
- Repeating mistakes
- Wasting compute on known failures
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class MemoryCategory(str, Enum):
    """Categories of research memory"""
    FEATURE = "FEATURE"
    ALPHA = "ALPHA"
    MUTATION = "MUTATION"
    STRATEGY = "STRATEGY"
    TOURNAMENT = "TOURNAMENT"
    STRESS = "STRESS"
    REGIME = "REGIME"
    AUTOPSY = "AUTOPSY"


class MemoryOutcome(str, Enum):
    """Outcome types"""
    FAILED = "FAILED"
    DEPRECATED = "DEPRECATED"
    REDUNDANT = "REDUNDANT"
    UNSTABLE = "UNSTABLE"
    LOW_EDGE = "LOW_EDGE"
    OVERFITTED = "OVERFITTED"
    REGIME_SENSITIVE = "REGIME_SENSITIVE"


class MemoryImportance(str, Enum):
    """Importance levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class MemoryEntry:
    """Single memory entry"""
    entry_id: str
    category: MemoryCategory
    entity_id: str  # ID of the failed entity
    entity_name: str
    
    # Outcome
    outcome: MemoryOutcome
    importance: MemoryImportance = MemoryImportance.MEDIUM
    
    # Context
    family: str = ""
    asset_class: str = ""
    regime: str = ""
    timeframe: str = ""
    
    # Failure details
    failure_reasons: List[str] = field(default_factory=list)
    root_causes: List[str] = field(default_factory=list)
    metrics_at_failure: Dict[str, float] = field(default_factory=dict)
    
    # Signatures for matching
    signature_hash: str = ""  # Hash of key properties for duplicate detection
    similar_to: List[str] = field(default_factory=list)  # Similar failed entities
    
    # Knowledge extraction
    lesson_learned: str = ""
    recommendations: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    # Source
    source_report_id: str = ""  # Link to autopsy report
    
    # Timestamps
    failed_at: int = 0
    recorded_at: int = 0
    last_referenced: int = 0
    reference_count: int = 0


@dataclass
class MemoryPattern:
    """Aggregated pattern from multiple failures"""
    pattern_id: str
    category: MemoryCategory
    
    # Pattern definition
    description: str = ""
    common_causes: List[str] = field(default_factory=list)
    affected_families: List[str] = field(default_factory=list)
    affected_regimes: List[str] = field(default_factory=list)
    
    # Statistics
    occurrence_count: int = 0
    avg_severity: float = 0.0
    
    # Entries in this pattern
    entry_ids: List[str] = field(default_factory=list)
    
    # Knowledge
    prevention_rules: List[str] = field(default_factory=list)
    
    first_seen: int = 0
    last_seen: int = 0


@dataclass
class MemoryQuery:
    """Query parameters for memory lookup"""
    category: Optional[MemoryCategory] = None
    outcome: Optional[MemoryOutcome] = None
    family: Optional[str] = None
    regime: Optional[str] = None
    asset_class: Optional[str] = None
    tags: Optional[List[str]] = None
    min_importance: Optional[MemoryImportance] = None
    signature_hash: Optional[str] = None


@dataclass
class MemorySummary:
    """Summary statistics of research memory"""
    total_entries: int = 0
    total_patterns: int = 0
    
    by_category: Dict[str, int] = field(default_factory=dict)
    by_outcome: Dict[str, int] = field(default_factory=dict)
    by_family: Dict[str, int] = field(default_factory=dict)
    
    most_common_causes: List[Dict[str, Any]] = field(default_factory=list)
    most_fragile_families: List[str] = field(default_factory=list)
    danger_regimes: List[str] = field(default_factory=list)
    
    compute_saved_estimate: int = 0  # Estimated compute saved by avoiding retests
    
    computed_at: int = 0


@dataclass
class MemoryMatch:
    """Result of checking if an entity matches memory"""
    matched: bool = False
    confidence: float = 0.0
    
    matching_entries: List[str] = field(default_factory=list)
    matching_patterns: List[str] = field(default_factory=list)
    
    recommendation: str = ""  # SKIP, CAUTION, PROCEED
    reasons: List[str] = field(default_factory=list)
