"""
Trade Simulator
===============

Honest and reusable trade simulation with:
- Fees
- Slippage
- Intrabar uncertainty policy
- Realistic fills
"""

import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .types import SimulatedTrade, AssetAdapter


@dataclass
class OpenPosition:
    """Tracks an open position"""
    position_id: str
    trade_id: str
    strategy_id: str
    
    side: str
    entry_price: float
    entry_bar: int
    entry_timestamp: int
    
    size: float
    stop_loss: float
    take_profit: float
    
    # Context
    regime_at_entry: str = ""
    risk_state_at_entry: str = ""
    strategy_health: float = 1.0
    overlay_multiplier: float = 1.0


class TradeSimulator:
    """
    Simulates trade execution with realistic assumptions.
    
    Features:
    - Fee calculation (maker/taker)
    - Slippage modeling
    - Position sizing after all multipliers
    - Exit condition checking (TP/SL/TIME/SIGNAL)
    """
    
    def __init__(self, adapter: AssetAdapter, initial_capital: float = 100000.0):
        self.adapter = adapter
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.peak_equity = initial_capital
        
        # Positions
        self.positions: Dict[str, OpenPosition] = {}
        self.trade_history: List[SimulatedTrade] = []
        
        # Tracking
        self.current_bar = 0
        self.total_fees = 0.0
        self.total_slippage = 0.0
        
        # Equity curve
        self.equity_history: List[Dict] = []
        
        # Streaks
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_winning_streak = 0
        self.max_losing_streak = 0
        
        # Kill switch
        self.kill_switch_active = False
    
    @property
    def drawdown(self) -> float:
        """Current drawdown in absolute terms"""
        return self.peak_equity - self.equity
    
    @property
    def drawdown_pct(self) -> float:
        """Current drawdown percentage"""
        if self.peak_equity <= 0:
            return 0.0
        return self.drawdown / self.peak_equity
    
    def calculate_slippage(self, price: float, side: str) -> float:
        """Calculate slippage based on execution profile"""
        slippage_pct = self.adapter.default_slippage_bps / 10000
        
        if side == "LONG":
            # Buy higher
            return price * (1 + slippage_pct)
        else:
            # Sell lower
            return price * (1 - slippage_pct)
    
    def calculate_fees(self, notional: float) -> float:
        """Calculate trading fees"""
        fee_pct = self.adapter.default_fee_bps / 10000
        return notional * fee_pct
    
    def can_open_position(self, signal_confidence: float = 0.5) -> Tuple[bool, str]:
        """Check if we can open a new position"""
        # Kill switch check
        if self.kill_switch_active:
            return False, "Kill switch active"
        
        # Max positions check
        if len(self.positions) >= 5:
            return False, "Max positions reached"
        
        # Drawdown check
        if self.drawdown_pct > self.adapter.max_drawdown_trigger:
            return False, f"Drawdown {self.drawdown_pct:.2%} exceeds trigger"
        
        # Minimum confidence
        if signal_confidence < 0.3:
            return False, "Signal confidence too low"
        
        return True, ""
    
    def calculate_position_size(
        self,
        signal_confidence: float,
        strategy_weight: float,
        overlay_multiplier: float,
        risk_per_trade: float = 0.02
    ) -> float:
        """
        Calculate position size with all multipliers applied.
        
        Formula:
        size = equity * max_position_pct * confidence * strategy_weight * overlay_mult
        """
        base_size = self.equity * self.adapter.max_position_pct
        
        size = (
            base_size *
            signal_confidence *
            strategy_weight *
            overlay_multiplier
        )
        
        # Minimum and maximum bounds
        min_size = self.equity * 0.01
        max_size = self.equity * self.adapter.max_position_pct
        
        return max(min_size, min(size, max_size))
    
    def open_position(
        self,
        run_id: str,
        asset: str,
        strategy_id: str,
        side: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        bar_index: int,
        timestamp: int,
        signal_confidence: float = 0.5,
        strategy_weight: float = 0.5,
        overlay_multiplier: float = 1.0,
        regime: str = "",
        risk_state: str = ""
    ) -> Optional[OpenPosition]:
        """Open a new position"""
        # Check if we can open
        can_open, reason = self.can_open_position(signal_confidence)
        if not can_open:
            return None
        
        # Calculate size
        size = self.calculate_position_size(
            signal_confidence,
            strategy_weight,
            overlay_multiplier
        )
        
        # Apply slippage to entry
        actual_entry = self.calculate_slippage(entry_price, side)
        
        # Calculate entry fees
        notional = size
        entry_fee = self.calculate_fees(notional)
        
        # Deduct fees from equity
        self.equity -= entry_fee
        self.total_fees += entry_fee
        
        # Create position
        position_id = f"pos_{uuid.uuid4().hex[:12]}"
        trade_id = f"trade_{uuid.uuid4().hex[:12]}"
        
        position = OpenPosition(
            position_id=position_id,
            trade_id=trade_id,
            strategy_id=strategy_id,
            side=side,
            entry_price=actual_entry,
            entry_bar=bar_index,
            entry_timestamp=timestamp,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            regime_at_entry=regime,
            risk_state_at_entry=risk_state,
            strategy_health=signal_confidence,
            overlay_multiplier=overlay_multiplier
        )
        
        self.positions[position_id] = position
        self.current_bar = bar_index
        
        return position
    
    def check_exits(
        self,
        run_id: str,
        asset: str,
        bar_index: int,
        timestamp: int,
        high: float,
        low: float,
        close: float,
        date_str: str
    ) -> List[SimulatedTrade]:
        """Check and execute exits for all positions"""
        closed_trades = []
        positions_to_close = []
        
        for pos_id, pos in self.positions.items():
            exit_price = None
            exit_reason = None
            
            if pos.side == "LONG":
                # Check stop loss
                if low <= pos.stop_loss:
                    exit_price = self.calculate_slippage(pos.stop_loss, "SHORT")
                    exit_reason = "SL"
                # Check take profit
                elif high >= pos.take_profit:
                    exit_price = self.calculate_slippage(pos.take_profit, "SHORT")
                    exit_reason = "TP"
            
            else:  # SHORT
                # Check stop loss
                if high >= pos.stop_loss:
                    exit_price = self.calculate_slippage(pos.stop_loss, "LONG")
                    exit_reason = "SL"
                # Check take profit
                elif low <= pos.take_profit:
                    exit_price = self.calculate_slippage(pos.take_profit, "LONG")
                    exit_reason = "TP"
            
            if exit_price is not None:
                positions_to_close.append((pos_id, exit_price, exit_reason, timestamp, date_str))
        
        # Close positions
        for pos_id, exit_price, exit_reason, ts, ds in positions_to_close:
            trade = self._close_position(
                run_id, asset, pos_id, exit_price, exit_reason, ts, ds
            )
            if trade:
                closed_trades.append(trade)
        
        return closed_trades
    
    def close_position(
        self,
        run_id: str,
        asset: str,
        position_id: str,
        exit_price: float,
        exit_reason: str,
        timestamp: int,
        date_str: str
    ) -> Optional[SimulatedTrade]:
        """Manually close a position"""
        return self._close_position(
            run_id, asset, position_id, exit_price, exit_reason, timestamp, date_str
        )
    
    def _close_position(
        self,
        run_id: str,
        asset: str,
        position_id: str,
        exit_price: float,
        exit_reason: str,
        timestamp: int,
        date_str: str
    ) -> Optional[SimulatedTrade]:
        """Internal position closing logic"""
        if position_id not in self.positions:
            return None
        
        pos = self.positions.pop(position_id)
        
        # Calculate P&L
        if pos.side == "LONG":
            raw_pnl = (exit_price - pos.entry_price) * pos.size / pos.entry_price
        else:
            raw_pnl = (pos.entry_price - exit_price) * pos.size / pos.entry_price
        
        # Exit fees
        exit_fee = self.calculate_fees(pos.size)
        self.total_fees += exit_fee
        
        # Net P&L
        net_pnl = raw_pnl - exit_fee
        
        # Update equity
        self.equity += net_pnl
        
        # Update peak
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        
        # Calculate R-multiple
        risk = abs(pos.entry_price - pos.stop_loss)
        r_multiple = (exit_price - pos.entry_price) / risk if risk > 0 else 0
        if pos.side == "SHORT":
            r_multiple = -r_multiple
        
        # Determine outcome
        if net_pnl > 0:
            outcome = "WIN"
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.max_winning_streak = max(self.max_winning_streak, self.consecutive_wins)
        elif net_pnl < 0:
            outcome = "LOSS"
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.max_losing_streak = max(self.max_losing_streak, self.consecutive_losses)
        else:
            outcome = "BREAKEVEN"
        
        # Create trade record
        trade = SimulatedTrade(
            trade_id=pos.trade_id,
            run_id=run_id,
            asset=asset,
            strategy_id=pos.strategy_id,
            entry_date="",  # Would need to track
            exit_date=date_str,
            entry_timestamp=pos.entry_timestamp,
            exit_timestamp=timestamp,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            size=pos.size,
            notional_value=pos.size,
            pnl=net_pnl,
            pnl_pct=net_pnl / pos.size if pos.size > 0 else 0,
            r_multiple=r_multiple,
            fees_paid=exit_fee,
            slippage_cost=0,  # Already in prices
            regime_at_entry=pos.regime_at_entry,
            risk_state_at_entry=pos.risk_state_at_entry,
            strategy_health_at_entry=pos.strategy_health,
            overlay_multiplier_at_entry=pos.overlay_multiplier,
            exit_reason=exit_reason,
            outcome=outcome
        )
        
        self.trade_history.append(trade)
        return trade
    
    def close_all_positions(
        self,
        run_id: str,
        asset: str,
        close_price: float,
        timestamp: int,
        date_str: str,
        reason: str = "END"
    ) -> List[SimulatedTrade]:
        """Close all open positions"""
        closed = []
        for pos_id in list(self.positions.keys()):
            trade = self._close_position(
                run_id, asset, pos_id, close_price, reason, timestamp, date_str
            )
            if trade:
                closed.append(trade)
        return closed
    
    def record_equity_point(self, bar_index: int, timestamp: int, regime: str):
        """Record equity for curve"""
        self.equity_history.append({
            "bar": bar_index,
            "timestamp": timestamp,
            "equity": self.equity,
            "drawdown_pct": self.drawdown_pct,
            "regime": regime,
            "positions": len(self.positions)
        })
    
    def activate_kill_switch(self):
        """Activate kill switch"""
        self.kill_switch_active = True
    
    def deactivate_kill_switch(self):
        """Deactivate kill switch"""
        self.kill_switch_active = False
    
    def reset(self):
        """Reset simulator"""
        self.equity = self.initial_capital
        self.peak_equity = self.initial_capital
        self.positions = {}
        self.trade_history = []
        self.equity_history = []
        self.total_fees = 0.0
        self.total_slippage = 0.0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_winning_streak = 0
        self.max_losing_streak = 0
        self.kill_switch_active = False
    
    def get_summary(self) -> Dict:
        """Get simulator summary"""
        return {
            "initial_capital": self.initial_capital,
            "current_equity": round(self.equity, 2),
            "peak_equity": round(self.peak_equity, 2),
            "drawdown_pct": round(self.drawdown_pct, 4),
            "total_trades": len(self.trade_history),
            "open_positions": len(self.positions),
            "total_fees": round(self.total_fees, 2),
            "max_winning_streak": self.max_winning_streak,
            "max_losing_streak": self.max_losing_streak,
            "kill_switch_active": self.kill_switch_active
        }
