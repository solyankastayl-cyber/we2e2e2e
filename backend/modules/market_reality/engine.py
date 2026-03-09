"""
Market Reality Layer Engine
===========================

Realistic market simulation that can radically change strategy results.

Models:
- Order book dynamics
- Slippage (volume-based, volatility-based, impact model)
- Latency simulation
- Queue priority
- Partial fills
- Market impact
- Gap events

This is the layer that separates backtest from reality.
"""

import time
import uuid
import random
import math
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .types import (
    OrderType, OrderSide, FillStatus, SlippageModel,
    OrderBookLevel, OrderBook, SimulatedOrder, Fill,
    MarketImpactResult, GapEvent, RealityConfig, RealityMetrics
)

# Event Bus integration
try:
    from modules.event_bus import create_publisher, EventType
    _event_publisher = create_publisher("market_reality")
    EVENT_BUS_ENABLED = True
except ImportError:
    _event_publisher = None
    EVENT_BUS_ENABLED = False


class MarketRealityEngine:
    """
    Market Reality simulation engine.
    
    Simulates realistic execution conditions:
    - Slippage based on order size and market conditions
    - Latency variation
    - Partial fills and rejections
    - Market impact
    - Gap events
    """
    
    def __init__(self, config: RealityConfig = None):
        self.config = config or RealityConfig()
        self.metrics = RealityMetrics()
        
        # Order books (symbol -> OrderBook)
        self.order_books: Dict[str, OrderBook] = {}
        
        # Fill history
        self.fills: Dict[str, Fill] = {}
        
        # Gap events
        self.gap_events: List[GapEvent] = []
        
        # Volume tracking (symbol -> daily volume)
        self.daily_volumes: Dict[str, float] = defaultdict(float)
    
    # ============================================
    # Order Book Simulation
    # ============================================
    
    def generate_order_book(
        self,
        symbol: str,
        mid_price: float,
        spread_bps: float = 5.0,
        depth_levels: int = 10
    ) -> OrderBook:
        """Generate a simulated order book"""
        
        spread = mid_price * spread_bps / 10000
        half_spread = spread / 2
        
        # Generate bids (below mid)
        bids = []
        bid_price = mid_price - half_spread
        for i in range(depth_levels):
            size = random.uniform(0.5, 5.0) * (1 + i * 0.2)
            bids.append(OrderBookLevel(
                price=bid_price - (i * spread * 0.2),
                size=size,
                order_count=random.randint(1, 10)
            ))
        
        # Generate asks (above mid)
        asks = []
        ask_price = mid_price + half_spread
        for i in range(depth_levels):
            size = random.uniform(0.5, 5.0) * (1 + i * 0.2)
            asks.append(OrderBookLevel(
                price=ask_price + (i * spread * 0.2),
                size=size,
                order_count=random.randint(1, 10)
            ))
        
        order_book = OrderBook(
            symbol=symbol,
            timestamp=int(time.time() * 1000),
            bids=bids,
            asks=asks,
            mid_price=mid_price,
            spread=spread,
            spread_bps=spread_bps
        )
        
        self.order_books[symbol] = order_book
        return order_book
    
    def get_order_book(self, symbol: str) -> Optional[OrderBook]:
        return self.order_books.get(symbol)
    
    # ============================================
    # Order Execution Simulation
    # ============================================
    
    def simulate_execution(
        self,
        order: SimulatedOrder,
        current_price: float,
        current_volume: float,
        volatility: float = 0.02
    ) -> Fill:
        """
        Simulate realistic order execution.
        
        Args:
            order: Order to execute
            current_price: Current market price
            current_volume: Current candle volume
            volatility: Current volatility (for slippage)
        """
        self.metrics.total_orders += 1
        
        # 1. Calculate latency
        latency_ms = self._simulate_latency()
        
        # 2. Check fill probability (for limit orders)
        if order.order_type == OrderType.LIMIT:
            if random.random() > self.config.limit_fill_probability:
                return self._create_rejected_fill(order, latency_ms, "Limit not filled")
        
        # 3. Calculate slippage
        slippage = self._calculate_slippage(
            order=order,
            current_price=current_price,
            volume=current_volume,
            volatility=volatility
        )
        
        # 4. Determine fill price
        if order.side == OrderSide.BUY:
            filled_price = current_price + slippage
        else:
            filled_price = current_price - slippage
        
        # 5. Check for partial fill
        filled_size = order.size
        status = FillStatus.FULL
        
        if random.random() < self.config.partial_fill_probability:
            filled_size = order.size * random.uniform(0.3, 0.9)
            status = FillStatus.PARTIAL
            self.metrics.partial_fills += 1
        
        # 6. Calculate market impact
        market_impact = self._calculate_market_impact(
            size=order.size,
            volume=current_volume,
            price=current_price
        )
        
        # 7. Create fill
        fill = Fill.create(
            order=order,
            status=status,
            filled_size=filled_size,
            filled_price=filled_price,
            slippage=slippage,
            latency_ms=latency_ms
        )
        fill.market_impact = market_impact.total_impact
        
        # Update metrics
        self._update_fill_metrics(fill)
        
        # Store fill
        self.fills[fill.fill_id] = fill
        
        # Publish event
        if EVENT_BUS_ENABLED and _event_publisher:
            _event_publisher.publish(
                "trade_opened" if order.side == OrderSide.BUY else "trade_closed",
                {
                    "order_id": order.order_id,
                    "fill_id": fill.fill_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "size": filled_size,
                    "price": filled_price,
                    "slippage_bps": fill.slippage_bps
                }
            )
        
        return fill
    
    def _simulate_latency(self) -> float:
        """Simulate execution latency"""
        latency = self.config.base_latency_ms + random.gauss(0, self.config.latency_std_ms)
        return max(1, min(latency, self.config.max_latency_ms))
    
    def _calculate_slippage(
        self,
        order: SimulatedOrder,
        current_price: float,
        volume: float,
        volatility: float
    ) -> float:
        """Calculate slippage based on model"""
        
        model = self.config.slippage_model
        
        if model == SlippageModel.FIXED:
            slippage_bps = self.config.base_slippage_bps
        
        elif model == SlippageModel.VOLUME_BASED:
            # Slippage increases with order size relative to volume
            participation = order.size / max(volume, 1)
            slippage_bps = self.config.base_slippage_bps * (
                1 + 10 * participation  # 10x multiplier for participation
            )
        
        elif model == SlippageModel.VOLATILITY_BASED:
            # Slippage increases with volatility
            vol_multiplier = volatility / 0.02  # 2% as baseline
            slippage_bps = self.config.base_slippage_bps * vol_multiplier
        
        elif model == SlippageModel.IMPACT_MODEL:
            # Square root market impact model
            participation = order.size / max(volume, 1)
            slippage_bps = (
                self.config.base_slippage_bps +
                self.config.impact_coefficient * math.sqrt(participation) * 10000
            )
        
        else:
            slippage_bps = self.config.base_slippage_bps
        
        # Cap slippage
        slippage_bps = min(slippage_bps, self.config.max_slippage_bps)
        
        # Convert to price
        slippage = current_price * slippage_bps / 10000
        
        return slippage
    
    def _calculate_market_impact(
        self,
        size: float,
        volume: float,
        price: float
    ) -> MarketImpactResult:
        """Calculate market impact using square root model"""
        
        participation = size / max(volume, 1)
        
        # Square root impact model: Impact = sigma * coefficient * sqrt(participation)
        total_impact_bps = self.config.impact_coefficient * math.sqrt(participation) * 10000
        total_impact = price * total_impact_bps / 10000
        
        # Split into temporary and permanent
        permanent_impact = total_impact * self.config.permanent_impact_ratio
        temporary_impact = total_impact - permanent_impact
        
        return MarketImpactResult(
            temporary_impact=temporary_impact,
            permanent_impact=permanent_impact,
            total_impact=total_impact,
            reversion_time_ms=random.randint(100, 5000)
        )
    
    def _create_rejected_fill(
        self,
        order: SimulatedOrder,
        latency_ms: float,
        reason: str
    ) -> Fill:
        """Create a rejected fill"""
        self.metrics.rejected_fills += 1
        
        fill = Fill(
            fill_id=f"fill_{uuid.uuid4().hex[:10]}",
            order_id=order.order_id,
            status=FillStatus.REJECTED,
            filled_size=0,
            filled_price=0,
            slippage=0,
            slippage_bps=0,
            latency_ms=latency_ms,
            queue_position=0,
            market_impact=0,
            timestamp=int(time.time() * 1000)
        )
        
        self.fills[fill.fill_id] = fill
        
        # Publish rejection event
        if EVENT_BUS_ENABLED and _event_publisher:
            _event_publisher.publish(
                "fill_rejected",
                {"order_id": order.order_id, "reason": reason}
            )
        
        return fill
    
    def _update_fill_metrics(self, fill: Fill):
        """Update metrics with fill data"""
        self.metrics.total_fills += 1
        
        self.metrics.total_slippage += fill.slippage_bps
        self.metrics.avg_slippage_bps = (
            self.metrics.total_slippage / self.metrics.total_fills
        )
        self.metrics.max_slippage_bps = max(
            self.metrics.max_slippage_bps, fill.slippage_bps
        )
        
        self.metrics.total_latency_ms += fill.latency_ms
        self.metrics.avg_latency_ms = (
            self.metrics.total_latency_ms / self.metrics.total_fills
        )
        self.metrics.max_latency_ms = max(
            self.metrics.max_latency_ms, fill.latency_ms
        )
        
        self.metrics.total_market_impact += fill.market_impact
    
    # ============================================
    # Gap Simulation
    # ============================================
    
    def check_for_gap(
        self,
        symbol: str,
        price_before: float,
        price_after: float
    ) -> Optional[GapEvent]:
        """Check if a price gap occurred"""
        
        gap_size = abs(price_after - price_before)
        gap_percent = gap_size / price_before
        
        # Check if this qualifies as a gap
        if gap_percent < self.config.avg_gap_size:
            return None
        
        gap_type = "UP" if price_after > price_before else "DOWN"
        
        gap = GapEvent(
            gap_id=f"gap_{uuid.uuid4().hex[:8]}",
            symbol=symbol,
            gap_type=gap_type,
            gap_size=gap_size,
            gap_percent=gap_percent,
            price_before=price_before,
            price_after=price_after,
            timestamp=int(time.time() * 1000)
        )
        
        self.gap_events.append(gap)
        self.metrics.gap_events += 1
        
        # Publish gap event
        if EVENT_BUS_ENABLED and _event_publisher:
            _event_publisher.publish(
                "gap_event_detected",
                gap.to_dict()
            )
        
        return gap
    
    def simulate_gap(
        self,
        symbol: str,
        current_price: float
    ) -> Optional[GapEvent]:
        """Randomly simulate a gap event"""
        
        if random.random() > self.config.gap_probability:
            return None
        
        gap_percent = random.uniform(
            self.config.avg_gap_size * 0.5,
            self.config.avg_gap_size * 2.0
        )
        
        gap_direction = random.choice([1, -1])
        price_after = current_price * (1 + gap_direction * gap_percent)
        
        return self.check_for_gap(symbol, current_price, price_after)
    
    # ============================================
    # Batch Simulation
    # ============================================
    
    def simulate_trade_series(
        self,
        trades: List[Dict[str, Any]],
        prices: List[float],
        volumes: List[float]
    ) -> Dict[str, Any]:
        """
        Simulate a series of trades with realistic execution.
        
        Args:
            trades: List of trade dicts with {symbol, side, size}
            prices: Price at each trade
            volumes: Volume at each trade
        
        Returns:
            Summary of execution results
        """
        fills = []
        total_slippage_cost = 0.0
        
        for i, trade in enumerate(trades):
            price = prices[i] if i < len(prices) else prices[-1]
            volume = volumes[i] if i < len(volumes) else volumes[-1]
            
            order = SimulatedOrder.create(
                symbol=trade.get("symbol", "BTCUSDT"),
                side=OrderSide(trade.get("side", "BUY")),
                order_type=OrderType.MARKET,
                size=trade.get("size", 1.0)
            )
            
            fill = self.simulate_execution(order, price, volume)
            fills.append(fill)
            
            if fill.status != FillStatus.REJECTED:
                total_slippage_cost += fill.slippage * fill.filled_size
        
        return {
            "total_trades": len(trades),
            "successful_fills": sum(1 for f in fills if f.status != FillStatus.REJECTED),
            "partial_fills": sum(1 for f in fills if f.status == FillStatus.PARTIAL),
            "rejected_fills": sum(1 for f in fills if f.status == FillStatus.REJECTED),
            "total_slippage_cost": total_slippage_cost,
            "avg_slippage_bps": sum(f.slippage_bps for f in fills) / len(fills) if fills else 0,
            "fills": [f.to_dict() for f in fills]
        }
    
    # ============================================
    # Getters
    # ============================================
    
    def get_fill(self, fill_id: str) -> Optional[Fill]:
        return self.fills.get(fill_id)
    
    def get_recent_fills(self, limit: int = 50) -> List[Fill]:
        sorted_fills = sorted(
            self.fills.values(),
            key=lambda f: f.timestamp,
            reverse=True
        )
        return sorted_fills[:limit]
    
    def get_gap_events(self, limit: int = 20) -> List[GapEvent]:
        return list(reversed(self.gap_events[-limit:]))
    
    def get_metrics(self) -> RealityMetrics:
        return self.metrics
    
    def get_health(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "version": "market_reality_v1",
            "status": "ok",
            "config": self.config.to_dict(),
            "metrics": self.metrics.to_dict(),
            "order_books_count": len(self.order_books),
            "total_fills": len(self.fills),
            "gap_events": len(self.gap_events)
        }
    
    def reset_metrics(self):
        """Reset metrics"""
        self.metrics = RealityMetrics()


# Singleton instance
market_reality_engine = MarketRealityEngine()
