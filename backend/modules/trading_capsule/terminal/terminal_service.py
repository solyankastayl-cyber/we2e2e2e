"""
Terminal Service (T5)
=====================

Core service for Terminal Backend.

Aggregates data from all Trading Capsule subsystems.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from .terminal_types import (
    AccountOverview,
    PositionView,
    OrderView,
    PnLView,
    DailyPnLRecord,
    ExecutionLogEntry,
    RiskOverview,
    AveragingView,
    TradingSystemState,
    ActionResult,
    EventType
)


class TerminalService:
    """
    Terminal Backend Service.
    
    Provides unified interface for admin monitoring and control.
    """
    
    def __init__(self):
        # Execution log storage
        self._execution_log: List[ExecutionLogEntry] = []
        
        # PnL history
        self._daily_pnl_history: Dict[str, DailyPnLRecord] = {}  # date_conn -> record
        
        # Service start time for uptime calculation
        self._start_time = datetime.now(timezone.utc)
        
        # Price estimates for position valuation
        self._price_estimates: Dict[str, float] = {
            "BTC": 65000.0,
            "ETH": 3500.0,
            "SOL": 150.0,
            "BNB": 450.0
        }
        
        print("[TerminalService] Initialized")
    
    # ===========================================
    # Account Monitor
    # ===========================================
    
    async def get_accounts_overview(self) -> List[AccountOverview]:
        """Get overview of all accounts"""
        from ..broker import broker_registry, list_connections
        from ..orders import order_service
        
        accounts = []
        connections = list_connections()
        
        for conn in connections:
            overview = AccountOverview(
                connection_id=conn.connection_id,
                exchange=conn.exchange.value,
                label=conn.label,
                status=conn.status.value,
                health=conn.health.value
            )
            
            # Try to get account state
            try:
                adapter = await broker_registry.get_or_create_adapter(conn.connection_id)
                if adapter:
                    if not adapter._connected:
                        await adapter.connect()
                    
                    state = await adapter.fetch_account_state()
                    overview.total_equity_usd = state.equity_usd
                    
                    for balance in state.balances:
                        if balance.asset == "USDT":
                            overview.available_cash_usd = balance.free
                        overview.spot_equity_usd += balance.usd_value
                    
                    overview.open_positions = state.open_positions
                    overview.open_orders = state.open_orders
                    
            except Exception as e:
                print(f"[TerminalService] Failed to get account state: {e}")
            
            # Count open positions from OMS
            open_trades = order_service.get_trades(connection_id=conn.connection_id, is_open=True)
            overview.open_positions = len(open_trades)
            
            # Count open orders
            active_orders = order_service.get_active_orders(conn.connection_id)
            overview.open_orders = len(active_orders)
            
            accounts.append(overview)
        
        return accounts
    
    async def get_account_overview(self, connection_id: str) -> Optional[AccountOverview]:
        """Get overview for specific account"""
        accounts = await self.get_accounts_overview()
        for acc in accounts:
            if acc.connection_id == connection_id:
                return acc
        return None
    
    # ===========================================
    # Positions Monitor
    # ===========================================
    
    async def get_positions(self, connection_id: Optional[str] = None) -> List[PositionView]:
        """Get all open positions"""
        from ..orders import order_service
        from ..broker import broker_registry
        
        positions = []
        open_trades = order_service.get_open_trades()
        
        for trade in open_trades:
            if connection_id and trade.connection_id != connection_id:
                continue
            
            # Get current price
            current_price = self._price_estimates.get(trade.asset, trade.entry_price)
            
            # Calculate unrealized PnL
            if trade.side == "LONG":
                unrealized_pnl = (current_price - trade.entry_price) * trade.quantity
                unrealized_pnl_pct = (current_price - trade.entry_price) / trade.entry_price if trade.entry_price > 0 else 0
            else:
                unrealized_pnl = (trade.entry_price - current_price) * trade.quantity
                unrealized_pnl_pct = (trade.entry_price - current_price) / trade.entry_price if trade.entry_price > 0 else 0
            
            # Get account equity for exposure calculation
            exposure_pct = 0.0
            try:
                adapter = await broker_registry.get_or_create_adapter(trade.connection_id)
                if adapter and adapter._connected:
                    state = await adapter.fetch_account_state()
                    if state.equity_usd > 0:
                        exposure_pct = (current_price * trade.quantity) / state.equity_usd
            except:
                pass
            
            position = PositionView(
                position_id=trade.trade_id,
                connection_id=trade.connection_id,
                asset=trade.asset,
                symbol=trade.symbol,
                side=trade.side,
                market_type="SPOT",  # Default
                quantity=trade.quantity,
                avg_entry_price=trade.entry_price,
                current_price=current_price,
                unrealized_pnl_usd=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
                exposure_usd=current_price * trade.quantity,
                exposure_pct=exposure_pct,
                opened_at=trade.open_time,
                duration_minutes=trade.duration_minutes
            )
            positions.append(position)
        
        return positions
    
    async def get_position(self, asset: str, connection_id: Optional[str] = None) -> Optional[PositionView]:
        """Get position for specific asset"""
        positions = await self.get_positions(connection_id)
        for pos in positions:
            if pos.asset == asset:
                return pos
        return None
    
    # ===========================================
    # Orders Monitor
    # ===========================================
    
    def get_orders(
        self,
        connection_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[OrderView]:
        """Get orders"""
        from ..orders import order_service
        from ..orders.order_types import OrderStatus
        
        order_status = None
        if status:
            try:
                order_status = OrderStatus(status.upper())
            except ValueError:
                pass
        
        orders = order_service.get_orders(
            connection_id=connection_id,
            status=order_status,
            limit=limit
        )
        
        views = []
        for order in orders:
            view = OrderView(
                order_id=order.order_id,
                client_order_id=order.client_order_id,
                exchange_order_id=order.broker_order_id,
                connection_id=order.connection_id,
                asset=order.asset,
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=order.quantity,
                filled_quantity=order.filled_quantity,
                fill_pct=order.fill_pct,
                price=order.price,
                avg_fill_price=order.avg_fill_price if order.avg_fill_price > 0 else None,
                status=order.status.value,
                notional_usd=order.notional_usd,
                commission_usd=order.commission,
                source=order.client_tag,
                created_at=order.created_at,
                filled_at=order.filled_at
            )
            views.append(view)
        
        return views
    
    def get_open_orders(self, connection_id: Optional[str] = None) -> List[OrderView]:
        """Get open orders"""
        from ..orders import order_service
        
        orders = order_service.get_active_orders(connection_id)
        
        views = []
        for order in orders:
            view = OrderView(
                order_id=order.order_id,
                client_order_id=order.client_order_id,
                exchange_order_id=order.broker_order_id,
                connection_id=order.connection_id,
                asset=order.asset,
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=order.quantity,
                filled_quantity=order.filled_quantity,
                fill_pct=order.fill_pct,
                price=order.price,
                status=order.status.value,
                notional_usd=order.notional_usd,
                source=order.client_tag,
                created_at=order.created_at
            )
            views.append(view)
        
        return views
    
    def get_order_history(self, connection_id: Optional[str] = None, limit: int = 100) -> List[OrderView]:
        """Get order history (filled/cancelled)"""
        from ..orders import order_service
        
        all_orders = order_service.get_orders(connection_id=connection_id, limit=limit * 2)
        
        # Filter to completed orders only
        completed = [o for o in all_orders if not o.is_active]
        
        views = []
        for order in completed[:limit]:
            view = OrderView(
                order_id=order.order_id,
                client_order_id=order.client_order_id,
                exchange_order_id=order.broker_order_id,
                connection_id=order.connection_id,
                asset=order.asset,
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=order.quantity,
                filled_quantity=order.filled_quantity,
                fill_pct=order.fill_pct,
                price=order.price,
                avg_fill_price=order.avg_fill_price if order.avg_fill_price > 0 else None,
                status=order.status.value,
                notional_usd=order.notional_usd,
                commission_usd=order.commission,
                source=order.client_tag,
                created_at=order.created_at,
                filled_at=order.filled_at
            )
            views.append(view)
        
        return views
    
    # ===========================================
    # PnL Engine
    # ===========================================
    
    async def get_pnl(self, connection_id: Optional[str] = None) -> PnLView:
        """Get PnL overview"""
        from ..orders import order_service
        from ..risk import risk_service
        
        view = PnLView(connection_id=connection_id or "ALL")
        
        # Get all trades
        trades = order_service.get_trades(connection_id=connection_id)
        
        # Calculate realized PnL from closed trades
        closed_trades = [t for t in trades if not t.is_open]
        view.total_trades = len(closed_trades)
        
        total_win = 0.0
        total_loss = 0.0
        
        for trade in closed_trades:
            if trade.net_pnl > 0:
                view.winning_trades += 1
                total_win += trade.net_pnl
            elif trade.net_pnl < 0:
                view.losing_trades += 1
                total_loss += abs(trade.net_pnl)
            
            view.realized_pnl_usd += trade.net_pnl
        
        # Calculate unrealized PnL from open positions
        positions = await self.get_positions(connection_id)
        for pos in positions:
            view.unrealized_pnl_usd += pos.unrealized_pnl_usd
        
        view.total_pnl_usd = view.realized_pnl_usd + view.unrealized_pnl_usd
        
        # Win rate
        if view.total_trades > 0:
            view.win_rate = view.winning_trades / view.total_trades
        
        # Averages
        if view.winning_trades > 0:
            view.avg_win_usd = total_win / view.winning_trades
        if view.losing_trades > 0:
            view.avg_loss_usd = total_loss / view.losing_trades
        
        # Profit factor
        if total_loss > 0:
            view.profit_factor = total_win / total_loss
        
        # Daily PnL from risk service
        if connection_id:
            view.daily_pnl_usd = risk_service.get_daily_pnl(connection_id)
        
        return view
    
    def get_daily_pnl(self, connection_id: str) -> DailyPnLRecord:
        """Get today's PnL"""
        from ..risk import risk_service
        from ..orders import order_service
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        record = DailyPnLRecord(
            date=today,
            connection_id=connection_id,
            pnl_usd=risk_service.get_daily_pnl(connection_id)
        )
        
        # Count today's trades
        trades = order_service.get_trades(connection_id=connection_id)
        for trade in trades:
            if trade.open_time.strftime("%Y-%m-%d") == today:
                record.trades_count += 1
                record.volume_usd += trade.entry_price * trade.quantity
        
        return record
    
    def get_pnl_history(self, connection_id: Optional[str] = None, days: int = 30) -> List[DailyPnLRecord]:
        """Get PnL history"""
        # Return stored history
        records = []
        for key, record in self._daily_pnl_history.items():
            if connection_id and record.connection_id != connection_id:
                continue
            records.append(record)
        
        # Sort by date desc
        records = sorted(records, key=lambda r: r.date, reverse=True)
        return records[:days]
    
    # ===========================================
    # Execution Log
    # ===========================================
    
    def log_event(
        self,
        event_type: EventType,
        message: str,
        connection_id: Optional[str] = None,
        asset: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "INFO"
    ):
        """Log execution event"""
        entry = ExecutionLogEntry(
            event_type=event_type,
            connection_id=connection_id,
            asset=asset,
            message=message,
            details=details or {},
            severity=severity
        )
        
        self._execution_log.append(entry)
        
        # Keep last 1000 entries
        if len(self._execution_log) > 1000:
            self._execution_log = self._execution_log[-1000:]
    
    def get_execution_log(
        self,
        connection_id: Optional[str] = None,
        asset: Optional[str] = None,
        event_type: Optional[EventType] = None,
        limit: int = 100
    ) -> List[ExecutionLogEntry]:
        """Get execution log entries"""
        entries = self._execution_log.copy()
        
        if connection_id:
            entries = [e for e in entries if e.connection_id == connection_id]
        
        if asset:
            entries = [e for e in entries if e.asset == asset]
        
        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        
        # Sort by timestamp desc
        entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)
        
        return entries[:limit]
    
    # ===========================================
    # Risk Monitor
    # ===========================================
    
    async def get_risk_overview(self, connection_id: Optional[str] = None) -> RiskOverview:
        """Get risk overview"""
        from ..risk import risk_service
        from ..orders import order_service
        from ..routes.trading_routes import _capsule_state
        
        profile = risk_service.get_profile()
        
        overview = RiskOverview(
            profile_id=profile.profile_id,
            kill_switch_active=_capsule_state.kill_switch_active,
            paused=_capsule_state.paused,
            max_exposure_pct=profile.max_portfolio_exposure_pct,
            max_drawdown_pct=profile.max_daily_drawdown_pct,
            max_positions=profile.max_open_positions
        )
        
        # Calculate current exposure
        positions = await self.get_positions(connection_id)
        for pos in positions:
            overview.current_exposure_usd += pos.exposure_usd
        
        # Get account equity for exposure %
        if connection_id:
            acc = await self.get_account_overview(connection_id)
            if acc and acc.total_equity_usd > 0:
                overview.current_exposure_pct = overview.current_exposure_usd / acc.total_equity_usd
        
        # Open positions count
        overview.open_positions = len(positions)
        
        # Daily PnL and drawdown
        if connection_id:
            overview.daily_pnl_usd = risk_service.get_daily_pnl(connection_id)
            acc = await self.get_account_overview(connection_id)
            if acc and acc.total_equity_usd > 0 and overview.daily_pnl_usd < 0:
                overview.daily_drawdown_pct = abs(overview.daily_pnl_usd) / acc.total_equity_usd
        
        # Averaging active count
        averaging_states = risk_service._averaging_states
        overview.averaging_active_assets = len([s for s in averaging_states.values() if s.active])
        
        # Count blocked/adjusted trades from risk events
        risk_events = risk_service.get_risk_events(limit=500)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        for event in risk_events:
            event_time = datetime.fromisoformat(event["timestamp"])
            if event_time > cutoff:
                if event["type"] == "BLOCKED":
                    overview.blocked_trades_24h += 1
                elif event["type"] == "ADJUSTED":
                    overview.adjusted_trades_24h += 1
        
        # Last risk event
        if risk_events:
            last = risk_events[-1]
            overview.last_risk_event = f"{last['type']}: {last['asset']} {last['side']}"
        
        return overview
    
    # ===========================================
    # Averaging Monitor
    # ===========================================
    
    async def get_averaging_overview(self, connection_id: Optional[str] = None) -> List[AveragingView]:
        """Get all averaging states"""
        from ..risk import risk_service
        
        profile = risk_service.get_profile()
        views = []
        
        for key, state in risk_service._averaging_states.items():
            if connection_id and state.connection_id != connection_id:
                continue
            
            if not state.active:
                continue
            
            # Calculate max capital based on equity
            max_capital = 0.0
            try:
                acc = await self.get_account_overview(state.connection_id)
                if acc:
                    max_capital = acc.total_equity_usd * profile.max_averaging_capital_pct
            except:
                pass
            
            # Calculate price distance
            price_distance_pct = 0.0
            if state.avg_entry_price > 0 and state.current_price > 0:
                price_distance_pct = (state.avg_entry_price - state.current_price) / state.avg_entry_price
            
            # Calculate next entry trigger
            next_trigger = 0.0
            if state.last_entry_price > 0:
                next_trigger = state.last_entry_price * (1 - profile.averaging_min_price_drop_pct)
            
            # Calculate unrealized PnL
            current_price = state.current_price or self._price_estimates.get(state.asset, 0)
            total_qty = sum(e["quantity"] for e in state.entries)
            unrealized_pnl = (current_price - state.avg_entry_price) * total_qty if state.avg_entry_price > 0 else 0
            
            view = AveragingView(
                connection_id=state.connection_id,
                asset=state.asset,
                active=state.active,
                steps_used=state.steps_used,
                max_steps=profile.max_averaging_steps,
                capital_committed_usd=state.total_capital_committed_usd,
                max_capital_usd=max_capital,
                capital_used_pct=state.total_capital_committed_usd / max_capital if max_capital > 0 else 0,
                avg_entry_price=state.avg_entry_price,
                current_price=current_price,
                price_distance_pct=price_distance_pct,
                last_entry_price=state.last_entry_price,
                next_entry_trigger_price=next_trigger,
                unrealized_pnl_usd=unrealized_pnl,
                started_at=state.entries[0]["timestamp"] if state.entries else None
            )
            
            # Convert started_at if string
            if view.started_at and isinstance(view.started_at, str):
                view.started_at = datetime.fromisoformat(view.started_at)
            
            views.append(view)
        
        return views
    
    async def get_averaging_state(self, connection_id: str, asset: str) -> Optional[AveragingView]:
        """Get averaging state for specific asset"""
        views = await self.get_averaging_overview(connection_id)
        for v in views:
            if v.asset == asset:
                return v
        return None
    
    # ===========================================
    # System State
    # ===========================================
    
    async def get_system_state(self) -> TradingSystemState:
        """Get trading system state"""
        from ..routes.trading_routes import _capsule_state
        from ..broker import list_connections
        from ..orders import order_service
        
        state = TradingSystemState(
            execution_mode=_capsule_state.execution_mode.value,
            trading_mode=_capsule_state.trading_mode.value,
            paused=_capsule_state.paused,
            kill_switch_active=_capsule_state.kill_switch_active
        )
        
        # Connection stats
        connections = list_connections()
        state.active_connections = len(connections)
        state.healthy_connections = len([c for c in connections if c.health.value == "HEALTHY"])
        
        # Position and order counts
        positions = await self.get_positions()
        state.open_positions = len(positions)
        
        active_orders = order_service.get_active_orders()
        state.open_orders = len(active_orders)
        
        # Daily stats
        stats = order_service.get_stats()
        state.daily_trades = stats.get("orders_filled", 0)
        state.daily_volume_usd = stats.get("total_volume_usd", 0)
        
        # Uptime
        state.uptime_minutes = (datetime.now(timezone.utc) - self._start_time).total_seconds() / 60
        
        # Last trade
        trades = order_service.get_trades(limit=1)
        if trades:
            state.last_trade_at = trades[0].open_time
        
        return state
    
    # ===========================================
    # Terminal Actions
    # ===========================================
    
    async def action_pause(self) -> ActionResult:
        """Pause trading"""
        from ..routes.trading_routes import _capsule_state
        
        _capsule_state.paused = True
        _capsule_state.updated_at = datetime.now(timezone.utc)
        
        self.log_event(
            EventType.SYSTEM_PAUSED,
            "Trading paused by admin",
            severity="WARNING"
        )
        
        return ActionResult(
            success=True,
            action="PAUSE",
            message="Trading paused successfully"
        )
    
    async def action_resume(self) -> ActionResult:
        """Resume trading"""
        from ..routes.trading_routes import _capsule_state
        
        if _capsule_state.kill_switch_active:
            return ActionResult(
                success=False,
                action="RESUME",
                message="Cannot resume: kill switch is active"
            )
        
        _capsule_state.paused = False
        _capsule_state.updated_at = datetime.now(timezone.utc)
        
        self.log_event(
            EventType.SYSTEM_RESUMED,
            "Trading resumed by admin",
            severity="INFO"
        )
        
        return ActionResult(
            success=True,
            action="RESUME",
            message="Trading resumed successfully"
        )
    
    async def action_activate_kill_switch(self) -> ActionResult:
        """Activate kill switch"""
        from ..routes.trading_routes import _capsule_state
        
        _capsule_state.kill_switch_active = True
        _capsule_state.paused = True
        _capsule_state.updated_at = datetime.now(timezone.utc)
        
        self.log_event(
            EventType.KILL_SWITCH_ACTIVATED,
            "Kill switch activated by admin - ALL TRADING STOPPED",
            severity="ERROR"
        )
        
        return ActionResult(
            success=True,
            action="KILL_SWITCH",
            message="Kill switch activated. All trading stopped."
        )
    
    async def action_deactivate_kill_switch(self) -> ActionResult:
        """Deactivate kill switch"""
        from ..routes.trading_routes import _capsule_state
        
        _capsule_state.kill_switch_active = False
        _capsule_state.updated_at = datetime.now(timezone.utc)
        
        self.log_event(
            EventType.SYSTEM_RESUMED,
            "Kill switch deactivated by admin",
            severity="WARNING"
        )
        
        return ActionResult(
            success=True,
            action="DEACTIVATE_KILL_SWITCH",
            message="Kill switch deactivated. Manual resume required."
        )
    
    async def action_close_position(self, connection_id: str, asset: str) -> ActionResult:
        """Close position for asset"""
        from ..orders import order_service
        from ..orders.order_types import OrderSide, OrderType
        
        # Find open trade
        open_trades = order_service.get_open_trades()
        target_trade = None
        
        for trade in open_trades:
            if trade.connection_id == connection_id and trade.asset == asset:
                target_trade = trade
                break
        
        if not target_trade:
            return ActionResult(
                success=False,
                action="CLOSE_POSITION",
                message=f"No open position found for {asset}"
            )
        
        # Place close order
        close_side = OrderSide.SELL if target_trade.side == "LONG" else OrderSide.BUY
        
        order = await order_service.place_order(
            connection_id=connection_id,
            symbol=target_trade.symbol,
            side=close_side,
            order_type=OrderType.MARKET,
            quantity=target_trade.quantity,
            reduce_only=True,
            client_tag="TERMINAL_CLOSE"
        )
        
        self.log_event(
            EventType.POSITION_CLOSED,
            f"Position closed by admin: {asset}",
            connection_id=connection_id,
            asset=asset,
            details={"order_id": order.order_id, "quantity": target_trade.quantity}
        )
        
        return ActionResult(
            success=order.status.value in ["FILLED", "SUBMITTED", "NEW"],
            action="CLOSE_POSITION",
            message=f"Close order placed for {asset}",
            details={"order_id": order.order_id, "status": order.status.value}
        )
    
    async def action_cancel_order(self, order_id: str) -> ActionResult:
        """Cancel specific order"""
        from ..orders import order_service
        
        try:
            order = await order_service.cancel_order(order_id=order_id)
            
            self.log_event(
                EventType.ORDER_CANCELLED,
                f"Order cancelled by admin: {order_id}",
                connection_id=order.connection_id,
                asset=order.asset,
                details={"order_id": order_id}
            )
            
            return ActionResult(
                success=True,
                action="CANCEL_ORDER",
                message=f"Order {order_id} cancelled",
                details={"order_id": order_id, "status": order.status.value}
            )
        except ValueError as e:
            return ActionResult(
                success=False,
                action="CANCEL_ORDER",
                message=str(e)
            )
    
    async def action_cancel_all_orders(self, connection_id: Optional[str] = None) -> ActionResult:
        """Cancel all orders"""
        from ..orders import order_service
        
        cancelled = await order_service.cancel_all_orders(connection_id)
        
        self.log_event(
            EventType.ORDER_CANCELLED,
            f"All orders cancelled by admin ({len(cancelled)} orders)",
            connection_id=connection_id,
            details={"count": len(cancelled)}
        )
        
        return ActionResult(
            success=True,
            action="CANCEL_ALL_ORDERS",
            message=f"Cancelled {len(cancelled)} orders",
            details={"cancelled_count": len(cancelled)}
        )
    
    # ===========================================
    # Health
    # ===========================================
    
    def get_health(self) -> Dict[str, Any]:
        """Get terminal service health"""
        return {
            "enabled": True,
            "version": "terminal_t5",
            "status": "ok",
            "log_entries": len(self._execution_log),
            "uptime_minutes": round((datetime.now(timezone.utc) - self._start_time).total_seconds() / 60, 1),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # ===========================================
    # Price Updates
    # ===========================================
    
    def update_price(self, asset: str, price: float):
        """Update price estimate for asset"""
        self._price_estimates[asset] = price


# Global instance
terminal_service = TerminalService()
