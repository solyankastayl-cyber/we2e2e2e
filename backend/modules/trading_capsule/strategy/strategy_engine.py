"""
Strategy Engine (T6)
====================

Main Strategy Engine - unified interface for strategy management.

Combines:
- Registry (registration)
- State (enable/disable)
- Runtime (signal processing)
- Execution layer integration

Pipeline:
    Signal → Strategy Engine → Actions → Execution Layer
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from .strategy_types import (
    StrategyAction,
    StrategyContext,
    StrategyPlugin,
    SignalType,
    ActionType,
    StrategyStatus
)
from .strategy_registry import strategy_registry
from .strategy_state import strategy_state_manager
from .strategy_runtime import strategy_runtime


class StrategyEngine:
    """
    Main Strategy Engine.
    
    Unified interface for:
    - Registering strategies
    - Enabling/disabling strategies
    - Processing signals
    - Routing actions to Execution Layer
    """
    
    def __init__(self):
        self._registry = strategy_registry
        self._state_manager = strategy_state_manager
        self._runtime = strategy_runtime
        
        # Event publisher (lazy init)
        self._publisher = None
        
        print("[StrategyEngine] Initialized")
    
    def _get_publisher(self):
        """Get or create event publisher"""
        if self._publisher is None:
            try:
                from ..event_bus import create_publisher
                self._publisher = create_publisher("strategy_engine")
            except ImportError:
                pass
        return self._publisher
    
    # ===========================================
    # Strategy Registration
    # ===========================================
    
    def register_strategy(
        self,
        strategy: StrategyPlugin,
        auto_enable: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Register a strategy plugin.
        
        Args:
            strategy: Strategy plugin instance
            auto_enable: Enable immediately after registration
            metadata: Optional metadata
            
        Returns:
            True if successful
        """
        success = self._registry.register(strategy, metadata)
        
        if success:
            # Create initial state
            self._state_manager.get_or_create_state(strategy.strategy_id)
            
            # Auto-enable if requested
            if auto_enable:
                self.enable_strategy(strategy.strategy_id)
            
            # Publish event
            self._publish_event("strategy_registered", {
                "strategy_id": strategy.strategy_id,
                "name": strategy.name,
                "version": strategy.version,
                "auto_enabled": auto_enable
            })
        
        return success
    
    def unregister_strategy(self, strategy_id: str) -> bool:
        """
        Unregister a strategy.
        
        Args:
            strategy_id: Strategy to remove
            
        Returns:
            True if successful
        """
        # Disable first
        self._state_manager.disable(strategy_id)
        
        # Unregister
        success = self._registry.unregister(strategy_id)
        
        if success:
            self._publish_event("strategy_unregistered", {
                "strategy_id": strategy_id
            })
        
        return success
    
    # ===========================================
    # Strategy Control
    # ===========================================
    
    def enable_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Enable a strategy.
        
        Returns strategy state dict or None if not found.
        """
        if not self._registry.exists(strategy_id):
            return None
        
        state = self._state_manager.enable(strategy_id)
        
        self._publish_event("strategy_enabled", {
            "strategy_id": strategy_id
        })
        
        return state.to_dict()
    
    def disable_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Disable a strategy.
        
        Returns strategy state dict or None if not found.
        """
        state = self._state_manager.disable(strategy_id)
        
        if state:
            self._publish_event("strategy_disabled", {
                "strategy_id": strategy_id
            })
            return state.to_dict()
        
        return None
    
    def pause_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Pause a strategy temporarily.
        """
        state = self._state_manager.pause(strategy_id)
        
        if state:
            self._publish_event("strategy_paused", {
                "strategy_id": strategy_id
            })
            return state.to_dict()
        
        return None
    
    def resume_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Resume a paused strategy.
        """
        state = self._state_manager.resume(strategy_id)
        
        if state:
            self._publish_event("strategy_resumed", {
                "strategy_id": strategy_id
            })
            return state.to_dict()
        
        return None
    
    # ===========================================
    # Signal Processing
    # ===========================================
    
    async def process_ta_signal(
        self,
        signal_data: Dict[str, Any],
        connection_id: Optional[str] = None,
        auto_execute: bool = False
    ) -> Dict[str, Any]:
        """
        Process TA signal through strategies.
        
        Args:
            signal_data: TA signal payload
            connection_id: Connection for execution
            auto_execute: Automatically execute actions
            
        Returns:
            Processing result with actions
        """
        return await self._process_signal(
            SignalType.TA_SIGNAL,
            signal_data,
            connection_id,
            auto_execute
        )
    
    async def process_manual_signal(
        self,
        signal_data: Dict[str, Any],
        connection_id: Optional[str] = None,
        auto_execute: bool = False
    ) -> Dict[str, Any]:
        """
        Process manual signal through strategies.
        """
        return await self._process_signal(
            SignalType.MANUAL_SIGNAL,
            signal_data,
            connection_id,
            auto_execute
        )
    
    async def process_mbrain_signal(
        self,
        signal_data: Dict[str, Any],
        connection_id: Optional[str] = None,
        auto_execute: bool = False
    ) -> Dict[str, Any]:
        """
        Process M-Brain signal through strategies.
        """
        return await self._process_signal(
            SignalType.MBRAIN_SIGNAL,
            signal_data,
            connection_id,
            auto_execute
        )
    
    async def _process_signal(
        self,
        signal_type: SignalType,
        signal_data: Dict[str, Any],
        connection_id: Optional[str],
        auto_execute: bool
    ) -> Dict[str, Any]:
        """
        Internal signal processing.
        """
        result = {
            "signal_type": signal_type.value,
            "signal_data": signal_data,
            "actions": [],
            "executed": [],
            "errors": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Process through runtime
        actions = await self._runtime.process_signal(
            signal_type,
            signal_data,
            connection_id
        )
        
        result["actions"] = [a.to_dict() for a in actions]
        
        # Auto-execute if requested
        if auto_execute and actions and connection_id:
            for action in actions:
                try:
                    exec_result = await self._execute_action(action, connection_id)
                    result["executed"].append(exec_result)
                except Exception as e:
                    result["errors"].append({
                        "action_id": action.action_id,
                        "error": str(e)
                    })
        
        return result
    
    async def _execute_action(
        self,
        action: StrategyAction,
        connection_id: str
    ) -> Dict[str, Any]:
        """
        Execute strategy action through Execution Layer.
        """
        from ..execution import execution_service
        from ..execution.execution_types import ExecutionDecision, ExecutionAction, SignalSource
        
        # Map action to execution action
        exec_action_map = {
            ActionType.ENTER_LONG: ExecutionAction.ENTER_LONG,
            ActionType.EXIT_LONG: ExecutionAction.EXIT_LONG,
            ActionType.ENTER_SHORT: ExecutionAction.ENTER_SHORT,
            ActionType.EXIT_SHORT: ExecutionAction.EXIT_SHORT,
            ActionType.AVERAGE: ExecutionAction.ADD_TO_LONG,
            ActionType.HOLD: ExecutionAction.HOLD,
            ActionType.SCALE_IN: ExecutionAction.ADD_TO_LONG,
            ActionType.SCALE_OUT: ExecutionAction.EXIT_LONG,
            ActionType.FLIP: ExecutionAction.EXIT_LONG  # Simplified
        }
        
        exec_action = exec_action_map.get(action.action, ExecutionAction.HOLD)
        
        # Create execution decision
        decision = ExecutionDecision(
            source_mode=SignalSource.TA_ONLY,  # From strategy
            source_ref=f"strategy_{action.strategy_id}_{action.action_id}",
            asset=action.asset,
            symbol=f"{action.asset}USDT",
            action=exec_action,
            confidence=action.confidence,
            suggested_size_pct=action.size_pct,
            stop_loss=action.stop_loss,
            take_profit=action.take_profit,
            reason=action.reason,
            metadata={"strategy_id": action.strategy_id}
        )
        
        # Execute
        exec_result = await execution_service.execute(decision, connection_id)
        
        return exec_result.to_dict()
    
    # ===========================================
    # Queries
    # ===========================================
    
    def get_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Get strategy info"""
        strategy = self._registry.get(strategy_id)
        if not strategy:
            return None
        
        metadata = self._registry.get_metadata(strategy_id)
        state = self._state_manager.get_state(strategy_id)
        
        return {
            "strategy_id": strategy_id,
            "name": strategy.name,
            "description": strategy.description,
            "version": strategy.version,
            "metadata": metadata,
            "state": state.to_dict() if state else None
        }
    
    def list_strategies(self) -> List[Dict[str, Any]]:
        """List all registered strategies"""
        strategies = []
        
        for strategy_id in self._registry.get_ids():
            info = self.get_strategy(strategy_id)
            if info:
                strategies.append(info)
        
        return strategies
    
    def get_active_strategies(self) -> List[Dict[str, Any]]:
        """Get active strategies"""
        active_ids = self._state_manager.get_active_ids()
        return [
            self.get_strategy(sid)
            for sid in active_ids
            if self.get_strategy(sid)
        ]
    
    # ===========================================
    # Configuration
    # ===========================================
    
    def set_multi_strategy_mode(self, enabled: bool) -> None:
        """Enable/disable multi-strategy mode"""
        self._runtime.set_multi_strategy_mode(enabled)
    
    def is_multi_strategy(self) -> bool:
        """Check if multi-strategy mode is enabled"""
        return self._runtime.is_multi_strategy()
    
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
    # Health
    # ===========================================
    
    def get_health(self) -> Dict[str, Any]:
        """Get engine health"""
        return {
            "enabled": True,
            "version": "strategy_engine_t6",
            "status": "ok",
            "multi_strategy_mode": self._runtime.is_multi_strategy(),
            "registry": self._registry.get_summary(),
            "state": self._state_manager.get_summary(),
            "runtime": self._runtime.get_stats(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global singleton
strategy_engine = StrategyEngine()
