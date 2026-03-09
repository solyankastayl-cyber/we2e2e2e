"""
Research Loop Engine
====================

Phase 9.33 - Automated research cycle engine.

Orchestrates the full research pipeline:
Feature Factory → Alpha Registry → Tournament → Shadow Portfolio → Memory

The loop learns from failures and avoids repeating mistakes.

Phase D: Integrated with Event Bus for loosely-coupled communication.
"""

import time
import uuid
import asyncio
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .types import (
    LoopConfig, LoopCycleResult, LoopState, LoopEvent, LoopMetrics,
    LoopPhase, LoopMode, LoopStatus
)

# Event Bus integration
try:
    from modules.event_bus import create_publisher, EventType
    _event_publisher = create_publisher("research_loop")
    EVENT_BUS_ENABLED = True
except ImportError:
    _event_publisher = None
    EVENT_BUS_ENABLED = False


class ResearchLoopEngine:
    """
    Research Loop Engine.
    
    Coordinates automated research cycles across all modules.
    """
    
    def __init__(self):
        # State
        self.loops: Dict[str, LoopState] = {}
        self.configs: Dict[str, LoopConfig] = {}
        self.cycles: Dict[str, LoopCycleResult] = {}
        self.events: List[LoopEvent] = []
        
        # Module references (lazy loaded)
        self._feature_factory = None
        self._mutation_engine = None
        self._alpha_registry = None
        self._alpha_tournament = None
        self._shadow_portfolio = None
        self._research_memory = None
        
        # Default loop
        self._create_default_loop()
    
    def _create_default_loop(self):
        """Create default research loop"""
        loop_id = "LOOP_DEFAULT"
        config = LoopConfig(
            loop_id=loop_id,
            name="Default Research Loop"
        )
        self.configs[loop_id] = config
        self.loops[loop_id] = LoopState(
            loop_id=loop_id,
            config=config
        )
    
    # ============================================
    # Module Loading
    # ============================================
    
    def _load_modules(self):
        """Lazy load dependent modules"""
        try:
            from modules.feature_factory.mutation import mutation_engine
            self._mutation_engine = mutation_engine
        except ImportError:
            pass
        
        try:
            from modules.research_memory.engine import research_memory
            self._research_memory = research_memory
        except ImportError:
            pass
        
        try:
            from modules.alpha_registry.service import alpha_registry_service
            self._alpha_registry = alpha_registry_service
        except ImportError:
            pass
        
        try:
            from modules.alpha_tournament.service import alpha_tournament_service
            self._alpha_tournament = alpha_tournament_service
        except ImportError:
            pass
        
        try:
            from modules.shadow_portfolio.service import shadow_portfolio_service
            self._shadow_portfolio = shadow_portfolio_service
        except ImportError:
            pass
    
    # ============================================
    # Loop Management
    # ============================================
    
    def create_loop(self, config: LoopConfig) -> LoopState:
        """Create a new research loop"""
        loop_id = config.loop_id or f"LOOP_{uuid.uuid4().hex[:8]}"
        config.loop_id = loop_id
        
        self.configs[loop_id] = config
        
        state = LoopState(
            loop_id=loop_id,
            status=LoopStatus.STOPPED,
            config=config
        )
        self.loops[loop_id] = state
        
        return state
    
    def get_loop(self, loop_id: str) -> Optional[LoopState]:
        """Get loop state"""
        return self.loops.get(loop_id)
    
    def list_loops(self) -> List[Dict]:
        """List all loops"""
        return [self._state_to_dict(s) for s in self.loops.values()]
    
    def update_config(self, loop_id: str, updates: Dict) -> Optional[LoopConfig]:
        """Update loop configuration"""
        config = self.configs.get(loop_id)
        if not config:
            return None
        
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    # ============================================
    # Cycle Execution
    # ============================================
    
    def run_cycle(self, loop_id: str = "LOOP_DEFAULT") -> LoopCycleResult:
        """Run a single research cycle"""
        
        self._load_modules()
        
        state = self.loops.get(loop_id)
        config = self.configs.get(loop_id)
        
        if not state or not config:
            return self._failed_cycle(loop_id, "Loop not found")
        
        # Check if we can run
        if state.status == LoopStatus.RUNNING:
            return self._failed_cycle(loop_id, "Loop already running")
        
        # Check daily limit
        if state.cycles_today >= config.max_cycles_per_day:
            return self._failed_cycle(loop_id, "Daily cycle limit reached")
        
        # Initialize cycle
        cycle_id = f"CYCLE_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)
        
        result = LoopCycleResult(
            cycle_id=cycle_id,
            loop_id=loop_id,
            started_at=now
        )
        
        # Update state
        state.status = LoopStatus.RUNNING
        state.current_cycle_id = cycle_id
        state.current_phase = LoopPhase.FEATURE_GENERATION
        
        # Publish cycle started event
        if EVENT_BUS_ENABLED and _event_publisher:
            _event_publisher.research_cycle_started(cycle_id, {
                "loop_id": loop_id,
                "mutation_categories": config.mutation_categories,
                "alpha_families": config.alpha_families
            })
        
        try:
            # Phase 1: Feature Generation
            self._log_event(cycle_id, LoopPhase.FEATURE_GENERATION, "STARTED", "Starting feature generation")
            result = self._run_feature_generation(result, config)
            result.phase_history.append(LoopPhase.FEATURE_GENERATION.value)
            
            # Phase 2: Alpha Generation
            state.current_phase = LoopPhase.ALPHA_GENERATION
            self._log_event(cycle_id, LoopPhase.ALPHA_GENERATION, "STARTED", "Starting alpha generation")
            result = self._run_alpha_generation(result, config)
            result.phase_history.append(LoopPhase.ALPHA_GENERATION.value)
            
            # Phase 3: Registry Submit
            state.current_phase = LoopPhase.REGISTRY_SUBMIT
            self._log_event(cycle_id, LoopPhase.REGISTRY_SUBMIT, "STARTED", "Submitting to registry")
            result = self._run_registry_submit(result, config)
            result.phase_history.append(LoopPhase.REGISTRY_SUBMIT.value)
            
            # Phase 4: Tournament
            state.current_phase = LoopPhase.TOURNAMENT_RUN
            self._log_event(cycle_id, LoopPhase.TOURNAMENT_RUN, "STARTED", "Running tournament")
            result = self._run_tournament(result, config)
            result.phase_history.append(LoopPhase.TOURNAMENT_RUN.value)
            
            # Phase 5: Shadow Admission
            state.current_phase = LoopPhase.SHADOW_ADMISSION
            self._log_event(cycle_id, LoopPhase.SHADOW_ADMISSION, "STARTED", "Shadow admission")
            result = self._run_shadow_admission(result, config)
            result.phase_history.append(LoopPhase.SHADOW_ADMISSION.value)
            
            # Phase 6: Memory Update
            state.current_phase = LoopPhase.MEMORY_UPDATE
            self._log_event(cycle_id, LoopPhase.MEMORY_UPDATE, "STARTED", "Updating memory")
            result = self._run_memory_update(result, config)
            result.phase_history.append(LoopPhase.MEMORY_UPDATE.value)
            
            # Complete
            result.phase = LoopPhase.COMPLETED
            result.success = True
            state.successful_cycles += 1
            
        except Exception as e:
            result.phase = LoopPhase.FAILED
            result.success = False
            result.error_message = str(e)
            state.failed_cycles += 1
            self._log_event(cycle_id, result.phase, "FAILED", str(e))
        
        # Finalize
        end_time = int(time.time() * 1000)
        result.completed_at = end_time
        result.duration_seconds = (end_time - now) / 1000
        
        # Update state
        state.status = LoopStatus.STOPPED
        state.current_phase = LoopPhase.IDLE
        state.total_cycles += 1
        state.cycles_today += 1
        state.last_cycle_at = end_time
        state.next_cycle_at = end_time + (config.cooldown_seconds * 1000)
        
        # Accumulate stats
        state.total_features_generated += result.features_generated
        state.total_alphas_generated += result.alphas_generated
        state.total_alphas_admitted += result.alphas_admitted_to_shadow
        state.total_failures_recorded += result.failures_recorded
        
        # Store cycle
        self.cycles[cycle_id] = result
        
        # Publish cycle completed event
        if EVENT_BUS_ENABLED and _event_publisher:
            _event_publisher.research_cycle_completed(
                cycle_id=cycle_id,
                features_generated=result.features_generated,
                alphas_generated=result.alphas_generated,
                alphas_promoted=result.alphas_admitted_to_shadow
            )
        
        self._log_event(cycle_id, LoopPhase.COMPLETED, "COMPLETED", 
                       f"Cycle completed in {result.duration_seconds:.2f}s")
        
        return result
    
    # ============================================
    # Phase Implementations
    # ============================================
    
    def _run_feature_generation(self, result: LoopCycleResult, config: LoopConfig) -> LoopCycleResult:
        """Phase 1: Generate features through mutation"""
        
        if not self._mutation_engine:
            return result
        
        # Check memory first
        if config.check_memory_before_generate and self._research_memory:
            # This would check if similar features already failed
            pass
        
        # Generate base feature values (mock for now)
        base_values = self._generate_mock_feature_values(100)
        
        generated = 0
        passed = 0
        rejected = 0
        best_score = 0.0
        best_id = ""
        
        # Run temporal mutations
        if "TEMPORAL" in config.mutation_categories:
            for lag in [1, 3, 5, 10]:
                if generated >= config.max_mutations_per_cycle:
                    break
                
                mut = self._mutation_engine.mutate_lag(
                    f"F_BASE_{generated}",
                    base_values,
                    lag
                )
                generated += 1
                
                if mut.status == "PASSED":
                    passed += 1
                    if mut.final_score > best_score:
                        best_score = mut.final_score
                        best_id = mut.feature_id
                else:
                    rejected += 1
        
        # Run arithmetic mutations
        if "ARITHMETIC" in config.mutation_categories:
            base_values_2 = self._generate_mock_feature_values(100)
            
            for op in ["ADD", "SUBTRACT", "MULTIPLY"]:
                if generated >= config.max_mutations_per_cycle:
                    break
                
                if op == "ADD":
                    mut = self._mutation_engine.mutate_add(
                        f"F_A_{generated}", f"F_B_{generated}",
                        base_values, base_values_2
                    )
                elif op == "SUBTRACT":
                    mut = self._mutation_engine.mutate_subtract(
                        f"F_A_{generated}", f"F_B_{generated}",
                        base_values, base_values_2
                    )
                else:
                    mut = self._mutation_engine.mutate_multiply(
                        f"F_A_{generated}", f"F_B_{generated}",
                        base_values, base_values_2
                    )
                
                generated += 1
                
                if mut.status == "PASSED":
                    passed += 1
                    if mut.final_score > best_score:
                        best_score = mut.final_score
                        best_id = mut.feature_id
                else:
                    rejected += 1
        
        result.features_generated = generated
        result.features_passed = passed
        result.features_rejected = rejected
        result.best_feature_id = best_id
        result.best_feature_score = best_score
        
        return result
    
    def _run_alpha_generation(self, result: LoopCycleResult, config: LoopConfig) -> LoopCycleResult:
        """Phase 2: Generate alpha signals from features"""
        
        # Generate mock alphas based on passed features
        n_alphas = min(result.features_passed, config.max_alphas_per_cycle)
        
        alphas = []
        for i in range(n_alphas):
            family = config.alpha_families[i % len(config.alpha_families)]
            sharpe = 0.3 + (i * 0.1) + (result.best_feature_score * 0.5)  # Mock Sharpe
            
            alpha = {
                "alpha_id": f"ALPHA_{uuid.uuid4().hex[:8]}",
                "name": f"Alpha_{family}_{i}",
                "family": family,
                "sharpe": round(sharpe, 3),
                "features_used": [result.best_feature_id] if result.best_feature_id else []
            }
            
            if sharpe >= config.min_alpha_sharpe:
                alphas.append(alpha)
        
        result.alphas_generated = n_alphas
        result.alphas_registered = len(alphas)
        result.alphas_rejected = n_alphas - len(alphas)
        
        if alphas:
            best = max(alphas, key=lambda a: a["sharpe"])
            result.best_alpha_id = best["alpha_id"]
            result.best_alpha_sharpe = best["sharpe"]
        
        return result
    
    def _run_registry_submit(self, result: LoopCycleResult, config: LoopConfig) -> LoopCycleResult:
        """Phase 3: Submit alphas to registry"""
        
        if not self._alpha_registry:
            return result
        
        # Would submit alphas to registry here
        # For now, just track the count
        
        return result
    
    def _run_tournament(self, result: LoopCycleResult, config: LoopConfig) -> LoopCycleResult:
        """Phase 4: Run tournament among alphas"""
        
        if result.alphas_registered < 2:
            return result
        
        # Simulate tournament
        tournament_id = f"TOURN_{uuid.uuid4().hex[:8]}"
        result.tournament_id = tournament_id
        result.tournament_rounds_completed = min(config.tournament_rounds, result.alphas_registered - 1)
        result.tournament_winner = result.best_alpha_id
        
        return result
    
    def _run_shadow_admission(self, result: LoopCycleResult, config: LoopConfig) -> LoopCycleResult:
        """Phase 5: Admit winners to shadow portfolio"""
        
        if not result.tournament_winner:
            return result
        
        # Simulate admission gate
        if result.best_alpha_sharpe >= config.min_tournament_score:
            result.alphas_admitted_to_shadow = 1
        else:
            result.alphas_rejected_from_shadow = 1
        
        return result
    
    def _run_memory_update(self, result: LoopCycleResult, config: LoopConfig) -> LoopCycleResult:
        """Phase 6: Update research memory with outcomes"""
        
        if not self._research_memory or not config.record_all_failures:
            return result
        
        failures_recorded = 0
        
        # Record rejected features
        if result.features_rejected > 0:
            self._research_memory.record_mutation_failure(
                mutation_id=f"MUT_BATCH_{result.cycle_id}",
                mutation_name=f"Batch mutations cycle {result.cycle_id}",
                outcome="FAILED",
                failure_reasons=[f"{result.features_rejected} mutations failed quality gates"]
            )
            failures_recorded += 1
        
        # Record rejected alphas
        if result.alphas_rejected > 0:
            self._research_memory.record_alpha_failure(
                alpha_id=f"ALPHA_BATCH_{result.cycle_id}",
                alpha_name=f"Batch alphas cycle {result.cycle_id}",
                outcome="LOW_EDGE",
                failure_reasons=[f"{result.alphas_rejected} alphas below Sharpe threshold"]
            )
            failures_recorded += 1
        
        # Record shadow rejections
        if result.alphas_rejected_from_shadow > 0:
            self._research_memory.record_tournament_loss(
                alpha_id=result.tournament_winner or "unknown",
                alpha_name="Tournament winner",
                reason="Failed shadow admission gate"
            )
            failures_recorded += 1
        
        result.failures_recorded = failures_recorded
        result.patterns_updated = len(self._research_memory.patterns) if self._research_memory else 0
        
        return result
    
    # ============================================
    # Helpers
    # ============================================
    
    def _generate_mock_feature_values(self, n: int) -> List[float]:
        """Generate mock feature values for testing"""
        import random
        random.seed(int(time.time()))
        return [random.gauss(0, 1) for _ in range(n)]
    
    def _failed_cycle(self, loop_id: str, message: str) -> LoopCycleResult:
        """Create a failed cycle result"""
        return LoopCycleResult(
            cycle_id=f"CYCLE_FAILED_{uuid.uuid4().hex[:8]}",
            loop_id=loop_id,
            phase=LoopPhase.FAILED,
            success=False,
            error_message=message,
            started_at=int(time.time() * 1000),
            completed_at=int(time.time() * 1000)
        )
    
    def _log_event(self, cycle_id: str, phase: LoopPhase, event_type: str, message: str):
        """Log an event"""
        event = LoopEvent(
            event_id=f"EVT_{uuid.uuid4().hex[:8]}",
            cycle_id=cycle_id,
            phase=phase,
            event_type=event_type,
            message=message,
            timestamp=int(time.time() * 1000)
        )
        self.events.append(event)
        
        # Keep only last 1000 events
        if len(self.events) > 1000:
            self.events = self.events[-1000:]
    
    # ============================================
    # Metrics
    # ============================================
    
    def get_metrics(self, loop_id: str = "LOOP_DEFAULT") -> LoopMetrics:
        """Calculate loop metrics"""
        
        state = self.loops.get(loop_id)
        if not state:
            return LoopMetrics(loop_id=loop_id)
        
        cycles = [c for c in self.cycles.values() if c.loop_id == loop_id]
        
        if not cycles:
            return LoopMetrics(loop_id=loop_id, computed_at=int(time.time() * 1000))
        
        total_features = sum(c.features_generated for c in cycles)
        total_passed = sum(c.features_passed for c in cycles)
        total_alphas = sum(c.alphas_generated for c in cycles)
        total_admitted = sum(c.alphas_admitted_to_shadow for c in cycles)
        total_memory_blocks = sum(c.memory_blocks_hit for c in cycles)
        
        return LoopMetrics(
            loop_id=loop_id,
            feature_pass_rate=total_passed / max(1, total_features),
            alpha_admission_rate=total_admitted / max(1, total_alphas),
            tournament_win_rate=sum(1 for c in cycles if c.tournament_winner) / max(1, len(cycles)),
            memory_block_rate=total_memory_blocks / max(1, total_features),
            avg_feature_quality=sum(c.best_feature_score for c in cycles) / max(1, len(cycles)),
            avg_alpha_sharpe=sum(c.best_alpha_sharpe for c in cycles) / max(1, len(cycles)),
            features_per_cycle=total_features / max(1, len(cycles)),
            alphas_per_cycle=total_alphas / max(1, len(cycles)),
            admissions_per_cycle=total_admitted / max(1, len(cycles)),
            computed_at=int(time.time() * 1000)
        )
    
    # ============================================
    # Queries
    # ============================================
    
    def get_cycle(self, cycle_id: str) -> Optional[Dict]:
        """Get cycle result"""
        cycle = self.cycles.get(cycle_id)
        return self._cycle_to_dict(cycle) if cycle else None
    
    def list_cycles(self, loop_id: str = None, limit: int = 50) -> List[Dict]:
        """List cycles"""
        cycles = list(self.cycles.values())
        
        if loop_id:
            cycles = [c for c in cycles if c.loop_id == loop_id]
        
        cycles.sort(key=lambda c: c.started_at, reverse=True)
        return [self._cycle_to_dict(c) for c in cycles[:limit]]
    
    def get_events(self, cycle_id: str = None, limit: int = 100) -> List[Dict]:
        """Get events"""
        events = self.events
        
        if cycle_id:
            events = [e for e in events if e.cycle_id == cycle_id]
        
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)
        
        return [
            {
                "event_id": e.event_id,
                "cycle_id": e.cycle_id,
                "phase": e.phase.value,
                "event_type": e.event_type,
                "message": e.message,
                "timestamp": e.timestamp
            }
            for e in events[:limit]
        ]
    
    def get_health(self) -> Dict:
        """Get engine health"""
        return {
            "enabled": True,
            "version": "phase9.33",
            "status": "ok",
            "total_loops": len(self.loops),
            "total_cycles": len(self.cycles),
            "total_events": len(self.events),
            "modules_loaded": {
                "mutation_engine": self._mutation_engine is not None,
                "research_memory": self._research_memory is not None,
                "alpha_registry": self._alpha_registry is not None,
                "alpha_tournament": self._alpha_tournament is not None,
                "shadow_portfolio": self._shadow_portfolio is not None
            },
            "timestamp": int(time.time() * 1000)
        }
    
    # ============================================
    # Serialization
    # ============================================
    
    def _state_to_dict(self, state: LoopState) -> Dict:
        """Convert state to dict"""
        return {
            "loop_id": state.loop_id,
            "status": state.status.value,
            "current_phase": state.current_phase.value,
            "total_cycles": state.total_cycles,
            "successful_cycles": state.successful_cycles,
            "failed_cycles": state.failed_cycles,
            "current_cycle_id": state.current_cycle_id,
            "cycles_today": state.cycles_today,
            "total_features_generated": state.total_features_generated,
            "total_alphas_generated": state.total_alphas_generated,
            "total_alphas_admitted": state.total_alphas_admitted,
            "total_failures_recorded": state.total_failures_recorded,
            "last_cycle_at": state.last_cycle_at,
            "next_cycle_at": state.next_cycle_at
        }
    
    def _cycle_to_dict(self, cycle: LoopCycleResult) -> Dict:
        """Convert cycle to dict"""
        return {
            "cycle_id": cycle.cycle_id,
            "loop_id": cycle.loop_id,
            "phase": cycle.phase.value,
            "phase_history": cycle.phase_history,
            "features_generated": cycle.features_generated,
            "features_passed": cycle.features_passed,
            "features_rejected": cycle.features_rejected,
            "best_feature_id": cycle.best_feature_id,
            "best_feature_score": cycle.best_feature_score,
            "alphas_generated": cycle.alphas_generated,
            "alphas_registered": cycle.alphas_registered,
            "alphas_rejected": cycle.alphas_rejected,
            "best_alpha_id": cycle.best_alpha_id,
            "best_alpha_sharpe": cycle.best_alpha_sharpe,
            "tournament_id": cycle.tournament_id,
            "tournament_winner": cycle.tournament_winner,
            "tournament_rounds_completed": cycle.tournament_rounds_completed,
            "alphas_admitted_to_shadow": cycle.alphas_admitted_to_shadow,
            "alphas_rejected_from_shadow": cycle.alphas_rejected_from_shadow,
            "failures_recorded": cycle.failures_recorded,
            "patterns_updated": cycle.patterns_updated,
            "memory_blocks_hit": cycle.memory_blocks_hit,
            "started_at": cycle.started_at,
            "completed_at": cycle.completed_at,
            "duration_seconds": cycle.duration_seconds,
            "success": cycle.success,
            "error_message": cycle.error_message
        }
    
    def _config_to_dict(self, config: LoopConfig) -> Dict:
        """Convert config to dict"""
        return {
            "loop_id": config.loop_id,
            "name": config.name,
            "mode": config.mode.value,
            "max_mutations_per_cycle": config.max_mutations_per_cycle,
            "mutation_categories": config.mutation_categories,
            "max_alphas_per_cycle": config.max_alphas_per_cycle,
            "alpha_families": config.alpha_families,
            "min_feature_quality": config.min_feature_quality,
            "min_alpha_sharpe": config.min_alpha_sharpe,
            "max_crowding": config.max_crowding,
            "tournament_rounds": config.tournament_rounds,
            "min_tournament_score": config.min_tournament_score,
            "require_shadow_approval": config.require_shadow_approval,
            "shadow_observation_days": config.shadow_observation_days,
            "record_all_failures": config.record_all_failures,
            "check_memory_before_generate": config.check_memory_before_generate,
            "cooldown_seconds": config.cooldown_seconds,
            "max_cycles_per_day": config.max_cycles_per_day,
            "target_assets": config.target_assets,
            "target_timeframes": config.target_timeframes
        }


# Singleton
research_loop_engine = ResearchLoopEngine()
