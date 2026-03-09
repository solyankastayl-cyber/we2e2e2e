"""
Risk Service (T4)
=================

Core risk control layer service.

Handles:
- Pre-trade validation
- Exposure checks
- Position sizing
- Drawdown guards
- Averaging constraints
- Risk verdicts
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from .risk_types import (
    RiskProfile,
    RiskCheckContext,
    RiskVerdict,
    RiskSeverity,
    AveragingState
)
from ..execution.execution_types import OrderIntent


class RiskService:
    """
    Risk Control Layer Service.
    
    Evaluates order intents against risk rules.
    """
    
    def __init__(self):
        # Risk profile
        self._profile = RiskProfile()
        
        # Averaging states per asset
        self._averaging_states: Dict[str, AveragingState] = {}
        
        # Daily PnL tracking
        self._daily_pnl: Dict[str, float] = {}  # connection_id -> pnl
        self._daily_pnl_date: Optional[str] = None
        
        # Risk events history
        self._risk_events: List[Dict[str, Any]] = []
        
        print("[RiskService] Initialized")
    
    # ===========================================
    # Profile Management
    # ===========================================
    
    def get_profile(self) -> RiskProfile:
        """Get current risk profile"""
        return self._profile
    
    def update_profile(self, updates: Dict[str, Any]) -> RiskProfile:
        """Update risk profile"""
        for key, value in updates.items():
            if hasattr(self._profile, key):
                setattr(self._profile, key, value)
        return self._profile
    
    # ===========================================
    # Context Building
    # ===========================================
    
    async def build_context(
        self,
        connection_id: str,
        asset: str,
        market_type: str = "SPOT"
    ) -> RiskCheckContext:
        """Build risk check context"""
        from ..broker import broker_registry
        from ..orders import order_service
        
        context = RiskCheckContext(
            connection_id=connection_id,
            asset=asset,
            market_type=market_type
        )
        
        # Get account state
        try:
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
            print(f"[RiskService] Failed to get account state: {e}")
        
        # Get position counts
        open_trades = order_service.get_open_trades()
        context.open_positions_count = len(open_trades)
        
        # Calculate exposures
        for trade in open_trades:
            notional = trade.entry_price * trade.quantity
            context.current_portfolio_exposure_usd += notional
            
            if trade.asset == asset:
                context.current_asset_exposure_usd += notional
        
        # Get order counts
        active_orders = order_service.get_active_orders(connection_id)
        context.open_orders_count = len(active_orders)
        context.asset_orders_count = len([o for o in active_orders if o.asset == asset])
        
        # Get daily PnL
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._daily_pnl_date != today:
            self._daily_pnl = {}
            self._daily_pnl_date = today
        
        context.daily_pnl_usd = self._daily_pnl.get(connection_id, 0.0)
        
        if context.account_equity_usd > 0:
            context.current_daily_drawdown_pct = min(0, context.daily_pnl_usd) / context.account_equity_usd
        
        # Get capsule state
        try:
            from ..routes.trading_routes import _capsule_state
            context.paused = _capsule_state.paused
            context.kill_switch_active = _capsule_state.kill_switch_active
        except Exception:
            pass
        
        return context
    
    # ===========================================
    # Risk Checks
    # ===========================================
    
    def _check_global_halt(self, context: RiskCheckContext) -> tuple[bool, Optional[str]]:
        """Check global halt conditions"""
        if context.kill_switch_active:
            return False, "KILL_SWITCH_ACTIVE"
        
        if context.paused:
            return False, "TRADING_PAUSED"
        
        if self._profile.emergency_stop_enabled:
            # Check if we should trigger emergency stop
            if context.current_daily_drawdown_pct < -self._profile.max_daily_drawdown_pct:
                return False, "EMERGENCY_STOP_DAILY_DRAWDOWN"
        
        return True, None
    
    def _check_mode_constraints(
        self,
        intent: OrderIntent,
        context: RiskCheckContext
    ) -> tuple[bool, Optional[str]]:
        """Check mode-specific constraints"""
        
        if context.market_type == "SPOT":
            if not self._profile.spot_enabled:
                return False, "SPOT_DISABLED"
            
            if intent.side == "SELL" and not intent.reduce_only:
                # In SPOT, can only sell what we have
                pass
        
        elif context.market_type == "FUTURES":
            if not self._profile.futures_enabled:
                return False, "FUTURES_DISABLED"
            
            if intent.side == "SELL" and not intent.reduce_only:
                if not self._profile.short_allowed:
                    return False, "SHORT_NOT_ALLOWED"
        
        return True, None
    
    def _check_position_size(
        self,
        intent: OrderIntent,
        context: RiskCheckContext
    ) -> tuple[bool, Optional[str], Optional[float]]:
        """Check position size limits"""
        adjusted_notional = None
        
        if intent.notional_usd > self._profile.max_position_usd:
            # Trim to max
            adjusted_notional = self._profile.max_position_usd
            return True, "MAX_POSITION_TRIMMED", adjusted_notional
        
        return True, None, None
    
    def _check_exposure_limits(
        self,
        intent: OrderIntent,
        context: RiskCheckContext
    ) -> tuple[bool, Optional[str], Optional[float]]:
        """Check exposure limits"""
        adjusted_notional = None
        
        if context.account_equity_usd <= 0:
            return True, None, None
        
        # Asset exposure check
        new_asset_exposure = context.current_asset_exposure_usd + intent.notional_usd
        max_asset_exposure = context.account_equity_usd * self._profile.max_asset_exposure_pct
        
        if new_asset_exposure > max_asset_exposure:
            allowed_notional = max_asset_exposure - context.current_asset_exposure_usd
            if allowed_notional <= 0:
                return False, "MAX_ASSET_EXPOSURE_REACHED", None
            adjusted_notional = max(0, allowed_notional)
            return True, "ASSET_EXPOSURE_TRIMMED", adjusted_notional
        
        # Portfolio exposure check
        new_portfolio_exposure = context.current_portfolio_exposure_usd + intent.notional_usd
        max_portfolio_exposure = context.account_equity_usd * self._profile.max_portfolio_exposure_pct
        
        if new_portfolio_exposure > max_portfolio_exposure:
            allowed_notional = max_portfolio_exposure - context.current_portfolio_exposure_usd
            if allowed_notional <= 0:
                return False, "MAX_PORTFOLIO_EXPOSURE_REACHED", None
            if adjusted_notional is None or allowed_notional < adjusted_notional:
                adjusted_notional = max(0, allowed_notional)
            return True, "PORTFOLIO_EXPOSURE_TRIMMED", adjusted_notional
        
        return True, None, adjusted_notional
    
    def _check_position_count(
        self,
        intent: OrderIntent,
        context: RiskCheckContext
    ) -> tuple[bool, Optional[str]]:
        """Check position and order counts"""
        
        # Skip for reduce_only orders
        if intent.reduce_only:
            return True, None
        
        if context.open_positions_count >= self._profile.max_open_positions:
            return False, "MAX_OPEN_POSITIONS_REACHED"
        
        if context.asset_orders_count >= self._profile.max_orders_per_asset:
            return False, "MAX_ORDERS_PER_ASSET_REACHED"
        
        return True, None
    
    def _check_daily_drawdown(
        self,
        intent: OrderIntent,
        context: RiskCheckContext
    ) -> tuple[bool, Optional[str]]:
        """Check daily drawdown limits"""
        
        # Allow reduce_only orders even at DD limit
        if intent.reduce_only:
            return True, None
        
        if context.current_daily_drawdown_pct < -self._profile.max_daily_drawdown_pct:
            return False, "DAILY_DRAWDOWN_LIMIT_REACHED"
        
        return True, None
    
    def _check_averaging(
        self,
        intent: OrderIntent,
        context: RiskCheckContext
    ) -> tuple[bool, Optional[str], Optional[float]]:
        """Check averaging ladder constraints"""
        
        if not self._profile.averaging_enabled:
            return True, None, None
        
        # Only applies to adding to positions (not initial entry or exits)
        if intent.reduce_only:
            return True, None, None
        
        asset_key = f"{context.connection_id}_{intent.asset}"
        avg_state = self._averaging_states.get(asset_key)
        
        if not avg_state or not avg_state.active:
            # First entry, not averaging yet
            return True, None, None
        
        # Check max steps
        if avg_state.steps_used >= self._profile.max_averaging_steps:
            return False, "MAX_AVERAGING_STEPS_REACHED", None
        
        # Check max capital committed
        max_avg_capital = context.account_equity_usd * self._profile.max_averaging_capital_pct
        if avg_state.total_capital_committed_usd + intent.notional_usd > max_avg_capital:
            allowed = max_avg_capital - avg_state.total_capital_committed_usd
            if allowed <= 0:
                return False, "MAX_AVERAGING_CAPITAL_REACHED", None
            return True, "AVERAGING_CAPITAL_TRIMMED", allowed
        
        # Check price drop requirement
        if avg_state.last_entry_price > 0 and avg_state.current_price > 0:
            price_drop_pct = (avg_state.last_entry_price - avg_state.current_price) / avg_state.last_entry_price
            if price_drop_pct < self._profile.averaging_min_price_drop_pct:
                return False, "AVERAGING_PRICE_DROP_NOT_MET", None
        
        return True, None, None
    
    # ===========================================
    # Main Evaluation
    # ===========================================
    
    async def evaluate(
        self,
        intent: OrderIntent,
        context_or_execution_context: Any
    ) -> RiskVerdict:
        """
        Evaluate order intent against risk rules.
        
        Returns RiskVerdict with allowed/blocked status and adjustments.
        """
        verdict = RiskVerdict()
        
        # Build context if needed
        if isinstance(context_or_execution_context, RiskCheckContext):
            context = context_or_execution_context
        else:
            # It's an ExecutionContext, build RiskCheckContext
            context = await self.build_context(
                intent.connection_id,
                intent.asset,
                "SPOT"  # Default
            )
        
        adjusted_notional = None
        
        # Run all checks
        checks = [
            ("global_halt", self._check_global_halt(context)),
            ("mode_constraints", self._check_mode_constraints(intent, context)),
            ("position_count", self._check_position_count(intent, context)),
            ("daily_drawdown", self._check_daily_drawdown(intent, context))
        ]
        
        for check_name, (passed, reason) in checks:
            if passed:
                verdict.checks_passed.append(check_name)
            else:
                verdict.checks_failed.append(check_name)
                verdict.reason_codes.append(reason)
                verdict.allowed = False
                verdict.severity = RiskSeverity.BLOCKED
        
        # Early return if blocked
        if not verdict.allowed:
            self._record_event("BLOCKED", intent, verdict)
            return verdict
        
        # Checks that may adjust quantity
        size_passed, size_reason, size_adj = self._check_position_size(intent, context)
        if size_passed:
            verdict.checks_passed.append("position_size")
            if size_reason:
                verdict.notes.append(size_reason)
                adjusted_notional = size_adj
        else:
            verdict.checks_failed.append("position_size")
            verdict.reason_codes.append(size_reason)
            verdict.allowed = False
            verdict.severity = RiskSeverity.BLOCKED
        
        exp_passed, exp_reason, exp_adj = self._check_exposure_limits(intent, context)
        if exp_passed:
            verdict.checks_passed.append("exposure_limits")
            if exp_reason:
                verdict.notes.append(exp_reason)
                if exp_adj and (adjusted_notional is None or exp_adj < adjusted_notional):
                    adjusted_notional = exp_adj
        else:
            verdict.checks_failed.append("exposure_limits")
            verdict.reason_codes.append(exp_reason)
            verdict.allowed = False
            verdict.severity = RiskSeverity.BLOCKED
        
        avg_passed, avg_reason, avg_adj = self._check_averaging(intent, context)
        if avg_passed:
            verdict.checks_passed.append("averaging")
            if avg_reason:
                verdict.notes.append(avg_reason)
                if avg_adj and (adjusted_notional is None or avg_adj < adjusted_notional):
                    adjusted_notional = avg_adj
        else:
            verdict.checks_failed.append("averaging")
            verdict.reason_codes.append(avg_reason)
            verdict.allowed = False
            verdict.severity = RiskSeverity.BLOCKED
        
        # Apply adjustments
        if adjusted_notional and adjusted_notional < intent.notional_usd:
            verdict.adjusted_notional_usd = adjusted_notional
            # Estimate adjusted quantity
            price_estimate = intent.notional_usd / intent.quantity if intent.quantity > 0 else 65000
            verdict.adjusted_quantity = adjusted_notional / price_estimate
            verdict.severity = RiskSeverity.WARNING
        
        # Record event
        if verdict.allowed:
            self._record_event("PASSED" if not adjusted_notional else "ADJUSTED", intent, verdict)
        else:
            self._record_event("BLOCKED", intent, verdict)
        
        return verdict
    
    def _record_event(self, event_type: str, intent: OrderIntent, verdict: RiskVerdict):
        """Record risk event for audit"""
        self._risk_events.append({
            "type": event_type,
            "intent_id": intent.intent_id,
            "asset": intent.asset,
            "side": intent.side,
            "notional_usd": intent.notional_usd,
            "verdict_severity": verdict.severity.value,
            "reason_codes": verdict.reason_codes,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Keep last 1000 events
        if len(self._risk_events) > 1000:
            self._risk_events = self._risk_events[-1000:]
    
    # ===========================================
    # Averaging Management
    # ===========================================
    
    def get_averaging_state(self, connection_id: str, asset: str) -> Optional[AveragingState]:
        """Get averaging state for asset"""
        key = f"{connection_id}_{asset}"
        return self._averaging_states.get(key)
    
    def start_averaging(
        self,
        connection_id: str,
        asset: str,
        entry_price: float,
        quantity: float,
        notional_usd: float
    ) -> AveragingState:
        """Start averaging ladder for asset"""
        key = f"{connection_id}_{asset}"
        
        state = AveragingState(
            asset=asset,
            connection_id=connection_id
        )
        state.add_entry(entry_price, quantity, notional_usd)
        
        self._averaging_states[key] = state
        return state
    
    def add_averaging_entry(
        self,
        connection_id: str,
        asset: str,
        entry_price: float,
        quantity: float,
        notional_usd: float
    ) -> Optional[AveragingState]:
        """Add entry to averaging ladder"""
        key = f"{connection_id}_{asset}"
        state = self._averaging_states.get(key)
        
        if not state:
            return self.start_averaging(connection_id, asset, entry_price, quantity, notional_usd)
        
        state.add_entry(entry_price, quantity, notional_usd)
        return state
    
    def reset_averaging(self, connection_id: str, asset: str):
        """Reset averaging state when position is closed"""
        key = f"{connection_id}_{asset}"
        if key in self._averaging_states:
            self._averaging_states[key].reset()
    
    def update_current_price(self, connection_id: str, asset: str, price: float):
        """Update current price for averaging calculations"""
        key = f"{connection_id}_{asset}"
        if key in self._averaging_states:
            self._averaging_states[key].current_price = price
    
    # ===========================================
    # Daily PnL Tracking
    # ===========================================
    
    def record_pnl(self, connection_id: str, pnl: float):
        """Record PnL for daily tracking"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._daily_pnl_date != today:
            self._daily_pnl = {}
            self._daily_pnl_date = today
        
        if connection_id not in self._daily_pnl:
            self._daily_pnl[connection_id] = 0.0
        
        self._daily_pnl[connection_id] += pnl
    
    def get_daily_pnl(self, connection_id: str) -> float:
        """Get daily PnL for connection"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._daily_pnl_date != today:
            return 0.0
        return self._daily_pnl.get(connection_id, 0.0)
    
    # ===========================================
    # Queries
    # ===========================================
    
    def get_risk_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent risk events"""
        return self._risk_events[-limit:]
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health"""
        return {
            "enabled": True,
            "version": "risk_t4",
            "status": "ok",
            "profile": self._profile.to_dict(),
            "active_averaging_states": len([s for s in self._averaging_states.values() if s.active]),
            "total_risk_events": len(self._risk_events),
            "blocked_events": sum(1 for e in self._risk_events if e["type"] == "BLOCKED"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global instance
risk_service = RiskService()
