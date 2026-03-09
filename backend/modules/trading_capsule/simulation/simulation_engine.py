"""
Simulation Engine (S1)
======================

Main Trading Simulation Engine.

Combines:
- Run Manager (S1.1)
- State Manager (S1.1)
- Determinism Guard (S1.1)
- Market Replay (S1.2)
- Simulated Broker (S1.3)

Pipeline:
    Market Replay
    ↓
    Strategy Runtime (T6)
    ↓
    Execution Layer (T3)
    ↓
    Risk Layer (T4)
    ↓
    OMS (T2)
    ↓
    Simulated Broker
    ↓
    State Update
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from .simulation_types import (
    SimulationRun,
    SimulationState,
    SimulationStatus,
    SimulationFingerprint,
    CapitalProfile,
    MarketType,
    Timeframe,
    ReplayMode,
    ReplayStatus,
    MarketTickEvent,
    get_capital_for_profile
)

from .simulation_run_service import simulation_run_service
from .simulation_state_service import simulation_state_service
from .simulation_determinism_service import simulation_determinism_service

from .replay import (
    market_dataset_service,
    replay_cursor_service,
    replay_driver_service
)

from .broker import simulated_broker_service
from .metrics import trade_normalizer_service


class SimulationEngine:
    """
    Main Trading Simulation Engine.
    
    Unified interface for all simulation operations.
    """
    
    def __init__(self):
        self._run_service = simulation_run_service
        self._state_service = simulation_state_service
        self._determinism_service = simulation_determinism_service
        
        # Set up tick callback for strategy integration
        replay_driver_service.set_tick_callback(self._on_market_tick)
        
        print("[SimulationEngine] Initialized")
    
    # ===========================================
    # Run Management
    # ===========================================
    
    async def create_simulation(
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
        strategy_config: Optional[Dict[str, Any]] = None,
        risk_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new simulation.
        
        Returns created run with dataset and fingerprint.
        """
        # Create mock dataset if not exists
        # In production, would load from data source
        dataset = market_dataset_service.create_mock_dataset(
            asset=asset,
            timeframe=timeframe,
            days=365
        )
        
        # Create run
        run = self._run_service.create_run(
            strategy_id=strategy_id,
            asset=asset,
            start_date=start_date,
            end_date=end_date,
            capital_profile=capital_profile,
            initial_capital_usd=initial_capital_usd,
            market_type=market_type,
            timeframe=timeframe,
            strategy_version=strategy_version,
            risk_profile_id=risk_profile_id,
            dataset_id=dataset.dataset_id
        )
        
        # Update run with dataset checksum
        run.dataset_checksum = dataset.checksum
        
        # Create state
        capital = initial_capital_usd or get_capital_for_profile(capital_profile)
        self._state_service.create_state(run.run_id, capital)
        
        # Create simulated broker
        simulated_broker_service.create_broker(run.run_id, capital)
        
        # Build fingerprint
        fingerprint = self._determinism_service.build_fingerprint(
            run,
            strategy_config=strategy_config or {},
            risk_config=risk_config or {}
        )
        
        # Create replay
        replay_driver_service.create_replay(
            run.run_id,
            dataset.dataset_id,
            ReplayMode.AUTO
        )
        
        return {
            "run": run.to_dict(),
            "dataset": dataset.to_dict(),
            "fingerprint": fingerprint.to_dict()
        }
    
    async def start_simulation(
        self,
        run_id: str,
        strategy_config: Optional[Dict[str, Any]] = None,
        risk_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Start a simulation run.
        
        Freezes config and begins replay.
        """
        run = self._run_service.get_run(run_id)
        if not run:
            return {"success": False, "error": "Run not found"}
        
        if run.status != SimulationStatus.CREATED:
            return {"success": False, "error": f"Cannot start run in status: {run.status.value}"}
        
        # Freeze config
        self._determinism_service.freeze_config(
            run_id,
            strategy_config=strategy_config or {},
            risk_config=risk_config or {}
        )
        
        # Start run
        self._run_service.start_run(run_id)
        
        return {
            "success": True,
            "run_id": run_id,
            "status": "RUNNING"
        }
    
    async def run_simulation(
        self,
        run_id: str,
        strategy_config: Optional[Dict[str, Any]] = None,
        risk_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run complete simulation (start + replay).
        """
        # Start if needed
        run = self._run_service.get_run(run_id)
        if not run:
            return {"success": False, "error": "Run not found"}
        
        if run.status == SimulationStatus.CREATED:
            await self.start_simulation(run_id, strategy_config, risk_config)
        
        # Run replay
        result = await replay_driver_service.run_full_replay(run_id)
        
        if result.get("success"):
            # Get final state
            state = self._state_service.get_state(run_id)
            
            # Normalize trades (S1.4A)
            trades = trade_normalizer_service.normalize_from_broker(run_id, close_open_positions=True)
            trade_stats = trade_normalizer_service.get_trade_stats(run_id)
            
            # Complete run with accurate trade count
            if state:
                self._run_service.complete_run(
                    run_id,
                    final_equity_usd=state.equity_usd,
                    total_trades=len(trades)
                )
            
            run = self._run_service.get_run(run_id)
            
            return {
                "success": True,
                "run": run.to_dict() if run else None,
                "state": state.to_dict() if state else None,
                "total_steps": result.get("total_steps", 0),
                "trade_stats": trade_stats.to_dict()
            }
        
        return result
    
    async def step_simulation(self, run_id: str) -> Dict[str, Any]:
        """Execute single step"""
        return await replay_driver_service.step_replay(run_id)
    
    async def pause_simulation(self, run_id: str) -> Dict[str, Any]:
        """Pause simulation"""
        run = self._run_service.pause_run(run_id)
        await replay_driver_service.pause_replay(run_id)
        
        return {
            "success": run is not None,
            "status": run.status.value if run else None
        }
    
    async def resume_simulation(self, run_id: str) -> Dict[str, Any]:
        """Resume simulation"""
        run = self._run_service.resume_run(run_id)
        await replay_driver_service.start_replay(run_id)
        
        return {
            "success": run is not None,
            "status": run.status.value if run else None
        }
    
    async def stop_simulation(self, run_id: str) -> Dict[str, Any]:
        """Stop simulation"""
        state = self._state_service.get_state(run_id)
        
        if state:
            self._run_service.complete_run(
                run_id,
                final_equity_usd=state.equity_usd,
                total_trades=0
            )
        
        await replay_driver_service.stop_replay(run_id)
        
        run = self._run_service.get_run(run_id)
        return {
            "success": True,
            "run": run.to_dict() if run else None,
            "state": state.to_dict() if state else None
        }
    
    # ===========================================
    # Query Methods
    # ===========================================
    
    def get_simulation(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get simulation details"""
        run = self._run_service.get_run(run_id)
        if not run:
            return None
        
        state = self._state_service.get_state(run_id)
        fingerprint = self._determinism_service.get_fingerprint(run_id)
        replay_state = replay_driver_service.get_replay_state(run_id)
        
        return {
            "run": run.to_dict(),
            "state": state.to_dict() if state else None,
            "fingerprint": fingerprint.to_dict() if fingerprint else None,
            "replay": replay_state.to_dict() if replay_state else None
        }
    
    def list_simulations(
        self,
        status: Optional[SimulationStatus] = None,
        strategy_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List simulations"""
        runs = self._run_service.list_runs(
            status=status,
            strategy_id=strategy_id,
            limit=limit
        )
        
        return [r.to_dict() for r in runs]
    
    def get_state(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get simulation state"""
        state = self._state_service.get_state(run_id)
        return state.to_dict() if state else None
    
    def get_positions(self, run_id: str) -> List[Dict[str, Any]]:
        """Get simulation positions"""
        positions = self._state_service.get_all_positions(run_id)
        return [p.to_dict() for p in positions]
    
    def get_equity_history(self, run_id: str) -> List[Dict[str, Any]]:
        """Get equity curve"""
        return self._state_service.get_equity_history(run_id)
    
    def get_fingerprint(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get simulation fingerprint"""
        fp = self._determinism_service.get_fingerprint(run_id)
        return fp.to_dict() if fp else None
    
    def get_fills(self, run_id: str) -> List[Dict[str, Any]]:
        """Get simulation fills from broker"""
        broker = simulated_broker_service.get_broker(run_id)
        if not broker:
            return []
        return [f.to_dict() for f in broker.get_fills()]
    
    def get_orders(self, run_id: str) -> Dict[str, Any]:
        """Get simulation orders from broker"""
        broker = simulated_broker_service.get_broker(run_id)
        if not broker:
            return {"open": [], "closed": []}
        
        account = broker.get_account_state()
        return {
            "open": [o.to_dict() for o in account.open_orders.values()],
            "closed": [o.to_dict() for o in account.closed_orders]
        }
    
    # ===========================================
    # Market Tick Callback
    # ===========================================
    
    async def _on_market_tick(
        self,
        run_id: str,
        tick_event: MarketTickEvent
    ) -> None:
        """
        Handle market tick from replay.
        
        This is where Strategy Runtime integration happens.
        """
        state = self._state_service.get_state(run_id)
        if not state:
            return
        
        # Get broker
        broker = simulated_broker_service.get_broker(run_id)
        
        # Update step info
        self._state_service.update_step(
            run_id,
            tick_event.step_index,
            tick_event.timestamp
        )
        
        # Get current price
        if tick_event.candle:
            # Update broker with new price (processes pending orders)
            if broker:
                broker.update_price(tick_event.asset, tick_event.candle)
            
            current_price = tick_event.candle.close
            
            # Get state from broker
            if broker:
                cash = broker.get_cash()
                equity = broker.get_equity()
                realized_pnl = broker.get_realized_pnl()
                unrealized_pnl = broker.get_unrealized_pnl()
                
                # Sync broker positions to state service
                broker_positions = broker.get_all_positions()
                for pos in broker_positions:
                    if pos.size > 0:
                        self._state_service.set_position(
                            run_id,
                            pos.asset,
                            pos.side,
                            pos.size,
                            pos.entry_price
                        )
                        self._state_service.update_position_price(run_id, pos.asset, pos.current_price)
                
                # Update portfolio state
                self._state_service.update_portfolio(
                    run_id,
                    equity_usd=equity,
                    cash_usd=cash,
                    realized_pnl_usd=realized_pnl,
                    unrealized_pnl_usd=unrealized_pnl
                )
                
                # Update counts
                self._state_service.update_counts(
                    run_id,
                    open_positions=len([p for p in broker_positions if p.size > 0]),
                    open_orders=len(broker.get_open_orders())
                )
            else:
                # Fallback to state service positions
                positions = self._state_service.get_all_positions(run_id)
                total_unrealized = 0.0
                
                for pos in positions:
                    if pos.asset == tick_event.asset:
                        self._state_service.update_position_price(run_id, pos.asset, current_price)
                        updated_pos = self._state_service.get_position(run_id, pos.asset)
                        if updated_pos:
                            total_unrealized += updated_pos.unrealized_pnl
                
                equity = state.cash_usd + total_unrealized
                self._state_service.update_portfolio(
                    run_id,
                    equity_usd=equity,
                    unrealized_pnl_usd=total_unrealized
                )
            
            # Record equity point
            updated_state = self._state_service.get_state(run_id)
            if updated_state:
                self._state_service.record_equity(run_id, tick_event.timestamp, updated_state.equity_usd)
        
        # Strategy Runtime Integration
        await self._process_strategy_signals(run_id, tick_event)
    
    async def _process_strategy_signals(
        self,
        run_id: str,
        tick_event: MarketTickEvent
    ) -> None:
        """
        Process signals through Strategy Runtime (T6).
        
        This integrates T6 with the simulation engine.
        """
        if not tick_event.candle:
            return
        
        broker = simulated_broker_service.get_broker(run_id)
        if not broker:
            return
        
        try:
            from ..strategy import strategy_engine
            from ..strategy.strategy_types import SignalType
            
            # Determine bias from candle (simple momentum)
            candle = tick_event.candle
            price_change = (candle.close - candle.open) / candle.open if candle.open > 0 else 0
            
            # Simple rules:
            # - Bullish if close > open by more than 1%
            # - Bearish if close < open by more than 1%
            if price_change > 0.01:
                bias = "BULLISH"
                confidence = min(0.5 + abs(price_change) * 10, 0.95)  # Scale confidence
            elif price_change < -0.01:
                bias = "BEARISH"
                confidence = min(0.5 + abs(price_change) * 10, 0.95)
            else:
                bias = "NEUTRAL"
                confidence = 0.3
            
            # Build signal from candle
            signal_data = {
                "asset": tick_event.asset,
                "bias": bias,
                "confidence": confidence,
                "price": candle.close,
                "timestamp": tick_event.timestamp
            }
            
            # Get current position from broker to pass to strategy
            broker_position = broker.get_position(tick_event.asset)
            has_position = broker_position is not None and broker_position.size > 0
            
            # Process through strategy (without auto-execute since we use simulated broker)
            # We pass position info via signal_data since we don't have a connection_id
            signal_data["has_position"] = has_position
            signal_data["position_side"] = broker_position.side if has_position else None
            signal_data["position_size"] = broker_position.size if has_position else 0
            
            result = await strategy_engine.process_ta_signal(signal_data, auto_execute=False)
            
            # Execute actions through simulated broker
            for action in result.get("actions", []):
                action_type = action.get("action")
                
                if action_type == "ENTER_LONG":
                    # Calculate position size
                    size_pct = action.get("size_pct") or 0.02  # Default 2%
                    cash = broker.get_cash()
                    size = (cash * size_pct) / tick_event.candle.close
                    
                    broker.submit_order(
                        asset=tick_event.asset,
                        side="BUY",
                        order_type="MARKET",
                        quantity=size,
                        timestamp=tick_event.timestamp
                    )
                
                elif action_type == "EXIT_LONG":
                    pos = broker.get_position(tick_event.asset)
                    if pos and pos.size > 0:
                        broker.submit_order(
                            asset=tick_event.asset,
                            side="SELL",
                            order_type="MARKET",
                            quantity=pos.size,
                            timestamp=tick_event.timestamp
                        )
                        
        except ImportError:
            # Strategy module not available
            pass
        except Exception as e:
            print(f"[SimulationEngine] Strategy processing error: {e}")
    
    # ===========================================
    # Health
    # ===========================================
    
    def get_health(self) -> Dict[str, Any]:
        """Get engine health"""
        return {
            "enabled": True,
            "version": "simulation_engine_s1.3",
            "status": "ok",
            "runs": self._run_service.count(),
            "active_runs": len(self._run_service.get_active_runs()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global singleton
simulation_engine = SimulationEngine()
