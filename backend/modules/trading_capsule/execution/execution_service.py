"""
Execution Service (T3)
======================

Core execution decision layer service.

Handles:
- Signal source routing
- Decision normalization
- Intent building
- Preview mode
- OMS handoff
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import asyncio

from .execution_types import (
    ExecutionDecision,
    ExecutionContext,
    ExecutionAction,
    SignalSource,
    Horizon,
    OrderIntent,
    ExecutionPreview,
    ExecutionResult
)
from ..trading_types import ExecutionMode, MarketMode
from ..broker import broker_registry
from ..orders import order_service
from ..orders.order_types import OrderSide, OrderType


class ExecutionService:
    """
    Execution Decision Layer Service.
    
    Converts signals/decisions into executable order intents.
    """
    
    def __init__(self):
        # Decision history
        self._decisions: Dict[str, ExecutionDecision] = {}
        self._intents: Dict[str, OrderIntent] = {}
        
        # Execution results
        self._results: List[ExecutionResult] = []
        
        # Default sizing
        self._default_size_pct = 0.02  # 2% of equity per trade
        self._min_confidence = 0.5     # Minimum confidence to execute
        
        # Price estimates (would come from market data in production)
        self._price_estimates: Dict[str, float] = {
            "BTC": 65000.0,
            "ETH": 3500.0,
            "SOL": 150.0,
            "BNB": 450.0
        }
        
        print("[ExecutionService] Initialized")
    
    # ===========================================
    # Signal Source Adapters
    # ===========================================
    
    def normalize_ta_signal(self, ta_payload: Dict[str, Any]) -> ExecutionDecision:
        """
        Normalize TA module signal to ExecutionDecision.
        
        Expected TA payload:
        {
            "asset": "BTC",
            "bias": "BULLISH" | "BEARISH" | "NEUTRAL",
            "confidence": 0.75,
            "patterns": [...],
            "entry_price": 65000,
            "stop_loss": 64000,
            "take_profit": 68000
        }
        """
        asset = ta_payload.get("asset", "BTC")
        bias = ta_payload.get("bias", "NEUTRAL").upper()
        confidence = ta_payload.get("confidence", 0.0)
        
        # Map TA bias to action
        if bias == "BULLISH":
            action = ExecutionAction.ENTER_LONG
        elif bias == "BEARISH":
            action = ExecutionAction.EXIT_LONG  # In SPOT mode, bearish = exit
        else:
            action = ExecutionAction.HOLD
        
        decision = ExecutionDecision(
            source_mode=SignalSource.TA_ONLY,
            source_ref=f"ta_signal_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            asset=asset,
            symbol=f"{asset}USDT",
            market_type="SPOT",
            action=action,
            confidence=confidence,
            horizon=Horizon.INTRADAY,
            suggested_price=ta_payload.get("entry_price"),
            stop_loss=ta_payload.get("stop_loss"),
            take_profit=ta_payload.get("take_profit"),
            reason=f"TA Signal: {bias} with {confidence:.0%} confidence",
            metadata={"patterns": ta_payload.get("patterns", [])}
        )
        
        self._decisions[decision.decision_id] = decision
        return decision
    
    def normalize_manual_signal(self, payload: Dict[str, Any]) -> ExecutionDecision:
        """
        Normalize manual signal payload to ExecutionDecision.
        
        Expected payload:
        {
            "asset": "BTC",
            "action": "ENTER_LONG",
            "confidence": 0.8,
            "size_pct": 0.05,
            "reason": "Manual entry"
        }
        """
        asset = payload.get("asset", "BTC")
        action_str = payload.get("action", "HOLD").upper()
        
        try:
            action = ExecutionAction(action_str)
        except ValueError:
            action = ExecutionAction.HOLD
        
        decision = ExecutionDecision(
            source_mode=SignalSource.MANUAL_SIGNAL_SOURCE,
            source_ref=f"manual_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            asset=asset,
            symbol=f"{asset}USDT",
            market_type=payload.get("market_type", "SPOT"),
            action=action,
            confidence=payload.get("confidence", 1.0),
            horizon=Horizon(payload.get("horizon", "1D")),
            suggested_size_pct=payload.get("size_pct"),
            suggested_price=payload.get("price"),
            stop_loss=payload.get("stop_loss"),
            take_profit=payload.get("take_profit"),
            reason=payload.get("reason", "Manual signal")
        )
        
        self._decisions[decision.decision_id] = decision
        return decision
    
    def normalize_mbrain_signal(self, payload: Dict[str, Any]) -> ExecutionDecision:
        """
        Normalize M-Brain routed signal to ExecutionDecision.
        
        Expected payload from future M-Brain:
        {
            "asset": "BTC",
            "ensemble_action": "ENTER_LONG",
            "ensemble_confidence": 0.85,
            "module_votes": {...}
        }
        """
        asset = payload.get("asset", "BTC")
        action_str = payload.get("ensemble_action", "HOLD").upper()
        
        try:
            action = ExecutionAction(action_str)
        except ValueError:
            action = ExecutionAction.HOLD
        
        decision = ExecutionDecision(
            source_mode=SignalSource.MBRAIN_ROUTED,
            source_ref=f"mbrain_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            asset=asset,
            symbol=f"{asset}USDT",
            market_type=payload.get("market_type", "SPOT"),
            action=action,
            confidence=payload.get("ensemble_confidence", 0.0),
            horizon=Horizon.INTRADAY,
            reason="M-Brain ensemble decision",
            metadata={"module_votes": payload.get("module_votes", {})}
        )
        
        self._decisions[decision.decision_id] = decision
        return decision
    
    # ===========================================
    # Context Building
    # ===========================================
    
    async def build_context(self, connection_id: str) -> ExecutionContext:
        """Build execution context from current state"""
        
        context = ExecutionContext(connection_id=connection_id)
        
        # Get connection
        connection = broker_registry.get_connection(connection_id)
        if connection:
            context.selected_mode = connection.selected_mode.value
        
        # Get account state
        try:
            adapter = await broker_registry.get_or_create_adapter(connection_id)
            if adapter:
                if not adapter._connected:
                    await adapter.connect()
                
                account = await adapter.fetch_account_state()
                context.account_equity_usd = account.equity_usd
                
                # Calculate available cash
                for balance in account.balances:
                    if balance.asset == "USDT":
                        context.available_cash_usd = balance.free
                        break
        except Exception as e:
            print(f"[ExecutionService] Failed to get account state: {e}")
        
        # Get current position from OMS
        open_trades = order_service.get_open_trades()
        for trade in open_trades:
            if trade.connection_id == connection_id:
                context.has_position = True
                context.current_position_side = trade.side
                context.current_position_size = trade.quantity
                context.current_position_entry = trade.entry_price
                break
        
        # Get capsule state
        from ..routes.trading_routes import _capsule_state
        context.active_execution_mode = SignalSource(_capsule_state.execution_mode.value)
        context.paused = _capsule_state.paused
        context.kill_switch_active = _capsule_state.kill_switch_active
        
        return context
    
    # ===========================================
    # Intent Building
    # ===========================================
    
    def build_intent(
        self,
        decision: ExecutionDecision,
        context: ExecutionContext
    ) -> Optional[OrderIntent]:
        """
        Build order intent from decision and context.
        
        Converts decision action to concrete order parameters.
        """
        # HOLD means no order
        if decision.action == ExecutionAction.HOLD:
            return None
        
        # Get price estimate
        price = self._price_estimates.get(decision.asset, 1000.0)
        
        # Calculate quantity
        size_pct = decision.suggested_size_pct or self._default_size_pct
        notional_usd = context.account_equity_usd * size_pct
        
        if notional_usd < 10:  # Minimum notional
            notional_usd = min(100, context.available_cash_usd * 0.5)
        
        quantity = notional_usd / price if price > 0 else 0
        
        # Determine order side and reduce_only
        side = "BUY"
        reduce_only = False
        
        if decision.action in [ExecutionAction.ENTER_LONG, ExecutionAction.ADD_TO_LONG]:
            side = "BUY"
            reduce_only = False
            
        elif decision.action == ExecutionAction.EXIT_LONG:
            side = "SELL"
            reduce_only = True
            # Use position size if available
            if context.has_position and context.current_position_side == "LONG":
                quantity = context.current_position_size
            
        elif decision.action in [ExecutionAction.ENTER_SHORT, ExecutionAction.ADD_TO_SHORT]:
            # Only in FUTURES mode
            if context.selected_mode != "FUTURES":
                return None
            side = "SELL"
            reduce_only = False
            
        elif decision.action == ExecutionAction.EXIT_SHORT:
            if context.selected_mode != "FUTURES":
                return None
            side = "BUY"
            reduce_only = True
            if context.has_position and context.current_position_side == "SHORT":
                quantity = context.current_position_size
        
        intent = OrderIntent(
            connection_id=context.connection_id,
            asset=decision.asset,
            symbol=decision.symbol,
            side=side,
            order_type="MARKET",
            quantity=quantity,
            notional_usd=quantity * price,
            price=decision.suggested_price,
            reduce_only=reduce_only,
            client_tag=f"exec_{decision.source_mode.value}",
            source_decision_id=decision.decision_id
        )
        
        self._intents[intent.intent_id] = intent
        return intent
    
    # ===========================================
    # Execution Policies
    # ===========================================
    
    def check_execution_policy(
        self,
        decision: ExecutionDecision,
        context: ExecutionContext
    ) -> tuple[bool, List[str], List[str]]:
        """
        Check execution policies.
        
        Returns: (can_execute, block_reasons, warnings)
        """
        block_reasons = []
        warnings = []
        
        # Global halt checks
        if context.kill_switch_active:
            block_reasons.append("KILL_SWITCH_ACTIVE")
            return False, block_reasons, warnings
        
        if context.paused:
            block_reasons.append("TRADING_PAUSED")
            return False, block_reasons, warnings
        
        # Mode checks
        if decision.source_mode != context.active_execution_mode:
            block_reasons.append(f"SOURCE_MODE_MISMATCH: expected {context.active_execution_mode.value}")
            return False, block_reasons, warnings
        
        # HOLD = no execution
        if decision.action == ExecutionAction.HOLD:
            block_reasons.append("ACTION_IS_HOLD")
            return False, block_reasons, warnings
        
        # Confidence check
        if decision.confidence < self._min_confidence:
            warnings.append(f"LOW_CONFIDENCE: {decision.confidence:.0%} < {self._min_confidence:.0%}")
        
        # SPOT mode constraints
        if context.selected_mode == "SPOT":
            if decision.action in [ExecutionAction.ENTER_SHORT, ExecutionAction.ADD_TO_SHORT, ExecutionAction.EXIT_SHORT]:
                block_reasons.append("SHORT_NOT_ALLOWED_IN_SPOT_MODE")
                return False, block_reasons, warnings
        
        # Check if we have funds for entry
        if decision.action in [ExecutionAction.ENTER_LONG, ExecutionAction.ADD_TO_LONG]:
            if context.available_cash_usd < 10:
                block_reasons.append("INSUFFICIENT_FUNDS")
                return False, block_reasons, warnings
        
        # Check if we have position to exit
        if decision.action == ExecutionAction.EXIT_LONG:
            if not context.has_position or context.current_position_side != "LONG":
                block_reasons.append("NO_LONG_POSITION_TO_EXIT")
                return False, block_reasons, warnings
        
        if decision.action == ExecutionAction.EXIT_SHORT:
            if not context.has_position or context.current_position_side != "SHORT":
                block_reasons.append("NO_SHORT_POSITION_TO_EXIT")
                return False, block_reasons, warnings
        
        return True, block_reasons, warnings
    
    # ===========================================
    # Preview
    # ===========================================
    
    async def preview(
        self,
        decision: ExecutionDecision,
        connection_id: str
    ) -> ExecutionPreview:
        """
        Preview execution without actually executing.
        
        Shows what would happen if we executed this decision.
        """
        # Build context
        context = await self.build_context(connection_id)
        
        # Check policies
        can_execute, block_reasons, warnings = self.check_execution_policy(decision, context)
        
        # Build intent (even if blocked, for preview)
        intent = self.build_intent(decision, context)
        
        preview = ExecutionPreview(
            decision=decision.to_dict(),
            context=context.to_dict(),
            intent=intent.to_dict() if intent else None,
            would_execute=can_execute and intent is not None,
            blocked=not can_execute,
            block_reasons=block_reasons,
            warnings=warnings
        )
        
        if intent:
            preview.estimated_notional_usd = intent.notional_usd
            preview.estimated_commission_usd = intent.notional_usd * 0.001  # 0.1%
        
        return preview
    
    # ===========================================
    # Execute
    # ===========================================
    
    async def execute(
        self,
        decision: ExecutionDecision,
        connection_id: str,
        skip_risk_check: bool = False
    ) -> ExecutionResult:
        """
        Execute a decision.
        
        Full pipeline:
        1. Build context
        2. Check policies
        3. Check risk (T4)
        4. Build intent
        5. Submit to OMS
        """
        result = ExecutionResult(decision_id=decision.decision_id)
        
        try:
            # Build context
            context = await self.build_context(connection_id)
            
            # Check policies
            can_execute, block_reasons, warnings = self.check_execution_policy(decision, context)
            result.warnings = warnings
            
            if not can_execute:
                result.blocked = True
                result.block_reasons = block_reasons
                self._results.append(result)
                return result
            
            # Build intent
            intent = self.build_intent(decision, context)
            
            if not intent:
                result.blocked = True
                result.block_reasons = ["INTENT_BUILD_FAILED"]
                self._results.append(result)
                return result
            
            result.intent_id = intent.intent_id
            
            # Risk check (T4) - will be called here
            if not skip_risk_check:
                from ..risk import risk_service
                risk_verdict = await risk_service.evaluate(intent, context)
                
                if not risk_verdict.allowed:
                    result.blocked = True
                    result.block_reasons = risk_verdict.reason_codes
                    result.warnings.extend(risk_verdict.notes or [])
                    self._results.append(result)
                    return result
                
                # Apply risk adjustments
                if risk_verdict.adjusted_quantity:
                    intent.quantity = risk_verdict.adjusted_quantity
                    intent.notional_usd = risk_verdict.adjusted_notional_usd or intent.notional_usd
                
                result.warnings.extend(risk_verdict.notes or [])
            
            # Submit to OMS
            order = await order_service.place_order(
                connection_id=intent.connection_id,
                symbol=intent.symbol,
                side=OrderSide(intent.side),
                order_type=OrderType(intent.order_type),
                quantity=intent.quantity,
                price=intent.price,
                reduce_only=intent.reduce_only,
                client_tag=intent.client_tag,
                source_decision_id=intent.source_decision_id,
                source_intent_id=intent.intent_id
            )
            
            result.order_id = order.order_id
            result.order_status = order.status.value
            result.executed = order.status.value in ["FILLED", "NEW", "SUBMITTED", "PARTIALLY_FILLED"]
            result.success = result.executed
            
            if order.filled_quantity > 0:
                result.fill_price = order.avg_fill_price
                result.fill_quantity = order.filled_quantity
            
        except Exception as e:
            result.error = str(e)
            result.success = False
        
        self._results.append(result)
        return result
    
    # ===========================================
    # Queries
    # ===========================================
    
    def get_decision(self, decision_id: str) -> Optional[ExecutionDecision]:
        """Get decision by ID"""
        return self._decisions.get(decision_id)
    
    def get_decisions(self, limit: int = 50) -> List[ExecutionDecision]:
        """Get recent decisions"""
        decisions = list(self._decisions.values())
        decisions = sorted(decisions, key=lambda d: d.timestamp, reverse=True)
        return decisions[:limit]
    
    def get_intent(self, intent_id: str) -> Optional[OrderIntent]:
        """Get intent by ID"""
        return self._intents.get(intent_id)
    
    def get_results(self, limit: int = 50) -> List[ExecutionResult]:
        """Get recent execution results"""
        return self._results[-limit:]
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health"""
        return {
            "enabled": True,
            "version": "execution_t3",
            "status": "ok",
            "decisions_processed": len(self._decisions),
            "intents_built": len(self._intents),
            "executions_total": len(self._results),
            "executions_successful": sum(1 for r in self._results if r.success),
            "executions_blocked": sum(1 for r in self._results if r.blocked),
            "min_confidence": self._min_confidence,
            "default_size_pct": self._default_size_pct,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
execution_service = ExecutionService()
