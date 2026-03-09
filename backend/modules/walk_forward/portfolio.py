"""
Walk-Forward Portfolio Manager
==============================

Manages portfolio state during simulation:
- Position tracking
- Equity calculation
- Drawdown monitoring
- Risk limits
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import math

from .types import (
    Trade, Signal, Candle, PortfolioState,
    WalkForwardConfig
)


@dataclass
class Position:
    trade_id: str
    strategy_id: str
    direction: str
    entry_price: float
    entry_time: int
    size: float
    stop_loss: float
    take_profit: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    max_favorable: float = 0.0
    max_adverse: float = 0.0
    bars_held: int = 0


class WalkForwardPortfolio:
    """Portfolio state manager for walk-forward simulation"""
    
    def __init__(self, config: WalkForwardConfig):
        self.config = config
        self.initial_capital = config.initial_capital
        
        # Core state
        self.cash = config.initial_capital
        self.equity = config.initial_capital
        self.peak_equity = config.initial_capital
        self.drawdown = 0.0
        self.drawdown_pct = 0.0
        
        # Positions
        self.positions: Dict[str, Position] = {}
        
        # Strategy weights (from meta-strategy)
        self.strategy_weights: Dict[str, float] = {}
        self.family_budgets: Dict[str, float] = {}
        
        # Risk state
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.kill_switch_active = False
        
        # History
        self.equity_history: List[Dict[str, Any]] = []
        self.trade_history: List[Trade] = []
        
    def update_prices(self, candle: Candle) -> None:
        """Update position prices with new candle"""
        total_positions_value = 0.0
        
        for pos_id, pos in self.positions.items():
            pos.current_price = candle.close
            pos.bars_held += 1
            
            # Calculate unrealized PnL
            if pos.direction == "LONG":
                pos.unrealized_pnl = (candle.close - pos.entry_price) * pos.size
                # Track MFE/MAE
                favorable = (candle.high - pos.entry_price) * pos.size
                adverse = (pos.entry_price - candle.low) * pos.size
            else:
                pos.unrealized_pnl = (pos.entry_price - candle.close) * pos.size
                favorable = (pos.entry_price - candle.low) * pos.size
                adverse = (candle.high - pos.entry_price) * pos.size
            
            pos.max_favorable = max(pos.max_favorable, favorable)
            pos.max_adverse = max(pos.max_adverse, adverse)
            
            total_positions_value += pos.unrealized_pnl
        
        # Update equity
        self.equity = self.cash + total_positions_value
        
        # Update peak and drawdown
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
            self.drawdown = 0.0
            self.drawdown_pct = 0.0
        else:
            self.drawdown = self.peak_equity - self.equity
            self.drawdown_pct = self.drawdown / self.peak_equity if self.peak_equity > 0 else 0.0
    
    def can_open_position(self, signal: Signal) -> bool:
        """Check if we can open a new position"""
        # Max positions limit
        if len(self.positions) >= self.config.max_positions:
            return False
        
        # Kill switch check
        if self.kill_switch_active:
            return False
        
        # Minimum equity check - don't trade if equity too low
        if self.equity < self.initial_capital * 0.2:  # Below 20% of initial
            return False
        
        # Strategy weight check
        strategy_weight = self.strategy_weights.get(signal.strategy_id, 0.5)
        if strategy_weight < 0.1:
            return False
        
        # Risk check - enough cash (use max of equity or current cash)
        available = max(self.cash, self.equity * 0.5)
        position_value = self.equity * self.config.position_size_pct
        if position_value > available:
            return False
        
        return True
    
    def open_position(self, signal: Signal, candle: Candle) -> Optional[Trade]:
        """Open a new position from signal"""
        if not self.can_open_position(signal):
            return None
        
        # Calculate position size with slippage
        slippage = signal.entry_price * (self.config.slippage_bps / 10000)
        if signal.direction == "LONG":
            entry_price = signal.entry_price + slippage
        else:
            entry_price = signal.entry_price - slippage
        
        # Calculate size based on risk
        risk_amount = self.equity * self.config.position_size_pct
        risk_per_unit = abs(entry_price - signal.stop_loss)
        
        if risk_per_unit <= 0:
            risk_per_unit = entry_price * 0.02  # Default 2% risk
        
        size = risk_amount / risk_per_unit
        position_value = size * entry_price
        
        # Fee
        fee = position_value * (self.config.fee_bps / 10000)
        
        # Create position
        trade_id = f"trade_{candle.timestamp}_{signal.strategy_id}"
        
        position = Position(
            trade_id=trade_id,
            strategy_id=signal.strategy_id,
            direction=signal.direction,
            entry_price=entry_price,
            entry_time=candle.timestamp,
            size=size,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            current_price=entry_price
        )
        
        self.positions[trade_id] = position
        self.cash -= (position_value + fee)
        
        # Create trade record
        trade = Trade(
            id=trade_id,
            signal_id=signal.id,
            strategy_id=signal.strategy_id,
            direction=signal.direction,
            entry_price=entry_price,
            entry_time=candle.timestamp,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            size=size,
            regime=signal.regime
        )
        
        return trade
    
    def check_exits(self, candle: Candle) -> List[Trade]:
        """Check for position exits (SL/TP hits)"""
        closed_trades = []
        positions_to_close = []
        
        for pos_id, pos in self.positions.items():
            exit_price = None
            exit_reason = None
            
            if pos.direction == "LONG":
                # Check stop loss
                if candle.low <= pos.stop_loss:
                    exit_price = pos.stop_loss
                    exit_reason = "SL"
                # Check take profit
                elif candle.high >= pos.take_profit:
                    exit_price = pos.take_profit
                    exit_reason = "TP"
            else:  # SHORT
                # Check stop loss
                if candle.high >= pos.stop_loss:
                    exit_price = pos.stop_loss
                    exit_reason = "SL"
                # Check take profit
                elif candle.low <= pos.take_profit:
                    exit_price = pos.take_profit
                    exit_reason = "TP"
            
            if exit_price is not None:
                positions_to_close.append((pos_id, exit_price, exit_reason))
        
        # Close positions
        for pos_id, exit_price, exit_reason in positions_to_close:
            trade = self.close_position(pos_id, candle, exit_price, exit_reason)
            if trade:
                closed_trades.append(trade)
        
        return closed_trades
    
    def close_position(
        self, 
        position_id: str, 
        candle: Candle, 
        exit_price: float,
        exit_reason: str
    ) -> Optional[Trade]:
        """Close a position"""
        if position_id not in self.positions:
            return None
        
        pos = self.positions[position_id]
        
        # Apply slippage
        slippage = exit_price * (self.config.slippage_bps / 10000)
        if pos.direction == "LONG":
            final_exit_price = exit_price - slippage
        else:
            final_exit_price = exit_price + slippage
        
        # Calculate PnL
        if pos.direction == "LONG":
            pnl = (final_exit_price - pos.entry_price) * pos.size
        else:
            pnl = (pos.entry_price - final_exit_price) * pos.size
        
        # Fee
        position_value = pos.size * final_exit_price
        fee = position_value * (self.config.fee_bps / 10000)
        pnl -= fee
        
        # Update cash
        self.cash += position_value - fee
        
        # Calculate R-multiple
        risk_per_unit = abs(pos.entry_price - pos.stop_loss)
        if risk_per_unit > 0:
            r_multiple = pnl / (risk_per_unit * pos.size)
        else:
            r_multiple = 0.0
        
        # Determine outcome
        if pnl > 0:
            outcome = "WIN"
            self.consecutive_losses = 0
        elif pnl < 0:
            outcome = "LOSS"
            self.consecutive_losses += 1
        else:
            outcome = "BREAKEVEN"
        
        # Get decade from timestamp
        dt = datetime.utcfromtimestamp(candle.timestamp / 1000)
        decade = f"{(dt.year // 10) * 10}s"
        
        # Create trade result
        trade = Trade(
            id=pos.trade_id,
            signal_id="",
            strategy_id=pos.strategy_id,
            direction=pos.direction,
            entry_price=pos.entry_price,
            entry_time=pos.entry_time,
            exit_price=final_exit_price,
            exit_time=candle.timestamp,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            size=pos.size,
            pnl=pnl,
            pnl_pct=pnl / (pos.entry_price * pos.size) if pos.size > 0 else 0,
            r_multiple=r_multiple,
            outcome=outcome,
            exit_reason=exit_reason,
            regime="",  # Will be filled by engine
            decade=decade,
            bars_held=pos.bars_held,
            max_favorable=pos.max_favorable,
            max_adverse=pos.max_adverse
        )
        
        # Remove position
        del self.positions[position_id]
        
        # Update daily PnL
        self.daily_pnl += pnl
        
        # Add to history
        self.trade_history.append(trade)
        
        return trade
    
    def reset_daily(self) -> None:
        """Reset daily counters"""
        self.daily_pnl = 0.0
    
    def update_weights(
        self, 
        strategy_weights: Dict[str, float],
        family_budgets: Dict[str, float]
    ) -> None:
        """Update strategy weights from meta-strategy"""
        self.strategy_weights = strategy_weights.copy()
        self.family_budgets = family_budgets.copy()
    
    def activate_kill_switch(self) -> None:
        """Activate kill switch - no new trades"""
        self.kill_switch_active = True
    
    def deactivate_kill_switch(self) -> None:
        """Deactivate kill switch"""
        self.kill_switch_active = False
    
    def get_state(self, timestamp: int) -> PortfolioState:
        """Get current portfolio state"""
        positions_value = sum(pos.unrealized_pnl for pos in self.positions.values())
        
        return PortfolioState(
            timestamp=timestamp,
            equity=self.equity,
            cash=self.cash,
            positions_value=positions_value,
            open_positions=len(self.positions),
            drawdown=self.drawdown,
            drawdown_pct=self.drawdown_pct,
            peak_equity=self.peak_equity,
            strategy_weights=self.strategy_weights.copy(),
            family_budgets=self.family_budgets.copy()
        )
    
    def record_equity(self, timestamp: int, regime: str = "") -> None:
        """Record equity point for curve"""
        self.equity_history.append({
            "timestamp": timestamp,
            "equity": self.equity,
            "drawdown_pct": self.drawdown_pct,
            "positions": len(self.positions),
            "regime": regime
        })
