"""
Phase 8: Market Replay Engine
Replays market candle-by-candle for analysis.
"""
import time
import random
from typing import Dict, List, Optional, Any

from .types import (
    ReplayState,
    ReplayStatus,
    VALIDATION_CONFIG
)


class ReplayEngine:
    """
    Market Replay Engine.
    
    Replays market history bar-by-bar to see:
    - How scenarios changed
    - Where MetaBrain switched modes
    - Where strategy broke down
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or VALIDATION_CONFIG
        self._active_replays: Dict[str, ReplayState] = {}
    
    def start(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        start_date: str = "2024-01-01",
        end_date: str = "2024-03-01",
        speed: float = 1.0
    ) -> ReplayState:
        """
        Start a new market replay.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Start date
            end_date: End date
            speed: Replay speed multiplier
            
        Returns:
            Initial ReplayState
        """
        run_id = f"replay_{symbol}_{timeframe}_{int(time.time() * 1000)}"
        
        # Calculate total bars (mock)
        total_bars = random.randint(200, 400)
        
        state = ReplayState(
            run_id=run_id,
            symbol=symbol,
            timeframe=timeframe,
            current_bar=0,
            total_bars=total_bars,
            current_time=int(time.time() * 1000) - total_bars * 4 * 3600000,
            current_price=40000 + random.uniform(-5000, 10000),
            current_regime="RANGE",
            current_scenario="COMPRESSION",
            current_structure="NEUTRAL",
            metabrain_mode="BALANCED",
            metabrain_confidence=0.6,
            status=ReplayStatus.RUNNING,
            progress=0.0
        )
        
        self._active_replays[run_id] = state
        
        return state
    
    def step(self, run_id: str) -> Optional[ReplayState]:
        """
        Advance replay by one bar.
        
        Returns:
            Updated ReplayState or None if not found
        """
        state = self._active_replays.get(run_id)
        if not state:
            return None
        
        if state.status != ReplayStatus.RUNNING:
            return state
        
        if state.current_bar >= state.total_bars:
            state.status = ReplayStatus.COMPLETED
            state.progress = 1.0
            return state
        
        # Advance one bar
        state.current_bar += 1
        state.progress = state.current_bar / state.total_bars
        state.current_time += 4 * 3600000  # 4 hours in ms
        
        # Simulate price movement
        price_change = random.uniform(-0.02, 0.025) * state.current_price
        state.current_price = round(state.current_price + price_change, 2)
        
        # Simulate regime changes (occasionally)
        if random.random() < 0.05:
            old_regime = state.current_regime
            state.current_regime = random.choice(["TREND_UP", "TREND_DOWN", "RANGE"])
            if old_regime != state.current_regime:
                state.events.append({
                    "bar": state.current_bar,
                    "type": "REGIME_CHANGE",
                    "from": old_regime,
                    "to": state.current_regime,
                    "time": state.current_time
                })
        
        # Simulate scenario changes
        if random.random() < 0.08:
            old_scenario = state.current_scenario
            state.current_scenario = random.choice([
                "COMPRESSION", "BREAKOUT", "RETEST", "EXPANSION", "REVERSAL"
            ])
            if old_scenario != state.current_scenario:
                state.scenario_changes.append({
                    "bar": state.current_bar,
                    "from": old_scenario,
                    "to": state.current_scenario,
                    "time": state.current_time
                })
        
        # Simulate MetaBrain mode changes
        if random.random() < 0.03:
            old_mode = state.metabrain_mode
            state.metabrain_mode = random.choice(["AGGRESSIVE", "BALANCED", "DEFENSIVE"])
            state.metabrain_confidence = round(0.4 + random.uniform(0, 0.5), 2)
            if old_mode != state.metabrain_mode:
                state.metabrain_changes.append({
                    "bar": state.current_bar,
                    "from": old_mode,
                    "to": state.metabrain_mode,
                    "confidence": state.metabrain_confidence,
                    "time": state.current_time
                })
        
        # Update structure
        if random.random() < 0.1:
            state.current_structure = random.choice(["BULLISH", "BEARISH", "NEUTRAL"])
        
        return state
    
    def run_to_completion(self, run_id: str) -> Optional[ReplayState]:
        """
        Run replay to completion.
        
        Returns:
            Final ReplayState
        """
        state = self._active_replays.get(run_id)
        if not state:
            return None
        
        while state.status == ReplayStatus.RUNNING:
            self.step(run_id)
        
        return state
    
    def pause(self, run_id: str) -> bool:
        """Pause a replay"""
        state = self._active_replays.get(run_id)
        if state and state.status == ReplayStatus.RUNNING:
            state.status = ReplayStatus.PAUSED
            return True
        return False
    
    def resume(self, run_id: str) -> bool:
        """Resume a paused replay"""
        state = self._active_replays.get(run_id)
        if state and state.status == ReplayStatus.PAUSED:
            state.status = ReplayStatus.RUNNING
            return True
        return False
    
    def stop(self, run_id: str) -> bool:
        """Stop a replay"""
        state = self._active_replays.get(run_id)
        if state:
            state.status = ReplayStatus.COMPLETED
            return True
        return False
    
    def get_state(self, run_id: str) -> Optional[ReplayState]:
        """Get current replay state"""
        return self._active_replays.get(run_id)
    
    def list_replays(self, limit: int = 20) -> List[Dict]:
        """List active replays"""
        replays = list(self._active_replays.values())
        replays = sorted(replays, key=lambda r: r.current_time, reverse=True)[:limit]
        
        return [
            {
                "runId": r.run_id,
                "symbol": r.symbol,
                "timeframe": r.timeframe,
                "progress": round(r.progress, 4),
                "status": r.status.value,
                "currentBar": r.current_bar,
                "totalBars": r.total_bars
            }
            for r in replays
        ]
    
    def get_events(self, run_id: str) -> Dict[str, Any]:
        """Get all events from a replay"""
        state = self._active_replays.get(run_id)
        if not state:
            return {"events": [], "scenarioChanges": [], "metabrainChanges": []}
        
        return {
            "events": state.events,
            "scenarioChanges": state.scenario_changes,
            "metabrainChanges": state.metabrain_changes
        }


def replay_state_to_dict(state: ReplayState) -> Dict[str, Any]:
    """Convert ReplayState to JSON-serializable dict"""
    return {
        "runId": state.run_id,
        "symbol": state.symbol,
        "timeframe": state.timeframe,
        "currentBar": state.current_bar,
        "totalBars": state.total_bars,
        "currentTime": state.current_time,
        "currentPrice": state.current_price,
        "currentRegime": state.current_regime,
        "currentScenario": state.current_scenario,
        "currentStructure": state.current_structure,
        "metabrainMode": state.metabrain_mode,
        "metabrainConfidence": state.metabrain_confidence,
        "status": state.status.value,
        "progress": round(state.progress, 4),
        "eventsCount": len(state.events),
        "scenarioChangesCount": len(state.scenario_changes),
        "metabrainChangesCount": len(state.metabrain_changes)
    }
