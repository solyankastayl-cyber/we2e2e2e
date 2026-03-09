"""
Phase 9.5: Type definitions for Edge Validation
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import time


class StrategyStatus(str, Enum):
    """Strategy lifecycle status"""
    CANDIDATE = "CANDIDATE"      # Newly discovered, needs validation
    TESTING = "TESTING"          # Under robustness testing
    APPROVED = "APPROVED"        # Passed validation, ready for live
    QUARANTINE = "QUARANTINE"    # Suspicious, needs review
    DEPRECATED = "DEPRECATED"    # No longer viable


class RegimeType(str, Enum):
    """Market regime types"""
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"


@dataclass
class RegimeMetrics:
    """Performance metrics for a specific regime"""
    regime: str
    win_rate: float
    sample_size: int
    avg_r: float = 0.0
    profit_factor: float = 1.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0


@dataclass
class RobustnessScore:
    """Robustness assessment result"""
    overall_score: float           # 0-1 aggregate robustness
    regime_scores: Dict[str, float] = field(default_factory=dict)  # Score per regime
    cross_asset_score: float = 0.0  # Performance across assets
    temporal_stability: float = 0.0  # Performance stability over time
    minimum_evidence: bool = False   # Has enough trades
    regime_coverage: float = 0.0     # % of regimes tested
    weakest_regime: Optional[str] = None
    notes: List[str] = field(default_factory=list)


@dataclass 
class SimilarityPenalty:
    """Similarity assessment with existing strategies"""
    penalty: float                 # 0-1, higher = more similar
    similar_strategies: List[str] = field(default_factory=list)  # IDs of similar strategies
    overlap_features: List[str] = field(default_factory=list)    # Common features
    correlation: float = 0.0       # Return correlation with existing
    is_redundant: bool = False     # True if too similar to existing
    notes: List[str] = field(default_factory=list)


@dataclass
class ConfidenceScore:
    """Final confidence assessment"""
    score: float                   # 0-1 final confidence
    robustness_component: float = 0.0
    similarity_component: float = 0.0  # Negative if similar
    evidence_component: float = 0.0
    regime_stability_component: float = 0.0
    breakdown: Dict[str, float] = field(default_factory=dict)
    verdict: str = "NEEDS_REVIEW"  # STRONG, MODERATE, WEAK, REJECT
    reasons: List[str] = field(default_factory=list)


@dataclass
class EdgeValidationResult:
    """Complete edge validation result for a strategy"""
    strategy_id: str
    robustness: RobustnessScore
    similarity: SimilarityPenalty
    confidence: ConfidenceScore
    recommended_status: StrategyStatus
    lifecycle_action: str = "HOLD"  # PROMOTE, DEMOTE, HOLD, DEPRECATE
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    notes: List[str] = field(default_factory=list)


# Thresholds for validation
VALIDATION_THRESHOLDS = {
    # Minimum evidence requirements
    "min_trades": 30,              # Minimum trades for validation
    "min_trades_per_regime": 10,   # Minimum trades per regime
    "min_regimes_tested": 2,       # Minimum different regimes
    
    # Robustness thresholds
    "min_robustness": 0.5,         # Minimum robustness score
    "min_regime_win_rate": 0.45,   # Win rate floor per regime
    "max_regime_variance": 0.20,   # Max variance across regimes
    
    # Similarity thresholds
    "max_similarity": 0.75,        # Max similarity to existing
    "redundancy_threshold": 0.85,  # Above this = redundant
    "min_unique_features": 1,      # Must have at least N unique features
    
    # Confidence thresholds
    "strong_confidence": 0.75,     # Above = STRONG
    "moderate_confidence": 0.55,   # Above = MODERATE
    "weak_confidence": 0.40,       # Above = WEAK, below = REJECT
    
    # Lifecycle thresholds
    "promote_threshold": 0.70,     # Confidence to promote
    "demote_threshold": 0.35,      # Confidence to demote
    "deprecate_threshold": 0.25,   # Confidence to deprecate
}


# Feature weights for similarity calculation
FEATURE_WEIGHTS = {
    # Pattern features (most important)
    "BREAKOUT": 1.0,
    "COMPRESSION": 0.9,
    "TRIANGLE": 0.85,
    "FLAG": 0.85,
    "DIVERGENCE": 0.95,
    "DOUBLE_TOP": 0.9,
    
    # Structure features
    "SWEEP": 0.8,
    "EXPANSION": 0.75,
    "ACCUMULATION": 0.85,
    "DISTRIBUTION": 0.85,
    
    # Indicator features
    "RSI_OVERSOLD": 0.7,
    "RSI_OVERBOUGHT": 0.7,
    "VOLUME_SPIKE": 0.75,
    "MACD_CROSSOVER": 0.65,
    
    # MTF features  
    "MTF_ALIGNED": 0.6,
    "MTF_CONFLICT": 0.55,
    "HIGHER_TF_BULL": 0.5,
    "HIGHER_TF_BEAR": 0.5,
    
    # Regime features (context, less unique)
    "TREND_UP": 0.4,
    "TREND_DOWN": 0.4,
    "RANGE": 0.35,
    
    # Memory features
    "MEMORY_MATCH": 0.65,
    "MEMORY_WEAK": 0.45,
    "HISTORICAL_WIN": 0.55,
}
