"""
Evolution Engine
================

Self-Evolving Quant Platform (SEQP).

The system automatically:
1. Observes - Collects performance metrics
2. Analyzes - Detects edge decay
3. Adapts - Adjusts weights
4. Evolves - Creates new mutations

This transforms the system from a research framework into a self-improving platform.
"""

import time
import uuid
import random
import math
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .types import (
    EvolutionAction, MutationType, DecayReason, EvolutionStatus,
    DecaySignal, Mutation, EvolutionCycle, EvolutionConfig, EvolutionMetrics
)

# Event Bus integration
try:
    from modules.event_bus import create_publisher, EventType
    _event_publisher = create_publisher("evolution_engine")
    EVENT_BUS_ENABLED = True
except ImportError:
    _event_publisher = None
    EVENT_BUS_ENABLED = False


class EvolutionEngine:
    """
    Evolution Engine for self-evolving alpha system.
    
    Pipeline:
    observe → analyze → adapt → evolve
    """
    
    def __init__(self, config: EvolutionConfig = None):
        self.config = config or EvolutionConfig()
        self.metrics = EvolutionMetrics()
        
        # History
        self.cycles: Dict[str, EvolutionCycle] = {}
        self.mutations: Dict[str, Mutation] = {}
        self.decay_signals: List[DecaySignal] = []
        
        # Alpha baselines (alpha_id -> baseline sharpe)
        self.alpha_baselines: Dict[str, float] = {}
        
        # Module references
        self._alpha_registry = None
        self._shadow_portfolio = None
        self._research_memory = None
        
        # Event Bus subscriptions
        self._init_event_subscriptions()
    
    def _init_event_subscriptions(self):
        """Subscribe to events for automatic evolution triggers"""
        if not EVENT_BUS_ENABLED:
            return
        
        try:
            from modules.event_bus import create_subscriber
            subscriber = create_subscriber("evolution_engine")
            
            def on_alpha_decay(event):
                """Trigger observation when decay is detected"""
                payload = event.payload
                alpha_id = payload.get("alpha_id", "")
                if alpha_id and alpha_id in self.alpha_baselines:
                    # Record decay signal
                    self.observe({alpha_id: {
                        "sharpe": payload.get("sharpe_current", 0),
                        "crowding": payload.get("crowding", 0)
                    }})
            
            subscriber.subscribe(
                ["alpha_decay_detected", "alpha_demoted"],
                on_alpha_decay
            )
            print("[EvolutionEngine] Subscribed to alpha events")
        except Exception as e:
            print(f"[EvolutionEngine] Event subscription failed: {e}")
    
    def _load_modules(self):
        """Lazy load dependent modules"""
        try:
            from modules.alpha_registry.service import alpha_registry
            self._alpha_registry = alpha_registry
        except ImportError:
            pass
        
        try:
            from modules.shadow_portfolio.engine import shadow_portfolio_engine
            self._shadow_portfolio = shadow_portfolio_engine
        except ImportError:
            pass
        
        try:
            from modules.research_memory.engine import research_memory
            self._research_memory = research_memory
        except ImportError:
            pass
    
    # ============================================
    # Phase 1: Observation
    # ============================================
    
    def observe(self, alpha_performances: Dict[str, Dict[str, float]] = None) -> List[DecaySignal]:
        """
        Observe current alpha performance and detect decay.
        
        Args:
            alpha_performances: Dict of alpha_id -> {sharpe, pf, wr, trades}
        
        Returns:
            List of decay signals
        """
        if alpha_performances is None:
            alpha_performances = self._get_mock_performances()
        
        signals = []
        
        for alpha_id, perf in alpha_performances.items():
            current_sharpe = perf.get("sharpe", 0)
            baseline_sharpe = self.alpha_baselines.get(alpha_id, current_sharpe)
            
            # Update baseline if first time
            if alpha_id not in self.alpha_baselines:
                self.alpha_baselines[alpha_id] = current_sharpe
                continue
            
            # Calculate decay rate
            if baseline_sharpe > 0:
                decay_rate = (current_sharpe - baseline_sharpe) / baseline_sharpe
            else:
                decay_rate = 0
            
            # Check if decaying
            if decay_rate < self.config.decay_threshold:
                # Determine reason
                reason = self._analyze_decay_reason(alpha_id, perf)
                
                signal = DecaySignal(
                    alpha_id=alpha_id,
                    decay_rate=decay_rate,
                    sharpe_current=current_sharpe,
                    sharpe_baseline=baseline_sharpe,
                    decay_reason=reason,
                    confidence=min(1.0, abs(decay_rate) / 0.3),
                    detected_at=int(time.time() * 1000)
                )
                signals.append(signal)
                self.decay_signals.append(signal)
        
        return signals
    
    def _analyze_decay_reason(self, alpha_id: str, perf: Dict) -> DecayReason:
        """Analyze why an alpha is decaying"""
        
        # Check regime dependency
        regime_pf = perf.get("regime_pf", {})
        if regime_pf:
            pf_values = list(regime_pf.values())
            if max(pf_values) > 2 * min(pf_values):
                return DecayReason.REGIME_SHIFT
        
        # Check crowding
        crowding = perf.get("crowding", 0)
        if crowding > 0.8:
            return DecayReason.CROWDING
        
        # Check feature stability
        feature_stability = perf.get("feature_stability", 1.0)
        if feature_stability < 0.5:
            return DecayReason.FEATURE_INSTABILITY
        
        # Check for overfitting
        oos_sharpe = perf.get("oos_sharpe", perf.get("sharpe", 0))
        if oos_sharpe < perf.get("sharpe", 0) * 0.5:
            return DecayReason.OVERFITTING
        
        return DecayReason.UNKNOWN
    
    def _get_mock_performances(self) -> Dict[str, Dict[str, float]]:
        """Generate mock performance data for testing"""
        alphas = [
            "MOMENTUM_EMA_V1",
            "BREAKOUT_ATR_V2",
            "MEAN_REV_RSI_V1",
            "TREND_MACD_V3",
            "STRUCTURE_VOL_V1"
        ]
        
        performances = {}
        for alpha in alphas:
            baseline = self.alpha_baselines.get(alpha, 1.0 + random.random() * 0.5)
            
            # Simulate some decay
            decay = random.uniform(-0.3, 0.1)
            current = max(0.1, baseline * (1 + decay))
            
            performances[alpha] = {
                "sharpe": current,
                "pf": 1.2 + random.random() * 0.8,
                "wr": 0.5 + random.random() * 0.15,
                "trades": random.randint(50, 200),
                "crowding": random.random() * 0.9,
                "feature_stability": 0.3 + random.random() * 0.7
            }
        
        return performances
    
    # ============================================
    # Phase 2: Analysis
    # ============================================
    
    def analyze(self, signals: List[DecaySignal]) -> Dict[str, Any]:
        """
        Analyze decay signals to determine patterns.
        
        Returns:
            Analysis results with action recommendations
        """
        if not signals:
            return {"has_decay": False, "recommendations": []}
        
        # Group by reason
        by_reason: Dict[DecayReason, List[DecaySignal]] = defaultdict(list)
        for signal in signals:
            by_reason[signal.decay_reason].append(signal)
        
        # Find dominant reason
        dominant_reason = max(by_reason.keys(), key=lambda r: len(by_reason[r]))
        
        # Generate recommendations
        recommendations = []
        
        if dominant_reason == DecayReason.REGIME_SHIFT:
            recommendations.append({
                "action": "REGIME_MUTATION",
                "description": "Create regime-masked variants",
                "alphas": [s.alpha_id for s in by_reason[DecayReason.REGIME_SHIFT]]
            })
        
        if dominant_reason == DecayReason.CROWDING:
            recommendations.append({
                "action": "DIVERSIFY",
                "description": "Generate orthogonal alternatives",
                "alphas": [s.alpha_id for s in by_reason[DecayReason.CROWDING]]
            })
        
        if dominant_reason == DecayReason.FEATURE_INSTABILITY:
            recommendations.append({
                "action": "TEMPORAL_MUTATION",
                "description": "Create smoothed/lagged variants",
                "alphas": [s.alpha_id for s in by_reason[DecayReason.FEATURE_INSTABILITY]]
            })
        
        return {
            "has_decay": True,
            "total_decaying": len(signals),
            "by_reason": {r.value: len(sigs) for r, sigs in by_reason.items()},
            "dominant_reason": dominant_reason.value,
            "recommendations": recommendations,
            "avg_decay_rate": sum(s.decay_rate for s in signals) / len(signals)
        }
    
    # ============================================
    # Phase 3: Adaptation
    # ============================================
    
    def adapt(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt system based on analysis.
        
        This adjusts weights and parameters without creating new alphas.
        """
        adaptations = []
        
        if not analysis.get("has_decay", False):
            return {"adaptations": [], "weight_changes": {}}
        
        # Weight reduction for decaying alphas
        weight_changes = {}
        for rec in analysis.get("recommendations", []):
            for alpha_id in rec.get("alphas", []):
                # Reduce weight by 30%
                weight_changes[alpha_id] = -0.3
                adaptations.append({
                    "alpha_id": alpha_id,
                    "action": "REDUCE_WEIGHT",
                    "change": -0.3
                })
        
        # Publish portfolio adaptation event
        if EVENT_BUS_ENABLED and _event_publisher:
            _event_publisher.publish(
                "portfolio_rebalanced",
                {
                    "changes": weight_changes,
                    "reason": f"Evolution adaptation: {analysis.get('dominant_reason', 'decay')}",
                    "total_value": 0  # Would come from portfolio
                }
            )
        
        return {
            "adaptations": adaptations,
            "weight_changes": weight_changes,
            "total_adapted": len(adaptations)
        }
    
    # ============================================
    # Phase 4: Evolution
    # ============================================
    
    def evolve(self, analysis: Dict[str, Any]) -> List[Mutation]:
        """
        Create mutations to replace decaying alphas.
        
        Returns:
            List of created mutations
        """
        mutations = []
        
        if not analysis.get("has_decay", False):
            return mutations
        
        for rec in analysis.get("recommendations", []):
            action = rec.get("action", "")
            alphas = rec.get("alphas", [])
            
            for alpha_id in alphas[:self.config.max_mutations_per_cycle]:
                # Create mutations based on recommendation
                if action == "REGIME_MUTATION":
                    mut = self._create_regime_mutation(alpha_id)
                elif action == "TEMPORAL_MUTATION":
                    mut = self._create_temporal_mutation(alpha_id)
                elif action == "DIVERSIFY":
                    mut = self._create_arithmetic_mutation(alpha_id)
                else:
                    mut = self._create_random_mutation(alpha_id)
                
                if mut:
                    mutations.append(mut)
                    self.mutations[mut.mutation_id] = mut
        
        return mutations
    
    def _create_regime_mutation(self, source_id: str) -> Mutation:
        """Create a regime-masked mutation"""
        regimes = ["TREND_UP", "TREND_DOWN", "RANGE"]
        selected_regime = random.choice(regimes)
        
        result_id = f"{source_id}_REG_{selected_regime[:3]}"
        
        return Mutation.create(
            source_id=source_id,
            mutation_type=MutationType.REGIME,
            parameters={"regime": selected_regime, "mask": True},
            result_id=result_id,
            score=random.uniform(0.5, 0.9)
        )
    
    def _create_temporal_mutation(self, source_id: str) -> Mutation:
        """Create a temporal mutation (lag/smooth)"""
        lag = random.choice([1, 3, 5, 10, 20])
        
        result_id = f"{source_id}_LAG{lag}"
        
        return Mutation.create(
            source_id=source_id,
            mutation_type=MutationType.TEMPORAL,
            parameters={"lag": lag, "smoothing": "ema"},
            result_id=result_id,
            score=random.uniform(0.4, 0.85)
        )
    
    def _create_arithmetic_mutation(self, source_id: str) -> Mutation:
        """Create an arithmetic mutation"""
        operations = ["ADD", "MULTIPLY", "NORMALIZE"]
        op = random.choice(operations)
        
        result_id = f"{source_id}_{op[:3]}"
        
        return Mutation.create(
            source_id=source_id,
            mutation_type=MutationType.ARITHMETIC,
            parameters={"operation": op, "factor": random.uniform(0.5, 2.0)},
            result_id=result_id,
            score=random.uniform(0.4, 0.8)
        )
    
    def _create_random_mutation(self, source_id: str) -> Mutation:
        """Create a random mutation"""
        mut_type = random.choice(list(MutationType))
        result_id = f"{source_id}_MUT_{uuid.uuid4().hex[:4]}"
        
        return Mutation.create(
            source_id=source_id,
            mutation_type=mut_type,
            parameters={"random": True},
            result_id=result_id,
            score=random.uniform(0.3, 0.7)
        )
    
    # ============================================
    # Selection
    # ============================================
    
    def select(self, mutations: List[Mutation]) -> List[Mutation]:
        """
        Run tournament selection on mutations.
        
        Returns:
            List of promoted mutations
        """
        if not mutations:
            return []
        
        # Sort by score
        sorted_mutations = sorted(mutations, key=lambda m: m.score, reverse=True)
        
        # Promote top performers
        promoted = []
        for mut in sorted_mutations:
            if mut.score >= self.config.promotion_threshold:
                if len(promoted) < self.config.max_promoted_per_cycle:
                    mut.promoted = True
                    promoted.append(mut)
                    
                    # Publish alpha promoted event
                    if EVENT_BUS_ENABLED and _event_publisher:
                        _event_publisher.alpha_promoted(
                            alpha_id=mut.result_id,
                            score=mut.score,
                            family=mut.mutation_type.value,
                            reason=f"Mutation from {mut.source_id}"
                        )
        
        return promoted
    
    # ============================================
    # Full Cycle
    # ============================================
    
    def run_cycle(self, alpha_performances: Dict[str, Dict[str, float]] = None) -> EvolutionCycle:
        """
        Run a complete evolution cycle.
        
        Pipeline: observe → analyze → adapt → evolve → select
        """
        self._load_modules()
        
        cycle = EvolutionCycle.create()
        self.cycles[cycle.cycle_id] = cycle
        
        try:
            # Phase 1: Observe
            cycle.status = EvolutionStatus.OBSERVING
            signals = self.observe(alpha_performances)
            cycle.decay_signals = signals
            
            # Phase 2: Analyze
            cycle.status = EvolutionStatus.ANALYZING
            analysis = self.analyze(signals)
            cycle.decay_reasons = analysis.get("by_reason", {})
            cycle.avg_sharpe_before = sum(
                s.sharpe_current for s in signals
            ) / len(signals) if signals else 0
            
            # Phase 3: Adapt
            cycle.status = EvolutionStatus.ADAPTING
            self.adapt(analysis)
            
            # Phase 4: Evolve
            cycle.status = EvolutionStatus.EVOLVING
            mutations = self.evolve(analysis)
            cycle.mutations = mutations
            cycle.mutations_created = len(mutations)
            
            # Phase 5: Select
            promoted = self.select(mutations)
            cycle.mutations_promoted = len(promoted)
            cycle.mutations_tested = len(mutations)
            
            # Calculate metrics
            if promoted:
                cycle.avg_sharpe_after = sum(m.score for m in promoted) / len(promoted)
                cycle.edge_recovery_rate = (
                    cycle.avg_sharpe_after - cycle.avg_sharpe_before
                ) / abs(cycle.avg_sharpe_before) if cycle.avg_sharpe_before != 0 else 0
            
            cycle.status = EvolutionStatus.COMPLETED
            cycle.completed_at = int(time.time() * 1000)
            
            # Update metrics
            self.metrics.total_cycles += 1
            self.metrics.successful_cycles += 1
            self.metrics.total_mutations += len(mutations)
            self.metrics.total_promoted += len(promoted)
            self.metrics.last_cycle_at = cycle.completed_at
            
            if self.metrics.total_mutations > 0:
                self.metrics.mutation_success_rate = (
                    self.metrics.total_promoted / self.metrics.total_mutations
                )
            
        except Exception as e:
            cycle.status = EvolutionStatus.FAILED
            cycle.error_message = str(e)
            cycle.completed_at = int(time.time() * 1000)
        
        return cycle
    
    # ============================================
    # Getters
    # ============================================
    
    def get_cycle(self, cycle_id: str) -> Optional[EvolutionCycle]:
        return self.cycles.get(cycle_id)
    
    def get_recent_cycles(self, limit: int = 20) -> List[EvolutionCycle]:
        sorted_cycles = sorted(
            self.cycles.values(),
            key=lambda c: c.started_at,
            reverse=True
        )
        return sorted_cycles[:limit]
    
    def get_metrics(self) -> EvolutionMetrics:
        return self.metrics
    
    def get_decay_signals(self, limit: int = 50) -> List[DecaySignal]:
        return list(reversed(self.decay_signals[-limit:]))
    
    def get_health(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "version": "evolution_v1",
            "status": "ok",
            "config": self.config.to_dict(),
            "metrics": self.metrics.to_dict(),
            "total_cycles": len(self.cycles),
            "total_mutations": len(self.mutations),
            "alpha_baselines_count": len(self.alpha_baselines)
        }


# Singleton instance
evolution_engine = EvolutionEngine()
