"""
Strategy Lifecycle Engine
=========================

Manages the complete lifecycle of strategies from birth to death.

Pipeline:
CANDIDATE → SANDBOX → VALIDATED → SHADOW → LIMITED → CORE → MATURE
                                                    ↓
                                               DEGRADED → DISABLED → ARCHIVED

Features:
- Formal state transitions with rules
- Recovery path for degraded strategies
- Integration with Registry, Tournament, Shadow, Autopsy
- Event Bus publishing for all transitions
- History tracking for each strategy
"""

import time
import uuid
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .types import (
    LifecycleState, StrategyAge, DeathQuality,
    ALLOWED_TRANSITIONS, STATE_CONFIG,
    LifecycleScores, LifecycleTransition, StrategyLifecycleRecord, LifecycleMetrics,
    is_transition_allowed, get_state_config, calculate_age_category
)

# Event Bus integration
try:
    from modules.event_bus import create_publisher, create_subscriber
    _event_publisher = create_publisher("strategy_lifecycle")
    _event_subscriber = create_subscriber("strategy_lifecycle")
    EVENT_BUS_ENABLED = True
except ImportError:
    _event_publisher = None
    _event_subscriber = None
    EVENT_BUS_ENABLED = False


class StrategyLifecycleEngine:
    """
    Strategy Lifecycle Engine.
    
    Manages the complete lifecycle of strategies:
    - State transitions
    - Recovery paths
    - Death tracking
    - Integration with other modules
    """
    
    def __init__(self):
        # Strategy records
        self.strategies: Dict[str, StrategyLifecycleRecord] = {}
        
        # Transition history
        self.transitions: Dict[str, List[LifecycleTransition]] = defaultdict(list)
        
        # Metrics
        self.metrics = LifecycleMetrics()
        
        # Initialize event subscriptions
        self._init_event_subscriptions()
    
    def _init_event_subscriptions(self):
        """Subscribe to relevant events"""
        if not EVENT_BUS_ENABLED or not _event_subscriber:
            return
        
        def on_alpha_promoted(event):
            """Handle alpha promoted from tournament"""
            payload = event.payload
            alpha_id = payload.get("alpha_id", "")
            if alpha_id:
                # Find or create strategy record
                strategy = self._find_by_alpha(alpha_id)
                if strategy:
                    # Promote to next appropriate state
                    self._auto_promote(strategy.strategy_id, "Tournament winner")
        
        def on_alpha_demoted(event):
            """Handle alpha demotion"""
            payload = event.payload
            alpha_id = payload.get("alpha_id", "")
            reason = payload.get("reason", "unknown")
            if alpha_id:
                strategy = self._find_by_alpha(alpha_id)
                if strategy:
                    self.demote(strategy.strategy_id, reason)
        
        try:
            _event_subscriber.subscribe(["alpha_promoted"], on_alpha_promoted)
            _event_subscriber.subscribe(["alpha_demoted", "alpha_rejected"], on_alpha_demoted)
            print("[StrategyLifecycle] Subscribed to alpha events")
        except Exception as e:
            print(f"[StrategyLifecycle] Event subscription failed: {e}")
    
    def _find_by_alpha(self, alpha_id: str) -> Optional[StrategyLifecycleRecord]:
        """Find strategy by alpha_id"""
        for strategy in self.strategies.values():
            if strategy.alpha_id == alpha_id:
                return strategy
        return None
    
    # ============================================
    # Strategy Registration
    # ============================================
    
    def register(
        self,
        strategy_id: str,
        alpha_id: str,
        name: str,
        family: str,
        initial_scores: LifecycleScores = None
    ) -> StrategyLifecycleRecord:
        """
        Register a new strategy in the lifecycle system.
        Starts as CANDIDATE.
        """
        record = StrategyLifecycleRecord.create(
            strategy_id=strategy_id,
            alpha_id=alpha_id,
            name=name,
            family=family
        )
        
        if initial_scores:
            record.scores = initial_scores
        
        self.strategies[strategy_id] = record
        self.metrics.total_strategies += 1
        self._update_state_counts()
        
        # Publish event
        self._publish_event("strategy_registered", {
            "strategy_id": strategy_id,
            "alpha_id": alpha_id,
            "name": name,
            "family": family,
            "state": record.current_state.value
        })
        
        return record
    
    # ============================================
    # State Transitions
    # ============================================
    
    def transition(
        self,
        strategy_id: str,
        to_state: LifecycleState,
        reason: str,
        triggered_by: str = "system",
        force: bool = False
    ) -> Optional[LifecycleTransition]:
        """
        Transition strategy to a new state.
        
        Args:
            strategy_id: Strategy to transition
            to_state: Target state
            reason: Why transition is happening
            triggered_by: Who/what triggered it
            force: Bypass transition rules
        """
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None
        
        from_state = strategy.current_state
        
        # Check if transition is allowed
        if not force and not is_transition_allowed(from_state, to_state):
            print(f"[SLE] Transition {from_state.value} → {to_state.value} not allowed")
            return None
        
        # Check minimum time in state
        config = get_state_config(from_state)
        min_days = config.get("min_days_in_state", 0)
        if not force and strategy.days_in_current_state < min_days:
            print(f"[SLE] Strategy must be in {from_state.value} for at least {min_days} days")
            return None
        
        # Create transition record
        transition = LifecycleTransition.create(
            strategy_id=strategy_id,
            from_state=from_state.value,
            to_state=to_state.value,
            reason=reason,
            triggered_by=triggered_by
        )
        transition.scores_at_transition = strategy.scores
        
        # Update strategy
        now = int(time.time() * 1000)
        strategy.previous_state = from_state.value
        strategy.current_state = to_state
        strategy.state_entered_at = now
        strategy.days_in_current_state = 0
        
        # Track promotions/demotions
        promotion_states = [
            LifecycleState.SANDBOX, LifecycleState.VALIDATED, LifecycleState.SHADOW,
            LifecycleState.LIMITED, LifecycleState.CORE, LifecycleState.MATURE
        ]
        demotion_states = [LifecycleState.DEGRADED, LifecycleState.DISABLED, LifecycleState.ARCHIVED]
        
        if to_state in promotion_states and from_state not in promotion_states:
            strategy.promotions += 1
            self.metrics.total_promotions += 1
        elif to_state in demotion_states:
            strategy.demotions += 1
            self.metrics.total_demotions += 1
        
        # Check for recovery
        if from_state == LifecycleState.DEGRADED and to_state in [LifecycleState.LIMITED, LifecycleState.SHADOW]:
            strategy.recovery_count += 1
            self.metrics.total_recoveries += 1
        
        # Check for death
        if to_state in [LifecycleState.DISABLED, LifecycleState.ARCHIVED]:
            self.metrics.total_deaths += 1
        
        # Store transition
        self.transitions[strategy_id].append(transition)
        self.metrics.last_transition_at = now
        self._update_state_counts()
        
        # Publish event
        event_type = self._get_transition_event_type(from_state, to_state)
        self._publish_event(event_type, {
            "strategy_id": strategy_id,
            "from_state": from_state.value,
            "to_state": to_state.value,
            "reason": reason,
            "triggered_by": triggered_by
        })
        
        print(f"[SLE] {strategy_id}: {from_state.value} → {to_state.value} ({reason})")
        
        return transition
    
    def _get_transition_event_type(
        self,
        from_state: LifecycleState,
        to_state: LifecycleState
    ) -> str:
        """Determine event type based on transition"""
        if to_state == LifecycleState.MATURE:
            return "strategy_matured"
        elif to_state == LifecycleState.DEGRADED:
            return "strategy_degraded"
        elif to_state == LifecycleState.DISABLED:
            return "strategy_disabled"
        elif to_state == LifecycleState.ARCHIVED:
            return "strategy_archived"
        elif to_state in [LifecycleState.SHADOW, LifecycleState.LIMITED, LifecycleState.CORE]:
            if from_state == LifecycleState.DEGRADED:
                return "strategy_recovered"
            return "strategy_promoted"
        else:
            return "strategy_demoted"
    
    def promote(self, strategy_id: str, reason: str = "Promotion criteria met") -> Optional[LifecycleTransition]:
        """Promote strategy to next state"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None
        
        # Determine next promotion state
        promotion_path = {
            LifecycleState.CANDIDATE: LifecycleState.SANDBOX,
            LifecycleState.SANDBOX: LifecycleState.VALIDATED,
            LifecycleState.VALIDATED: LifecycleState.SHADOW,
            LifecycleState.SHADOW: LifecycleState.LIMITED,
            LifecycleState.LIMITED: LifecycleState.CORE,
            LifecycleState.CORE: LifecycleState.MATURE,
        }
        
        next_state = promotion_path.get(strategy.current_state)
        if not next_state:
            return None
        
        return self.transition(strategy_id, next_state, reason, "promotion_engine")
    
    def demote(self, strategy_id: str, reason: str = "Performance degradation") -> Optional[LifecycleTransition]:
        """Demote strategy to degraded state"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None
        
        # Can only demote active strategies
        if strategy.current_state in [LifecycleState.DISABLED, LifecycleState.ARCHIVED]:
            return None
        
        strategy.decay_incidents += 1
        return self.transition(strategy_id, LifecycleState.DEGRADED, reason, "demotion_engine")
    
    def disable(
        self,
        strategy_id: str,
        reason: str,
        death_quality: DeathQuality = DeathQuality.UNKNOWN
    ) -> Optional[LifecycleTransition]:
        """Disable a strategy"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None
        
        strategy.death_quality = death_quality
        strategy.death_reason = reason
        
        # Update death metrics
        quality_key = death_quality.value
        self.metrics.deaths_by_quality[quality_key] = self.metrics.deaths_by_quality.get(quality_key, 0) + 1
        
        return self.transition(strategy_id, LifecycleState.DISABLED, reason, "disable_engine")
    
    def archive(self, strategy_id: str, reason: str = "Formally retired") -> Optional[LifecycleTransition]:
        """Archive a strategy"""
        return self.transition(strategy_id, LifecycleState.ARCHIVED, reason, "archive_engine")
    
    def recover(self, strategy_id: str, to_state: LifecycleState = LifecycleState.SHADOW) -> Optional[LifecycleTransition]:
        """Attempt to recover a degraded/disabled strategy"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None
        
        # Can only recover from DEGRADED or DISABLED
        if strategy.current_state not in [LifecycleState.DEGRADED, LifecycleState.DISABLED]:
            return None
        
        return self.transition(strategy_id, to_state, "Recovery attempt", "recovery_engine")
    
    def _auto_promote(self, strategy_id: str, reason: str):
        """Auto-promote based on current state"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return
        
        # Don't auto-promote from CORE or higher
        if strategy.current_state in [LifecycleState.CORE, LifecycleState.MATURE]:
            return
        
        self.promote(strategy_id, reason)
    
    # ============================================
    # Score Updates
    # ============================================
    
    def update_scores(
        self,
        strategy_id: str,
        sharpe: float = None,
        profit_factor: float = None,
        stability: float = None,
        regime_robustness: float = None,
        orthogonality: float = None,
        capital_efficiency: float = None,
        fragility_penalty: float = None,
        crowding: float = None
    ):
        """Update strategy scores"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return
        
        scores = strategy.scores
        if sharpe is not None:
            scores.sharpe = sharpe
        if profit_factor is not None:
            scores.profit_factor = profit_factor
        if stability is not None:
            scores.stability = stability
        if regime_robustness is not None:
            scores.regime_robustness = regime_robustness
        if orthogonality is not None:
            scores.orthogonality = orthogonality
        if capital_efficiency is not None:
            scores.capital_efficiency = capital_efficiency
        if fragility_penalty is not None:
            scores.fragility_penalty = fragility_penalty
        if crowding is not None:
            scores.crowding = crowding
    
    # ============================================
    # Evaluation
    # ============================================
    
    def evaluate(self, strategy_id: str) -> Dict[str, Any]:
        """
        Evaluate strategy and recommend action.
        """
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return {"error": "Strategy not found"}
        
        score = strategy.scores.lifecycle_score
        current = strategy.current_state
        
        recommendation = "HOLD"
        reason = ""
        
        # Evaluation logic
        if current == LifecycleState.CANDIDATE:
            if score > 0.5:
                recommendation = "PROMOTE"
                reason = "Good initial scores, move to sandbox"
            else:
                recommendation = "HOLD"
                reason = "Needs more evidence"
        
        elif current == LifecycleState.SHADOW:
            if score > 0.7 and strategy.shadow_survival_rate > 0.8:
                recommendation = "PROMOTE"
                reason = "Strong shadow performance"
            elif score < 0.4:
                recommendation = "DEMOTE"
                reason = "Poor shadow performance"
        
        elif current == LifecycleState.LIMITED:
            if score > 0.75 and strategy.stress_survival_rate > 0.7:
                recommendation = "PROMOTE"
                reason = "Ready for CORE"
            elif score < 0.35:
                recommendation = "DEMOTE"
                reason = "Performance degradation"
        
        elif current == LifecycleState.CORE:
            if score > 0.8 and strategy.total_age_days > 180:
                recommendation = "PROMOTE"
                reason = "Mature and stable"
            elif score < 0.3:
                recommendation = "DEMOTE"
                reason = "Significant decay"
        
        elif current == LifecycleState.DEGRADED:
            if score > 0.6 and strategy.days_in_current_state > 7:
                recommendation = "RECOVER"
                reason = "Scores improved"
            elif score < 0.2 or strategy.days_in_current_state > 30:
                recommendation = "DISABLE"
                reason = "No recovery"
        
        return {
            "strategy_id": strategy_id,
            "current_state": current.value,
            "lifecycle_score": round(score, 3),
            "recommendation": recommendation,
            "reason": reason,
            "scores": strategy.scores.to_dict()
        }
    
    def evaluate_all(self) -> List[Dict[str, Any]]:
        """Evaluate all strategies"""
        return [self.evaluate(sid) for sid in self.strategies.keys()]
    
    # ============================================
    # Age Updates
    # ============================================
    
    def update_ages(self):
        """Update age-related fields for all strategies"""
        now = int(time.time() * 1000)
        day_ms = 86400000
        
        for strategy in self.strategies.values():
            # Total age
            strategy.total_age_days = (now - strategy.created_at) // day_ms
            
            # Days in current state
            strategy.days_in_current_state = (now - strategy.state_entered_at) // day_ms
            
            # Age category
            strategy.age_category = calculate_age_category(strategy.total_age_days)
    
    # ============================================
    # Helpers
    # ============================================
    
    def _update_state_counts(self):
        """Update state count metrics"""
        counts = defaultdict(int)
        for strategy in self.strategies.values():
            counts[strategy.current_state.value] += 1
        self.metrics.strategies_by_state = dict(counts)
    
    def _publish_event(self, event_type: str, payload: Dict[str, Any]):
        """Publish event to Event Bus"""
        if EVENT_BUS_ENABLED and _event_publisher:
            _event_publisher.publish(event_type, payload)
    
    # ============================================
    # Getters
    # ============================================
    
    def get_strategy(self, strategy_id: str) -> Optional[StrategyLifecycleRecord]:
        return self.strategies.get(strategy_id)
    
    def get_strategies_by_state(self, state: LifecycleState) -> List[StrategyLifecycleRecord]:
        return [s for s in self.strategies.values() if s.current_state == state]
    
    def get_history(self, strategy_id: str) -> List[LifecycleTransition]:
        return self.transitions.get(strategy_id, [])
    
    def get_recent_transitions(self, limit: int = 50) -> List[LifecycleTransition]:
        all_transitions = []
        for trans_list in self.transitions.values():
            all_transitions.extend(trans_list)
        
        return sorted(all_transitions, key=lambda t: t.timestamp, reverse=True)[:limit]
    
    def get_metrics(self) -> LifecycleMetrics:
        return self.metrics
    
    def get_health(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "version": "lifecycle_v1",
            "status": "ok",
            "total_strategies": len(self.strategies),
            "metrics": self.metrics.to_dict()
        }


# Singleton instance
strategy_lifecycle_engine = StrategyLifecycleEngine()
