"""
Mock Broker Adapter
===================

Mock adapter for testing and simulation.
Simulates broker operations without real API calls.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import random
import asyncio

from .base_adapter import (
    BaseBrokerAdapter,
    BrokerCredentials,
    BrokerStatus,
    OrderSide,
    OrderType,
    OrderStatus,
    TimeInForce,
    Order,
    Position,
    Balance,
    Ticker,
    OrderError,
    InsufficientFundsError
)


class MockAdapter(BaseBrokerAdapter):
    """
    Mock broker adapter for testing.
    
    Simulates:
    - Balance management
    - Order placement/cancellation
    - Position tracking
    - Market data
    """
    
    def __init__(self, credentials: BrokerCredentials, initial_balance: float = 100000.0):
        super().__init__(credentials)
        
        # Simulated state
        self._balances: Dict[str, Balance] = {
            "USDT": Balance(asset="USDT", free=initial_balance, locked=0.0, usd_value=initial_balance),
            "BTC": Balance(asset="BTC", free=0.0, locked=0.0, usd_value=0.0),
            "ETH": Balance(asset="ETH", free=0.0, locked=0.0, usd_value=0.0)
        }
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Order] = {}
        self._order_counter = 0
        
        # Simulated prices
        self._prices: Dict[str, float] = {
            "BTCUSDT": 65000.0,
            "ETHUSDT": 3500.0,
            "BNBUSDT": 450.0,
            "SOLUSDT": 150.0
        }
        
        # Execution delay simulation (ms)
        self._execution_delay = 50
    
    @property
    def broker_name(self) -> str:
        return "mock"
    
    @property
    def supports_futures(self) -> bool:
        return True
    
    @property
    def supports_margin(self) -> bool:
        return True
    
    # ===========================================
    # Connection
    # ===========================================
    
    async def connect(self) -> bool:
        """Simulate connection"""
        self.status = BrokerStatus.CONNECTING
        await asyncio.sleep(0.1)  # Simulate network delay
        self.status = BrokerStatus.CONNECTED
        self.connected_at = datetime.now(timezone.utc)
        return True
    
    async def disconnect(self) -> bool:
        """Simulate disconnection"""
        self.status = BrokerStatus.DISCONNECTED
        self.connected_at = None
        return True
    
    async def is_connected(self) -> bool:
        """Check connection status"""
        return self.status == BrokerStatus.CONNECTED
    
    # ===========================================
    # Account
    # ===========================================
    
    async def get_balance(self, asset: Optional[str] = None) -> List[Balance]:
        """Get simulated balances"""
        self._increment_request_count()
        
        if asset:
            if asset in self._balances:
                return [self._balances[asset]]
            return []
        
        return [b for b in self._balances.values() if b.total > 0]
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get simulated positions"""
        self._increment_request_count()
        
        if symbol:
            if symbol in self._positions:
                return [self._positions[symbol]]
            return []
        
        return list(self._positions.values())
    
    # ===========================================
    # Market Data
    # ===========================================
    
    async def get_ticker(self, symbol: str) -> Ticker:
        """Get simulated ticker"""
        self._increment_request_count()
        
        base_price = self._prices.get(symbol, 100.0)
        
        # Add some randomness
        spread_bps = random.uniform(1, 5)  # 1-5 bps spread
        spread = base_price * spread_bps / 10000
        
        bid = base_price - spread / 2
        ask = base_price + spread / 2
        
        return Ticker(
            symbol=symbol,
            bid=bid,
            ask=ask,
            last=base_price,
            volume_24h=random.uniform(1000000, 50000000),
            change_24h=random.uniform(-0.05, 0.05),
            high_24h=base_price * 1.02,
            low_24h=base_price * 0.98
        )
    
    async def get_tickers(self, symbols: Optional[List[str]] = None) -> List[Ticker]:
        """Get multiple tickers"""
        self._increment_request_count()
        
        if symbols is None:
            symbols = list(self._prices.keys())
        
        tickers = []
        for symbol in symbols:
            ticker = await self.get_ticker(symbol)
            tickers.append(ticker)
        
        return tickers
    
    # ===========================================
    # Orders
    # ===========================================
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_order_id: Optional[str] = None
    ) -> Order:
        """Place simulated order"""
        self._increment_request_count()
        
        # Get current price
        current_price = self._prices.get(symbol, 100.0)
        
        # Calculate order value
        execution_price = price if price and order_type == OrderType.LIMIT else current_price
        order_value = quantity * execution_price
        
        # Check balance
        if side == OrderSide.BUY:
            quote_asset = "USDT"  # Simplified
            if self._balances[quote_asset].free < order_value:
                raise InsufficientFundsError(
                    f"Insufficient {quote_asset} balance. Required: {order_value}, Available: {self._balances[quote_asset].free}"
                )
        
        # Create order
        self._order_counter += 1
        order = Order(
            id=client_order_id or f"mock_{self._order_counter}",
            broker_order_id=f"MOCK{self._order_counter:08d}",
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            status=OrderStatus.NEW
        )
        
        # Simulate execution delay
        await asyncio.sleep(self._execution_delay / 1000)
        
        # Market orders execute immediately
        if order_type == OrderType.MARKET:
            order = await self._execute_order(order, execution_price)
        else:
            # Limit orders stay pending
            self._orders[order.id] = order
        
        return order
    
    async def _execute_order(self, order: Order, price: float) -> Order:
        """Execute order (fill simulation)"""
        
        # Add slippage for market orders
        slippage_bps = random.uniform(0, 3)  # 0-3 bps
        slippage = price * slippage_bps / 10000
        
        if order.side == OrderSide.BUY:
            fill_price = price + slippage
        else:
            fill_price = price - slippage
        
        # Update order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.commission = order.quantity * fill_price * 0.001  # 0.1% commission
        order.commission_asset = "USDT"
        order.updated_at = datetime.now(timezone.utc)
        
        # Update balances
        await self._update_balances(order)
        
        # Store order
        self._orders[order.id] = order
        
        return order
    
    async def _update_balances(self, order: Order):
        """Update balances after order fill"""
        
        # Extract base asset from symbol (simplified)
        base_asset = order.symbol.replace("USDT", "")
        quote_asset = "USDT"
        
        order_value = order.filled_quantity * order.avg_fill_price
        
        if order.side == OrderSide.BUY:
            # Deduct quote, add base
            self._balances[quote_asset].free -= order_value + order.commission
            
            if base_asset not in self._balances:
                self._balances[base_asset] = Balance(asset=base_asset, free=0.0, locked=0.0)
            
            self._balances[base_asset].free += order.filled_quantity
        else:
            # Deduct base, add quote
            if base_asset in self._balances:
                self._balances[base_asset].free -= order.filled_quantity
            
            self._balances[quote_asset].free += order_value - order.commission
        
        # Update totals
        for balance in self._balances.values():
            balance.total = balance.free + balance.locked
    
    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """Cancel simulated order"""
        self._increment_request_count()
        
        # Find order
        lookup_id = order_id or client_order_id
        
        if lookup_id not in self._orders:
            raise OrderError(f"Order not found: {lookup_id}")
        
        order = self._orders[lookup_id]
        
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED]:
            raise OrderError(f"Cannot cancel order in status: {order.status.value}")
        
        order.status = OrderStatus.CANCELED
        order.updated_at = datetime.now(timezone.utc)
        
        return order
    
    async def get_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """Get order details"""
        self._increment_request_count()
        
        lookup_id = order_id or client_order_id
        
        if lookup_id not in self._orders:
            raise OrderError(f"Order not found: {lookup_id}")
        
        return self._orders[lookup_id]
    
    async def get_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100
    ) -> List[Order]:
        """Get list of orders"""
        self._increment_request_count()
        
        orders = list(self._orders.values())
        
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        
        if status:
            orders = [o for o in orders if o.status == status]
        
        # Sort by created_at desc
        orders = sorted(orders, key=lambda o: o.created_at, reverse=True)
        
        return orders[:limit]
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Cancel all open orders"""
        self._increment_request_count()
        
        cancelled = []
        
        for order in self._orders.values():
            if symbol and order.symbol != symbol:
                continue
            
            if order.status in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
                order.status = OrderStatus.CANCELED
                order.updated_at = datetime.now(timezone.utc)
                cancelled.append(order)
        
        return cancelled
    
    # ===========================================
    # Mock-specific methods
    # ===========================================
    
    def set_price(self, symbol: str, price: float):
        """Set simulated price for testing"""
        self._prices[symbol] = price
    
    def set_balance(self, asset: str, free: float, locked: float = 0.0):
        """Set simulated balance for testing"""
        self._balances[asset] = Balance(
            asset=asset,
            free=free,
            locked=locked,
            total=free + locked,
            usd_value=free + locked if asset == "USDT" else 0.0
        )
    
    def get_fill_history(self) -> List[Order]:
        """Get all filled orders"""
        return [o for o in self._orders.values() if o.status == OrderStatus.FILLED]
