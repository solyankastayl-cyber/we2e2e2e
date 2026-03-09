"""
Simulation State Service (S1.1)
===============================

Manages runtime state of simulations.

Tracks:
- Equity/cash
- Positions/orders
- PnL
- Drawdown
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import threading

from .simulation_types import (
    SimulationState,
    SimulationPosition
)


class SimulationStateService:
    """
    Service for managing simulation state.
    
    Thread-safe singleton.
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
        self._states: Dict[str, SimulationState] = {}
        
        # Position storage
        self._positions: Dict[str, Dict[str, SimulationPosition]] = {}  # run_id -> asset -> position
        
        # Equity history
        self._equity_history: Dict[str, List[Dict[str, Any]]] = {}  # run_id -> [(timestamp, equity)]
        
        self._initialized = True
        print("[SimulationStateService] Initialized")
    
    # ===========================================
    # State Management
    # ===========================================
    
    def create_state(self, run_id: str, initial_capital_usd: float) -> SimulationState:
        """
        Create initial state for a run.
        """
        state = SimulationState(
            run_id=run_id,
            equity_usd=initial_capital_usd,
            cash_usd=initial_capital_usd,
            peak_equity_usd=initial_capital_usd
        )
        
        self._states[run_id] = state
        self._positions[run_id] = {}
        self._equity_history[run_id] = []
        
        print(f"[SimulationStateService] Created state for run: {run_id}")
        return state
    
    def get_state(self, run_id: str) -> Optional[SimulationState]:
        """Get state by run ID"""
        return self._states.get(run_id)
    
    def get_or_create_state(self, run_id: str, initial_capital: float = 0) -> SimulationState:
        """Get or create state"""
        if run_id not in self._states:
            return self.create_state(run_id, initial_capital)
        return self._states[run_id]
    
    # ===========================================
    # State Updates
    # ===========================================
    
    def update_step(
        self,
        run_id: str,
        step_index: int,
        timestamp: str
    ) -> Optional[SimulationState]:
        """Update current step"""
        state = self._states.get(run_id)
        if not state:
            return None
        
        state.current_step_index = step_index
        state.current_timestamp = timestamp
        
        return state
    
    def update_portfolio(
        self,
        run_id: str,
        equity_usd: Optional[float] = None,
        cash_usd: Optional[float] = None,
        realized_pnl_usd: Optional[float] = None,
        unrealized_pnl_usd: Optional[float] = None
    ) -> Optional[SimulationState]:
        """Update portfolio state"""
        state = self._states.get(run_id)
        if not state:
            return None
        
        if equity_usd is not None:
            state.equity_usd = equity_usd
            
            # Track peak and drawdown
            if equity_usd > state.peak_equity_usd:
                state.peak_equity_usd = equity_usd
            
            if state.peak_equity_usd > 0:
                state.current_drawdown_pct = (state.peak_equity_usd - equity_usd) / state.peak_equity_usd
                if state.current_drawdown_pct > state.max_drawdown_pct:
                    state.max_drawdown_pct = state.current_drawdown_pct
        
        if cash_usd is not None:
            state.cash_usd = cash_usd
        
        if realized_pnl_usd is not None:
            state.realized_pnl_usd = realized_pnl_usd
        
        if unrealized_pnl_usd is not None:
            state.unrealized_pnl_usd = unrealized_pnl_usd
        
        return state
    
    def update_counts(
        self,
        run_id: str,
        open_positions: Optional[int] = None,
        open_orders: Optional[int] = None
    ) -> Optional[SimulationState]:
        """Update position/order counts"""
        state = self._states.get(run_id)
        if not state:
            return None
        
        if open_positions is not None:
            state.open_positions = open_positions
        
        if open_orders is not None:
            state.open_orders = open_orders
        
        return state
    
    def add_realized_pnl(self, run_id: str, pnl: float) -> Optional[SimulationState]:
        """Add to realized PnL"""
        state = self._states.get(run_id)
        if not state:
            return None
        
        state.realized_pnl_usd += pnl
        return state
    
    # ===========================================
    # Position Management
    # ===========================================
    
    def set_position(
        self,
        run_id: str,
        asset: str,
        side: str,
        size: float,
        entry_price: float
    ) -> SimulationPosition:
        """Set or update position"""
        if run_id not in self._positions:
            self._positions[run_id] = {}
        
        position = SimulationPosition(
            run_id=run_id,
            asset=asset,
            side=side,
            size=size,
            entry_price=entry_price
        )
        
        self._positions[run_id][asset] = position
        
        # Update state
        state = self._states.get(run_id)
        if state:
            state.open_positions = sum(
                1 for p in self._positions[run_id].values()
                if p.size > 0
            )
        
        return position
    
    def get_position(self, run_id: str, asset: str) -> Optional[SimulationPosition]:
        """Get position for asset"""
        if run_id not in self._positions:
            return None
        return self._positions[run_id].get(asset)
    
    def get_all_positions(self, run_id: str) -> List[SimulationPosition]:
        """Get all positions for run"""
        if run_id not in self._positions:
            return []
        return list(self._positions[run_id].values())
    
    def close_position(self, run_id: str, asset: str) -> Optional[SimulationPosition]:
        """Close position (set size to 0)"""
        position = self.get_position(run_id, asset)
        if position:
            position.side = "FLAT"
            position.size = 0
            position.unrealized_pnl = 0
        
        # Update state
        state = self._states.get(run_id)
        if state:
            state.open_positions = sum(
                1 for p in self._positions.get(run_id, {}).values()
                if p.size > 0
            )
        
        return position
    
    def update_position_price(
        self,
        run_id: str,
        asset: str,
        current_price: float
    ) -> Optional[SimulationPosition]:
        """Update position with current price and calculate unrealized PnL"""
        position = self.get_position(run_id, asset)
        if not position or position.size == 0:
            return position
        
        position.current_price = current_price
        
        # Calculate unrealized PnL
        if position.side == "LONG":
            position.unrealized_pnl = (current_price - position.entry_price) * position.size
        elif position.side == "SHORT":
            position.unrealized_pnl = (position.entry_price - current_price) * position.size
        
        return position
    
    # ===========================================
    # Equity History
    # ===========================================
    
    def record_equity(
        self,
        run_id: str,
        timestamp: str,
        equity_usd: float
    ) -> None:
        """Record equity point for history"""
        if run_id not in self._equity_history:
            self._equity_history[run_id] = []
        
        self._equity_history[run_id].append({
            "timestamp": timestamp,
            "equity_usd": round(equity_usd, 2)
        })
    
    def get_equity_history(self, run_id: str) -> List[Dict[str, Any]]:
        """Get equity history for run"""
        return self._equity_history.get(run_id, [])
    
    # ===========================================
    # Cleanup
    # ===========================================
    
    def delete_state(self, run_id: str) -> bool:
        """Delete state for run"""
        deleted = False
        
        if run_id in self._states:
            del self._states[run_id]
            deleted = True
        
        if run_id in self._positions:
            del self._positions[run_id]
        
        if run_id in self._equity_history:
            del self._equity_history[run_id]
        
        return deleted
    
    def clear_all(self) -> int:
        """Clear all states"""
        count = len(self._states)
        self._states.clear()
        self._positions.clear()
        self._equity_history.clear()
        return count


# Global singleton
simulation_state_service = SimulationStateService()
