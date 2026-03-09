"""
Replay Driver Service (S1.2)
============================

Core replay engine that drives simulation.

Modes:
- STEP: Manual step-by-step
- AUTO: Automatic replay
- FAST: Maximum speed

Pipeline per step:
1. Get candle from dataset
2. Create MarketTickEvent
3. Start step orchestration
4. Process through Strategy Runtime
5. Wait for step completion
6. Advance cursor
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
import threading
import asyncio

from ..simulation_types import (
    ReplayState,
    ReplayStatus,
    ReplayMode,
    MarketTickEvent,
    SimulationStatus
)

from .dataset_service import market_dataset_service
from .cursor_service import replay_cursor_service
from .orchestrator_service import step_orchestrator_service


class ReplayDriverService:
    """
    Main replay driver that controls simulation execution.
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
        
        # Replay state storage
        self._replay_states: Dict[str, ReplayState] = {}
        
        # Running flags
        self._running: Dict[str, bool] = {}
        
        # Tick callback (for strategy runtime)
        self._tick_callback: Optional[Callable] = None
        
        # Event publisher
        self._publisher = None
        
        self._initialized = True
        print("[ReplayDriverService] Initialized")
    
    def _get_publisher(self):
        if self._publisher is None:
            try:
                from ...event_bus import create_publisher
                self._publisher = create_publisher("replay_driver")
            except ImportError:
                pass
        return self._publisher
    
    # ===========================================
    # Replay State Management
    # ===========================================
    
    def create_replay(
        self,
        run_id: str,
        dataset_id: str,
        mode: ReplayMode = ReplayMode.AUTO
    ) -> ReplayState:
        """
        Create replay state for a run.
        """
        # Create cursor
        replay_cursor_service.create_cursor(run_id, dataset_id)
        
        # Get dataset length
        total_steps = market_dataset_service.get_dataset_length(dataset_id)
        
        # Create state
        state = ReplayState(
            run_id=run_id,
            cursor_index=0,
            total_steps=total_steps,
            progress=0.0,
            mode=mode,
            status=ReplayStatus.IDLE
        )
        
        self._replay_states[run_id] = state
        self._running[run_id] = False
        
        print(f"[ReplayDriverService] Created replay for run: {run_id}")
        return state
    
    def get_replay_state(self, run_id: str) -> Optional[ReplayState]:
        """Get replay state"""
        return self._replay_states.get(run_id)
    
    def set_tick_callback(self, callback: Callable) -> None:
        """
        Set callback for market ticks.
        
        Callback signature: async def callback(run_id, tick_event)
        """
        self._tick_callback = callback
    
    # ===========================================
    # Replay Control
    # ===========================================
    
    async def start_replay(self, run_id: str) -> Optional[ReplayState]:
        """
        Start replay execution.
        """
        state = self._replay_states.get(run_id)
        if not state:
            return None
        
        if state.status == ReplayStatus.RUNNING:
            return state
        
        state.status = ReplayStatus.RUNNING
        self._running[run_id] = True
        
        self._publish_event("simulation_replay_started", {"run_id": run_id})
        
        # If AUTO mode, start continuous replay
        if state.mode == ReplayMode.AUTO:
            asyncio.create_task(self._run_auto_replay(run_id))
        
        return state
    
    async def pause_replay(self, run_id: str) -> Optional[ReplayState]:
        """Pause replay"""
        state = self._replay_states.get(run_id)
        if not state:
            return None
        
        self._running[run_id] = False
        state.status = ReplayStatus.PAUSED
        
        self._publish_event("simulation_replay_paused", {"run_id": run_id})
        
        return state
    
    async def stop_replay(self, run_id: str) -> Optional[ReplayState]:
        """Stop replay"""
        state = self._replay_states.get(run_id)
        if not state:
            return None
        
        self._running[run_id] = False
        state.status = ReplayStatus.FINISHED
        
        self._publish_event("simulation_replay_finished", {"run_id": run_id})
        
        return state
    
    async def step_replay(self, run_id: str) -> Dict[str, Any]:
        """
        Execute single step of replay.
        
        This is the core execution method.
        """
        state = self._replay_states.get(run_id)
        if not state:
            return {"success": False, "error": "Replay not found"}
        
        cursor = replay_cursor_service.get_cursor(run_id)
        if not cursor:
            return {"success": False, "error": "Cursor not found"}
        
        if cursor.finished:
            state.status = ReplayStatus.FINISHED
            return {"success": True, "finished": True}
        
        # Get current candle
        candle = market_dataset_service.get_candle(cursor.dataset_id, cursor.current_index)
        if not candle:
            return {"success": False, "error": "No candle data"}
        
        # Create tick event
        tick_event = MarketTickEvent(
            run_id=run_id,
            step_index=cursor.current_index,
            asset=market_dataset_service.get_dataset(cursor.dataset_id).asset,
            timestamp=candle.timestamp,
            candle=candle
        )
        
        # Start step orchestration
        step = step_orchestrator_service.start_step(
            run_id=run_id,
            step_index=cursor.current_index,
            timestamp=candle.timestamp
        )
        
        # Register MARKET_TICK event
        step_orchestrator_service.register_event(run_id, "MARKET_TICK", tick_event.to_dict())
        
        # Call tick callback (Strategy Runtime)
        if self._tick_callback:
            try:
                await self._tick_callback(run_id, tick_event)
            except Exception as e:
                print(f"[ReplayDriver] Tick callback error: {e}")
        
        # Register STEP_COMPLETED
        step_orchestrator_service.register_event(run_id, "STEP_COMPLETED")
        
        # Complete step
        step_orchestrator_service.complete_step(run_id)
        
        # Advance cursor
        replay_cursor_service.advance_cursor(run_id)
        
        # Update state
        cursor = replay_cursor_service.get_cursor(run_id)
        state.cursor_index = cursor.current_index
        state.current_timestamp = cursor.current_timestamp
        state.progress = replay_cursor_service.get_progress(run_id)
        
        # Publish step event
        self._publish_event("simulation_replay_step", {
            "run_id": run_id,
            "step_index": step.step_index,
            "timestamp": step.timestamp,
            "progress": state.progress
        })
        
        # Check if finished
        if cursor.finished:
            state.status = ReplayStatus.FINISHED
            self._publish_event("simulation_replay_finished", {"run_id": run_id})
            return {"success": True, "finished": True, "step": step.to_dict()}
        
        return {
            "success": True,
            "finished": False,
            "step": step.to_dict(),
            "tick": tick_event.to_dict()
        }
    
    async def _run_auto_replay(self, run_id: str) -> None:
        """
        Run automatic replay until paused or finished.
        """
        state = self._replay_states.get(run_id)
        if not state:
            return
        
        while self._running.get(run_id, False):
            result = await self.step_replay(run_id)
            
            if result.get("finished", False):
                break
            
            # Small delay to prevent blocking (adjustable for FAST mode)
            if state.mode == ReplayMode.AUTO:
                await asyncio.sleep(0.01)
            elif state.mode == ReplayMode.FAST:
                await asyncio.sleep(0)
    
    async def run_full_replay(self, run_id: str) -> Dict[str, Any]:
        """
        Run full replay to completion (blocking).
        
        Used for FAST mode or programmatic simulation.
        """
        state = self._replay_states.get(run_id)
        if not state:
            return {"success": False, "error": "Replay not found"}
        
        state.status = ReplayStatus.RUNNING
        
        total_steps = 0
        while True:
            result = await self.step_replay(run_id)
            total_steps += 1
            
            if result.get("finished", False):
                break
            
            if not result.get("success", False):
                return result
        
        return {
            "success": True,
            "total_steps": total_steps,
            "final_progress": state.progress
        }
    
    # ===========================================
    # Events
    # ===========================================
    
    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        publisher = self._get_publisher()
        if publisher:
            try:
                publisher.publish(event_type, payload)
            except Exception:
                pass
    
    # ===========================================
    # Cleanup
    # ===========================================
    
    def delete_replay(self, run_id: str) -> bool:
        """Delete replay state"""
        deleted = False
        
        if run_id in self._replay_states:
            del self._replay_states[run_id]
            deleted = True
        
        self._running.pop(run_id, None)
        replay_cursor_service.delete_cursor(run_id)
        step_orchestrator_service.clear_run(run_id)
        
        return deleted


# Global singleton
replay_driver_service = ReplayDriverService()
