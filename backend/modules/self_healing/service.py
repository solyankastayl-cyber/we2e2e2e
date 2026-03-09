"""
Phase 9.26: Self-Healing Strategy Engine
=========================================

Автоматическое восстановление и защита стратегий.

Компоненты:
1. Strategy Health Score Engine — расчёт здоровья
2. Auto Weight Adjuster — корректировка весов
3. Auto Demotion Engine — автоматическое понижение
4. Recovery Engine — восстановление стратегий
5. Regime/Asset Adaptive Healing — локальное исцеление
6. Audit Trail — история всех действий

API:
- GET /api/self-healing/status
- GET /api/self-healing/health
- GET /api/self-healing/events
- GET /api/self-healing/strategy/{id}
- POST /api/self-healing/recompute
- POST /api/self-healing/override
- POST /api/self-healing/recovery-check
"""
import time
import math
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# Types & Enums
# ═══════════════════════════════════════════════════════════════

class HealthVerdict(str, Enum):
    """Strategy health verdict"""
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class HealingAction(str, Enum):
    """Self-healing action types"""
    WEIGHT_REDUCED = "WEIGHT_REDUCED"
    WEIGHT_RESTORED = "WEIGHT_RESTORED"
    DEMOTED = "DEMOTED"
    PROMOTED = "PROMOTED"
    DISABLED = "DISABLED"
    RECOVERY_STARTED = "RECOVERY_STARTED"
    REGIME_RESTRICTED = "REGIME_RESTRICTED"
    ASSET_RESTRICTED = "ASSET_RESTRICTED"
    NO_ACTION = "NO_ACTION"


class RecoveryStatus(str, Enum):
    """Recovery status"""
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class StrategyHealthScore:
    """Complete health score for a strategy"""
    strategy_id: str
    
    # Rolling metrics
    rolling_pf: float = 0.0
    rolling_wr: float = 0.0
    rolling_sharpe: float = 0.0
    rolling_drawdown: float = 0.0
    recent_trade_count: int = 0
    
    # Component scores (0-1)
    rolling_pf_score: float = 0.0
    rolling_sharpe_score: float = 0.0
    drawdown_score: float = 0.0
    edge_decay_score: float = 0.0
    regime_fit_score: float = 0.0
    confidence_integrity_score: float = 0.0
    overfit_risk_score: float = 0.0
    
    # Final health
    health_score: float = 0.0
    verdict: HealthVerdict = HealthVerdict.HEALTHY
    
    # Trend
    health_trend: str = "STABLE"  # IMPROVING, STABLE, DECLINING
    previous_health_score: float = 0.0
    
    computed_at: int = 0


@dataclass
class RegimeHealthState:
    """Health state for a strategy in a specific regime"""
    strategy_id: str
    regime: str
    
    pf: float = 0.0
    wr: float = 0.0
    sharpe: float = 0.0
    trades: int = 0
    
    health_score: float = 0.0
    verdict: HealthVerdict = HealthVerdict.HEALTHY
    
    is_restricted: bool = False
    restriction_reason: str = ""


@dataclass
class AssetHealthState:
    """Health state for a strategy on a specific asset"""
    strategy_id: str
    asset: str
    
    pf: float = 0.0
    wr: float = 0.0
    sharpe: float = 0.0
    trades: int = 0
    
    health_score: float = 0.0
    verdict: HealthVerdict = HealthVerdict.HEALTHY
    
    is_restricted: bool = False
    restriction_reason: str = ""


@dataclass
class WeightAdjustment:
    """Weight adjustment record"""
    strategy_id: str
    old_weight: float
    new_weight: float
    target_weight: float
    
    reason: str = ""
    daily_change: float = 0.0
    
    adjusted_at: int = 0


@dataclass
class RecoveryState:
    """Recovery state for a strategy"""
    strategy_id: str
    status: RecoveryStatus = RecoveryStatus.NOT_STARTED
    
    # Recovery progress
    recovery_trades: int = 0
    recovery_pf: float = 0.0
    recovery_sharpe: float = 0.0
    
    # Targets
    target_trades: int = 50
    target_pf: float = 1.2
    target_sharpe: float = 0.8
    
    # Progress
    progress_pct: float = 0.0
    
    # Timing
    started_at: int = 0
    completed_at: int = 0
    grace_period_ends: int = 0


@dataclass
class SelfHealingEvent:
    """Audit trail event"""
    event_id: str
    strategy_id: str
    timestamp: int
    
    action: HealingAction
    old_state: str
    new_state: str
    
    reason: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class SelfHealingStatus:
    """Overall self-healing status"""
    enabled: bool = True
    mode: str = "AUTO"  # AUTO, MANUAL, DISABLED
    
    # Summary
    healthy_strategies: int = 0
    warning_strategies: int = 0
    degraded_strategies: int = 0
    critical_strategies: int = 0
    
    # Recent activity
    recent_demotions: int = 0
    recent_recoveries: int = 0
    recent_weight_adjustments: int = 0
    
    # Active restrictions
    regime_restrictions: int = 0
    asset_restrictions: int = 0
    
    last_recompute: int = 0
    version: str = "phase9.26"


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

SELF_HEALING_CONFIG = {
    "version": "phase9.26",
    "enabled": True,
    "mode": "AUTO",
    
    # Health thresholds
    "health_thresholds": {
        "healthy": 0.80,
        "warning": 0.60,
        "degraded": 0.40,
        "critical": 0.25
    },
    
    # Weight adjustment multipliers
    "weight_adjustment": {
        "HEALTHY": 1.0,
        "WARNING": 0.75,
        "DEGRADED": 0.40,
        "CRITICAL": 0.0
    },
    
    # Maximum daily/weekly weight changes
    "weight_limits": {
        "max_daily_change": 0.10,  # 10%
        "max_weekly_change": 0.25  # 25%
    },
    
    # Demotion rules
    "demotion_rules": {
        "approved_to_limited": {
            "min_pf": 1.1,
            "consecutive_windows": 2
        },
        "limited_to_watch": {
            "min_pf": 1.0,
            "consecutive_windows": 2
        },
        "watch_to_disabled": {
            "critical_windows": 2
        }
    },
    
    # Recovery rules
    "recovery_rules": {
        "min_trades": 50,
        "min_pf": 1.2,
        "min_sharpe": 0.8,
        "grace_period_days": 14
    },
    
    # Regime healing thresholds
    "regime_healing": {
        "min_regime_pf": 1.0,
        "min_regime_trades": 20,
        "restriction_threshold": 0.40
    },
    
    # Asset healing thresholds
    "asset_healing": {
        "min_asset_pf": 1.0,
        "min_asset_trades": 15,
        "restriction_threshold": 0.40
    },
    
    # Health score weights
    "score_weights": {
        "rolling_pf": 0.30,
        "rolling_sharpe": 0.20,
        "drawdown": 0.15,
        "edge_decay": 0.15,
        "regime_fit": 0.10,
        "confidence_integrity": 0.10
    }
}


# ═══════════════════════════════════════════════════════════════
# Strategy Health Score Engine
# ═══════════════════════════════════════════════════════════════

class StrategyHealthEngine:
    """
    Calculates health scores for strategies.
    
    Health Score = weighted combination of:
    - Rolling PF score
    - Rolling Sharpe score
    - Drawdown score
    - Edge decay score
    - Regime fit score
    - Confidence integrity score
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or SELF_HEALING_CONFIG
        self._health_scores: Dict[str, StrategyHealthScore] = {}
        self._health_history: Dict[str, List[float]] = {}
    
    def compute_health(
        self,
        strategy_id: str,
        rolling_metrics: Optional[Dict] = None,
        edge_metrics: Optional[Dict] = None,
        regime_metrics: Optional[Dict] = None
    ) -> StrategyHealthScore:
        """
        Compute health score for a strategy.
        """
        weights = self.config.get("score_weights", {})
        thresholds = self.config.get("health_thresholds", {})
        
        # Get or simulate metrics
        rm = rolling_metrics or self._get_default_rolling(strategy_id)
        em = edge_metrics or self._get_default_edge(strategy_id)
        rgm = regime_metrics or self._get_default_regime(strategy_id)
        
        # Calculate component scores (0-1 scale)
        rolling_pf_score = self._normalize_pf(rm.get("pf", 1.5))
        rolling_sharpe_score = self._normalize_sharpe(rm.get("sharpe", 1.2))
        drawdown_score = self._normalize_dd(rm.get("dd", 0.10))
        edge_decay_score = em.get("edge_health", 0.8)
        regime_fit_score = rgm.get("regime_fit", 0.7)
        confidence_score = em.get("confidence_integrity", 0.85)
        
        # Calculate weighted health score
        health_score = (
            rolling_pf_score * weights.get("rolling_pf", 0.30) +
            rolling_sharpe_score * weights.get("rolling_sharpe", 0.20) +
            drawdown_score * weights.get("drawdown", 0.15) +
            edge_decay_score * weights.get("edge_decay", 0.15) +
            regime_fit_score * weights.get("regime_fit", 0.10) +
            confidence_score * weights.get("confidence_integrity", 0.10)
        )
        
        health_score = max(0, min(1, health_score))
        
        # Determine verdict
        if health_score >= thresholds.get("healthy", 0.80):
            verdict = HealthVerdict.HEALTHY
        elif health_score >= thresholds.get("warning", 0.60):
            verdict = HealthVerdict.WARNING
        elif health_score >= thresholds.get("degraded", 0.40):
            verdict = HealthVerdict.DEGRADED
        else:
            verdict = HealthVerdict.CRITICAL
        
        # Calculate trend
        prev_score = self._health_scores.get(strategy_id)
        previous_health = prev_score.health_score if prev_score else health_score
        
        if health_score > previous_health + 0.05:
            trend = "IMPROVING"
        elif health_score < previous_health - 0.05:
            trend = "DECLINING"
        else:
            trend = "STABLE"
        
        # Store history
        if strategy_id not in self._health_history:
            self._health_history[strategy_id] = []
        self._health_history[strategy_id].append(health_score)
        if len(self._health_history[strategy_id]) > 100:
            self._health_history[strategy_id] = self._health_history[strategy_id][-100:]
        
        score = StrategyHealthScore(
            strategy_id=strategy_id,
            rolling_pf=rm.get("pf", 0),
            rolling_wr=rm.get("wr", 0),
            rolling_sharpe=rm.get("sharpe", 0),
            rolling_drawdown=rm.get("dd", 0),
            recent_trade_count=rm.get("trades", 0),
            rolling_pf_score=round(rolling_pf_score, 4),
            rolling_sharpe_score=round(rolling_sharpe_score, 4),
            drawdown_score=round(drawdown_score, 4),
            edge_decay_score=round(edge_decay_score, 4),
            regime_fit_score=round(regime_fit_score, 4),
            confidence_integrity_score=round(confidence_score, 4),
            overfit_risk_score=round(1 - em.get("overfit_risk", 0.2), 4),
            health_score=round(health_score, 4),
            verdict=verdict,
            health_trend=trend,
            previous_health_score=round(previous_health, 4),
            computed_at=int(time.time() * 1000)
        )
        
        self._health_scores[strategy_id] = score
        return score
    
    def get_health(self, strategy_id: str) -> Optional[StrategyHealthScore]:
        """Get cached health score"""
        return self._health_scores.get(strategy_id)
    
    def get_all_health(self) -> Dict[str, StrategyHealthScore]:
        """Get all health scores"""
        return self._health_scores
    
    def _normalize_pf(self, pf: float) -> float:
        """Normalize PF to 0-1 score"""
        if pf <= 0.5:
            return 0.0
        if pf >= 3.0:
            return 1.0
        return (pf - 0.5) / 2.5
    
    def _normalize_sharpe(self, sharpe: float) -> float:
        """Normalize Sharpe to 0-1 score"""
        if sharpe <= 0:
            return 0.0
        if sharpe >= 3.0:
            return 1.0
        return sharpe / 3.0
    
    def _normalize_dd(self, dd: float) -> float:
        """Normalize drawdown to 0-1 score (inverse)"""
        if dd >= 0.50:
            return 0.0
        if dd <= 0.02:
            return 1.0
        return 1.0 - (dd / 0.50)
    
    def _get_default_rolling(self, strategy_id: str) -> Dict:
        """Get default rolling metrics"""
        # Simulated based on strategy
        defaults = {
            "MTF_BREAKOUT": {"pf": 2.1, "wr": 0.64, "sharpe": 1.8, "dd": 0.07, "trades": 100},
            "DOUBLE_BOTTOM": {"pf": 2.3, "wr": 0.66, "sharpe": 1.9, "dd": 0.06, "trades": 95},
            "DOUBLE_TOP": {"pf": 2.0, "wr": 0.63, "sharpe": 1.7, "dd": 0.08, "trades": 90},
            "CHANNEL_BREAKOUT": {"pf": 1.8, "wr": 0.58, "sharpe": 1.5, "dd": 0.09, "trades": 85},
            "MOMENTUM_CONTINUATION": {"pf": 1.9, "wr": 0.62, "sharpe": 1.6, "dd": 0.08, "trades": 92},
            "HEAD_SHOULDERS": {"pf": 1.25, "wr": 0.52, "sharpe": 0.9, "dd": 0.12, "trades": 50},
            "HARMONIC_ABCD": {"pf": 1.4, "wr": 0.54, "sharpe": 1.0, "dd": 0.11, "trades": 45},
            "WEDGE_RISING": {"pf": 1.15, "wr": 0.51, "sharpe": 0.7, "dd": 0.14, "trades": 40},
            "WEDGE_FALLING": {"pf": 1.2, "wr": 0.53, "sharpe": 0.8, "dd": 0.13, "trades": 42},
            "LIQUIDITY_SWEEP": {"pf": 0.85, "wr": 0.42, "sharpe": 0.3, "dd": 0.20, "trades": 60},
            "RANGE_REVERSAL": {"pf": 0.72, "wr": 0.36, "sharpe": 0.1, "dd": 0.25, "trades": 55},
        }
        return defaults.get(strategy_id, {"pf": 1.5, "wr": 0.55, "sharpe": 1.2, "dd": 0.10, "trades": 50})
    
    def _get_default_edge(self, strategy_id: str) -> Dict:
        """Get default edge metrics"""
        base = hash(strategy_id) % 100 / 100
        return {
            "edge_health": 0.7 + base * 0.25,
            "confidence_integrity": 0.75 + base * 0.20,
            "overfit_risk": 0.1 + base * 0.15
        }
    
    def _get_default_regime(self, strategy_id: str) -> Dict:
        """Get default regime metrics"""
        base = hash(strategy_id) % 100 / 100
        return {
            "regime_fit": 0.65 + base * 0.30
        }


# ═══════════════════════════════════════════════════════════════
# Auto Weight Adjuster
# ═══════════════════════════════════════════════════════════════

class AutoWeightAdjuster:
    """
    Automatically adjusts strategy weights based on health.
    
    Respects daily/weekly change limits to prevent jerky behavior.
    """
    
    def __init__(self, config: Optional[Dict] = None, health_engine: Optional[StrategyHealthEngine] = None):
        self.config = config or SELF_HEALING_CONFIG
        self.health_engine = health_engine or StrategyHealthEngine(config)
        
        self._current_weights: Dict[str, float] = {}
        self._daily_changes: Dict[str, float] = {}
        self._adjustments: List[WeightAdjustment] = []
        
        # Initialize with default weights
        for s in ["MTF_BREAKOUT", "DOUBLE_BOTTOM", "DOUBLE_TOP", "CHANNEL_BREAKOUT", 
                  "MOMENTUM_CONTINUATION", "HEAD_SHOULDERS", "HARMONIC_ABCD",
                  "WEDGE_RISING", "WEDGE_FALLING", "LIQUIDITY_SWEEP", "RANGE_REVERSAL"]:
            self._current_weights[s] = 1.0
    
    def compute_adjustment(self, strategy_id: str) -> WeightAdjustment:
        """
        Compute weight adjustment for a strategy.
        """
        health = self.health_engine.get_health(strategy_id)
        if not health:
            health = self.health_engine.compute_health(strategy_id)
        
        weight_map = self.config.get("weight_adjustment", {})
        limits = self.config.get("weight_limits", {})
        
        # Get target weight based on verdict
        target = weight_map.get(health.verdict.value, 1.0)
        current = self._current_weights.get(strategy_id, 1.0)
        
        # Calculate desired change
        desired_change = target - current
        
        # Apply daily limit
        max_daily = limits.get("max_daily_change", 0.10)
        daily_used = self._daily_changes.get(strategy_id, 0.0)
        available = max_daily - abs(daily_used)
        
        if abs(desired_change) > available:
            actual_change = available * (1 if desired_change > 0 else -1)
        else:
            actual_change = desired_change
        
        new_weight = max(0, min(1.5, current + actual_change))
        
        # Create adjustment record
        reason = f"Health verdict: {health.verdict.value} (score: {health.health_score:.2f})"
        
        adjustment = WeightAdjustment(
            strategy_id=strategy_id,
            old_weight=round(current, 4),
            new_weight=round(new_weight, 4),
            target_weight=round(target, 4),
            reason=reason,
            daily_change=round(actual_change, 4),
            adjusted_at=int(time.time() * 1000)
        )
        
        # Apply adjustment
        if abs(actual_change) > 0.001:
            self._current_weights[strategy_id] = new_weight
            self._daily_changes[strategy_id] = daily_used + actual_change
            self._adjustments.append(adjustment)
        
        return adjustment
    
    def get_weight(self, strategy_id: str) -> float:
        """Get current weight"""
        return self._current_weights.get(strategy_id, 1.0)
    
    def get_all_weights(self) -> Dict[str, float]:
        """Get all weights"""
        return self._current_weights
    
    def get_recent_adjustments(self, limit: int = 50) -> List[WeightAdjustment]:
        """Get recent adjustments"""
        return self._adjustments[-limit:]
    
    def reset_daily_changes(self):
        """Reset daily change tracking (call at day boundary)"""
        self._daily_changes = {}


# ═══════════════════════════════════════════════════════════════
# Auto Demotion Engine
# ═══════════════════════════════════════════════════════════════

class AutoDemotionEngine:
    """
    Automatically demotes strategies based on health degradation.
    
    Tracks consecutive warning windows to trigger demotions.
    """
    
    def __init__(self, config: Optional[Dict] = None, health_engine: Optional[StrategyHealthEngine] = None):
        self.config = config or SELF_HEALING_CONFIG
        self.health_engine = health_engine or StrategyHealthEngine(config)
        
        self._consecutive_warnings: Dict[str, int] = {}
        self._consecutive_critical: Dict[str, int] = {}
        self._lifecycle_states: Dict[str, str] = {}
        self._demotions: List[Dict] = []
        
        # Initialize lifecycle states
        states = {
            "MTF_BREAKOUT": "APPROVED", "DOUBLE_BOTTOM": "APPROVED", "DOUBLE_TOP": "APPROVED",
            "CHANNEL_BREAKOUT": "APPROVED", "MOMENTUM_CONTINUATION": "APPROVED",
            "HEAD_SHOULDERS": "LIMITED", "HARMONIC_ABCD": "LIMITED",
            "WEDGE_RISING": "LIMITED", "WEDGE_FALLING": "LIMITED",
            "LIQUIDITY_SWEEP": "DEPRECATED", "RANGE_REVERSAL": "DEPRECATED"
        }
        self._lifecycle_states = states
    
    def check_demotion(self, strategy_id: str) -> Optional[Dict]:
        """
        Check if strategy should be demoted.
        
        Returns demotion action if triggered, None otherwise.
        """
        health = self.health_engine.get_health(strategy_id)
        if not health:
            health = self.health_engine.compute_health(strategy_id)
        
        rules = self.config.get("demotion_rules", {})
        current_state = self._lifecycle_states.get(strategy_id, "APPROVED")
        
        # Track consecutive warnings
        if health.verdict == HealthVerdict.WARNING:
            self._consecutive_warnings[strategy_id] = self._consecutive_warnings.get(strategy_id, 0) + 1
        else:
            self._consecutive_warnings[strategy_id] = 0
        
        if health.verdict == HealthVerdict.CRITICAL:
            self._consecutive_critical[strategy_id] = self._consecutive_critical.get(strategy_id, 0) + 1
        else:
            self._consecutive_critical[strategy_id] = 0
        
        # Check demotion conditions
        demotion = None
        
        # APPROVED → LIMITED
        if current_state == "APPROVED":
            rule = rules.get("approved_to_limited", {})
            if health.rolling_pf < rule.get("min_pf", 1.1):
                if self._consecutive_warnings.get(strategy_id, 0) >= rule.get("consecutive_windows", 2):
                    demotion = self._execute_demotion(strategy_id, "APPROVED", "LIMITED",
                        f"PF {health.rolling_pf:.2f} < {rule.get('min_pf')} for {rule.get('consecutive_windows')} windows")
        
        # LIMITED → WATCH
        elif current_state == "LIMITED":
            rule = rules.get("limited_to_watch", {})
            if health.rolling_pf < rule.get("min_pf", 1.0):
                if self._consecutive_warnings.get(strategy_id, 0) >= rule.get("consecutive_windows", 2):
                    demotion = self._execute_demotion(strategy_id, "LIMITED", "WATCH",
                        f"PF {health.rolling_pf:.2f} < {rule.get('min_pf')} for {rule.get('consecutive_windows')} windows")
        
        # WATCH → DISABLED
        elif current_state == "WATCH":
            rule = rules.get("watch_to_disabled", {})
            if self._consecutive_critical.get(strategy_id, 0) >= rule.get("critical_windows", 2):
                demotion = self._execute_demotion(strategy_id, "WATCH", "DISABLED",
                    f"CRITICAL for {rule.get('critical_windows')} consecutive windows")
        
        return demotion
    
    def _execute_demotion(self, strategy_id: str, from_state: str, to_state: str, reason: str) -> Dict:
        """Execute demotion and record it"""
        self._lifecycle_states[strategy_id] = to_state
        
        demotion = {
            "strategy_id": strategy_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "timestamp": int(time.time() * 1000)
        }
        
        self._demotions.append(demotion)
        return demotion
    
    def get_lifecycle(self, strategy_id: str) -> str:
        """Get current lifecycle state"""
        return self._lifecycle_states.get(strategy_id, "APPROVED")
    
    def get_all_lifecycles(self) -> Dict[str, str]:
        """Get all lifecycle states"""
        return self._lifecycle_states
    
    def get_recent_demotions(self, limit: int = 20) -> List[Dict]:
        """Get recent demotions"""
        return self._demotions[-limit:]


# ═══════════════════════════════════════════════════════════════
# Recovery Engine
# ═══════════════════════════════════════════════════════════════

class RecoveryEngine:
    """
    Manages strategy recovery from degraded states.
    
    Strategies can recover if they meet recovery criteria over grace period.
    """
    
    def __init__(self, config: Optional[Dict] = None, health_engine: Optional[StrategyHealthEngine] = None):
        self.config = config or SELF_HEALING_CONFIG
        self.health_engine = health_engine or StrategyHealthEngine(config)
        
        self._recovery_states: Dict[str, RecoveryState] = {}
        self._recoveries: List[Dict] = []
    
    def start_recovery(self, strategy_id: str) -> RecoveryState:
        """Start recovery process for a strategy"""
        rules = self.config.get("recovery_rules", {})
        grace_days = rules.get("grace_period_days", 14)
        
        now = int(time.time() * 1000)
        
        state = RecoveryState(
            strategy_id=strategy_id,
            status=RecoveryStatus.IN_PROGRESS,
            target_trades=rules.get("min_trades", 50),
            target_pf=rules.get("min_pf", 1.2),
            target_sharpe=rules.get("min_sharpe", 0.8),
            started_at=now,
            grace_period_ends=now + grace_days * 86400 * 1000
        )
        
        self._recovery_states[strategy_id] = state
        return state
    
    def check_recovery(self, strategy_id: str) -> RecoveryState:
        """Check recovery progress"""
        state = self._recovery_states.get(strategy_id)
        
        if not state or state.status != RecoveryStatus.IN_PROGRESS:
            return state or RecoveryState(strategy_id=strategy_id)
        
        health = self.health_engine.get_health(strategy_id)
        if not health:
            health = self.health_engine.compute_health(strategy_id)
        
        # Update recovery metrics
        state.recovery_trades = health.recent_trade_count
        state.recovery_pf = health.rolling_pf
        state.recovery_sharpe = health.rolling_sharpe
        
        # Calculate progress
        trades_progress = min(1.0, state.recovery_trades / state.target_trades)
        pf_progress = min(1.0, state.recovery_pf / state.target_pf) if state.target_pf > 0 else 0
        sharpe_progress = min(1.0, state.recovery_sharpe / state.target_sharpe) if state.target_sharpe > 0 else 0
        
        state.progress_pct = round((trades_progress + pf_progress + sharpe_progress) / 3 * 100, 1)
        
        # Check completion
        now = int(time.time() * 1000)
        
        if state.recovery_trades >= state.target_trades and \
           state.recovery_pf >= state.target_pf and \
           state.recovery_sharpe >= state.target_sharpe:
            state.status = RecoveryStatus.COMPLETED
            state.completed_at = now
            
            self._recoveries.append({
                "strategy_id": strategy_id,
                "status": "COMPLETED",
                "final_pf": state.recovery_pf,
                "timestamp": now
            })
        
        # Check timeout
        elif now > state.grace_period_ends:
            state.status = RecoveryStatus.FAILED
            state.completed_at = now
            
            self._recoveries.append({
                "strategy_id": strategy_id,
                "status": "FAILED",
                "reason": "Grace period expired",
                "timestamp": now
            })
        
        self._recovery_states[strategy_id] = state
        return state
    
    def get_recovery(self, strategy_id: str) -> Optional[RecoveryState]:
        """Get recovery state"""
        return self._recovery_states.get(strategy_id)
    
    def get_all_recoveries(self) -> Dict[str, RecoveryState]:
        """Get all recovery states"""
        return self._recovery_states
    
    def get_recent_recoveries(self, limit: int = 20) -> List[Dict]:
        """Get recent completed/failed recoveries"""
        return self._recoveries[-limit:]


# ═══════════════════════════════════════════════════════════════
# Regime/Asset Adaptive Healing
# ═══════════════════════════════════════════════════════════════

class AdaptiveHealingEngine:
    """
    Manages regime-specific and asset-specific healing.
    
    A strategy may be healthy overall but degraded in specific regimes/assets.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or SELF_HEALING_CONFIG
        
        self._regime_states: Dict[str, Dict[str, RegimeHealthState]] = {}
        self._asset_states: Dict[str, Dict[str, AssetHealthState]] = {}
        self._restrictions: List[Dict] = []
    
    def compute_regime_health(
        self,
        strategy_id: str,
        regime_metrics: Optional[Dict[str, Dict]] = None
    ) -> Dict[str, RegimeHealthState]:
        """
        Compute health for each regime.
        """
        thresholds = self.config.get("regime_healing", {})
        min_pf = thresholds.get("min_regime_pf", 1.0)
        restriction_threshold = thresholds.get("restriction_threshold", 0.40)
        
        regimes = regime_metrics or self._get_default_regime_metrics(strategy_id)
        
        results = {}
        for regime, metrics in regimes.items():
            health_score = self._calculate_regime_score(metrics)
            
            if health_score >= 0.6:
                verdict = HealthVerdict.HEALTHY
            elif health_score >= 0.4:
                verdict = HealthVerdict.WARNING
            elif health_score >= 0.25:
                verdict = HealthVerdict.DEGRADED
            else:
                verdict = HealthVerdict.CRITICAL
            
            is_restricted = health_score < restriction_threshold or metrics.get("pf", 1.0) < min_pf
            
            state = RegimeHealthState(
                strategy_id=strategy_id,
                regime=regime,
                pf=metrics.get("pf", 1.0),
                wr=metrics.get("wr", 0.5),
                sharpe=metrics.get("sharpe", 1.0),
                trades=metrics.get("trades", 0),
                health_score=round(health_score, 4),
                verdict=verdict,
                is_restricted=is_restricted,
                restriction_reason=f"Health score {health_score:.2f} below threshold" if is_restricted else ""
            )
            
            results[regime] = state
            
            if is_restricted:
                self._restrictions.append({
                    "type": "REGIME",
                    "strategy_id": strategy_id,
                    "regime": regime,
                    "reason": state.restriction_reason,
                    "timestamp": int(time.time() * 1000)
                })
        
        self._regime_states[strategy_id] = results
        return results
    
    def compute_asset_health(
        self,
        strategy_id: str,
        asset_metrics: Optional[Dict[str, Dict]] = None
    ) -> Dict[str, AssetHealthState]:
        """
        Compute health for each asset.
        """
        thresholds = self.config.get("asset_healing", {})
        min_pf = thresholds.get("min_asset_pf", 1.0)
        restriction_threshold = thresholds.get("restriction_threshold", 0.40)
        
        assets = asset_metrics or self._get_default_asset_metrics(strategy_id)
        
        results = {}
        for asset, metrics in assets.items():
            health_score = self._calculate_asset_score(metrics)
            
            if health_score >= 0.6:
                verdict = HealthVerdict.HEALTHY
            elif health_score >= 0.4:
                verdict = HealthVerdict.WARNING
            elif health_score >= 0.25:
                verdict = HealthVerdict.DEGRADED
            else:
                verdict = HealthVerdict.CRITICAL
            
            is_restricted = health_score < restriction_threshold or metrics.get("pf", 1.0) < min_pf
            
            state = AssetHealthState(
                strategy_id=strategy_id,
                asset=asset,
                pf=metrics.get("pf", 1.0),
                wr=metrics.get("wr", 0.5),
                sharpe=metrics.get("sharpe", 1.0),
                trades=metrics.get("trades", 0),
                health_score=round(health_score, 4),
                verdict=verdict,
                is_restricted=is_restricted,
                restriction_reason=f"Health score {health_score:.2f} below threshold" if is_restricted else ""
            )
            
            results[asset] = state
            
            if is_restricted:
                self._restrictions.append({
                    "type": "ASSET",
                    "strategy_id": strategy_id,
                    "asset": asset,
                    "reason": state.restriction_reason,
                    "timestamp": int(time.time() * 1000)
                })
        
        self._asset_states[strategy_id] = results
        return results
    
    def get_regime_states(self, strategy_id: str) -> Dict[str, RegimeHealthState]:
        """Get regime states for strategy"""
        return self._regime_states.get(strategy_id, {})
    
    def get_asset_states(self, strategy_id: str) -> Dict[str, AssetHealthState]:
        """Get asset states for strategy"""
        return self._asset_states.get(strategy_id, {})
    
    def get_restrictions(self, limit: int = 50) -> List[Dict]:
        """Get recent restrictions"""
        return self._restrictions[-limit:]
    
    def _calculate_regime_score(self, metrics: Dict) -> float:
        """Calculate regime health score"""
        pf = metrics.get("pf", 1.0)
        wr = metrics.get("wr", 0.5)
        
        pf_score = min(1, max(0, (pf - 0.5) / 2.0))
        wr_score = min(1, max(0, (wr - 0.3) / 0.4))
        
        return pf_score * 0.6 + wr_score * 0.4
    
    def _calculate_asset_score(self, metrics: Dict) -> float:
        """Calculate asset health score"""
        return self._calculate_regime_score(metrics)
    
    def _get_default_regime_metrics(self, strategy_id: str) -> Dict[str, Dict]:
        """Get default regime metrics"""
        base = hash(strategy_id) % 100
        return {
            "TREND_UP": {"pf": 2.0 + base/100, "wr": 0.60, "sharpe": 1.5, "trades": 50},
            "TREND_DOWN": {"pf": 1.8 + base/100, "wr": 0.58, "sharpe": 1.4, "trades": 45},
            "RANGE": {"pf": 1.2 + base/200, "wr": 0.52, "sharpe": 0.9, "trades": 40},
            "COMPRESSION": {"pf": 1.3 + base/150, "wr": 0.54, "sharpe": 1.0, "trades": 30},
            "EXPANSION": {"pf": 2.2 + base/80, "wr": 0.62, "sharpe": 1.7, "trades": 25}
        }
    
    def _get_default_asset_metrics(self, strategy_id: str) -> Dict[str, Dict]:
        """Get default asset metrics"""
        base = hash(strategy_id) % 100
        return {
            "BTC": {"pf": 2.2 + base/100, "wr": 0.58, "sharpe": 1.6, "trades": 80},
            "ETH": {"pf": 2.4 + base/100, "wr": 0.60, "sharpe": 1.7, "trades": 75},
            "SOL": {"pf": 2.8 + base/80, "wr": 0.64, "sharpe": 2.0, "trades": 70},
            "SPX": {"pf": 2.0 + base/120, "wr": 0.62, "sharpe": 1.5, "trades": 85},
            "GOLD": {"pf": 1.6 + base/150, "wr": 0.56, "sharpe": 1.2, "trades": 60},
            "DXY": {"pf": 1.7 + base/140, "wr": 0.57, "sharpe": 1.3, "trades": 65}
        }


# ═══════════════════════════════════════════════════════════════
# Audit Trail
# ═══════════════════════════════════════════════════════════════

class AuditTrail:
    """
    Records all self-healing actions for compliance and analysis.
    """
    
    def __init__(self):
        self._events: List[SelfHealingEvent] = []
    
    def record(
        self,
        strategy_id: str,
        action: HealingAction,
        old_state: str,
        new_state: str,
        reason: str = "",
        metadata: Optional[Dict] = None
    ) -> SelfHealingEvent:
        """Record a healing event"""
        event = SelfHealingEvent(
            event_id=f"event_{int(time.time() * 1000)}_{len(self._events)}",
            strategy_id=strategy_id,
            timestamp=int(time.time() * 1000),
            action=action,
            old_state=old_state,
            new_state=new_state,
            reason=reason,
            metadata=metadata or {}
        )
        
        self._events.append(event)
        return event
    
    def get_events(self, limit: int = 100) -> List[SelfHealingEvent]:
        """Get recent events"""
        return self._events[-limit:]
    
    def get_events_for_strategy(self, strategy_id: str, limit: int = 50) -> List[SelfHealingEvent]:
        """Get events for a specific strategy"""
        return [e for e in self._events if e.strategy_id == strategy_id][-limit:]
    
    def get_events_by_action(self, action: HealingAction, limit: int = 50) -> List[SelfHealingEvent]:
        """Get events by action type"""
        return [e for e in self._events if e.action == action][-limit:]


# ═══════════════════════════════════════════════════════════════
# Self-Healing Service
# ═══════════════════════════════════════════════════════════════

class SelfHealingService:
    """
    Main Self-Healing Service.
    
    Orchestrates:
    - Health scoring
    - Weight adjustments
    - Demotions/promotions
    - Recovery tracking
    - Adaptive healing
    - Audit trail
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or SELF_HEALING_CONFIG
        
        self.health_engine = StrategyHealthEngine(config)
        self.weight_adjuster = AutoWeightAdjuster(config, self.health_engine)
        self.demotion_engine = AutoDemotionEngine(config, self.health_engine)
        self.recovery_engine = RecoveryEngine(config, self.health_engine)
        self.adaptive_healing = AdaptiveHealingEngine(config)
        self.audit_trail = AuditTrail()
        
        self._last_recompute = 0
    
    def recompute_all(self, strategies: Optional[List[str]] = None) -> Dict:
        """
        Recompute health and adjustments for all strategies.
        """
        if strategies is None:
            strategies = [
                "MTF_BREAKOUT", "DOUBLE_BOTTOM", "DOUBLE_TOP", "CHANNEL_BREAKOUT",
                "MOMENTUM_CONTINUATION", "HEAD_SHOULDERS", "HARMONIC_ABCD",
                "WEDGE_RISING", "WEDGE_FALLING", "LIQUIDITY_SWEEP", "RANGE_REVERSAL"
            ]
        
        results = {
            "health": {},
            "weights": {},
            "demotions": [],
            "recoveries": [],
            "regime_states": {},
            "asset_states": {},
            "events": []
        }
        
        for strategy_id in strategies:
            # Compute health
            health = self.health_engine.compute_health(strategy_id)
            results["health"][strategy_id] = health_to_dict(health)
            
            # Compute weight adjustment
            adjustment = self.weight_adjuster.compute_adjustment(strategy_id)
            results["weights"][strategy_id] = {
                "current": adjustment.new_weight,
                "target": adjustment.target_weight,
                "change": adjustment.daily_change
            }
            
            # Record if significant adjustment
            if abs(adjustment.daily_change) > 0.01:
                self.audit_trail.record(
                    strategy_id,
                    HealingAction.WEIGHT_REDUCED if adjustment.daily_change < 0 else HealingAction.WEIGHT_RESTORED,
                    f"weight={adjustment.old_weight}",
                    f"weight={adjustment.new_weight}",
                    adjustment.reason
                )
            
            # Check demotion
            demotion = self.demotion_engine.check_demotion(strategy_id)
            if demotion:
                results["demotions"].append(demotion)
                self.audit_trail.record(
                    strategy_id,
                    HealingAction.DEMOTED,
                    demotion["from_state"],
                    demotion["to_state"],
                    demotion["reason"]
                )
            
            # Compute adaptive healing
            regime_states = self.adaptive_healing.compute_regime_health(strategy_id)
            asset_states = self.adaptive_healing.compute_asset_health(strategy_id)
            results["regime_states"][strategy_id] = {r: regime_state_to_dict(s) for r, s in regime_states.items()}
            results["asset_states"][strategy_id] = {a: asset_state_to_dict(s) for a, s in asset_states.items()}
        
        self._last_recompute = int(time.time() * 1000)
        
        results["events"] = [event_to_dict(e) for e in self.audit_trail.get_events(20)]
        
        return results
    
    def get_status(self) -> SelfHealingStatus:
        """Get overall self-healing status"""
        all_health = self.health_engine.get_all_health()
        
        healthy = sum(1 for h in all_health.values() if h.verdict == HealthVerdict.HEALTHY)
        warning = sum(1 for h in all_health.values() if h.verdict == HealthVerdict.WARNING)
        degraded = sum(1 for h in all_health.values() if h.verdict == HealthVerdict.DEGRADED)
        critical = sum(1 for h in all_health.values() if h.verdict == HealthVerdict.CRITICAL)
        
        recent_demotions = len(self.demotion_engine.get_recent_demotions(10))
        recent_recoveries = len(self.recovery_engine.get_recent_recoveries(10))
        recent_adjustments = len([a for a in self.weight_adjuster.get_recent_adjustments(10) if abs(a.daily_change) > 0.01])
        
        restrictions = self.adaptive_healing.get_restrictions(100)
        regime_restrictions = sum(1 for r in restrictions if r["type"] == "REGIME")
        asset_restrictions = sum(1 for r in restrictions if r["type"] == "ASSET")
        
        return SelfHealingStatus(
            enabled=self.config.get("enabled", True),
            mode=self.config.get("mode", "AUTO"),
            healthy_strategies=healthy,
            warning_strategies=warning,
            degraded_strategies=degraded,
            critical_strategies=critical,
            recent_demotions=recent_demotions,
            recent_recoveries=recent_recoveries,
            recent_weight_adjustments=recent_adjustments,
            regime_restrictions=regime_restrictions,
            asset_restrictions=asset_restrictions,
            last_recompute=self._last_recompute,
            version=self.config.get("version", "phase9.26")
        )
    
    def get_strategy_details(self, strategy_id: str) -> Dict:
        """Get detailed healing info for a strategy"""
        health = self.health_engine.get_health(strategy_id)
        if not health:
            health = self.health_engine.compute_health(strategy_id)
        
        weight = self.weight_adjuster.get_weight(strategy_id)
        lifecycle = self.demotion_engine.get_lifecycle(strategy_id)
        recovery = self.recovery_engine.get_recovery(strategy_id)
        regime_states = self.adaptive_healing.get_regime_states(strategy_id)
        asset_states = self.adaptive_healing.get_asset_states(strategy_id)
        events = self.audit_trail.get_events_for_strategy(strategy_id, 10)
        
        return {
            "strategyId": strategy_id,
            "health": health_to_dict(health),
            "weight": weight,
            "lifecycle": lifecycle,
            "recovery": recovery_state_to_dict(recovery) if recovery else None,
            "regimeStates": {r: regime_state_to_dict(s) for r, s in regime_states.items()},
            "assetStates": {a: asset_state_to_dict(s) for a, s in asset_states.items()},
            "recentEvents": [event_to_dict(e) for e in events]
        }
    
    def override(self, strategy_id: str, action: str, params: Dict) -> Dict:
        """Manual override for a strategy"""
        if action == "SET_WEIGHT":
            new_weight = params.get("weight", 1.0)
            old_weight = self.weight_adjuster.get_weight(strategy_id)
            self.weight_adjuster._current_weights[strategy_id] = new_weight
            
            self.audit_trail.record(
                strategy_id,
                HealingAction.WEIGHT_RESTORED,
                f"weight={old_weight}",
                f"weight={new_weight}",
                "Manual override",
                {"override": True}
            )
            
            return {"success": True, "action": "SET_WEIGHT", "newWeight": new_weight}
        
        elif action == "SET_LIFECYCLE":
            new_state = params.get("state", "APPROVED")
            old_state = self.demotion_engine.get_lifecycle(strategy_id)
            self.demotion_engine._lifecycle_states[strategy_id] = new_state
            
            self.audit_trail.record(
                strategy_id,
                HealingAction.PROMOTED if new_state in ["APPROVED", "LIMITED"] else HealingAction.DEMOTED,
                old_state,
                new_state,
                "Manual override",
                {"override": True}
            )
            
            return {"success": True, "action": "SET_LIFECYCLE", "newState": new_state}
        
        elif action == "START_RECOVERY":
            state = self.recovery_engine.start_recovery(strategy_id)
            
            self.audit_trail.record(
                strategy_id,
                HealingAction.RECOVERY_STARTED,
                "DEGRADED",
                "RECOVERY",
                "Manual recovery start"
            )
            
            return {"success": True, "action": "START_RECOVERY", "recoveryState": recovery_state_to_dict(state)}
        
        return {"success": False, "error": f"Unknown action: {action}"}
    
    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": self.config.get("enabled", True),
            "version": self.config.get("version", "phase9.26"),
            "status": "ok",
            "mode": self.config.get("mode", "AUTO"),
            "components": {
                "health_engine": "ok",
                "weight_adjuster": "ok",
                "demotion_engine": "ok",
                "recovery_engine": "ok",
                "adaptive_healing": "ok",
                "audit_trail": "ok"
            },
            "lastRecompute": self._last_recompute,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }


# ═══════════════════════════════════════════════════════════════
# Serialization Functions
# ═══════════════════════════════════════════════════════════════

def health_to_dict(health: StrategyHealthScore) -> Dict:
    """Convert StrategyHealthScore to dict"""
    return {
        "strategyId": health.strategy_id,
        "rollingMetrics": {
            "pf": health.rolling_pf,
            "wr": health.rolling_wr,
            "sharpe": health.rolling_sharpe,
            "drawdown": health.rolling_drawdown,
            "trades": health.recent_trade_count
        },
        "componentScores": {
            "rollingPf": health.rolling_pf_score,
            "rollingSharpe": health.rolling_sharpe_score,
            "drawdown": health.drawdown_score,
            "edgeDecay": health.edge_decay_score,
            "regimeFit": health.regime_fit_score,
            "confidenceIntegrity": health.confidence_integrity_score,
            "overfitRisk": health.overfit_risk_score
        },
        "healthScore": health.health_score,
        "verdict": health.verdict.value,
        "trend": health.health_trend,
        "previousScore": health.previous_health_score,
        "computedAt": health.computed_at
    }


def regime_state_to_dict(state: RegimeHealthState) -> Dict:
    """Convert RegimeHealthState to dict"""
    return {
        "strategyId": state.strategy_id,
        "regime": state.regime,
        "pf": state.pf,
        "wr": state.wr,
        "sharpe": state.sharpe,
        "trades": state.trades,
        "healthScore": state.health_score,
        "verdict": state.verdict.value,
        "isRestricted": state.is_restricted,
        "restrictionReason": state.restriction_reason
    }


def asset_state_to_dict(state: AssetHealthState) -> Dict:
    """Convert AssetHealthState to dict"""
    return {
        "strategyId": state.strategy_id,
        "asset": state.asset,
        "pf": state.pf,
        "wr": state.wr,
        "sharpe": state.sharpe,
        "trades": state.trades,
        "healthScore": state.health_score,
        "verdict": state.verdict.value,
        "isRestricted": state.is_restricted,
        "restrictionReason": state.restriction_reason
    }


def recovery_state_to_dict(state: RecoveryState) -> Dict:
    """Convert RecoveryState to dict"""
    return {
        "strategyId": state.strategy_id,
        "status": state.status.value,
        "progress": {
            "trades": state.recovery_trades,
            "pf": state.recovery_pf,
            "sharpe": state.recovery_sharpe,
            "pct": state.progress_pct
        },
        "targets": {
            "trades": state.target_trades,
            "pf": state.target_pf,
            "sharpe": state.target_sharpe
        },
        "timing": {
            "startedAt": state.started_at,
            "completedAt": state.completed_at,
            "gracePeriodEnds": state.grace_period_ends
        }
    }


def event_to_dict(event: SelfHealingEvent) -> Dict:
    """Convert SelfHealingEvent to dict"""
    return {
        "eventId": event.event_id,
        "strategyId": event.strategy_id,
        "timestamp": event.timestamp,
        "action": event.action.value,
        "oldState": event.old_state,
        "newState": event.new_state,
        "reason": event.reason,
        "metadata": event.metadata
    }


def status_to_dict(status: SelfHealingStatus) -> Dict:
    """Convert SelfHealingStatus to dict"""
    return {
        "enabled": status.enabled,
        "mode": status.mode,
        "strategies": {
            "healthy": status.healthy_strategies,
            "warning": status.warning_strategies,
            "degraded": status.degraded_strategies,
            "critical": status.critical_strategies
        },
        "recentActivity": {
            "demotions": status.recent_demotions,
            "recoveries": status.recent_recoveries,
            "weightAdjustments": status.recent_weight_adjustments
        },
        "restrictions": {
            "regime": status.regime_restrictions,
            "asset": status.asset_restrictions
        },
        "lastRecompute": status.last_recompute,
        "version": status.version
    }
