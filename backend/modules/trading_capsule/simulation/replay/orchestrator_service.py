"""
Step Orchestrator Service (S1.2)
================================

Orchestrates single simulation step execution.

Ensures deterministic event order:
1. MARKET_TICK
2. STRATEGY_ACTION
3. EXECUTION_INTENT
4. RISK_VERDICT
5. ORDER_EVENT
6. POSITION_UPDATE
7. STEP_COMPLETED
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
import threading
import asyncio

from ..simulation_types import (
    SimulationStep,
    SimulationStepStatus,
    MarketTickEvent,
    MarketCandle
)


# Expected events in deterministic order
EXPECTED_STEP_EVENTS = [
    "MARKET_TICK",
    "STRATEGY_ACTION",
    "EXECUTION_INTENT", 
    "RISK_VERDICT",
    "ORDER_EVENT",
    "POSITION_UPDATE",
    "STEP_COMPLETED"
]


class StepOrchestratorService:
    """
    Orchestrates execution of simulation steps.
    
    Ensures deterministic event order.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Step storage: run_id -> current step
        self._current_steps: Dict[str, SimulationStep] = {}
        
        # Step history: run_id -> list of completed steps
        self._step_history: Dict[str, List[SimulationStep]] = {}
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        self._initialized = True
        print("[StepOrchestratorService] Initialized")
    
    # ===========================================
    # Step Lifecycle
    # ===========================================
    
    def start_step(
        self,
        run_id: str,
        step_index: int,
        timestamp: str
    ) -> SimulationStep:
        """
        Start a new simulation step.
        
        Initializes step with expected events.
        """
        step = SimulationStep(
            run_id=run_id,
            step_index=step_index,
            timestamp=timestamp,
            status=SimulationStepStatus.IN_PROGRESS,
            expected_events=EXPECTED_STEP_EVENTS.copy(),
            received_events=[],
            started_at=datetime.now(timezone.utc)
        )
        
        self._current_steps[run_id] = step
        
        # Initialize history if needed
        if run_id not in self._step_history:
            self._step_history[run_id] = []
        
        return step
    
    def register_event(
        self,
        run_id: str,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Register that an event occurred in current step.
        
        Returns True if event was expected and registered.
        """
        step = self._current_steps.get(run_id)
        if not step:
            return False
        
        if step.status != SimulationStepStatus.IN_PROGRESS:
            return False
        
        # Register event
        step.received_events.append(event_type)
        
        # Trigger handlers
        self._trigger_handlers(event_type, run_id, event_data)
        
        return True
    
    def check_step_completion(self, run_id: str) -> bool:
        """
        Check if current step is complete.
        
        Step is complete when STEP_COMPLETED event is received.
        """
        step = self._current_steps.get(run_id)
        if not step:
            return True
        
        return "STEP_COMPLETED" in step.received_events
    
    def complete_step(self, run_id: str) -> Optional[SimulationStep]:
        """
        Mark current step as completed and archive.
        """
        step = self._current_steps.get(run_id)
        if not step:
            return None
        
        step.status = SimulationStepStatus.COMPLETED
        step.completed_at = datetime.now(timezone.utc)
        
        # Archive
        self._step_history[run_id].append(step)
        
        return step
    
    def fail_step(self, run_id: str, reason: str = "") -> Optional[SimulationStep]:
        """Mark current step as failed"""
        step = self._current_steps.get(run_id)
        if not step:
            return None
        
        step.status = SimulationStepStatus.FAILED
        step.completed_at = datetime.now(timezone.utc)
        
        # Archive
        self._step_history[run_id].append(step)
        
        return step
    
    # ===========================================
    # Step Queries
    # ===========================================
    
    def get_current_step(self, run_id: str) -> Optional[SimulationStep]:
        """Get current step"""
        return self._current_steps.get(run_id)
    
    def get_step_history(self, run_id: str) -> List[SimulationStep]:
        """Get step history for run"""
        return self._step_history.get(run_id, [])
    
    def get_missing_events(self, run_id: str) -> List[str]:
        """Get events that haven't been received yet"""
        step = self._current_steps.get(run_id)
        if not step:
            return []
        
        return [e for e in step.expected_events if e not in step.received_events]
    
    # ===========================================
    # Event Handlers
    # ===========================================
    
    def on_event(self, event_type: str, handler: Callable) -> None:
        """Register event handler"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def _trigger_handlers(
        self,
        event_type: str,
        run_id: str,
        event_data: Optional[Dict[str, Any]]
    ) -> None:
        """Trigger handlers for event"""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(run_id, event_data)
            except Exception as e:
                print(f"[StepOrchestrator] Handler error: {e}")
    
    # ===========================================
    # Cleanup
    # ===========================================
    
    def clear_run(self, run_id: str) -> None:
        """Clear step data for run"""
        if run_id in self._current_steps:
            del self._current_steps[run_id]
        if run_id in self._step_history:
            del self._step_history[run_id]
    
    def clear_all(self) -> None:
        """Clear all step data"""
        self._current_steps.clear()
        self._step_history.clear()


# Global singleton
step_orchestrator_service = StepOrchestratorService()
