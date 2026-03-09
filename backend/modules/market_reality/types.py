"""
Market Reality Layer Types
==========================

Realistic market simulation for strategy validation.

Models:
- Order book dynamics
- Latency impact
- Queue priority
- Partial fills
- Market impact
- Slippage models

This layer can RADICALLY change strategy results.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


class OrderType(str, Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(str, Enum):
    """Order side"""
    BUY = "BUY"
    SELL = "SELL"


class FillStatus(str, Enum):
    """Fill status"""
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class SlippageModel(str, Enum):
    """Slippage calculation models"""
    FIXED = "FIXED"              # Fixed % slippage
    VOLUME_BASED = "VOLUME_BASED"  # Based on trade size vs volume
    VOLATILITY_BASED = "VOLATILITY_BASED"  # Based on current volatility
    IMPACT_MODEL = "IMPACT_MODEL"  # Square root market impact


@dataclass
class OrderBookLevel:
    """Single level in order book"""
    price: float
    size: float
    order_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "price": self.price,
            "size": self.size,
            "order_count": self.order_count
        }


@dataclass
class OrderBook:
    """Order book snapshot"""
    symbol: str
    timestamp: int
    bids: List[OrderBookLevel]  # Sorted descending by price
    asks: List[OrderBookLevel]  # Sorted ascending by price
    mid_price: float
    spread: float
    spread_bps: float
    
    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0
    
    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0
    
    @property
    def bid_depth(self) -> float:
        return sum(level.size for level in self.bids)
    
    @property
    def ask_depth(self) -> float:
        return sum(level.size for level in self.asks)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "bids": [b.to_dict() for b in self.bids[:5]],
            "asks": [a.to_dict() for a in self.asks[:5]],
            "mid_price": self.mid_price,
            "spread": self.spread,
            "spread_bps": round(self.spread_bps, 2),
            "bid_depth": self.bid_depth,
            "ask_depth": self.ask_depth
        }


@dataclass
class SimulatedOrder:
    """Order to be simulated"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    size: float
    price: Optional[float] = None  # For limit orders
    stop_price: Optional[float] = None  # For stop orders
    time_in_force: str = "GTC"
    created_at: int = 0
    
    @classmethod
    def create(
        cls,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        size: float,
        price: float = None
    ) -> "SimulatedOrder":
        return cls(
            order_id=f"ord_{uuid.uuid4().hex[:12]}",
            symbol=symbol,
            side=side,
            order_type=order_type,
            size=size,
            price=price,
            created_at=int(datetime.now(timezone.utc).timestamp() * 1000)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "size": self.size,
            "price": self.price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force,
            "created_at": self.created_at
        }


@dataclass
class Fill:
    """Execution fill"""
    fill_id: str
    order_id: str
    status: FillStatus
    filled_size: float
    filled_price: float
    slippage: float
    slippage_bps: float
    latency_ms: float
    queue_position: int
    market_impact: float
    timestamp: int
    
    @classmethod
    def create(
        cls,
        order: SimulatedOrder,
        status: FillStatus,
        filled_size: float,
        filled_price: float,
        slippage: float,
        latency_ms: float
    ) -> "Fill":
        slippage_bps = 0
        if order.price and order.price > 0:
            slippage_bps = abs(filled_price - order.price) / order.price * 10000
        
        return cls(
            fill_id=f"fill_{uuid.uuid4().hex[:10]}",
            order_id=order.order_id,
            status=status,
            filled_size=filled_size,
            filled_price=filled_price,
            slippage=slippage,
            slippage_bps=slippage_bps,
            latency_ms=latency_ms,
            queue_position=0,
            market_impact=0,
            timestamp=int(datetime.now(timezone.utc).timestamp() * 1000)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "status": self.status.value,
            "filled_size": self.filled_size,
            "filled_price": round(self.filled_price, 6),
            "slippage": round(self.slippage, 6),
            "slippage_bps": round(self.slippage_bps, 2),
            "latency_ms": round(self.latency_ms, 2),
            "queue_position": self.queue_position,
            "market_impact": round(self.market_impact, 6),
            "timestamp": self.timestamp
        }


@dataclass
class MarketImpactResult:
    """Result of market impact calculation"""
    temporary_impact: float  # Price move that reverses
    permanent_impact: float  # Price move that persists
    total_impact: float
    reversion_time_ms: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "temporary_impact": round(self.temporary_impact, 6),
            "permanent_impact": round(self.permanent_impact, 6),
            "total_impact": round(self.total_impact, 6),
            "reversion_time_ms": self.reversion_time_ms
        }


@dataclass
class GapEvent:
    """Price gap event"""
    gap_id: str
    symbol: str
    gap_type: str  # UP, DOWN
    gap_size: float
    gap_percent: float
    price_before: float
    price_after: float
    timestamp: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "symbol": self.symbol,
            "gap_type": self.gap_type,
            "gap_size": round(self.gap_size, 4),
            "gap_percent": round(self.gap_percent, 4),
            "price_before": self.price_before,
            "price_after": self.price_after,
            "timestamp": self.timestamp
        }


@dataclass
class RealityConfig:
    """Configuration for market reality simulation"""
    # Slippage
    slippage_model: SlippageModel = SlippageModel.VOLUME_BASED
    base_slippage_bps: float = 2.0
    max_slippage_bps: float = 50.0
    
    # Latency
    base_latency_ms: float = 50.0
    latency_std_ms: float = 20.0
    max_latency_ms: float = 500.0
    
    # Fill probability
    limit_fill_probability: float = 0.8
    partial_fill_probability: float = 0.3
    
    # Market impact
    impact_coefficient: float = 0.1  # For square root model
    permanent_impact_ratio: float = 0.3
    
    # Gaps
    gap_probability: float = 0.02  # 2% of candles have gaps
    avg_gap_size: float = 0.01  # 1%
    
    # Capacity
    max_participation_rate: float = 0.1  # Max 10% of volume
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "slippage_model": self.slippage_model.value,
            "base_slippage_bps": self.base_slippage_bps,
            "max_slippage_bps": self.max_slippage_bps,
            "base_latency_ms": self.base_latency_ms,
            "latency_std_ms": self.latency_std_ms,
            "limit_fill_probability": self.limit_fill_probability,
            "partial_fill_probability": self.partial_fill_probability,
            "impact_coefficient": self.impact_coefficient,
            "gap_probability": self.gap_probability,
            "max_participation_rate": self.max_participation_rate
        }


@dataclass
class RealityMetrics:
    """Metrics from reality simulation"""
    total_orders: int = 0
    total_fills: int = 0
    partial_fills: int = 0
    rejected_fills: int = 0
    
    total_slippage: float = 0.0
    avg_slippage_bps: float = 0.0
    max_slippage_bps: float = 0.0
    
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    
    total_market_impact: float = 0.0
    gap_events: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_orders": self.total_orders,
            "total_fills": self.total_fills,
            "partial_fills": self.partial_fills,
            "rejected_fills": self.rejected_fills,
            "avg_slippage_bps": round(self.avg_slippage_bps, 2),
            "max_slippage_bps": round(self.max_slippage_bps, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "total_market_impact": round(self.total_market_impact, 6),
            "gap_events": self.gap_events
        }
