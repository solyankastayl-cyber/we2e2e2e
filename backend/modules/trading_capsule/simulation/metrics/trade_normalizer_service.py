"""
Trade Normalizer Service (S1.4A)
================================

Service for normalizing trade history from simulation artifacts.

Post-simulation analysis:
1. Get fills from broker
2. Build closed trades
3. Compute trade stats
4. Store for metrics engine
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import threading

from .trade_types import ClosedTrade, TradeStats, TradeSide
from .trade_builder import TradeBuilder, compute_trade_stats

from ..simulation_types import SimulationFill
from ..broker import simulated_broker_service


class TradeNormalizerService:
    """
    Service for normalizing simulation trades.
    
    Singleton that manages trade reconstruction per run.
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
        
        # Trade storage: run_id -> List[ClosedTrade]
        self._trades: Dict[str, List[ClosedTrade]] = {}
        
        # Stats cache: run_id -> TradeStats
        self._stats_cache: Dict[str, TradeStats] = {}
        
        self._initialized = True
        print("[TradeNormalizerService] Initialized")
    
    # ===========================================
    # Trade Normalization
    # ===========================================
    
    def normalize_trades(
        self,
        run_id: str,
        fills: Optional[List[SimulationFill]] = None,
        final_prices: Optional[Dict[str, float]] = None
    ) -> List[ClosedTrade]:
        """
        Normalize trades from fills.
        
        Args:
            run_id: Simulation run ID
            fills: Optional fills (will fetch from broker if not provided)
            final_prices: Final prices to close open positions
            
        Returns:
            List of closed trades
        """
        # Get fills from broker if not provided
        if fills is None:
            broker = simulated_broker_service.get_broker(run_id)
            if not broker:
                return []
            fills = broker.get_fills()
        
        if not fills:
            return []
        
        # Build trades
        builder = TradeBuilder(run_id)
        trades = builder.build_from_fills(fills, final_prices)
        
        # Store
        self._trades[run_id] = trades
        
        # Invalidate stats cache
        self._stats_cache.pop(run_id, None)
        
        print(f"[TradeNormalizer] Normalized {len(trades)} trades for run: {run_id}")
        return trades
    
    def normalize_from_broker(
        self,
        run_id: str,
        close_open_positions: bool = True
    ) -> List[ClosedTrade]:
        """
        Normalize trades from broker state.
        
        Convenience method that gets fills and final prices from broker.
        """
        broker = simulated_broker_service.get_broker(run_id)
        if not broker:
            return []
        
        fills = broker.get_fills()
        
        final_prices = None
        if close_open_positions:
            # Get final prices from broker's current prices
            account = broker.get_account_state()
            final_prices = {}
            for asset, pos in account.positions.items():
                if pos.current_price > 0:
                    final_prices[asset] = pos.current_price
        
        return self.normalize_trades(run_id, fills, final_prices)
    
    # ===========================================
    # Trade Queries
    # ===========================================
    
    def get_trades(self, run_id: str) -> List[ClosedTrade]:
        """Get normalized trades for run"""
        if run_id not in self._trades:
            # Try to normalize if not done yet
            self.normalize_from_broker(run_id)
        
        return self._trades.get(run_id, [])
    
    def get_trade(self, run_id: str, trade_id: str) -> Optional[ClosedTrade]:
        """Get specific trade"""
        trades = self.get_trades(run_id)
        for trade in trades:
            if trade.trade_id == trade_id:
                return trade
        return None
    
    def get_winning_trades(self, run_id: str) -> List[ClosedTrade]:
        """Get winning trades"""
        return [t for t in self.get_trades(run_id) if t.is_winner]
    
    def get_losing_trades(self, run_id: str) -> List[ClosedTrade]:
        """Get losing trades"""
        return [t for t in self.get_trades(run_id) if not t.is_winner]
    
    # ===========================================
    # Trade Statistics
    # ===========================================
    
    def get_trade_stats(self, run_id: str) -> TradeStats:
        """
        Get aggregate trade statistics.
        
        Cached for performance.
        """
        if run_id in self._stats_cache:
            return self._stats_cache[run_id]
        
        trades = self.get_trades(run_id)
        stats = compute_trade_stats(trades)
        
        # Cache
        self._stats_cache[run_id] = stats
        
        return stats
    
    def invalidate_cache(self, run_id: str) -> None:
        """Invalidate stats cache for run"""
        self._stats_cache.pop(run_id, None)
    
    # ===========================================
    # Summary
    # ===========================================
    
    def get_trade_summary(self, run_id: str) -> Dict[str, Any]:
        """Get full trade summary"""
        trades = self.get_trades(run_id)
        stats = self.get_trade_stats(run_id)
        
        return {
            "run_id": run_id,
            "trade_count": len(trades),
            "stats": stats.to_dict(),
            "trades": [t.to_dict() for t in trades]
        }
    
    # ===========================================
    # Cleanup
    # ===========================================
    
    def clear_run(self, run_id: str) -> None:
        """Clear trades for run"""
        self._trades.pop(run_id, None)
        self._stats_cache.pop(run_id, None)
    
    def clear_all(self) -> int:
        """Clear all trades"""
        count = len(self._trades)
        self._trades.clear()
        self._stats_cache.clear()
        return count


# Global singleton
trade_normalizer_service = TradeNormalizerService()
