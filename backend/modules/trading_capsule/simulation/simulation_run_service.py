"""
Simulation Run Service (S1.1)
=============================

Manages simulation run lifecycle.

Core operations:
- create_run: Create new simulation run
- start_run: Start simulation
- pause_run: Pause running simulation
- resume_run: Resume paused simulation
- stop_run: Stop and complete simulation
- get_run: Get run by ID
- list_runs: List all runs
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import threading

from .simulation_types import (
    SimulationRun,
    SimulationState,
    SimulationStatus,
    CapitalProfile,
    MarketType,
    Timeframe,
    get_capital_for_profile
)


class SimulationRunService:
    """
    Service for managing simulation runs.
    
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
        
        # Storage
        self._runs: Dict[str, SimulationRun] = {}
        
        # Event publisher (lazy init)
        self._publisher = None
        
        self._initialized = True
        print("[SimulationRunService] Initialized")
    
    def _get_publisher(self):
        """Get or create event publisher"""
        if self._publisher is None:
            try:
                from ..event_bus import create_publisher
                self._publisher = create_publisher("simulation_run")
            except ImportError:
                pass
        return self._publisher
    
    # ===========================================
    # Create Run
    # ===========================================
    
    def create_run(
        self,
        strategy_id: str,
        asset: str,
        start_date: str,
        end_date: str,
        capital_profile: CapitalProfile = CapitalProfile.SMALL,
        initial_capital_usd: Optional[float] = None,
        market_type: MarketType = MarketType.SPOT,
        timeframe: Timeframe = Timeframe.D1,
        strategy_version: Optional[str] = None,
        risk_profile_id: Optional[str] = None,
        dataset_id: Optional[str] = None
    ) -> SimulationRun:
        """
        Create a new simulation run.
        
        Args:
            strategy_id: Strategy to simulate
            asset: Asset to trade (e.g., "BTCUSDT")
            start_date: Simulation start date (YYYY-MM-DD)
            end_date: Simulation end date (YYYY-MM-DD)
            capital_profile: Predefined capital profile
            initial_capital_usd: Custom initial capital (overrides profile)
            market_type: SPOT or FUTURES
            timeframe: 1D, 4H, or 1H
            strategy_version: Strategy version
            risk_profile_id: Risk profile to use
            dataset_id: Dataset ID (generated if not provided)
            
        Returns:
            Created SimulationRun
        """
        # Determine capital
        capital = initial_capital_usd if initial_capital_usd else get_capital_for_profile(capital_profile)
        
        # Create run
        run = SimulationRun(
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            asset=asset,
            market_type=market_type,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            dataset_id=dataset_id,
            initial_capital_usd=capital,
            capital_profile=capital_profile,
            risk_profile_id=risk_profile_id,
            status=SimulationStatus.CREATED
        )
        
        # Store
        self._runs[run.run_id] = run
        
        # Publish event
        self._publish_event("simulation_run_created", {
            "run_id": run.run_id,
            "strategy_id": strategy_id,
            "asset": asset,
            "capital": capital
        })
        
        print(f"[SimulationRunService] Created run: {run.run_id}")
        return run
    
    # ===========================================
    # Run Lifecycle
    # ===========================================
    
    def start_run(self, run_id: str) -> Optional[SimulationRun]:
        """
        Start a simulation run.
        
        Changes status: CREATED → RUNNING
        """
        run = self._runs.get(run_id)
        if not run:
            return None
        
        if run.status != SimulationStatus.CREATED:
            print(f"[SimulationRunService] Cannot start run {run_id}: status={run.status.value}")
            return run
        
        run.status = SimulationStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        
        self._publish_event("simulation_run_started", {
            "run_id": run_id,
            "started_at": run.started_at.isoformat()
        })
        
        print(f"[SimulationRunService] Started run: {run_id}")
        return run
    
    def pause_run(self, run_id: str) -> Optional[SimulationRun]:
        """
        Pause a running simulation.
        
        Changes status: RUNNING → PAUSED
        """
        run = self._runs.get(run_id)
        if not run:
            return None
        
        if run.status != SimulationStatus.RUNNING:
            return run
        
        run.status = SimulationStatus.PAUSED
        
        self._publish_event("simulation_run_paused", {"run_id": run_id})
        
        print(f"[SimulationRunService] Paused run: {run_id}")
        return run
    
    def resume_run(self, run_id: str) -> Optional[SimulationRun]:
        """
        Resume a paused simulation.
        
        Changes status: PAUSED → RUNNING
        """
        run = self._runs.get(run_id)
        if not run:
            return None
        
        if run.status != SimulationStatus.PAUSED:
            return run
        
        run.status = SimulationStatus.RUNNING
        
        self._publish_event("simulation_run_resumed", {"run_id": run_id})
        
        print(f"[SimulationRunService] Resumed run: {run_id}")
        return run
    
    def stop_run(
        self,
        run_id: str,
        completed: bool = True,
        error_message: Optional[str] = None
    ) -> Optional[SimulationRun]:
        """
        Stop a simulation run.
        
        Changes status: RUNNING/PAUSED → COMPLETED/FAILED
        """
        run = self._runs.get(run_id)
        if not run:
            return None
        
        if run.status not in [SimulationStatus.RUNNING, SimulationStatus.PAUSED]:
            return run
        
        run.status = SimulationStatus.COMPLETED if completed else SimulationStatus.FAILED
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = error_message
        
        event_type = "simulation_run_completed" if completed else "simulation_run_failed"
        self._publish_event(event_type, {
            "run_id": run_id,
            "status": run.status.value,
            "finished_at": run.finished_at.isoformat()
        })
        
        print(f"[SimulationRunService] Stopped run: {run_id} ({run.status.value})")
        return run
    
    def complete_run(
        self,
        run_id: str,
        final_equity_usd: float,
        total_trades: int
    ) -> Optional[SimulationRun]:
        """
        Complete a run with final results.
        """
        run = self._runs.get(run_id)
        if not run:
            return None
        
        run.final_equity_usd = final_equity_usd
        run.total_trades = total_trades
        run.status = SimulationStatus.COMPLETED
        run.finished_at = datetime.now(timezone.utc)
        
        self._publish_event("simulation_run_completed", {
            "run_id": run_id,
            "final_equity_usd": final_equity_usd,
            "total_trades": total_trades
        })
        
        return run
    
    # ===========================================
    # Queries
    # ===========================================
    
    def get_run(self, run_id: str) -> Optional[SimulationRun]:
        """Get run by ID"""
        return self._runs.get(run_id)
    
    def list_runs(
        self,
        status: Optional[SimulationStatus] = None,
        strategy_id: Optional[str] = None,
        asset: Optional[str] = None,
        limit: int = 100
    ) -> List[SimulationRun]:
        """
        List simulation runs with optional filters.
        """
        runs = list(self._runs.values())
        
        # Filter by status
        if status:
            runs = [r for r in runs if r.status == status]
        
        # Filter by strategy
        if strategy_id:
            runs = [r for r in runs if r.strategy_id == strategy_id]
        
        # Filter by asset
        if asset:
            runs = [r for r in runs if r.asset == asset]
        
        # Sort by created_at desc
        runs.sort(key=lambda r: r.created_at, reverse=True)
        
        return runs[:limit]
    
    def get_active_runs(self) -> List[SimulationRun]:
        """Get all running simulations"""
        return [
            r for r in self._runs.values()
            if r.status == SimulationStatus.RUNNING
        ]
    
    def count(self) -> int:
        """Get total number of runs"""
        return len(self._runs)
    
    # ===========================================
    # Update
    # ===========================================
    
    def update_run_results(
        self,
        run_id: str,
        final_equity_usd: Optional[float] = None,
        total_trades: Optional[int] = None
    ) -> Optional[SimulationRun]:
        """Update run results"""
        run = self._runs.get(run_id)
        if not run:
            return None
        
        if final_equity_usd is not None:
            run.final_equity_usd = final_equity_usd
        
        if total_trades is not None:
            run.total_trades = total_trades
        
        return run
    
    # ===========================================
    # Events
    # ===========================================
    
    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Publish event to Event Bus"""
        publisher = self._get_publisher()
        if publisher:
            try:
                publisher.publish(event_type, payload)
            except Exception:
                pass
    
    # ===========================================
    # Cleanup
    # ===========================================
    
    def delete_run(self, run_id: str) -> bool:
        """Delete a run"""
        if run_id in self._runs:
            del self._runs[run_id]
            return True
        return False
    
    def clear_completed(self) -> int:
        """Clear completed runs"""
        to_delete = [
            run_id for run_id, run in self._runs.items()
            if run.status in [SimulationStatus.COMPLETED, SimulationStatus.FAILED]
        ]
        for run_id in to_delete:
            del self._runs[run_id]
        return len(to_delete)


# Global singleton
simulation_run_service = SimulationRunService()
