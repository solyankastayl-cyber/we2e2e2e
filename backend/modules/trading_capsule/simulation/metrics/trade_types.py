"""
Trade Types (S1.4A)
===================

Type definitions for trade normalization.

Core entity: ClosedTrade
- Reconstructed from fills
- Contains entry/exit, PnL, duration
- Source of truth for all metrics
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid


class TradeSide(str, Enum):
    """Trade direction"""
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(str, Enum):
    """Trade lifecycle status"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class ClosedTrade:
    """
    Normalized closed trade.
    
    Reconstructed from fills. Contains all info needed for metrics.
    """
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    run_id: str = ""
    asset: str = ""
    
    # Direction
    side: TradeSide = TradeSide.LONG
    
    # Timing
    entry_time: str = ""
    exit_time: str = ""
    
    # Prices
    entry_price: float = 0.0
    exit_price: float = 0.0
    
    # Size
    quantity: float = 0.0
    
    # PnL
    gross_pnl_usd: float = 0.0
    fees_usd: float = 0.0
    net_pnl_usd: float = 0.0
    
    # Duration
    duration_bars: int = 0
    
    # Fill references
    entry_fill_ids: List[str] = field(default_factory=list)
    exit_fill_ids: List[str] = field(default_factory=list)
    
    # Metadata
    is_winner: bool = False
    return_pct: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "run_id": self.run_id,
            "asset": self.asset,
            "side": self.side.value,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry_price": round(self.entry_price, 8),
            "exit_price": round(self.exit_price, 8),
            "quantity": round(self.quantity, 8),
            "gross_pnl_usd": round(self.gross_pnl_usd, 2),
            "fees_usd": round(self.fees_usd, 4),
            "net_pnl_usd": round(self.net_pnl_usd, 2),
            "duration_bars": self.duration_bars,
            "is_winner": self.is_winner,
            "return_pct": round(self.return_pct, 4),
            "entry_fill_ids": self.entry_fill_ids,
            "exit_fill_ids": self.exit_fill_ids
        }


@dataclass
class OpenPosition:
    """
    Position state during trade reconstruction.
    
    Used internally by TradeBuilder.
    """
    asset: str
    side: TradeSide = TradeSide.LONG
    
    # Position tracking
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    total_entry_cost: float = 0.0
    
    # Timing
    entry_time: Optional[str] = None
    entry_bar_index: int = 0
    
    # Fees accumulated
    entry_fees: float = 0.0
    
    # Fill references
    fill_ids: List[str] = field(default_factory=list)
    
    def add_fill(
        self,
        quantity: float,
        price: float,
        fee: float,
        fill_id: str,
        timestamp: str,
        bar_index: int = 0
    ) -> None:
        """Add a fill to the position (averaging)"""
        if self.quantity == 0:
            # First fill - set entry time
            self.entry_time = timestamp
            self.entry_bar_index = bar_index
        
        # Update position with averaging
        old_cost = self.quantity * self.avg_entry_price
        new_cost = quantity * price
        self.total_entry_cost = old_cost + new_cost
        self.quantity += quantity
        
        if self.quantity > 0:
            self.avg_entry_price = self.total_entry_cost / self.quantity
        
        self.entry_fees += fee
        self.fill_ids.append(fill_id)
    
    def reduce_fill(
        self,
        quantity: float,
        price: float,
        fee: float,
        fill_id: str,
        timestamp: str,
        bar_index: int = 0
    ) -> Optional['ClosedTrade']:
        """
        Reduce position and potentially close trade.
        
        Returns ClosedTrade if position is fully closed.
        """
        if quantity >= self.quantity:
            # Full close
            exit_quantity = self.quantity
            self.quantity = 0
        else:
            # Partial close
            exit_quantity = quantity
            self.quantity -= quantity
        
        # Calculate PnL
        if self.side == TradeSide.LONG:
            gross_pnl = (price - self.avg_entry_price) * exit_quantity
        else:
            gross_pnl = (self.avg_entry_price - price) * exit_quantity
        
        # Create closed trade
        entry_notional = self.avg_entry_price * exit_quantity
        entry_fees_proportion = self.entry_fees * (exit_quantity / (exit_quantity + self.quantity)) if self.quantity > 0 else self.entry_fees
        total_fees = entry_fees_proportion + fee
        net_pnl = gross_pnl - total_fees
        
        trade = ClosedTrade(
            run_id="",  # Will be set by caller
            asset=self.asset,
            side=self.side,
            entry_time=self.entry_time or timestamp,
            exit_time=timestamp,
            entry_price=self.avg_entry_price,
            exit_price=price,
            quantity=exit_quantity,
            gross_pnl_usd=gross_pnl,
            fees_usd=total_fees,
            net_pnl_usd=net_pnl,
            duration_bars=bar_index - self.entry_bar_index,
            entry_fill_ids=self.fill_ids.copy(),
            exit_fill_ids=[fill_id],
            is_winner=net_pnl > 0,
            return_pct=(net_pnl / entry_notional) * 100 if entry_notional > 0 else 0
        )
        
        # If position fully closed, reset
        if self.quantity <= 0:
            self.quantity = 0
            self.avg_entry_price = 0
            self.total_entry_cost = 0
            self.entry_time = None
            self.entry_bar_index = 0
            self.entry_fees = 0
            self.fill_ids = []
        else:
            # Reduce proportionally for partial close
            self.entry_fees -= entry_fees_proportion
        
        return trade


@dataclass
class TradeStats:
    """
    Aggregate trade statistics.
    
    Computed from ClosedTrade list.
    """
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    win_rate: float = 0.0
    
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    
    avg_win: float = 0.0
    avg_loss: float = 0.0
    
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    profit_factor: float = 0.0
    expectancy: float = 0.0
    
    avg_duration_bars: float = 0.0
    total_fees: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "total_pnl": round(self.total_pnl, 2),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2),
            "profit_factor": round(self.profit_factor, 4),
            "expectancy": round(self.expectancy, 2),
            "avg_duration_bars": round(self.avg_duration_bars, 2),
            "total_fees": round(self.total_fees, 4)
        }
