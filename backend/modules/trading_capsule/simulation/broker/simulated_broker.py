"""
Simulated Broker Adapter (S1.3)
===============================

Simulated exchange adapter for simulation engine.

Simulates:
- Order submission
- Fill execution (market/limit)
- Position management
- Slippage model
- Fee calculation

Uses the SAME interface as real broker adapters.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import uuid
import threading

from ..simulation_types import (
    SimulationOrder,
    SimulationFill,
    SimulationPosition,
    MarketCandle
)


# ===========================================
# Fill Models
# ===========================================

class FillModel:
    """Base class for fill models"""
    
    def calculate_fill_price(
        self,
        order_type: str,
        side: str,
        order_price: Optional[float],
        candle: MarketCandle,
        size: float
    ) -> Optional[float]:
        """Calculate fill price. Returns None if order cannot be filled."""
        raise NotImplementedError


class InstantFillModel(FillModel):
    """
    Instant fill at candle close.
    
    Simple model for initial testing.
    """
    
    def calculate_fill_price(
        self,
        order_type: str,
        side: str,
        order_price: Optional[float],
        candle: MarketCandle,
        size: float
    ) -> Optional[float]:
        if order_type == "MARKET":
            return candle.close
        
        elif order_type == "LIMIT":
            if order_price is None:
                return None
            
            # Buy limit: fill if price touches or goes below limit
            if side == "BUY" and candle.low <= order_price:
                return order_price
            
            # Sell limit: fill if price touches or goes above limit
            if side == "SELL" and candle.high >= order_price:
                return order_price
        
        return None


class SlippageFillModel(FillModel):
    """
    Fill model with slippage simulation.
    
    Adds realistic slippage based on size and volatility.
    """
    
    def __init__(
        self,
        base_slippage_pct: float = 0.0005,  # 0.05% base slippage
        size_impact_factor: float = 0.0001   # Additional slippage per unit size
    ):
        self.base_slippage_pct = base_slippage_pct
        self.size_impact_factor = size_impact_factor
    
    def calculate_fill_price(
        self,
        order_type: str,
        side: str,
        order_price: Optional[float],
        candle: MarketCandle,
        size: float
    ) -> Optional[float]:
        base_price = None
        
        if order_type == "MARKET":
            base_price = candle.close
            
        elif order_type == "LIMIT":
            if order_price is None:
                return None
            
            if side == "BUY" and candle.low <= order_price:
                base_price = order_price
            elif side == "SELL" and candle.high >= order_price:
                base_price = order_price
        
        if base_price is None:
            return None
        
        # Calculate slippage
        slippage_pct = self.base_slippage_pct + (size * self.size_impact_factor)
        
        if side == "BUY":
            # Buyers get worse price (higher)
            return base_price * (1 + slippage_pct)
        else:
            # Sellers get worse price (lower)
            return base_price * (1 - slippage_pct)


# ===========================================
# Fee Calculator
# ===========================================

class FeeCalculator:
    """Calculates trading fees"""
    
    def __init__(
        self,
        maker_fee_pct: float = 0.001,  # 0.1%
        taker_fee_pct: float = 0.001   # 0.1%
    ):
        self.maker_fee_pct = maker_fee_pct
        self.taker_fee_pct = taker_fee_pct
    
    def calculate_fee(
        self,
        order_type: str,
        quantity: float,
        price: float
    ) -> float:
        """Calculate fee in USD"""
        notional = quantity * price
        
        if order_type == "LIMIT":
            return notional * self.maker_fee_pct
        else:  # MARKET
            return notional * self.taker_fee_pct


# ===========================================
# Simulated Account State
# ===========================================

@dataclass
class SimulatedAccountState:
    """Simulated account state for a run"""
    run_id: str
    
    # Cash
    cash_usd: float = 0.0
    
    # Positions: asset -> SimulationPosition
    positions: Dict[str, SimulationPosition] = field(default_factory=dict)
    
    # Orders: order_id -> SimulationOrder
    open_orders: Dict[str, SimulationOrder] = field(default_factory=dict)
    
    # History
    fills: List[SimulationFill] = field(default_factory=list)
    closed_orders: List[SimulationOrder] = field(default_factory=list)
    
    # PnL
    realized_pnl: float = 0.0
    
    def get_equity(self, current_prices: Dict[str, float]) -> float:
        """Calculate total equity"""
        equity = self.cash_usd
        
        for asset, position in self.positions.items():
            if position.size > 0:
                price = current_prices.get(asset, position.current_price)
                equity += position.size * price
        
        return equity
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "cash_usd": round(self.cash_usd, 2),
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "open_orders": len(self.open_orders),
            "total_fills": len(self.fills),
            "realized_pnl": round(self.realized_pnl, 2)
        }


# ===========================================
# Simulated Broker Adapter
# ===========================================

class SimulatedBrokerAdapter:
    """
    Simulated exchange adapter.
    
    Provides same interface as real broker adapters but
    executes against simulated state.
    """
    
    def __init__(
        self,
        run_id: str,
        initial_cash: float,
        fill_model: Optional[FillModel] = None,
        fee_calculator: Optional[FeeCalculator] = None
    ):
        self.run_id = run_id
        
        # Initialize account state
        self._account = SimulatedAccountState(
            run_id=run_id,
            cash_usd=initial_cash
        )
        
        # Fill model
        self._fill_model = fill_model or SlippageFillModel()
        
        # Fee calculator
        self._fee_calculator = fee_calculator or FeeCalculator()
        
        # Current market prices
        self._current_prices: Dict[str, float] = {}
        
        # Lock for thread safety
        self._lock = threading.Lock()
        
        print(f"[SimulatedBroker] Initialized for run: {run_id}")
    
    # ===========================================
    # Market Data
    # ===========================================
    
    def update_price(self, asset: str, candle: MarketCandle) -> None:
        """Update current price from candle"""
        with self._lock:
            self._current_prices[asset] = candle.close
            
            # Update position prices
            if asset in self._account.positions:
                pos = self._account.positions[asset]
                pos.current_price = candle.close
                self._update_unrealized_pnl(pos)
            
            # Try to fill pending limit orders
            self._process_pending_orders(asset, candle)
    
    # ===========================================
    # Order Management
    # ===========================================
    
    def submit_order(
        self,
        asset: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        timestamp: Optional[str] = None
    ) -> SimulationOrder:
        """
        Submit an order.
        
        For MARKET orders: attempts immediate fill
        For LIMIT orders: adds to pending orders
        """
        with self._lock:
            order = SimulationOrder(
                run_id=self.run_id,
                asset=asset,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status="NEW",
                created_at=timestamp or datetime.now(timezone.utc).isoformat()
            )
            
            if order_type == "MARKET":
                # Attempt immediate fill
                current_price = self._current_prices.get(asset)
                if current_price:
                    candle = MarketCandle(
                        timestamp=order.created_at,
                        open=current_price,
                        high=current_price,
                        low=current_price,
                        close=current_price
                    )
                    fill = self._try_fill_order(order, candle)
                    # Add filled order to closed orders
                    if fill and order.status == "FILLED":
                        self._account.closed_orders.append(order)
            else:
                # Add to pending orders
                self._account.open_orders[order.order_id] = order
            
            return order
    
    def cancel_order(self, order_id: str) -> Optional[SimulationOrder]:
        """Cancel an open order"""
        with self._lock:
            order = self._account.open_orders.pop(order_id, None)
            if order:
                order.status = "CANCELLED"
                self._account.closed_orders.append(order)
            return order
    
    def get_open_orders(self) -> List[SimulationOrder]:
        """Get all open orders"""
        return list(self._account.open_orders.values())
    
    # ===========================================
    # Fill Processing
    # ===========================================
    
    def _process_pending_orders(self, asset: str, candle: MarketCandle) -> List[SimulationFill]:
        """Process pending limit orders against new candle"""
        fills = []
        
        orders_to_remove = []
        
        for order_id, order in self._account.open_orders.items():
            if order.asset != asset:
                continue
            
            fill = self._try_fill_order(order, candle)
            if fill:
                fills.append(fill)
                orders_to_remove.append(order_id)
        
        # Remove filled orders
        for order_id in orders_to_remove:
            order = self._account.open_orders.pop(order_id)
            self._account.closed_orders.append(order)
        
        return fills
    
    def _try_fill_order(
        self,
        order: SimulationOrder,
        candle: MarketCandle
    ) -> Optional[SimulationFill]:
        """Try to fill an order"""
        fill_price = self._fill_model.calculate_fill_price(
            order.order_type,
            order.side,
            order.price,
            candle,
            order.quantity
        )
        
        if fill_price is None:
            return None
        
        # Calculate fee
        fee = self._fee_calculator.calculate_fee(
            order.order_type,
            order.quantity,
            fill_price
        )
        
        # Check if we have enough cash for BUY
        if order.side == "BUY":
            total_cost = (order.quantity * fill_price) + fee
            if total_cost > self._account.cash_usd:
                order.status = "REJECTED"
                return None
        
        # Create fill
        fill = SimulationFill(
            order_id=order.order_id,
            run_id=self.run_id,
            asset=order.asset,
            quantity=order.quantity,
            price=fill_price,
            fee_usd=fee,
            timestamp=candle.timestamp
        )
        
        # Update account state
        self._apply_fill(order, fill)
        
        # Store fill
        self._account.fills.append(fill)
        
        # Update order status
        order.status = "FILLED"
        order.filled_at = candle.timestamp
        
        return fill
    
    def _apply_fill(self, order: SimulationOrder, fill: SimulationFill) -> None:
        """Apply fill to account state"""
        asset = order.asset
        
        if order.side == "BUY":
            # Deduct cash
            total_cost = (fill.quantity * fill.price) + fill.fee_usd
            self._account.cash_usd -= total_cost
            
            # Update or create position
            if asset in self._account.positions:
                pos = self._account.positions[asset]
                # Average entry price
                old_notional = pos.size * pos.entry_price
                new_notional = fill.quantity * fill.price
                pos.size += fill.quantity
                pos.entry_price = (old_notional + new_notional) / pos.size if pos.size > 0 else 0
                pos.side = "LONG"
            else:
                self._account.positions[asset] = SimulationPosition(
                    run_id=self.run_id,
                    asset=asset,
                    side="LONG",
                    size=fill.quantity,
                    entry_price=fill.price,
                    current_price=fill.price
                )
        
        elif order.side == "SELL":
            if asset not in self._account.positions:
                return
            
            pos = self._account.positions[asset]
            
            # Calculate realized PnL
            pnl = (fill.price - pos.entry_price) * fill.quantity - fill.fee_usd
            self._account.realized_pnl += pnl
            
            # Add cash from sale
            self._account.cash_usd += (fill.quantity * fill.price) - fill.fee_usd
            
            # Update position
            pos.size -= fill.quantity
            
            if pos.size <= 0:
                pos.size = 0
                pos.side = "FLAT"
                pos.unrealized_pnl = 0
    
    def _update_unrealized_pnl(self, position: SimulationPosition) -> None:
        """Update unrealized PnL for position"""
        if position.size <= 0:
            position.unrealized_pnl = 0
            return
        
        if position.side == "LONG":
            position.unrealized_pnl = (position.current_price - position.entry_price) * position.size
        elif position.side == "SHORT":
            position.unrealized_pnl = (position.entry_price - position.current_price) * position.size
    
    # ===========================================
    # Account Queries
    # ===========================================
    
    def get_account_state(self) -> SimulatedAccountState:
        """Get current account state"""
        return self._account
    
    def get_cash(self) -> float:
        """Get available cash"""
        return self._account.cash_usd
    
    def get_equity(self) -> float:
        """Get total equity"""
        return self._account.get_equity(self._current_prices)
    
    def get_position(self, asset: str) -> Optional[SimulationPosition]:
        """Get position for asset"""
        return self._account.positions.get(asset)
    
    def get_all_positions(self) -> List[SimulationPosition]:
        """Get all positions"""
        return list(self._account.positions.values())
    
    def get_fills(self) -> List[SimulationFill]:
        """Get all fills"""
        return self._account.fills
    
    def get_realized_pnl(self) -> float:
        """Get realized PnL"""
        return self._account.realized_pnl
    
    def get_unrealized_pnl(self) -> float:
        """Get total unrealized PnL"""
        return sum(
            pos.unrealized_pnl 
            for pos in self._account.positions.values()
            if pos.size > 0
        )


# ===========================================
# Simulated Broker Service
# ===========================================

class SimulatedBrokerService:
    """
    Service for managing simulated brokers per run.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Broker storage: run_id -> SimulatedBrokerAdapter
        self._brokers: Dict[str, SimulatedBrokerAdapter] = {}
        
        self._initialized = True
        print("[SimulatedBrokerService] Initialized")
    
    def create_broker(
        self,
        run_id: str,
        initial_cash: float,
        fill_model: Optional[FillModel] = None,
        fee_calculator: Optional[FeeCalculator] = None
    ) -> SimulatedBrokerAdapter:
        """Create simulated broker for a run"""
        broker = SimulatedBrokerAdapter(
            run_id=run_id,
            initial_cash=initial_cash,
            fill_model=fill_model,
            fee_calculator=fee_calculator
        )
        
        self._brokers[run_id] = broker
        return broker
    
    def get_broker(self, run_id: str) -> Optional[SimulatedBrokerAdapter]:
        """Get broker for run"""
        return self._brokers.get(run_id)
    
    def delete_broker(self, run_id: str) -> bool:
        """Delete broker for run"""
        if run_id in self._brokers:
            del self._brokers[run_id]
            return True
        return False


# Global singleton
simulated_broker_service = SimulatedBrokerService()
