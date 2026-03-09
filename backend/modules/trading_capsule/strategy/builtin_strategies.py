"""
Built-in Strategy Plugins (T6)
==============================

Example strategy implementations.

Стратегии - это плагины которые:
- Получают сигналы
- Анализируют контекст
- Возвращают действия

Каждая стратегия реализует интерфейс StrategyPlugin.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .strategy_types import (
    BaseStrategy,
    StrategyAction,
    StrategyContext,
    SignalType,
    ActionType
)


class TASignalFollower(BaseStrategy):
    """
    TA Signal Follower Strategy.
    
    Простая стратегия которая следует за TA сигналами:
    - BULLISH → ENTER_LONG
    - BEARISH → EXIT_LONG
    - NEUTRAL → HOLD
    
    С фильтрами по confidence.
    """
    
    def __init__(
        self,
        min_confidence: float = 0.6,
        position_size_pct: float = 0.02  # 2% per trade
    ):
        super().__init__(
            strategy_id="TA_SIGNAL_FOLLOWER",
            name="TA Signal Follower",
            description="Follows TA signals with confidence filter",
            version="1.0.0"
        )
        
        self._min_confidence = min_confidence
        self._position_size_pct = position_size_pct
    
    def evaluate(self, context: StrategyContext) -> StrategyAction:
        """
        Evaluate TA signal and return action.
        """
        # Only process TA signals
        if context.signal_type != SignalType.TA_SIGNAL:
            return self._hold(context.asset, "Not a TA signal")
        
        signal = context.signal_data
        bias = signal.get("bias", "NEUTRAL").upper()
        confidence = signal.get("confidence", 0.0)
        
        # Confidence filter
        if confidence < self._min_confidence:
            return self._hold(
                context.asset,
                f"Low confidence: {confidence:.0%} < {self._min_confidence:.0%}"
            )
        
        # Map bias to action
        if bias == "BULLISH":
            # Check if we already have position
            if context.has_position and context.position_side == "LONG":
                return self._hold(context.asset, "Already in LONG position")
            
            return self._create_action(
                ActionType.ENTER_LONG,
                context.asset,
                confidence=confidence,
                reason=f"TA BULLISH signal ({confidence:.0%})",
                size_pct=self._position_size_pct,
                stop_loss=signal.get("stop_loss"),
                take_profit=signal.get("take_profit")
            )
            
        elif bias == "BEARISH":
            # Check if we have position to exit
            if not context.has_position:
                return self._hold(context.asset, "No position to exit")
            
            return self._create_action(
                ActionType.EXIT_LONG,
                context.asset,
                confidence=confidence,
                reason=f"TA BEARISH signal ({confidence:.0%})"
            )
        
        return self._hold(context.asset, "Neutral bias")


class ManualSignalExecutor(BaseStrategy):
    """
    Manual Signal Executor Strategy.
    
    Выполняет ручные сигналы напрямую:
    - Принимает action из сигнала
    - Проверяет валидность
    - Возвращает соответствующее действие
    """
    
    def __init__(self):
        super().__init__(
            strategy_id="MANUAL_SIGNAL_EXECUTOR",
            name="Manual Signal Executor",
            description="Executes manual signals directly",
            version="1.0.0"
        )
    
    def evaluate(self, context: StrategyContext) -> StrategyAction:
        """
        Evaluate manual signal and return action.
        """
        # Only process manual signals
        if context.signal_type != SignalType.MANUAL_SIGNAL:
            return self._hold(context.asset, "Not a manual signal")
        
        signal = context.signal_data
        action_str = signal.get("action", "HOLD").upper()
        
        # Map action
        action_map = {
            "ENTER_LONG": ActionType.ENTER_LONG,
            "EXIT_LONG": ActionType.EXIT_LONG,
            "ENTER_SHORT": ActionType.ENTER_SHORT,
            "EXIT_SHORT": ActionType.EXIT_SHORT,
            "AVERAGE": ActionType.AVERAGE,
            "HOLD": ActionType.HOLD
        }
        
        action = action_map.get(action_str, ActionType.HOLD)
        
        if action == ActionType.HOLD:
            return self._hold(context.asset, "Manual HOLD or invalid action")
        
        return self._create_action(
            action,
            context.asset,
            confidence=signal.get("confidence", 1.0),
            reason=signal.get("reason", "Manual signal"),
            size_pct=signal.get("size_pct"),
            stop_loss=signal.get("stop_loss"),
            take_profit=signal.get("take_profit")
        )


class MBrainSignalRouter(BaseStrategy):
    """
    M-Brain Signal Router Strategy.
    
    Роутит сигналы от M-Brain:
    - Анализирует ensemble решение
    - Проверяет consensus между модулями
    - Возвращает взвешенное действие
    """
    
    def __init__(
        self,
        min_confidence: float = 0.7,
        min_consensus: float = 0.5  # 50% модулей должны согласиться
    ):
        super().__init__(
            strategy_id="MBRAIN_SIGNAL_ROUTER",
            name="M-Brain Signal Router",
            description="Routes M-Brain ensemble signals",
            version="1.0.0"
        )
        
        self._min_confidence = min_confidence
        self._min_consensus = min_consensus
    
    def evaluate(self, context: StrategyContext) -> StrategyAction:
        """
        Evaluate M-Brain signal and return action.
        """
        # Only process M-Brain signals
        if context.signal_type != SignalType.MBRAIN_SIGNAL:
            return self._hold(context.asset, "Not an M-Brain signal")
        
        signal = context.signal_data
        action_str = signal.get("ensemble_action", "HOLD").upper()
        confidence = signal.get("ensemble_confidence", 0.0)
        
        # Confidence filter
        if confidence < self._min_confidence:
            return self._hold(
                context.asset,
                f"Low M-Brain confidence: {confidence:.0%}"
            )
        
        # Check module consensus
        module_votes = signal.get("module_votes", {})
        if module_votes:
            total_modules = len(module_votes)
            agreeing_modules = sum(
                1 for vote in module_votes.values()
                if vote.get("action") == action_str
            )
            consensus = agreeing_modules / total_modules if total_modules > 0 else 0
            
            if consensus < self._min_consensus:
                return self._hold(
                    context.asset,
                    f"Low consensus: {consensus:.0%} < {self._min_consensus:.0%}"
                )
        
        # Map action
        action_map = {
            "ENTER_LONG": ActionType.ENTER_LONG,
            "EXIT_LONG": ActionType.EXIT_LONG,
            "ENTER_SHORT": ActionType.ENTER_SHORT,
            "EXIT_SHORT": ActionType.EXIT_SHORT,
            "HOLD": ActionType.HOLD
        }
        
        action = action_map.get(action_str, ActionType.HOLD)
        
        if action == ActionType.HOLD:
            return self._hold(context.asset, "M-Brain HOLD decision")
        
        return self._create_action(
            action,
            context.asset,
            confidence=confidence,
            reason=f"M-Brain ensemble: {action_str} ({confidence:.0%})",
            metadata={"module_votes": module_votes}
        )


# ===========================================
# Factory Functions
# ===========================================

def create_ta_follower(
    min_confidence: float = 0.6,
    position_size_pct: float = 0.02
) -> TASignalFollower:
    """Create TA Signal Follower strategy"""
    return TASignalFollower(min_confidence, position_size_pct)


def create_manual_executor() -> ManualSignalExecutor:
    """Create Manual Signal Executor strategy"""
    return ManualSignalExecutor()


def create_mbrain_router(
    min_confidence: float = 0.7,
    min_consensus: float = 0.5
) -> MBrainSignalRouter:
    """Create M-Brain Signal Router strategy"""
    return MBrainSignalRouter(min_confidence, min_consensus)


def register_default_strategies():
    """
    Register default built-in strategies.
    
    Call this during system bootstrap.
    """
    from .strategy_engine import strategy_engine
    
    # Create strategies
    ta_follower = create_ta_follower()
    manual_executor = create_manual_executor()
    mbrain_router = create_mbrain_router()
    
    # Register
    strategy_engine.register_strategy(ta_follower, auto_enable=True)
    strategy_engine.register_strategy(manual_executor, auto_enable=True)
    strategy_engine.register_strategy(mbrain_router, auto_enable=False)
    
    print("[BuiltinStrategies] Registered default strategies")
    
    return [ta_follower, manual_executor, mbrain_router]
