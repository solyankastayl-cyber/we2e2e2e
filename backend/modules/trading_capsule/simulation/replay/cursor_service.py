"""
Replay Cursor Service (S1.2)
============================

Manages replay cursor position.

Cursor tracks:
- Current candle index
- Current timestamp
- Replay progress
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
import threading

from ..simulation_types import ReplayCursor
from .dataset_service import market_dataset_service


class ReplayCursorService:
    """
    Service for managing replay cursors.
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
        
        # Cursor storage: run_id -> ReplayCursor
        self._cursors: Dict[str, ReplayCursor] = {}
        
        self._initialized = True
        print("[ReplayCursorService] Initialized")
    
    # ===========================================
    # Cursor Operations
    # ===========================================
    
    def create_cursor(self, run_id: str, dataset_id: str) -> ReplayCursor:
        """
        Create a new cursor for a run.
        
        Initializes at position 0.
        """
        cursor = ReplayCursor(
            run_id=run_id,
            dataset_id=dataset_id,
            current_index=0,
            current_timestamp=None,
            finished=False
        )
        
        # Set initial timestamp from first candle
        candle = market_dataset_service.get_candle(dataset_id, 0)
        if candle:
            cursor.current_timestamp = candle.timestamp
        
        self._cursors[run_id] = cursor
        
        print(f"[ReplayCursorService] Created cursor for run: {run_id}")
        return cursor
    
    def get_cursor(self, run_id: str) -> Optional[ReplayCursor]:
        """Get cursor for run"""
        return self._cursors.get(run_id)
    
    def advance_cursor(self, run_id: str) -> Optional[ReplayCursor]:
        """
        Advance cursor to next candle.
        
        Returns updated cursor or None if finished.
        """
        cursor = self._cursors.get(run_id)
        if not cursor or cursor.finished:
            return cursor
        
        # Get dataset length
        dataset_length = market_dataset_service.get_dataset_length(cursor.dataset_id)
        
        # Advance
        cursor.current_index += 1
        
        # Check if finished
        if cursor.current_index >= dataset_length:
            cursor.finished = True
            return cursor
        
        # Update timestamp
        candle = market_dataset_service.get_candle(cursor.dataset_id, cursor.current_index)
        if candle:
            cursor.current_timestamp = candle.timestamp
        
        return cursor
    
    def reset_cursor(self, run_id: str) -> Optional[ReplayCursor]:
        """Reset cursor to beginning"""
        cursor = self._cursors.get(run_id)
        if not cursor:
            return None
        
        cursor.current_index = 0
        cursor.finished = False
        
        # Reset timestamp
        candle = market_dataset_service.get_candle(cursor.dataset_id, 0)
        if candle:
            cursor.current_timestamp = candle.timestamp
        
        return cursor
    
    def set_cursor_position(self, run_id: str, index: int) -> Optional[ReplayCursor]:
        """Set cursor to specific position"""
        cursor = self._cursors.get(run_id)
        if not cursor:
            return None
        
        dataset_length = market_dataset_service.get_dataset_length(cursor.dataset_id)
        
        if index < 0 or index >= dataset_length:
            return cursor
        
        cursor.current_index = index
        cursor.finished = False
        
        candle = market_dataset_service.get_candle(cursor.dataset_id, index)
        if candle:
            cursor.current_timestamp = candle.timestamp
        
        return cursor
    
    def get_progress(self, run_id: str) -> float:
        """Get replay progress (0.0 to 1.0)"""
        cursor = self._cursors.get(run_id)
        if not cursor:
            return 0.0
        
        dataset_length = market_dataset_service.get_dataset_length(cursor.dataset_id)
        if dataset_length == 0:
            return 0.0
        
        return cursor.current_index / dataset_length
    
    def delete_cursor(self, run_id: str) -> bool:
        """Delete cursor"""
        if run_id in self._cursors:
            del self._cursors[run_id]
            return True
        return False


# Global singleton
replay_cursor_service = ReplayCursorService()
