"""
Order Service (T2)
==================

Core OMS service for order lifecycle management.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import asyncio

from .order_types import (
    Order,
    OrderStatus,
    OrderType,
    OrderSide,
    TimeInForce,
    Fill,
    Trade,
    OrderPrecision,
    OrderValidationResult
)
from ..broker import broker_registry
from ..trading_types import MarketMode


class OrderService:
    """
    Order Management Service.
    
    Handles:
    - Order creation and placement
    - Order cancellation
    - Order tracking
    - Fill processing
    - Trade history
    """
    
    def __init__(self):
        # Order storage
        self._orders: Dict[str, Order] = {}
        self._orders_by_client_id: Dict[str, str] = {}
        
        # Fill storage
        self._fills: Dict[str, Fill] = {}
        self._fills_by_order: Dict[str, List[str]] = {}
        
        # Trade storage
        self._trades: Dict[str, Trade] = {}
        self._open_trades: Dict[str, str] = {}  # asset -> trade_id
        
        # Precision cache
        self._precision_cache: Dict[str, OrderPrecision] = {}
        
        # Statistics
        self._stats = {
            "orders_placed": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_rejected": 0,
            "total_volume_usd": 0.0,
            "total_commission": 0.0
        }
        
        print("[OrderService] Initialized")
    
    # ===========================================
    # Order Validation
    # ===========================================
    
    def validate_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        connection_id: Optional[str] = None
    ) -> OrderValidationResult:
        """
        Validate order parameters.
        
        Checks:
        - Minimum quantity
        - Minimum notional
        - Price precision
        - Quantity precision
        """
        errors = []
        warnings = []
        adjusted_quantity = None
        adjusted_price = None
        
        # Get precision rules
        precision = self._get_precision(symbol, connection_id)
        
        # Check minimum quantity
        if quantity < precision.min_quantity:
            errors.append(f"Quantity {quantity} below minimum {precision.min_quantity}")
        
        # Check price for limit orders
        if order_type == OrderType.LIMIT and price is None:
            errors.append("Price required for LIMIT orders")
        
        # Check minimum notional
        check_price = price or 0
        if check_price > 0:
            notional = quantity * check_price
            if notional < precision.min_notional:
                errors.append(f"Notional {notional:.2f} below minimum {precision.min_notional}")
        
        # Adjust quantity to step
        if quantity > 0:
            step = precision.quantity_step
            adjusted_qty = round(quantity / step) * step
            if adjusted_qty != quantity:
                adjusted_quantity = adjusted_qty
                warnings.append(f"Quantity adjusted to {adjusted_qty}")
        
        # Adjust price to step
        if price and price > 0:
            step = precision.price_step
            adjusted_px = round(price / step) * step
            if adjusted_px != price:
                adjusted_price = adjusted_px
                warnings.append(f"Price adjusted to {adjusted_px}")
        
        return OrderValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            adjusted_quantity=adjusted_quantity,
            adjusted_price=adjusted_price
        )
    
    def _get_precision(self, symbol: str, connection_id: Optional[str] = None) -> OrderPrecision:
        """Get precision rules for symbol"""
        cache_key = f"{connection_id}_{symbol}" if connection_id else symbol
        
        if cache_key in self._precision_cache:
            return self._precision_cache[cache_key]
        
        # Default precision (can be updated from exchange info)
        precision = OrderPrecision(
            symbol=symbol,
            exchange="DEFAULT",
            price_precision=2,
            quantity_precision=6,
            price_step=0.01,
            quantity_step=0.000001,
            min_quantity=0.0001,
            min_notional=10.0
        )
        
        # Specific rules for common pairs
        if "BTC" in symbol:
            precision.quantity_step = 0.00001
            precision.min_quantity = 0.0001
        elif "ETH" in symbol:
            precision.quantity_step = 0.0001
            precision.min_quantity = 0.001
        
        self._precision_cache[cache_key] = precision
        return precision
    
    # ===========================================
    # Order Placement
    # ===========================================
    
    async def place_order(
        self,
        connection_id: str,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        reduce_only: bool = False,
        client_tag: Optional[str] = None,
        source_decision_id: Optional[str] = None,
        source_intent_id: Optional[str] = None
    ) -> Order:
        """
        Place a new order.
        
        Args:
            connection_id: Broker connection ID
            symbol: Trading symbol (e.g., BTCUSDT)
            side: BUY or SELL
            order_type: MARKET, LIMIT, etc.
            quantity: Order quantity
            price: Limit price (for LIMIT orders)
            stop_price: Stop price (for STOP orders)
            time_in_force: GTC, IOC, FOK
            reduce_only: Reduce only flag
            client_tag: Custom tag
            source_decision_id: Source decision ID
            source_intent_id: Source intent ID
            
        Returns:
            Order object
        """
        # Validate
        validation = self.validate_order(symbol, side, order_type, quantity, price, connection_id)
        
        if not validation.valid:
            order = Order(
                connection_id=connection_id,
                symbol=symbol,
                asset=symbol.replace("USDT", ""),
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status=OrderStatus.REJECTED
            )
            self._stats["orders_rejected"] += 1
            return order
        
        # Apply adjustments
        if validation.adjusted_quantity:
            quantity = validation.adjusted_quantity
        if validation.adjusted_price:
            price = validation.adjusted_price
        
        # Get connection and adapter
        connection = broker_registry.get_connection(connection_id)
        if not connection:
            order = Order(
                connection_id=connection_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                status=OrderStatus.FAILED
            )
            return order
        
        # Create order
        order = Order(
            connection_id=connection_id,
            exchange=connection.exchange.value,
            symbol=symbol,
            asset=symbol.replace("USDT", ""),
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            client_tag=client_tag,
            source_decision_id=source_decision_id,
            source_intent_id=source_intent_id,
            status=OrderStatus.PENDING
        )
        
        # Store order
        self._orders[order.order_id] = order
        self._orders_by_client_id[order.client_order_id] = order.order_id
        
        # Submit to exchange
        try:
            adapter = await broker_registry.get_or_create_adapter(connection_id)
            
            if not adapter:
                order.status = OrderStatus.FAILED
                return order
            
            # Connect if needed
            if not adapter._connected:
                await adapter.connect()
            
            # Use broker_adapters module for actual order placement
            from ..broker.broker_adapters import MockBrokerAdapter
            
            if isinstance(adapter, MockBrokerAdapter):
                # For mock adapter, simulate order
                order = await self._execute_mock_order(order, adapter)
            else:
                # For real adapters, use the broker module
                order = await self._execute_real_order(order, adapter)
            
            self._stats["orders_placed"] += 1
            
        except Exception as e:
            order.status = OrderStatus.FAILED
            order.updated_at = datetime.now(timezone.utc)
            print(f"[OrderService] Order failed: {e}")
        
        return order
    
    async def _execute_mock_order(self, order: Order, adapter) -> Order:
        """Execute order on mock adapter"""
        import random
        
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now(timezone.utc)
        
        # Simulate execution delay
        await asyncio.sleep(0.05)
        
        # Get current price
        base_price = 65000.0 if "BTC" in order.symbol else 3500.0
        
        # Simulate fill
        if order.order_type == OrderType.MARKET:
            # Market orders fill immediately
            slippage_bps = random.uniform(0, 3)
            slippage = base_price * slippage_bps / 10000
            
            if order.side == OrderSide.BUY:
                fill_price = base_price + slippage
            else:
                fill_price = base_price - slippage
            
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.avg_fill_price = fill_price
            order.commission = order.quantity * fill_price * 0.001
            order.commission_asset = "USDT"
            order.filled_at = datetime.now(timezone.utc)
            
            # Create fill
            fill = Fill(
                order_id=order.order_id,
                asset=order.asset,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=fill_price,
                commission=order.commission,
                commission_asset="USDT"
            )
            self._record_fill(fill)
            
            # Update stats
            self._stats["orders_filled"] += 1
            self._stats["total_volume_usd"] += order.notional_usd
            self._stats["total_commission"] += order.commission
            
            # Update trade tracking
            await self._update_trade(order, fill)
        else:
            # Limit orders stay as NEW
            order.status = OrderStatus.NEW
            order.broker_order_id = f"MOCK_{order.client_order_id}"
        
        order.updated_at = datetime.now(timezone.utc)
        return order
    
    async def _execute_real_order(self, order: Order, adapter) -> Order:
        """Execute order on real exchange adapter"""
        # This would use the actual broker adapter methods
        # For now, we'll mark as submitted
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now(timezone.utc)
        order.updated_at = datetime.now(timezone.utc)
        return order
    
    def _record_fill(self, fill: Fill):
        """Record a fill"""
        self._fills[fill.fill_id] = fill
        
        if fill.order_id not in self._fills_by_order:
            self._fills_by_order[fill.order_id] = []
        
        self._fills_by_order[fill.order_id].append(fill.fill_id)
    
    async def _update_trade(self, order: Order, fill: Fill):
        """Update trade tracking based on fill"""
        asset = order.asset
        
        if order.side == OrderSide.BUY:
            # Opening or adding to position
            if asset in self._open_trades:
                # Add to existing trade (averaging)
                trade_id = self._open_trades[asset]
                trade = self._trades[trade_id]
                
                # Update average entry
                old_notional = trade.entry_price * trade.quantity
                new_notional = fill.price * fill.quantity
                trade.quantity += fill.quantity
                trade.entry_price = (old_notional + new_notional) / trade.quantity
                trade.commission += fill.commission
            else:
                # New trade
                trade = Trade(
                    connection_id=order.connection_id,
                    asset=asset,
                    symbol=order.symbol,
                    side="LONG",
                    entry_price=fill.price,
                    quantity=fill.quantity,
                    commission=fill.commission,
                    entry_order_id=order.order_id,
                    is_open=True
                )
                self._trades[trade.trade_id] = trade
                self._open_trades[asset] = trade.trade_id
                
        elif order.side == OrderSide.SELL:
            # Closing or reducing position
            if asset in self._open_trades:
                trade_id = self._open_trades[asset]
                trade = self._trades[trade_id]
                
                trade.exit_price = fill.price
                trade.exit_order_id = order.order_id
                trade.commission += fill.commission
                
                # Calculate PnL
                trade.gross_pnl = (fill.price - trade.entry_price) * min(fill.quantity, trade.quantity)
                trade.net_pnl = trade.gross_pnl - trade.commission
                
                # Check if fully closed
                remaining = trade.quantity - fill.quantity
                if remaining <= 0:
                    trade.is_open = False
                    trade.close_time = datetime.now(timezone.utc)
                    del self._open_trades[asset]
                else:
                    trade.quantity = remaining
    
    # ===========================================
    # Order Cancellation
    # ===========================================
    
    async def cancel_order(
        self,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """
        Cancel an order.
        
        Args:
            order_id: Internal order ID
            client_order_id: Client order ID
            
        Returns:
            Updated Order object
        """
        # Find order
        if order_id and order_id in self._orders:
            order = self._orders[order_id]
        elif client_order_id and client_order_id in self._orders_by_client_id:
            order_id = self._orders_by_client_id[client_order_id]
            order = self._orders[order_id]
        else:
            raise ValueError("Order not found")
        
        # Check if can cancel
        if not order.is_active:
            raise ValueError(f"Cannot cancel order in status: {order.status.value}")
        
        # Update status
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        
        self._stats["orders_cancelled"] += 1
        
        return order
    
    async def cancel_all_orders(
        self,
        connection_id: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> List[Order]:
        """Cancel all active orders"""
        cancelled = []
        
        for order in self._orders.values():
            if not order.is_active:
                continue
            
            if connection_id and order.connection_id != connection_id:
                continue
            
            if symbol and order.symbol != symbol:
                continue
            
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc)
            cancelled.append(order)
        
        self._stats["orders_cancelled"] += len(cancelled)
        
        return cancelled
    
    # ===========================================
    # Order Queries
    # ===========================================
    
    def get_order(
        self,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Optional[Order]:
        """Get order by ID"""
        if order_id and order_id in self._orders:
            return self._orders[order_id]
        
        if client_order_id and client_order_id in self._orders_by_client_id:
            order_id = self._orders_by_client_id[client_order_id]
            return self._orders[order_id]
        
        return None
    
    def get_orders(
        self,
        connection_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100
    ) -> List[Order]:
        """Get orders with filters"""
        orders = list(self._orders.values())
        
        if connection_id:
            orders = [o for o in orders if o.connection_id == connection_id]
        
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        
        if status:
            orders = [o for o in orders if o.status == status]
        
        # Sort by created_at desc
        orders = sorted(orders, key=lambda o: o.created_at, reverse=True)
        
        return orders[:limit]
    
    def get_active_orders(self, connection_id: Optional[str] = None) -> List[Order]:
        """Get all active orders"""
        orders = [o for o in self._orders.values() if o.is_active]
        
        if connection_id:
            orders = [o for o in orders if o.connection_id == connection_id]
        
        return orders
    
    # ===========================================
    # Fill Queries
    # ===========================================
    
    def get_fill(self, fill_id: str) -> Optional[Fill]:
        """Get fill by ID"""
        return self._fills.get(fill_id)
    
    def get_fills(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Fill]:
        """Get fills with filters"""
        if order_id and order_id in self._fills_by_order:
            fill_ids = self._fills_by_order[order_id]
            fills = [self._fills[fid] for fid in fill_ids]
        else:
            fills = list(self._fills.values())
        
        if symbol:
            fills = [f for f in fills if f.symbol == symbol]
        
        # Sort by timestamp desc
        fills = sorted(fills, key=lambda f: f.timestamp, reverse=True)
        
        return fills[:limit]
    
    # ===========================================
    # Trade Queries
    # ===========================================
    
    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID"""
        return self._trades.get(trade_id)
    
    def get_trades(
        self,
        connection_id: Optional[str] = None,
        symbol: Optional[str] = None,
        is_open: Optional[bool] = None,
        limit: int = 100
    ) -> List[Trade]:
        """Get trades with filters"""
        trades = list(self._trades.values())
        
        if connection_id:
            trades = [t for t in trades if t.connection_id == connection_id]
        
        if symbol:
            trades = [t for t in trades if t.symbol == symbol]
        
        if is_open is not None:
            trades = [t for t in trades if t.is_open == is_open]
        
        # Sort by open_time desc
        trades = sorted(trades, key=lambda t: t.open_time, reverse=True)
        
        return trades[:limit]
    
    def get_open_trades(self) -> List[Trade]:
        """Get all open trades"""
        return [self._trades[tid] for tid in self._open_trades.values()]
    
    # ===========================================
    # Statistics
    # ===========================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get OMS statistics"""
        return {
            **self._stats,
            "active_orders": len([o for o in self._orders.values() if o.is_active]),
            "total_orders": len(self._orders),
            "total_fills": len(self._fills),
            "total_trades": len(self._trades),
            "open_trades": len(self._open_trades)
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Get OMS health status"""
        return {
            "enabled": True,
            "version": "oms_t2",
            "status": "ok",
            "stats": self.get_stats(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ===========================================
# Global Instance
# ===========================================

order_service = OrderService()


# Convenience functions
async def place_order(
    connection_id: str,
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    quantity: float,
    **kwargs
) -> Order:
    return await order_service.place_order(
        connection_id, symbol, side, order_type, quantity, **kwargs
    )


async def cancel_order(
    order_id: Optional[str] = None,
    client_order_id: Optional[str] = None
) -> Order:
    return await order_service.cancel_order(order_id, client_order_id)


def get_order(
    order_id: Optional[str] = None,
    client_order_id: Optional[str] = None
) -> Optional[Order]:
    return order_service.get_order(order_id, client_order_id)


def get_orders(**kwargs) -> List[Order]:
    return order_service.get_orders(**kwargs)


def get_fills(**kwargs) -> List[Fill]:
    return order_service.get_fills(**kwargs)


def get_trades(**kwargs) -> List[Trade]:
    return order_service.get_trades(**kwargs)
