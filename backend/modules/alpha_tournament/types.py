"""
Alpha Tournament Types
======================

Phase 9.29 - Data structures for alpha tournament system.

Tournament System ensures:
- New alphas don't enter core without competition
- Alphas are compared within similar buckets
- Weak alphas are eliminated
- Strong alphas are promoted to Shadow Portfolio
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class TournamentVerdict(str, Enum):
    """Tournament outcome for an alpha"""
    PROMOTE = "PROMOTE"           # Promote to Shadow
    KEEP = "KEEP"                 # Keep in tournament (borderline)
    REJECT = "REJECT"             # Reject/archive


class TournamentStage(str, Enum):
    """Tournament stages"""
    ADMISSION = "ADMISSION"       # Basic qualification
    FAMILY_RANKING = "FAMILY_RANKING"   # Within-bucket comparison
    PROMOTION_GATE = "PROMOTION_GATE"   # Final promotion check


class TournamentStatus(str, Enum):
    """Tournament run status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class TournamentCandidate:
    """
    Alpha candidate entering tournament.
    """
    alpha_id: str
    name: str = ""
    family: str = "EXPERIMENTAL"
    asset_classes: List[str] = field(default_factory=lambda: ["CRYPTO"])
    timeframes: List[str] = field(default_factory=lambda: ["1D"])
    
    # Registry status
    registry_status: str = "VALIDATED"
    
    # Scores from registry
    validation_score: float = 0.0
    orthogonality_score: float = 0.0
    crowding_score: float = 0.0
    
    # Tournament assignment
    bucket_id: str = ""
    
    # Admission status
    admitted: bool = False
    admission_reasons: List[str] = field(default_factory=list)


@dataclass
class TournamentBucket:
    """
    Tournament bucket for grouping similar alphas.
    
    Alphas compete within their bucket, not across all alphas.
    """
    bucket_id: str
    family: str
    asset_class: str
    timeframe: str
    
    # Candidates in this bucket
    candidate_alpha_ids: List[str] = field(default_factory=list)
    
    # Stats
    candidate_count: int = 0
    min_candidates_required: int = 2
    
    # Results
    winner_ids: List[str] = field(default_factory=list)
    rejected_ids: List[str] = field(default_factory=list)
    
    # Status
    is_active: bool = True


@dataclass
class TournamentScorecard:
    """
    Scorecard for evaluating alpha in tournament.
    """
    alpha_id: str
    bucket_id: str
    
    # Performance metrics
    profit_factor: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    cagr: float = 0.0
    win_rate: float = 0.0
    
    # Quality metrics
    stability_score: float = 0.0
    regime_robustness: float = 0.0
    orthogonality_score: float = 0.0
    crowding_penalty: float = 0.0
    
    # Final score
    final_score: float = 0.0
    
    # Rank within bucket
    bucket_rank: int = 0
    
    # Verdict
    verdict: TournamentVerdict = TournamentVerdict.KEEP
    verdict_reasons: List[str] = field(default_factory=list)
    
    # Timestamp
    evaluated_at: int = 0


@dataclass
class TournamentRound:
    """
    Single tournament round.
    """
    round_id: str
    stage: TournamentStage
    
    # Scope
    bucket_id: str = ""  # Empty = all buckets
    
    # Input
    candidate_ids: List[str] = field(default_factory=list)
    
    # Output
    promoted_ids: List[str] = field(default_factory=list)
    kept_ids: List[str] = field(default_factory=list)
    rejected_ids: List[str] = field(default_factory=list)
    
    # Stats
    total_candidates: int = 0
    total_promoted: int = 0
    total_rejected: int = 0
    
    # Timestamps
    started_at: int = 0
    completed_at: int = 0


@dataclass
class TournamentRun:
    """
    Complete tournament run across all buckets.
    """
    run_id: str
    
    # Scope
    bucket_ids: List[str] = field(default_factory=list)
    
    # Status
    status: TournamentStatus = TournamentStatus.PENDING
    
    # Results
    total_candidates: int = 0
    total_promoted: int = 0
    total_kept: int = 0
    total_rejected: int = 0
    
    # Rounds
    rounds: List[TournamentRound] = field(default_factory=list)
    
    # Scorecards
    scorecards: Dict[str, TournamentScorecard] = field(default_factory=dict)
    
    # Timestamps
    started_at: int = 0
    completed_at: int = 0


@dataclass
class TournamentHistory:
    """
    Historical record of alpha's tournament participation.
    """
    alpha_id: str
    
    # Participation
    tournaments_entered: int = 0
    tournaments_won: int = 0
    tournaments_lost: int = 0
    
    # Best performance
    best_score: float = 0.0
    best_rank: int = 0
    
    # History
    run_history: List[Dict] = field(default_factory=list)
    # Each entry: {run_id, bucket_id, score, rank, verdict, timestamp}


@dataclass
class TournamentConfig:
    """
    Configuration for tournament system.
    """
    # Admission thresholds
    min_validation_score: float = 0.65
    max_crowding_score: float = 0.70
    min_orthogonality_score: float = 0.50
    
    # Scoring weights
    sharpe_weight: float = 0.25
    pf_weight: float = 0.20
    stability_weight: float = 0.15
    regime_weight: float = 0.15
    orthogonality_weight: float = 0.15
    crowding_penalty_weight: float = 0.10
    
    # Promotion thresholds
    promote_threshold: float = 0.75
    keep_threshold: float = 0.60
    reject_threshold: float = 0.60
    
    # Quotas
    max_promotions_per_cycle: int = 5
    max_promotions_per_family: int = 2
    max_promotions_per_bucket: int = 2
    min_candidates_per_bucket: int = 2
    
    # Bucket configuration
    default_asset_class: str = "ALL"
    default_timeframe: str = "1D"


# Default bucket definitions
DEFAULT_BUCKETS = [
    TournamentBucket(
        bucket_id="TREND_CRYPTO_1D",
        family="TREND",
        asset_class="CRYPTO",
        timeframe="1D"
    ),
    TournamentBucket(
        bucket_id="TREND_EQUITY_1D",
        family="TREND",
        asset_class="EQUITY",
        timeframe="1D"
    ),
    TournamentBucket(
        bucket_id="BREAKOUT_CRYPTO_1D",
        family="BREAKOUT",
        asset_class="CRYPTO",
        timeframe="1D"
    ),
    TournamentBucket(
        bucket_id="BREAKOUT_EQUITY_1D",
        family="BREAKOUT",
        asset_class="EQUITY",
        timeframe="1D"
    ),
    TournamentBucket(
        bucket_id="MOMENTUM_CRYPTO_1D",
        family="MOMENTUM",
        asset_class="CRYPTO",
        timeframe="1D"
    ),
    TournamentBucket(
        bucket_id="REVERSAL_ALL_1D",
        family="REVERSAL",
        asset_class="ALL",
        timeframe="1D"
    ),
    TournamentBucket(
        bucket_id="CROSS_ASSET_MULTI_1D",
        family="CROSS_ASSET",
        asset_class="MULTI",
        timeframe="1D"
    ),
    TournamentBucket(
        bucket_id="EXPERIMENTAL_ALL_1D",
        family="EXPERIMENTAL",
        asset_class="ALL",
        timeframe="1D"
    ),
]
