"""
Strategy Lifecycle Engine Types
===============================

Manages the complete lifecycle of strategies:
birth → validation → growth → maturity → decay → death

States:
- CANDIDATE: Just created, not yet trusted
- SANDBOX: Local testing, no serious exposure
- VALIDATED: Passed validation pipeline
- SHADOW: Quasi-production mode
- LIMITED: Limited exposure in system
- CORE: Main battle-tested strategy
- MATURE: Long-term proven stability
- DEGRADED: Edge weakening, under observation
- DISABLED: Turned off
- ARCHIVED: Retired, kept for history
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


class LifecycleState(str, Enum):
    """Strategy lifecycle states"""
    CANDIDATE = "CANDIDATE"
    SANDBOX = "SANDBOX"
    VALIDATED = "VALIDATED"
    SHADOW = "SHADOW"
    LIMITED = "LIMITED"
    CORE = "CORE"
    MATURE = "MATURE"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"
    ARCHIVED = "ARCHIVED"


class StrategyAge(str, Enum):
    """Strategy age categories"""
    NEWBORN = "NEWBORN"      # < 7 days
    YOUNG = "YOUNG"          # 7-30 days
    ESTABLISHED = "ESTABLISHED"  # 30-90 days
    MATURE = "MATURE"        # 90-365 days
    OLD = "OLD"              # > 365 days


class DeathQuality(str, Enum):
    """How strategy died"""
    NATURAL = "NATURAL"      # Gradual edge decay
    REGIME = "REGIME"        # Market regime changed
    OVERFIT = "OVERFIT"      # Was overfit
    CROWDED = "CROWDED"      # Became crowded
    EXECUTION = "EXECUTION"  # Execution issues
    POLICY = "POLICY"        # Killed by policy
    UNKNOWN = "UNKNOWN"


# Allowed state transitions
ALLOWED_TRANSITIONS: Dict[LifecycleState, Set[LifecycleState]] = {
    LifecycleState.CANDIDATE: {LifecycleState.SANDBOX, LifecycleState.ARCHIVED},
    LifecycleState.SANDBOX: {LifecycleState.VALIDATED, LifecycleState.CANDIDATE, LifecycleState.ARCHIVED},
    LifecycleState.VALIDATED: {LifecycleState.SHADOW, LifecycleState.SANDBOX, LifecycleState.ARCHIVED},
    LifecycleState.SHADOW: {LifecycleState.LIMITED, LifecycleState.VALIDATED, LifecycleState.DEGRADED, LifecycleState.ARCHIVED},
    LifecycleState.LIMITED: {LifecycleState.CORE, LifecycleState.SHADOW, LifecycleState.DEGRADED, LifecycleState.ARCHIVED},
    LifecycleState.CORE: {LifecycleState.MATURE, LifecycleState.LIMITED, LifecycleState.DEGRADED, LifecycleState.DISABLED},
    LifecycleState.MATURE: {LifecycleState.CORE, LifecycleState.DEGRADED, LifecycleState.DISABLED},
    LifecycleState.DEGRADED: {LifecycleState.LIMITED, LifecycleState.SHADOW, LifecycleState.DISABLED},  # Recovery path
    LifecycleState.DISABLED: {LifecycleState.ARCHIVED, LifecycleState.SHADOW},  # Can recover to shadow
    LifecycleState.ARCHIVED: set(),  # Terminal state
}


# State configurations
STATE_CONFIG: Dict[LifecycleState, Dict[str, Any]] = {
    LifecycleState.CANDIDATE: {
        "description": "Just created, not yet trusted",
        "max_exposure": 0.0,
        "can_trade": False,
        "monitoring_level": "LOW",
        "min_days_in_state": 0
    },
    LifecycleState.SANDBOX: {
        "description": "Local testing, no serious exposure",
        "max_exposure": 0.0,
        "can_trade": False,
        "monitoring_level": "MEDIUM",
        "min_days_in_state": 3
    },
    LifecycleState.VALIDATED: {
        "description": "Passed validation pipeline",
        "max_exposure": 0.0,
        "can_trade": False,
        "monitoring_level": "MEDIUM",
        "min_days_in_state": 1
    },
    LifecycleState.SHADOW: {
        "description": "Quasi-production mode",
        "max_exposure": 0.0,
        "can_trade": False,
        "monitoring_level": "HIGH",
        "min_days_in_state": 14
    },
    LifecycleState.LIMITED: {
        "description": "Limited exposure in system",
        "max_exposure": 0.05,
        "can_trade": True,
        "monitoring_level": "HIGH",
        "min_days_in_state": 30
    },
    LifecycleState.CORE: {
        "description": "Main battle-tested strategy",
        "max_exposure": 0.15,
        "can_trade": True,
        "monitoring_level": "MEDIUM",
        "min_days_in_state": 60
    },
    LifecycleState.MATURE: {
        "description": "Long-term proven stability",
        "max_exposure": 0.20,
        "can_trade": True,
        "monitoring_level": "LOW",
        "min_days_in_state": 180
    },
    LifecycleState.DEGRADED: {
        "description": "Edge weakening, under observation",
        "max_exposure": 0.02,
        "can_trade": True,
        "monitoring_level": "CRITICAL",
        "min_days_in_state": 7
    },
    LifecycleState.DISABLED: {
        "description": "Turned off",
        "max_exposure": 0.0,
        "can_trade": False,
        "monitoring_level": "LOW",
        "min_days_in_state": 0
    },
    LifecycleState.ARCHIVED: {
        "description": "Retired, kept for history",
        "max_exposure": 0.0,
        "can_trade": False,
        "monitoring_level": "NONE",
        "min_days_in_state": 0
    },
}


@dataclass
class LifecycleScores:
    """Composite scores for lifecycle decisions"""
    sharpe: float = 0.0
    profit_factor: float = 0.0
    stability: float = 0.0
    regime_robustness: float = 0.0
    orthogonality: float = 0.0
    capital_efficiency: float = 0.0
    fragility_penalty: float = 0.0
    crowding: float = 0.0
    
    @property
    def lifecycle_score(self) -> float:
        """Calculate composite lifecycle score"""
        return (
            0.20 * self.sharpe +
            0.20 * self.profit_factor +
            0.15 * self.stability +
            0.15 * self.regime_robustness +
            0.10 * self.orthogonality +
            0.10 * self.capital_efficiency -
            0.05 * self.fragility_penalty -
            0.05 * self.crowding
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sharpe": round(self.sharpe, 3),
            "profit_factor": round(self.profit_factor, 3),
            "stability": round(self.stability, 3),
            "regime_robustness": round(self.regime_robustness, 3),
            "orthogonality": round(self.orthogonality, 3),
            "capital_efficiency": round(self.capital_efficiency, 3),
            "fragility_penalty": round(self.fragility_penalty, 3),
            "crowding": round(self.crowding, 3),
            "lifecycle_score": round(self.lifecycle_score, 3)
        }


@dataclass
class LifecycleTransition:
    """Record of a lifecycle transition"""
    transition_id: str
    strategy_id: str
    from_state: str
    to_state: str
    timestamp: int
    reason: str
    triggered_by: str
    scores_at_transition: Optional[LifecycleScores] = None
    
    @classmethod
    def create(
        cls,
        strategy_id: str,
        from_state: str,
        to_state: str,
        reason: str,
        triggered_by: str = "system"
    ) -> "LifecycleTransition":
        return cls(
            transition_id=f"lct_{uuid.uuid4().hex[:12]}",
            strategy_id=strategy_id,
            from_state=from_state,
            to_state=to_state,
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            reason=reason,
            triggered_by=triggered_by
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "strategy_id": self.strategy_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "scores_at_transition": self.scores_at_transition.to_dict() if self.scores_at_transition else None
        }


@dataclass
class StrategyLifecycleRecord:
    """Complete lifecycle record for a strategy"""
    strategy_id: str
    alpha_id: str
    name: str
    family: str
    
    # Current state
    current_state: LifecycleState
    state_entered_at: int
    previous_state: Optional[str] = None
    
    # Scores
    scores: LifecycleScores = field(default_factory=LifecycleScores)
    
    # Age tracking
    created_at: int = 0
    age_category: StrategyAge = StrategyAge.NEWBORN
    total_age_days: int = 0
    days_in_current_state: int = 0
    
    # History
    promotions: int = 0
    demotions: int = 0
    recovery_count: int = 0
    decay_incidents: int = 0
    
    # Shadow/Stress survival
    shadow_survival_rate: float = 1.0
    stress_survival_rate: float = 1.0
    
    # Death info (if applicable)
    death_quality: Optional[DeathQuality] = None
    death_reason: Optional[str] = None
    
    # Notes
    notes: str = ""
    
    @classmethod
    def create(
        cls,
        strategy_id: str,
        alpha_id: str,
        name: str,
        family: str
    ) -> "StrategyLifecycleRecord":
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        return cls(
            strategy_id=strategy_id,
            alpha_id=alpha_id,
            name=name,
            family=family,
            current_state=LifecycleState.CANDIDATE,
            state_entered_at=now,
            created_at=now
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "alpha_id": self.alpha_id,
            "name": self.name,
            "family": self.family,
            "current_state": self.current_state.value,
            "state_entered_at": self.state_entered_at,
            "previous_state": self.previous_state,
            "scores": self.scores.to_dict(),
            "created_at": self.created_at,
            "age_category": self.age_category.value,
            "total_age_days": self.total_age_days,
            "days_in_current_state": self.days_in_current_state,
            "promotions": self.promotions,
            "demotions": self.demotions,
            "recovery_count": self.recovery_count,
            "decay_incidents": self.decay_incidents,
            "shadow_survival_rate": round(self.shadow_survival_rate, 3),
            "stress_survival_rate": round(self.stress_survival_rate, 3),
            "death_quality": self.death_quality.value if self.death_quality else None,
            "death_reason": self.death_reason,
            "notes": self.notes
        }


@dataclass
class LifecycleMetrics:
    """Aggregate lifecycle metrics"""
    total_strategies: int = 0
    
    # By state
    strategies_by_state: Dict[str, int] = field(default_factory=dict)
    
    # Transitions
    total_promotions: int = 0
    total_demotions: int = 0
    total_recoveries: int = 0
    total_deaths: int = 0
    
    # Death reasons
    deaths_by_quality: Dict[str, int] = field(default_factory=dict)
    
    # Average stats
    avg_lifespan_days: float = 0.0
    avg_time_to_core_days: float = 0.0
    
    last_transition_at: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_strategies": self.total_strategies,
            "strategies_by_state": self.strategies_by_state,
            "total_promotions": self.total_promotions,
            "total_demotions": self.total_demotions,
            "total_recoveries": self.total_recoveries,
            "total_deaths": self.total_deaths,
            "deaths_by_quality": self.deaths_by_quality,
            "avg_lifespan_days": round(self.avg_lifespan_days, 1),
            "avg_time_to_core_days": round(self.avg_time_to_core_days, 1),
            "last_transition_at": self.last_transition_at
        }


def is_transition_allowed(from_state: LifecycleState, to_state: LifecycleState) -> bool:
    """Check if transition is allowed"""
    allowed = ALLOWED_TRANSITIONS.get(from_state, set())
    return to_state in allowed


def get_state_config(state: LifecycleState) -> Dict[str, Any]:
    """Get configuration for a state"""
    return STATE_CONFIG.get(state, {})


def calculate_age_category(days: int) -> StrategyAge:
    """Calculate age category from days"""
    if days < 7:
        return StrategyAge.NEWBORN
    elif days < 30:
        return StrategyAge.YOUNG
    elif days < 90:
        return StrategyAge.ESTABLISHED
    elif days < 365:
        return StrategyAge.MATURE
    else:
        return StrategyAge.OLD
