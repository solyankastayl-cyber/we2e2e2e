"""
Evolution Engine Types
======================

Types for the Self-Evolving Quant Platform (SEQP).

The Evolution Engine enables automatic:
- Alpha mutation
- Strategy evolution  
- Parameter optimization
- Edge decay detection
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


class EvolutionAction(str, Enum):
    """Evolution actions"""
    MUTATE_FEATURE = "MUTATE_FEATURE"
    MUTATE_ALPHA = "MUTATE_ALPHA"
    MUTATE_STRATEGY = "MUTATE_STRATEGY"
    ADJUST_PARAMETER = "ADJUST_PARAMETER"
    CLONE_ALPHA = "CLONE_ALPHA"
    CROSSOVER = "CROSSOVER"


class MutationType(str, Enum):
    """Types of mutations"""
    ARITHMETIC = "ARITHMETIC"       # +, -, *, /
    TEMPORAL = "TEMPORAL"           # lag, slope, persistence
    REGIME = "REGIME"               # regime_mask
    CROSS_ASSET = "CROSS_ASSET"     # relative features
    PARAMETER = "PARAMETER"         # threshold, period changes


class DecayReason(str, Enum):
    """Reasons for edge decay"""
    REGIME_SHIFT = "REGIME_SHIFT"
    CROWDING = "CROWDING"
    FEATURE_INSTABILITY = "FEATURE_INSTABILITY"
    MARKET_STRUCTURE = "MARKET_STRUCTURE"
    OVERFITTING = "OVERFITTING"
    UNKNOWN = "UNKNOWN"


class EvolutionStatus(str, Enum):
    """Status of evolution cycle"""
    PENDING = "PENDING"
    OBSERVING = "OBSERVING"
    ANALYZING = "ANALYZING"
    ADAPTING = "ADAPTING"
    EVOLVING = "EVOLVING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class DecaySignal:
    """Signal indicating edge decay"""
    alpha_id: str
    decay_rate: float  # -1 to 0 (negative = decaying)
    sharpe_current: float
    sharpe_baseline: float
    decay_reason: DecayReason
    confidence: float
    detected_at: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha_id": self.alpha_id,
            "decay_rate": self.decay_rate,
            "sharpe_current": self.sharpe_current,
            "sharpe_baseline": self.sharpe_baseline,
            "decay_reason": self.decay_reason.value,
            "confidence": self.confidence,
            "detected_at": self.detected_at
        }


@dataclass
class Mutation:
    """Record of a mutation"""
    mutation_id: str
    source_id: str  # Alpha/feature being mutated
    mutation_type: MutationType
    parameters: Dict[str, Any]
    result_id: str  # ID of resulting alpha/feature
    score: float
    promoted: bool
    created_at: int
    
    @classmethod
    def create(
        cls,
        source_id: str,
        mutation_type: MutationType,
        parameters: Dict[str, Any],
        result_id: str,
        score: float = 0.0
    ) -> "Mutation":
        return cls(
            mutation_id=f"mut_{uuid.uuid4().hex[:12]}",
            source_id=source_id,
            mutation_type=mutation_type,
            parameters=parameters,
            result_id=result_id,
            score=score,
            promoted=False,
            created_at=int(datetime.now(timezone.utc).timestamp() * 1000)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "source_id": self.source_id,
            "mutation_type": self.mutation_type.value,
            "parameters": self.parameters,
            "result_id": self.result_id,
            "score": self.score,
            "promoted": self.promoted,
            "created_at": self.created_at
        }


@dataclass
class EvolutionCycle:
    """Record of an evolution cycle"""
    cycle_id: str
    started_at: int
    completed_at: Optional[int] = None
    status: EvolutionStatus = EvolutionStatus.PENDING
    
    # Observation phase
    decay_signals: List[DecaySignal] = field(default_factory=list)
    
    # Analysis phase
    decay_reasons: Dict[str, int] = field(default_factory=dict)
    
    # Evolution phase
    mutations_created: int = 0
    mutations_tested: int = 0
    mutations_promoted: int = 0
    mutations: List[Mutation] = field(default_factory=list)
    
    # Metrics
    avg_sharpe_before: float = 0.0
    avg_sharpe_after: float = 0.0
    edge_recovery_rate: float = 0.0
    
    error_message: Optional[str] = None
    
    @classmethod
    def create(cls) -> "EvolutionCycle":
        return cls(
            cycle_id=f"evo_{uuid.uuid4().hex[:12]}",
            started_at=int(datetime.now(timezone.utc).timestamp() * 1000)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status.value,
            "decay_signals": [s.to_dict() for s in self.decay_signals],
            "decay_reasons": self.decay_reasons,
            "mutations_created": self.mutations_created,
            "mutations_tested": self.mutations_tested,
            "mutations_promoted": self.mutations_promoted,
            "avg_sharpe_before": self.avg_sharpe_before,
            "avg_sharpe_after": self.avg_sharpe_after,
            "edge_recovery_rate": self.edge_recovery_rate,
            "error_message": self.error_message
        }


@dataclass
class EvolutionConfig:
    """Configuration for evolution engine"""
    # Observation
    decay_threshold: float = -0.15  # When sharpe drops 15% from baseline
    min_observation_days: int = 30
    
    # Mutation
    max_mutations_per_cycle: int = 50
    mutation_types: List[MutationType] = field(default_factory=lambda: [
        MutationType.ARITHMETIC,
        MutationType.TEMPORAL,
        MutationType.REGIME
    ])
    
    # Selection
    tournament_rounds: int = 3
    promotion_threshold: float = 0.7  # Score threshold for promotion
    max_promoted_per_cycle: int = 5
    
    # Quality gates
    min_sharpe: float = 0.8
    max_correlation: float = 0.7  # With existing alphas
    min_trades: int = 30
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decay_threshold": self.decay_threshold,
            "min_observation_days": self.min_observation_days,
            "max_mutations_per_cycle": self.max_mutations_per_cycle,
            "mutation_types": [t.value for t in self.mutation_types],
            "tournament_rounds": self.tournament_rounds,
            "promotion_threshold": self.promotion_threshold,
            "max_promoted_per_cycle": self.max_promoted_per_cycle,
            "min_sharpe": self.min_sharpe,
            "max_correlation": self.max_correlation,
            "min_trades": self.min_trades
        }


@dataclass
class EvolutionMetrics:
    """Metrics for evolution engine"""
    total_cycles: int = 0
    successful_cycles: int = 0
    total_mutations: int = 0
    total_promoted: int = 0
    
    alpha_survival_rate: float = 0.0  # % of alphas that didn't decay
    mutation_success_rate: float = 0.0  # % of mutations that passed
    avg_edge_growth: float = 0.0  # Average edge improvement
    
    last_cycle_at: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cycles": self.total_cycles,
            "successful_cycles": self.successful_cycles,
            "total_mutations": self.total_mutations,
            "total_promoted": self.total_promoted,
            "alpha_survival_rate": round(self.alpha_survival_rate, 3),
            "mutation_success_rate": round(self.mutation_success_rate, 3),
            "avg_edge_growth": round(self.avg_edge_growth, 3),
            "last_cycle_at": self.last_cycle_at
        }
