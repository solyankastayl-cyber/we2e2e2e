"""
Strategy State Manager (T6)
===========================

Manages runtime state of strategies.

Handles:
- Enable/disable strategies
- Pause/resume strategies
- Track metrics and errors
- Persist state
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import threading

from .strategy_types import StrategyState, StrategyStatus


class StrategyStateManager:
    """
    Manager for strategy runtime states.
    
    Tracks which strategies are enabled, paused, or in error state.
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
        
        # State storage
        self._states: Dict[str, StrategyState] = {}
        
        # Active strategies (enabled + not paused)
        self._active_ids: List[str] = []
        
        self._initialized = True
        print("[StrategyStateManager] Initialized")
    
    # ===========================================
    # State Management
    # ===========================================
    
    def get_state(self, strategy_id: str) -> Optional[StrategyState]:
        """Get strategy state"""
        return self._states.get(strategy_id)
    
    def get_or_create_state(self, strategy_id: str) -> StrategyState:
        """Get or create strategy state"""
        if strategy_id not in self._states:
            self._states[strategy_id] = StrategyState(strategy_id=strategy_id)
        return self._states[strategy_id]
    
    def get_all_states(self) -> List[StrategyState]:
        """Get all states"""
        return list(self._states.values())
    
    # ===========================================
    # Enable/Disable
    # ===========================================
    
    def enable(self, strategy_id: str) -> StrategyState:
        """
        Enable a strategy.
        
        Makes it eligible to receive signals and generate actions.
        """
        state = self.get_or_create_state(strategy_id)
        
        if state.status == StrategyStatus.ACTIVE:
            return state  # Already active
        
        state.status = StrategyStatus.ACTIVE
        state.enabled_at = datetime.now(timezone.utc)
        state.disabled_at = None
        state.paused_at = None
        
        # Add to active list
        if strategy_id not in self._active_ids:
            self._active_ids.append(strategy_id)
        
        print(f"[StrategyStateManager] Enabled: {strategy_id}")
        return state
    
    def disable(self, strategy_id: str) -> Optional[StrategyState]:
        """
        Disable a strategy.
        
        Stops it from receiving signals.
        """
        state = self._states.get(strategy_id)
        if not state:
            return None
        
        state.status = StrategyStatus.DISABLED
        state.disabled_at = datetime.now(timezone.utc)
        
        # Remove from active list
        if strategy_id in self._active_ids:
            self._active_ids.remove(strategy_id)
        
        print(f"[StrategyStateManager] Disabled: {strategy_id}")
        return state
    
    # ===========================================
    # Pause/Resume
    # ===========================================
    
    def pause(self, strategy_id: str) -> Optional[StrategyState]:
        """
        Pause a strategy temporarily.
        
        Strategy remains registered but doesn't process signals.
        """
        state = self._states.get(strategy_id)
        if not state:
            return None
        
        if state.status != StrategyStatus.ACTIVE:
            return state  # Can only pause active strategies
        
        state.status = StrategyStatus.PAUSED
        state.paused_at = datetime.now(timezone.utc)
        
        # Remove from active list
        if strategy_id in self._active_ids:
            self._active_ids.remove(strategy_id)
        
        print(f"[StrategyStateManager] Paused: {strategy_id}")
        return state
    
    def resume(self, strategy_id: str) -> Optional[StrategyState]:
        """
        Resume a paused strategy.
        """
        state = self._states.get(strategy_id)
        if not state:
            return None
        
        if state.status != StrategyStatus.PAUSED:
            return state  # Can only resume paused strategies
        
        state.status = StrategyStatus.ACTIVE
        state.paused_at = None
        
        # Add to active list
        if strategy_id not in self._active_ids:
            self._active_ids.append(strategy_id)
        
        print(f"[StrategyStateManager] Resumed: {strategy_id}")
        return state
    
    # ===========================================
    # Status Queries
    # ===========================================
    
    def is_active(self, strategy_id: str) -> bool:
        """Check if strategy is active"""
        return strategy_id in self._active_ids
    
    def get_active_ids(self) -> List[str]:
        """Get list of active strategy IDs"""
        return list(self._active_ids)
    
    def get_enabled_ids(self) -> List[str]:
        """Get list of enabled strategy IDs (active or paused)"""
        return [
            sid for sid, state in self._states.items()
            if state.status in [StrategyStatus.ACTIVE, StrategyStatus.PAUSED]
        ]
    
    def get_status(self, strategy_id: str) -> Optional[StrategyStatus]:
        """Get strategy status"""
        state = self._states.get(strategy_id)
        return state.status if state else None
    
    # ===========================================
    # Metrics
    # ===========================================
    
    def record_signal(self, strategy_id: str) -> None:
        """Record that strategy received a signal"""
        state = self.get_or_create_state(strategy_id)
        state.signals_received += 1
        state.last_signal_at = datetime.now(timezone.utc)
    
    def record_action(self, strategy_id: str) -> None:
        """Record that strategy generated an action"""
        state = self.get_or_create_state(strategy_id)
        state.actions_generated += 1
        state.last_action_at = datetime.now(timezone.utc)
    
    def record_error(self, strategy_id: str, error: str) -> None:
        """Record strategy error"""
        state = self.get_or_create_state(strategy_id)
        state.errors += 1
        state.last_error = error
        state.last_error_at = datetime.now(timezone.utc)
        
        # Auto-disable after too many errors
        if state.errors >= 10:
            state.status = StrategyStatus.ERROR
            if strategy_id in self._active_ids:
                self._active_ids.remove(strategy_id)
            print(f"[StrategyStateManager] Strategy error threshold reached: {strategy_id}")
    
    def update_pnl(self, strategy_id: str, pnl: float, is_win: bool) -> None:
        """Update strategy PnL and win rate"""
        state = self.get_or_create_state(strategy_id)
        state.total_pnl += pnl
        
        # Update win rate (exponential moving average)
        alpha = 0.1
        state.win_rate = state.win_rate * (1 - alpha) + (1.0 if is_win else 0.0) * alpha
    
    # ===========================================
    # Summary
    # ===========================================
    
    def get_summary(self) -> Dict[str, Any]:
        """Get state manager summary"""
        by_status = {}
        for state in self._states.values():
            status = state.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_strategies": len(self._states),
            "active_strategies": len(self._active_ids),
            "by_status": by_status,
            "active_ids": list(self._active_ids)
        }
    
    def clear(self) -> int:
        """Clear all states (for testing)"""
        count = len(self._states)
        self._states.clear()
        self._active_ids.clear()
        print(f"[StrategyStateManager] Cleared {count} states")
        return count


# Global singleton
strategy_state_manager = StrategyStateManager()
