"""
Strategy Runtime (T6)
=====================

Core runtime for strategy execution.

Handles:
- Signal routing to strategies
- Context building
- Action collection
- Event publishing
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import asyncio

from .strategy_types import (
    StrategyAction,
    StrategyContext,
    StrategyPlugin,
    SignalType,
    ActionType
)
from .strategy_registry import strategy_registry
from .strategy_state import strategy_state_manager, StrategyStatus


class StrategyRuntime:
    """
    Strategy Runtime.
    
    Routes signals to active strategies and collects actions.
    """
    
    def __init__(self):
        self._registry = strategy_registry
        self._state_manager = strategy_state_manager
        
        # Event publisher (lazy init)
        self._publisher = None
        
        # Processing stats
        self._signals_processed = 0
        self._actions_generated = 0
        
        # Multi-strategy mode
        self._multi_strategy_mode = False  # Single strategy by default
        
        print("[StrategyRuntime] Initialized")
    
    def _get_publisher(self):
        """Get or create event publisher"""
        if self._publisher is None:
            try:
                from ..event_bus import create_publisher
                self._publisher = create_publisher("strategy_runtime")
            except ImportError:
                # Event bus may not be available
                pass
        return self._publisher
    
    # ===========================================
    # Mode Control
    # ===========================================
    
    def set_multi_strategy_mode(self, enabled: bool) -> None:
        """Enable/disable multi-strategy mode"""
        self._multi_strategy_mode = enabled
        print(f"[StrategyRuntime] Multi-strategy mode: {enabled}")
    
    def is_multi_strategy(self) -> bool:
        """Check if multi-strategy mode is enabled"""
        return self._multi_strategy_mode
    
    # ===========================================
    # Context Building
    # ===========================================
    
    async def build_context(
        self,
        signal_type: SignalType,
        signal_data: Dict[str, Any],
        connection_id: Optional[str] = None
    ) -> StrategyContext:
        """
        Build context for strategy evaluation.
        
        Gathers data from various sources.
        """
        context = StrategyContext(
            signal_type=signal_type,
            signal_data=signal_data
        )
        
        # Extract asset from signal
        context.asset = signal_data.get("asset", "BTC")
        context.current_price = signal_data.get("price", 0.0)
        
        # Check if position info is passed directly (from simulation)
        if "has_position" in signal_data:
            context.has_position = signal_data.get("has_position", False)
            context.position_side = signal_data.get("position_side")
            context.position_size = signal_data.get("position_size", 0)
        
        # Get account state if connection provided
        if connection_id:
            try:
                from ..broker import broker_registry
                
                adapter = await broker_registry.get_or_create_adapter(connection_id)
                if adapter:
                    if not adapter._connected:
                        await adapter.connect()
                    
                    account = await adapter.fetch_account_state()
                    context.account_equity_usd = account.equity_usd
                    
                    for balance in account.balances:
                        if balance.asset == "USDT":
                            context.available_cash_usd = balance.free
                            break
            except Exception as e:
                print(f"[StrategyRuntime] Error building account context: {e}")
        
        # Get position from OMS
        try:
            from ..orders import order_service
            
            open_trades = order_service.get_open_trades()
            for trade in open_trades:
                if trade.asset == context.asset:
                    context.has_position = True
                    context.position_side = trade.side
                    context.position_size = trade.quantity
                    context.position_entry = trade.entry_price
                    context.position_pnl = trade.unrealized_pnl
                    break
        except Exception as e:
            print(f"[StrategyRuntime] Error building position context: {e}")
        
        # Get risk state
        try:
            from ..risk import risk_service
            
            if connection_id:
                context.daily_pnl = risk_service.get_daily_pnl(connection_id)
        except Exception as e:
            print(f"[StrategyRuntime] Error building risk context: {e}")
        
        # Get capsule state
        try:
            from ..routes.trading_routes import _capsule_state
            context.paused = _capsule_state.paused
            context.kill_switch_active = _capsule_state.kill_switch_active
        except Exception:
            pass
        
        return context
    
    # ===========================================
    # Signal Processing
    # ===========================================
    
    async def process_signal(
        self,
        signal_type: SignalType,
        signal_data: Dict[str, Any],
        connection_id: Optional[str] = None
    ) -> List[StrategyAction]:
        """
        Process a signal through active strategies.
        
        Args:
            signal_type: Type of signal
            signal_data: Signal payload
            connection_id: Optional connection for context
            
        Returns:
            List of actions from strategies
        """
        self._signals_processed += 1
        actions: List[StrategyAction] = []
        
        # Get active strategies
        active_ids = self._state_manager.get_active_ids()
        
        if not active_ids:
            return actions
        
        # Build context
        context = await self.build_context(signal_type, signal_data, connection_id)
        
        # Don't process if system is halted
        if context.kill_switch_active:
            return actions
        
        # Process through strategies
        strategies_to_process = active_ids
        if not self._multi_strategy_mode:
            # Single strategy mode - use first active
            # BUT: route signals to appropriate strategy by type
            if signal_type == SignalType.MANUAL_SIGNAL:
                # Manual signals go to MANUAL_SIGNAL_EXECUTOR if active
                if "MANUAL_SIGNAL_EXECUTOR" in active_ids:
                    strategies_to_process = ["MANUAL_SIGNAL_EXECUTOR"]
                else:
                    strategies_to_process = active_ids[:1]
            elif signal_type == SignalType.MBRAIN_SIGNAL:
                # M-Brain signals go to MBRAIN_SIGNAL_ROUTER if active
                if "MBRAIN_SIGNAL_ROUTER" in active_ids:
                    strategies_to_process = ["MBRAIN_SIGNAL_ROUTER"]
                else:
                    strategies_to_process = active_ids[:1]
            else:
                # Default: use first active (usually TA_SIGNAL_FOLLOWER)
                strategies_to_process = active_ids[:1]
        
        for strategy_id in strategies_to_process:
            strategy = self._registry.get(strategy_id)
            if not strategy:
                continue
            
            try:
                # Notify signal
                strategy.on_signal(signal_type, signal_data)
                self._state_manager.record_signal(strategy_id)
                
                # Evaluate
                action = strategy.evaluate(context)
                
                if action and action.action != ActionType.HOLD:
                    actions.append(action)
                    self._state_manager.record_action(strategy_id)
                    self._actions_generated += 1
                    
                    # Publish event
                    self._publish_action_event(strategy_id, action)
                    
            except Exception as e:
                self._state_manager.record_error(strategy_id, str(e))
                self._publish_error_event(strategy_id, str(e))
                print(f"[StrategyRuntime] Strategy error {strategy_id}: {e}")
        
        return actions
    
    async def process_market_update(
        self,
        market_data: Dict[str, Any]
    ) -> None:
        """
        Process market data update through active strategies.
        
        For real-time data processing.
        """
        active_ids = self._state_manager.get_active_ids()
        
        for strategy_id in active_ids:
            strategy = self._registry.get(strategy_id)
            if strategy:
                try:
                    strategy.on_market_update(market_data)
                except Exception as e:
                    self._state_manager.record_error(strategy_id, str(e))
    
    async def process_position_update(
        self,
        position_data: Dict[str, Any]
    ) -> None:
        """
        Process position update through active strategies.
        """
        active_ids = self._state_manager.get_active_ids()
        
        for strategy_id in active_ids:
            strategy = self._registry.get(strategy_id)
            if strategy:
                try:
                    strategy.on_position_update(position_data)
                except Exception as e:
                    self._state_manager.record_error(strategy_id, str(e))
    
    # ===========================================
    # Events
    # ===========================================
    
    def _publish_action_event(self, strategy_id: str, action: StrategyAction) -> None:
        """Publish strategy action event"""
        publisher = self._get_publisher()
        if publisher:
            try:
                publisher.publish(
                    "strategy_action_generated",
                    {
                        "strategy_id": strategy_id,
                        "action": action.to_dict()
                    }
                )
            except Exception:
                pass
    
    def _publish_error_event(self, strategy_id: str, error: str) -> None:
        """Publish strategy error event"""
        publisher = self._get_publisher()
        if publisher:
            try:
                publisher.publish(
                    "strategy_error",
                    {
                        "strategy_id": strategy_id,
                        "error": error,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                )
            except Exception:
                pass
    
    # ===========================================
    # Stats
    # ===========================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get runtime statistics"""
        return {
            "signals_processed": self._signals_processed,
            "actions_generated": self._actions_generated,
            "multi_strategy_mode": self._multi_strategy_mode,
            "active_strategies": len(self._state_manager.get_active_ids()),
            "registered_strategies": self._registry.count()
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Get runtime health"""
        return {
            "enabled": True,
            "version": "strategy_runtime_t6",
            "status": "ok",
            "stats": self.get_stats(),
            "state_summary": self._state_manager.get_summary(),
            "registry_summary": self._registry.get_summary(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global singleton
strategy_runtime = StrategyRuntime()
