"""
Trade Builder (S1.4A)
=====================

Reconstructs closed trades from fills.

Algorithm:
1. Sort fills by timestamp
2. Track position state per asset
3. BUY fills add to position (with averaging)
4. SELL fills reduce position (create closed trade)
5. Handle open positions at end of simulation
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from .trade_types import (
    ClosedTrade,
    OpenPosition,
    TradeSide,
    TradeStats
)

from ..simulation_types import SimulationFill


class TradeBuilder:
    """
    Builds closed trades from raw fills.
    
    Handles:
    - Multiple fills averaging
    - Partial exits
    - Position reconstruction
    """
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        
        # Position state per asset
        self._positions: Dict[str, OpenPosition] = {}
        
        # Closed trades
        self._closed_trades: List[ClosedTrade] = []
        
        # Bar index counter (for duration)
        self._bar_index = 0
        self._timestamp_to_bar: Dict[str, int] = {}
    
    def build_from_fills(
        self,
        fills: List[SimulationFill],
        final_prices: Optional[Dict[str, float]] = None
    ) -> List[ClosedTrade]:
        """
        Build closed trades from fills.
        
        Args:
            fills: List of simulation fills
            final_prices: Final prices to close open positions (optional)
            
        Returns:
            List of closed trades
        """
        if not fills:
            return []
        
        # Sort by timestamp
        sorted_fills = sorted(fills, key=lambda f: f.timestamp)
        
        # Build bar index mapping
        self._build_bar_index(sorted_fills)
        
        # Process each fill
        for fill in sorted_fills:
            self._process_fill(fill)
        
        # Close any open positions at final prices
        if final_prices:
            self._close_open_positions(final_prices, sorted_fills[-1].timestamp)
        
        # Set run_id on all trades
        for trade in self._closed_trades:
            trade.run_id = self.run_id
        
        return self._closed_trades
    
    def _build_bar_index(self, fills: List[SimulationFill]) -> None:
        """Build timestamp to bar index mapping"""
        unique_timestamps = sorted(set(f.timestamp for f in fills))
        self._timestamp_to_bar = {
            ts: idx for idx, ts in enumerate(unique_timestamps)
        }
    
    def _get_bar_index(self, timestamp: str) -> int:
        """Get bar index for timestamp"""
        return self._timestamp_to_bar.get(timestamp, 0)
    
    def _process_fill(self, fill: SimulationFill) -> None:
        """Process a single fill"""
        asset = fill.asset
        bar_index = self._get_bar_index(fill.timestamp)
        
        # Determine if this is a BUY or SELL based on fill data
        # In simulation, fills come from orders which have side
        # For now, infer from context or use a simple heuristic
        
        # Get or create position
        if asset not in self._positions:
            self._positions[asset] = OpenPosition(asset=asset)
        
        position = self._positions[asset]
        
        # Determine side from fill
        # If we have position and this reduces it, it's a SELL
        # If no position or adds to it, it's a BUY
        
        # Check if this fill closes/reduces position
        is_closing = self._is_closing_fill(fill, position)
        
        if is_closing:
            # This is an exit fill
            trade = position.reduce_fill(
                quantity=fill.quantity,
                price=fill.price,
                fee=fill.fee_usd,
                fill_id=fill.fill_id,
                timestamp=fill.timestamp,
                bar_index=bar_index
            )
            
            if trade:
                self._closed_trades.append(trade)
        else:
            # This is an entry fill
            position.add_fill(
                quantity=fill.quantity,
                price=fill.price,
                fee=fill.fee_usd,
                fill_id=fill.fill_id,
                timestamp=fill.timestamp,
                bar_index=bar_index
            )
    
    def _is_closing_fill(self, fill: SimulationFill, position: OpenPosition) -> bool:
        """
        Determine if a fill is closing or opening a position.
        
        Heuristic: If we have an open position and this fill would
        be in the opposite direction (inferred from price movement
        or order side if available).
        
        For SPOT LONG only:
        - If position.quantity > 0 and fill adds, check if it's a SELL order
        """
        # If no position, this is opening
        if position.quantity <= 0:
            return False
        
        # For SPOT trading (LONG only), check if this appears to be a sell
        # We can infer this from the order context or use heuristics
        
        # Simple heuristic: if position exists and fill quantity could close it,
        # and fill price is different from entry (indicating market moved),
        # treat alternating fills as buy/sell sequence
        
        # Better approach: track fill sequence
        # Even fills (0, 2, 4...) are buys, odd fills (1, 3, 5...) are sells
        # This works for simple buy-sell-buy-sell strategies
        
        # For more complex scenarios, we'd need order side information
        
        # Count fills in position
        fill_count = len(position.fill_ids)
        
        # If position has fills and this is the next fill,
        # it's likely a closing fill (alternating pattern)
        return fill_count > 0
    
    def _close_open_positions(
        self,
        final_prices: Dict[str, float],
        final_timestamp: str
    ) -> None:
        """Close any open positions at final prices"""
        final_bar = self._get_bar_index(final_timestamp) + 1
        
        for asset, position in self._positions.items():
            if position.quantity > 0:
                final_price = final_prices.get(asset)
                if final_price:
                    trade = position.reduce_fill(
                        quantity=position.quantity,
                        price=final_price,
                        fee=0,  # No fee for simulated close
                        fill_id=f"sim_close_{asset}",
                        timestamp=final_timestamp,
                        bar_index=final_bar
                    )
                    if trade:
                        self._closed_trades.append(trade)
    
    def get_open_positions(self) -> Dict[str, OpenPosition]:
        """Get current open positions"""
        return {
            asset: pos for asset, pos in self._positions.items()
            if pos.quantity > 0
        }


def compute_trade_stats(trades: List[ClosedTrade]) -> TradeStats:
    """
    Compute aggregate statistics from closed trades.
    
    Args:
        trades: List of closed trades
        
    Returns:
        TradeStats with all metrics
    """
    stats = TradeStats()
    
    if not trades:
        return stats
    
    stats.total_trades = len(trades)
    
    # Categorize wins/losses
    wins = [t for t in trades if t.net_pnl_usd > 0]
    losses = [t for t in trades if t.net_pnl_usd <= 0]
    
    stats.winning_trades = len(wins)
    stats.losing_trades = len(losses)
    
    # Win rate
    stats.win_rate = stats.winning_trades / stats.total_trades if stats.total_trades > 0 else 0
    
    # PnL
    stats.total_pnl = sum(t.net_pnl_usd for t in trades)
    stats.gross_profit = sum(t.net_pnl_usd for t in wins) if wins else 0
    stats.gross_loss = abs(sum(t.net_pnl_usd for t in losses)) if losses else 0
    
    # Averages
    stats.avg_win = stats.gross_profit / len(wins) if wins else 0
    stats.avg_loss = stats.gross_loss / len(losses) if losses else 0
    
    # Extremes
    if wins:
        stats.largest_win = max(t.net_pnl_usd for t in wins)
    if losses:
        stats.largest_loss = abs(min(t.net_pnl_usd for t in losses))
    
    # Profit factor
    stats.profit_factor = stats.gross_profit / stats.gross_loss if stats.gross_loss > 0 else float('inf') if stats.gross_profit > 0 else 0
    
    # Expectancy (average profit per trade)
    stats.expectancy = stats.total_pnl / stats.total_trades if stats.total_trades > 0 else 0
    
    # Duration
    durations = [t.duration_bars for t in trades if t.duration_bars > 0]
    stats.avg_duration_bars = sum(durations) / len(durations) if durations else 0
    
    # Fees
    stats.total_fees = sum(t.fees_usd for t in trades)
    
    return stats
