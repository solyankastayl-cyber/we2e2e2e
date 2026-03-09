"""
Feature Factory Types
=====================

Phase 9.31 - Data structures for industrial factor production.

Feature Factory is not a folder with 200 indicators.
It's a layer that:
- Generates features
- Normalizes them
- Groups by families
- Assesses quality
- Cuts garbage
- Checks stability
- Tracks crowding
- Passes only valid factors to alpha discovery
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class FeatureFamily(str, Enum):
    """Feature family classification"""
    TREND = "TREND"
    VOLATILITY = "VOLATILITY"
    STRUCTURE = "STRUCTURE"
    BREAKOUT = "BREAKOUT"
    MEAN_REVERSION = "MEAN_REVERSION"
    REGIME = "REGIME"
    CROSS_ASSET = "CROSS_ASSET"
    LIQUIDITY = "LIQUIDITY"
    MACRO = "MACRO"
    MOMENTUM = "MOMENTUM"
    BEHAVIORAL = "BEHAVIORAL"
    EXPERIMENTAL = "EXPERIMENTAL"


class FeatureStatus(str, Enum):
    """Feature lifecycle status"""
    CANDIDATE = "CANDIDATE"         # Newly generated
    SANDBOX = "SANDBOX"             # In sandbox testing
    APPROVED = "APPROVED"           # Production approved
    LIMITED = "LIMITED"             # Limited use (unstable)
    DEPRECATED = "DEPRECATED"       # No longer used


class NormalizationMethod(str, Enum):
    """Feature normalization methods"""
    NONE = "NONE"
    ZSCORE = "ZSCORE"
    ROLLING_ZSCORE = "ROLLING_ZSCORE"
    PERCENTILE = "PERCENTILE"
    ROBUST = "ROBUST"
    VOLATILITY_SCALED = "VOLATILITY_SCALED"


class FeatureType(str, Enum):
    """Feature generation type"""
    BASE = "BASE"                   # Direct from OHLCV
    DERIVED = "DERIVED"             # Combination of base
    MUTATED = "MUTATED"             # Algorithmic mutation
    CROSS_ASSET = "CROSS_ASSET"     # Multi-asset feature


class MutationOp(str, Enum):
    """Mutation operations"""
    ADD = "ADD"                     # f1 + f2
    SUBTRACT = "SUBTRACT"           # f1 - f2
    MULTIPLY = "MULTIPLY"           # f1 * f2
    DIVIDE = "DIVIDE"               # f1 / f2
    LAG = "LAG"                     # lag(f, n)
    SLOPE = "SLOPE"                 # slope(f, n)
    PERSISTENCE = "PERSISTENCE"     # persistence(f)
    REGIME_MASK = "REGIME_MASK"     # f * regime_indicator


@dataclass
class FeatureDescriptor:
    """
    Complete feature descriptor.
    
    Every feature in the system must have this record.
    """
    feature_id: str
    name: str
    
    # Classification
    family: FeatureFamily = FeatureFamily.EXPERIMENTAL
    feature_type: FeatureType = FeatureType.BASE
    
    # Formula/source
    source_fields: List[str] = field(default_factory=list)  # e.g., ["close", "high", "low"]
    formula: str = ""                                        # Human-readable formula
    
    # Normalization
    normalization: NormalizationMethod = NormalizationMethod.NONE
    normalization_window: int = 20
    
    # Scope
    asset_classes: List[str] = field(default_factory=lambda: ["CRYPTO"])
    timeframes: List[str] = field(default_factory=lambda: ["1D"])
    
    # Version
    version: str = "v1"
    
    # Quality metrics
    coverage: float = 1.0               # % of data where feature is available
    missing_rate: float = 0.0           # % missing values
    stability_score: float = 0.5        # Temporal stability
    utility_score: float = 0.5          # Predictive utility
    crowding_score: float = 0.0         # Overlap with other features
    portability_score: float = 0.5      # Works across assets
    regime_fit_score: float = 0.5       # Regime consistency
    final_score: float = 0.5
    
    # Status
    status: FeatureStatus = FeatureStatus.CANDIDATE
    
    # Dependencies
    parent_feature_ids: List[str] = field(default_factory=list)
    
    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: int = 0
    updated_at: int = 0


@dataclass
class FeatureValue:
    """Single feature value at a point in time"""
    feature_id: str
    timestamp: int
    raw_value: float
    normalized_value: float = None


@dataclass
class FeatureValueSeries:
    """Time series of feature values"""
    feature_id: str
    asset: str
    timeframe: str
    
    timestamps: List[int] = field(default_factory=list)
    values: List[float] = field(default_factory=list)
    normalized_values: List[float] = field(default_factory=list)


@dataclass
class FeatureQualityReport:
    """Quality assessment for a feature"""
    feature_id: str
    
    # Coverage
    coverage: float = 0.0
    missing_rate: float = 0.0
    
    # Stability
    variance: float = 0.0
    stability_score: float = 0.0
    is_constant: bool = False
    has_spikes: bool = False
    
    # Utility
    utility_score: float = 0.0
    
    # Verdict
    passed: bool = False
    failure_reasons: List[str] = field(default_factory=list)
    
    computed_at: int = 0


@dataclass
class FeatureCrowdingRecord:
    """Crowding record between two features"""
    feature_a: str
    feature_b: str
    
    correlation: float = 0.0
    mutual_info: float = 0.0
    regime_overlap: float = 0.0
    
    crowding_score: float = 0.0
    is_redundant: bool = False
    is_crowded: bool = False
    
    computed_at: int = 0


@dataclass
class FeatureFamilyBudget:
    """Budget limits for feature family"""
    family: FeatureFamily
    
    # Limits
    max_approved: int = 15
    max_sandbox: int = 30
    max_experimental: int = 20
    
    # Target portfolio share
    target_share: float = 0.10
    
    # Current counts
    current_approved: int = 0
    current_sandbox: int = 0
    current_experimental: int = 0


@dataclass
class MutationConfig:
    """Configuration for feature mutation"""
    operation: MutationOp
    operand_feature_ids: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    # e.g., {"lag_periods": 5, "regime": "TRENDING"}


@dataclass
class FeatureFactoryConfig:
    """Configuration for feature factory"""
    
    # Quality thresholds
    min_coverage: float = 0.90
    max_missing_rate: float = 0.05
    min_variance: float = 0.0001
    
    # Crowding thresholds
    medium_crowding_threshold: float = 0.70
    high_crowding_threshold: float = 0.85
    
    # Scoring weights
    stability_weight: float = 0.25
    utility_weight: float = 0.25
    portability_weight: float = 0.20
    regime_fit_weight: float = 0.15
    crowding_penalty_weight: float = 0.15
    
    # Promotion thresholds
    approved_threshold: float = 0.70
    sandbox_threshold: float = 0.55
    candidate_threshold: float = 0.40
    
    # Normalization defaults
    default_normalization_window: int = 20


# Default family budgets
DEFAULT_FEATURE_BUDGETS = {
    FeatureFamily.TREND: FeatureFamilyBudget(
        family=FeatureFamily.TREND,
        max_approved=15, max_sandbox=25, max_experimental=15,
        target_share=0.20
    ),
    FeatureFamily.VOLATILITY: FeatureFamilyBudget(
        family=FeatureFamily.VOLATILITY,
        max_approved=12, max_sandbox=20, max_experimental=12,
        target_share=0.15
    ),
    FeatureFamily.MOMENTUM: FeatureFamilyBudget(
        family=FeatureFamily.MOMENTUM,
        max_approved=12, max_sandbox=20, max_experimental=12,
        target_share=0.15
    ),
    FeatureFamily.STRUCTURE: FeatureFamilyBudget(
        family=FeatureFamily.STRUCTURE,
        max_approved=10, max_sandbox=18, max_experimental=10,
        target_share=0.12
    ),
    FeatureFamily.BREAKOUT: FeatureFamilyBudget(
        family=FeatureFamily.BREAKOUT,
        max_approved=10, max_sandbox=18, max_experimental=10,
        target_share=0.12
    ),
    FeatureFamily.CROSS_ASSET: FeatureFamilyBudget(
        family=FeatureFamily.CROSS_ASSET,
        max_approved=8, max_sandbox=15, max_experimental=10,
        target_share=0.08
    ),
    FeatureFamily.EXPERIMENTAL: FeatureFamilyBudget(
        family=FeatureFamily.EXPERIMENTAL,
        max_approved=5, max_sandbox=30, max_experimental=30,
        target_share=0.05
    ),
}
