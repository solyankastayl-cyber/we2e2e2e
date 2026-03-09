"""
Alpha Registry Types
====================

Phase 9.28 - Data structures for alpha registration and lineage tracking.

An alpha is not just a strategy - it's a research artifact with:
- Origin (creation source)
- Version history
- Family classification
- Feature dependencies
- Validation lineage
- Similarity relations
- Lifecycle status
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class AlphaFamily(str, Enum):
    """Alpha family classification"""
    TREND = "TREND"
    REVERSAL = "REVERSAL"
    BREAKOUT = "BREAKOUT"
    MOMENTUM = "MOMENTUM"
    STRUCTURE = "STRUCTURE"
    MEAN_REVERSION = "MEAN_REVERSION"
    REGIME = "REGIME"
    CROSS_ASSET = "CROSS_ASSET"
    PATTERN = "PATTERN"
    MACRO = "MACRO"
    ORTHOGONAL = "ORTHOGONAL"
    EXPERIMENTAL = "EXPERIMENTAL"


class AlphaCreationSource(str, Enum):
    """How the alpha was created"""
    HUMAN = "HUMAN"
    DISCOVERY_ENGINE = "DISCOVERY_ENGINE"
    FEATURE_FACTORY = "FEATURE_FACTORY"
    MUTATION_ENGINE = "MUTATION_ENGINE"
    IMPORT = "IMPORT"


class AlphaStatus(str, Enum):
    """Alpha lifecycle status"""
    CANDIDATE = "CANDIDATE"           # Newly registered
    SANDBOX = "SANDBOX"               # In sandbox testing
    VALIDATED = "VALIDATED"           # Passed validation
    SHADOW = "SHADOW"                 # In shadow portfolio
    LIMITED = "LIMITED"               # Limited production
    CORE = "CORE"                     # Core production
    DEGRADED = "DEGRADED"             # Performance degraded
    DISABLED = "DISABLED"             # Temporarily disabled
    ARCHIVED = "ARCHIVED"             # No longer used
    REJECTED = "REJECTED"             # Failed validation


class MutationType(str, Enum):
    """How alpha was derived from parent"""
    FEATURE_MUTATION = "FEATURE_MUTATION"
    PARAMETER_MUTATION = "PARAMETER_MUTATION"
    REGIME_VARIANT = "REGIME_VARIANT"
    ASSET_VARIANT = "ASSET_VARIANT"
    ORTHOGONAL_RESIDUAL = "ORTHOGONAL_RESIDUAL"
    MANUAL_FORK = "MANUAL_FORK"
    COMBINATION = "COMBINATION"


class ValidationVerdict(str, Enum):
    """Validation outcome"""
    PASS = "PASS"
    LIMITED = "LIMITED"
    FAIL = "FAIL"
    PENDING = "PENDING"


@dataclass
class AlphaDescriptor:
    """
    Complete alpha descriptor.
    
    Every alpha in the system must have this record.
    """
    alpha_id: str
    name: str
    
    # Classification
    family: AlphaFamily = AlphaFamily.EXPERIMENTAL
    
    # Creation info
    created_at: int = 0                              # Unix timestamp ms
    created_by: AlphaCreationSource = AlphaCreationSource.HUMAN
    
    # Versioning
    version: str = "v1"
    parent_alpha_id: Optional[str] = None            # Direct parent
    root_idea_id: Optional[str] = None               # Original idea root
    
    # Dependencies
    feature_ids: List[str] = field(default_factory=list)
    strategy_id: Optional[str] = None                # Link to strategy implementation
    
    # Scope
    asset_classes: List[str] = field(default_factory=lambda: ["CRYPTO"])
    timeframes: List[str] = field(default_factory=lambda: ["1D"])
    
    # Status
    status: AlphaStatus = AlphaStatus.CANDIDATE
    
    # Metrics (latest)
    profit_factor: float = 0.0
    win_rate: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    expectancy: float = 0.0
    
    # Quality scores
    stability_score: float = 0.0
    utility_score: float = 0.0
    portability_score: float = 0.0
    regime_fit_score: float = 0.0
    crowding_score: float = 0.0
    final_score: float = 0.0
    
    # Tags and notes
    tags: List[str] = field(default_factory=list)
    description: str = ""
    notes: str = ""
    
    # Timestamps
    updated_at: int = 0
    validated_at: int = 0
    promoted_at: int = 0


@dataclass
class AlphaLineageNode:
    """
    Lineage information for an alpha.
    
    Tracks how alphas evolve from each other.
    """
    alpha_id: str
    parent_alpha_id: Optional[str] = None
    root_idea_id: str = ""
    
    # How it was derived
    mutation_type: Optional[MutationType] = None
    
    # What it was created from
    created_from_feature_ids: List[str] = field(default_factory=list)
    created_from_validation_run_ids: List[str] = field(default_factory=list)
    
    # Children
    child_alpha_ids: List[str] = field(default_factory=list)
    
    # Depth in lineage tree
    generation: int = 0
    
    # Notes
    mutation_notes: str = ""


@dataclass
class AlphaVersion:
    """
    Version snapshot of an alpha.
    """
    alpha_id: str
    version: str
    
    # Snapshot IDs
    feature_ids: List[str] = field(default_factory=list)
    parameter_snapshot_id: str = ""
    policy_snapshot_id: str = ""
    validation_snapshot_ids: List[str] = field(default_factory=list)
    
    # Metrics at this version
    profit_factor: float = 0.0
    win_rate: float = 0.0
    sharpe: float = 0.0
    
    # Status at version
    status: AlphaStatus = AlphaStatus.CANDIDATE
    
    # Metadata
    notes: str = ""
    created_at: int = 0


@dataclass
class AlphaValidationLink:
    """
    Link between alpha and its validation runs.
    """
    alpha_id: str
    validation_run_id: str
    
    # Scope
    datasets: List[str] = field(default_factory=list)
    
    # Results by asset
    asset_results: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # Example: {"BTC": {"pf": 1.5, "wr": 0.55, "sharpe": 1.2, "max_dd": 0.15}}
    
    # Verdict
    verdict: ValidationVerdict = ValidationVerdict.PENDING
    
    # Timestamps
    validated_at: int = 0


@dataclass
class AlphaSimilarityRecord:
    """
    Similarity record between two alphas.
    """
    alpha_a: str
    alpha_b: str
    
    # Similarity metrics
    feature_overlap: float = 0.0           # 0-1
    signal_overlap: float = 0.0            # 0-1
    pnl_correlation: float = 0.0           # -1 to 1
    regime_overlap: float = 0.0            # 0-1
    
    # Final score
    similarity_score: float = 0.0
    
    # Flags
    is_clone: bool = False                 # similarity > 0.85
    is_crowded: bool = False               # similarity > 0.70
    
    # Computed at
    computed_at: int = 0


@dataclass
class AlphaFamilyBudget:
    """
    Budget limits for alpha family.
    """
    family: AlphaFamily
    
    # Limits
    max_core: int = 10
    max_shadow: int = 15
    max_sandbox: int = 30
    max_total: int = 50
    
    # Target portfolio share
    target_share: float = 0.10
    
    # Current counts (computed)
    current_core: int = 0
    current_shadow: int = 0
    current_sandbox: int = 0
    current_total: int = 0


@dataclass
class AlphaRegistryConfig:
    """
    Configuration for alpha registry.
    """
    # Similarity thresholds
    crowded_threshold: float = 0.70
    clone_threshold: float = 0.85
    
    # Promotion thresholds
    validated_threshold: float = 0.65
    shadow_threshold: float = 0.72
    core_threshold: float = 0.80
    
    # Scoring weights
    stability_weight: float = 0.20
    utility_weight: float = 0.25
    portability_weight: float = 0.15
    regime_fit_weight: float = 0.15
    crowding_penalty_weight: float = 0.15
    pf_weight: float = 0.10
    
    # Lifecycle rules
    require_orthogonality_check: bool = True
    require_cross_asset_for_core: bool = True
    min_validation_runs_for_shadow: int = 2
    min_shadow_days_for_core: int = 30


# Default family budgets
DEFAULT_FAMILY_BUDGETS = {
    AlphaFamily.TREND: AlphaFamilyBudget(
        family=AlphaFamily.TREND,
        max_core=8, max_shadow=12, max_sandbox=25, max_total=40,
        target_share=0.20
    ),
    AlphaFamily.BREAKOUT: AlphaFamilyBudget(
        family=AlphaFamily.BREAKOUT,
        max_core=6, max_shadow=10, max_sandbox=20, max_total=35,
        target_share=0.15
    ),
    AlphaFamily.MOMENTUM: AlphaFamilyBudget(
        family=AlphaFamily.MOMENTUM,
        max_core=6, max_shadow=10, max_sandbox=20, max_total=35,
        target_share=0.15
    ),
    AlphaFamily.REVERSAL: AlphaFamilyBudget(
        family=AlphaFamily.REVERSAL,
        max_core=4, max_shadow=8, max_sandbox=15, max_total=25,
        target_share=0.10
    ),
    AlphaFamily.MEAN_REVERSION: AlphaFamilyBudget(
        family=AlphaFamily.MEAN_REVERSION,
        max_core=4, max_shadow=8, max_sandbox=15, max_total=25,
        target_share=0.10
    ),
    AlphaFamily.STRUCTURE: AlphaFamilyBudget(
        family=AlphaFamily.STRUCTURE,
        max_core=4, max_shadow=8, max_sandbox=15, max_total=25,
        target_share=0.10
    ),
    AlphaFamily.CROSS_ASSET: AlphaFamilyBudget(
        family=AlphaFamily.CROSS_ASSET,
        max_core=3, max_shadow=6, max_sandbox=12, max_total=20,
        target_share=0.08
    ),
    AlphaFamily.EXPERIMENTAL: AlphaFamilyBudget(
        family=AlphaFamily.EXPERIMENTAL,
        max_core=2, max_shadow=5, max_sandbox=30, max_total=35,
        target_share=0.05
    ),
}
