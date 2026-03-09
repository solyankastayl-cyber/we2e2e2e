"""
Phase 8.5: Real Data Simulation Engine
Runs simulation on real market data from Binance.
"""
import time
import math
import random
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from .types import (
    SimulationConfig,
    SimulationResult,
    Trade,
    TradeOutcome,
    FailureType,
    VALIDATION_CONFIG
)
from .market_data import market_data_router


class RealDataSimulator:
    """
    Real Data Simulation Engine.
    
    Uses actual Binance candles for backtesting.
    Applies strategy logic to real price action.
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or VALIDATION_CONFIG
        self._results: Dict[str, SimulationResult] = {}
    
    async def run(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        start_date: str = "2022-01-01",
        end_date: str = "2024-01-01",
        initial_capital: float = 100000.0,
        strategies: Optional[List[str]] = None
    ) -> SimulationResult:
        """
        Run simulation on real market data.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Start date
            end_date: End date
            initial_capital: Starting capital
            strategies: List of strategies to test
            
        Returns:
            SimulationResult with real data metrics
        """
        run_id = f"real_sim_{symbol}_{timeframe}_{int(time.time() * 1000)}"
        started_at = int(time.time() * 1000)
        
        config = SimulationConfig(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        
        # Fetch real candles from Coinbase
        candles = await market_data_router.fetch_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date
        )
        
        if not candles:
            return SimulationResult(
                run_id=run_id,
                config=config,
                status="FAILED",
                error="No candles fetched from Binance"
            )
        
        # Apply strategies to candles
        strategies = strategies or [
            "MTF_BREAKOUT",
            "LIQUIDITY_SWEEP", 
            "RANGE_REVERSAL",
            "MOMENTUM_CONTINUATION"
        ]
        
        trades = self._generate_trades_from_candles(candles, strategies, config)
        metrics = self._calculate_metrics(trades, config)
        regime_breakdown = self._calculate_regime_breakdown(trades, candles)
        strategy_breakdown = self._calculate_strategy_breakdown(trades)
        
        completed_at = int(time.time() * 1000)
        
        result = SimulationResult(
            run_id=run_id,
            config=config,
            trades=len(trades),
            wins=metrics["wins"],
            losses=metrics["losses"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            total_pnl=metrics["total_pnl"],
            total_r=metrics["total_r"],
            avg_r=metrics["avg_r"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            max_consecutive_wins=metrics["max_consecutive_wins"],
            max_consecutive_losses=metrics["max_consecutive_losses"],
            avg_trade_duration=metrics["avg_trade_duration"],
            best_trade_r=metrics["best_trade_r"],
            worst_trade_r=metrics["worst_trade_r"],
            regime_breakdown=regime_breakdown,
            strategy_breakdown=strategy_breakdown,
            trade_list=trades,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=completed_at - started_at,
            status="COMPLETED"
        )
        
        self._results[run_id] = result
        
        return result
    
    def get_result(self, run_id: str) -> Optional[SimulationResult]:
        """Get simulation result"""
        return self._results.get(run_id)
    
    def _generate_trades_from_candles(
        self,
        candles: List[Dict],
        strategies: List[str],
        config: SimulationConfig
    ) -> List[Trade]:
        """
        Generate trades from real candle data.
        Uses basic technical signals on real prices.
        """
        trades = []
        if len(candles) < 50:
            return trades
        
        # Calculate simple indicators
        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        volumes = [c["volume"] for c in candles]
        
        # Simple moving averages
        ma20 = self._sma(closes, 20)
        ma50 = self._sma(closes, 50)
        
        # ATR for stops
        atr = self._atr(highs, lows, closes, 14)
        
        # RSI
        rsi = self._rsi(closes, 14)
        
        # Scan for signals
        lookback = 50
        for i in range(lookback, len(candles) - 10):
            current_candle = candles[i]
            price = current_candle["close"]
            timestamp = current_candle["timestamp"]
            
            # Skip if no indicators
            if i >= len(ma20) or i >= len(ma50) or i >= len(atr) or i >= len(rsi):
                continue
            
            current_ma20 = ma20[i]
            current_ma50 = ma50[i]
            current_atr = atr[i] if atr[i] > 0 else price * 0.01
            current_rsi = rsi[i]
            
            # Signal generation based on strategy
            signal = None
            strategy_used = None
            
            # MTF Breakout - price breaks above MA50 with momentum
            if price > current_ma50 and closes[i-1] <= ma50[i-1] and current_rsi > 50:
                signal = "LONG"
                strategy_used = "MTF_BREAKOUT"
            
            # Range Reversal - RSI oversold/overbought
            elif current_rsi < 30 and price < current_ma20:
                signal = "LONG"
                strategy_used = "RANGE_REVERSAL"
            elif current_rsi > 70 and price > current_ma20:
                signal = "SHORT"
                strategy_used = "RANGE_REVERSAL"
            
            # Liquidity Sweep - wick rejection at levels
            elif self._is_liquidity_sweep(candles, i):
                signal = "LONG" if current_candle["close"] > current_candle["open"] else "SHORT"
                strategy_used = "LIQUIDITY_SWEEP"
            
            # Momentum Continuation - trend following
            elif price > current_ma20 > current_ma50 and current_rsi > 55:
                if random.random() < 0.3:  # Not every bar
                    signal = "LONG"
                    strategy_used = "MOMENTUM_CONTINUATION"
            elif price < current_ma20 < current_ma50 and current_rsi < 45:
                if random.random() < 0.3:
                    signal = "SHORT"
                    strategy_used = "MOMENTUM_CONTINUATION"
            
            if not signal or not strategy_used:
                continue
            
            # Calculate exit (simplified: hold for 5-20 bars)
            hold_bars = random.randint(5, 20)
            exit_idx = min(i + hold_bars, len(candles) - 1)
            exit_candle = candles[exit_idx]
            exit_price = exit_candle["close"]
            
            # Calculate P&L
            if signal == "LONG":
                pnl_pct = (exit_price - price) / price
            else:
                pnl_pct = (price - exit_price) / price
            
            # Apply transaction costs
            pnl_pct -= 0.002  # 0.2% roundtrip costs
            
            # Calculate R-multiple (risk = 1.5 ATR)
            risk = current_atr * 1.5
            r_multiple = (pnl_pct * price) / risk if risk > 0 else 0
            
            # Determine outcome
            if pnl_pct > 0.001:
                outcome = TradeOutcome.WIN
                failure_type = None
            elif pnl_pct < -0.001:
                outcome = TradeOutcome.LOSS
                failure_type = self._assign_failure_type(candles, i, exit_idx, signal)
            else:
                outcome = TradeOutcome.BREAKEVEN
                failure_type = None
            
            # Detect regime
            regime = self._detect_regime(candles, i)
            
            trade = Trade(
                trade_id=f"trade_{len(trades)+1}",
                symbol=config.symbol,
                timeframe=config.timeframe,
                direction=signal,
                entry_price=round(price, 2),
                exit_price=round(exit_price, 2),
                entry_time=timestamp,
                exit_time=exit_candle["timestamp"],
                size=config.max_position_size,
                pnl=round(pnl_pct * config.initial_capital * config.max_position_size, 2),
                r_multiple=round(r_multiple, 2),
                outcome=outcome,
                strategy_id=strategy_used,
                scenario_id=f"scenario_{regime.lower()}",
                confidence=round(0.5 + random.uniform(0, 0.4), 2),
                failure_type=failure_type
            )
            trade.notes.append(f"Regime: {regime}")
            trade.notes.append(f"RSI: {round(current_rsi, 1)}")
            trades.append(trade)
            
            # Skip ahead to avoid overlapping trades
            i += hold_bars // 2
        
        return trades
    
    def _sma(self, data: List[float], period: int) -> List[float]:
        """Simple Moving Average"""
        result = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(data[i])
            else:
                result.append(sum(data[i-period+1:i+1]) / period)
        return result
    
    def _atr(self, highs: List[float], lows: List[float], closes: List[float], period: int) -> List[float]:
        """Average True Range"""
        tr = []
        for i in range(len(closes)):
            if i == 0:
                tr.append(highs[i] - lows[i])
            else:
                tr.append(max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1])
                ))
        return self._sma(tr, period)
    
    def _rsi(self, data: List[float], period: int) -> List[float]:
        """Relative Strength Index"""
        result = [50] * len(data)  # Default to neutral
        if len(data) < period + 1:
            return result
        
        gains = []
        losses = []
        
        for i in range(1, len(data)):
            change = data[i] - data[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        for i in range(period, len(data)):
            avg_gain = sum(gains[i-period:i]) / period
            avg_loss = sum(losses[i-period:i]) / period
            
            if avg_loss == 0:
                result[i] = 100
            else:
                rs = avg_gain / avg_loss
                result[i] = 100 - (100 / (1 + rs))
        
        return result
    
    def _is_liquidity_sweep(self, candles: List[Dict], idx: int) -> bool:
        """Detect liquidity sweep pattern"""
        if idx < 20:
            return False
        
        current = candles[idx]
        
        # Look for long wick rejection
        body = abs(current["close"] - current["open"])
        total_range = current["high"] - current["low"]
        
        if total_range == 0:
            return False
        
        wick_ratio = (total_range - body) / total_range
        
        # Find recent swing high/low
        recent_highs = [c["high"] for c in candles[idx-20:idx]]
        recent_lows = [c["low"] for c in candles[idx-20:idx]]
        
        swing_high = max(recent_highs)
        swing_low = min(recent_lows)
        
        # Check if swept and rejected
        if current["high"] > swing_high and current["close"] < swing_high and wick_ratio > 0.5:
            return True
        if current["low"] < swing_low and current["close"] > swing_low and wick_ratio > 0.5:
            return True
        
        return False
    
    def _detect_regime(self, candles: List[Dict], idx: int) -> str:
        """Detect market regime at index"""
        if idx < 50:
            return "RANGE"
        
        closes = [c["close"] for c in candles[idx-50:idx+1]]
        ma = sum(closes) / len(closes)
        current = closes[-1]
        
        # Calculate trend strength
        changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        up_count = len([c for c in changes if c > 0])
        down_count = len([c for c in changes if c < 0])
        
        total = up_count + down_count
        if total == 0:
            return "RANGE"
        
        up_ratio = up_count / total
        
        if up_ratio > 0.6 and current > ma:
            return "TREND_UP"
        elif up_ratio < 0.4 and current < ma:
            return "TREND_DOWN"
        else:
            return "RANGE"
    
    def _assign_failure_type(self, candles: List[Dict], entry_idx: int, exit_idx: int, direction: str) -> FailureType:
        """Assign failure type based on price action"""
        if exit_idx <= entry_idx:
            return FailureType.WRONG_SCENARIO
        
        entry_candle = candles[entry_idx]
        exit_candle = candles[exit_idx]
        
        # Check for false breakout
        if direction == "LONG":
            max_high = max(c["high"] for c in candles[entry_idx:exit_idx+1])
            if max_high > entry_candle["high"] * 1.02 and exit_candle["close"] < entry_candle["close"]:
                return FailureType.FALSE_BREAKOUT
        else:
            min_low = min(c["low"] for c in candles[entry_idx:exit_idx+1])
            if min_low < entry_candle["low"] * 0.98 and exit_candle["close"] > entry_candle["close"]:
                return FailureType.FALSE_BREAKOUT
        
        # Check timing
        mid_idx = (entry_idx + exit_idx) // 2
        mid_candles = candles[entry_idx:mid_idx+1]
        if direction == "LONG":
            if any(c["close"] > exit_candle["close"] for c in mid_candles):
                return FailureType.EARLY_EXIT
        else:
            if any(c["close"] < exit_candle["close"] for c in mid_candles):
                return FailureType.EARLY_EXIT
        
        # Default failures
        failure_weights = [
            (FailureType.WRONG_SCENARIO, 0.35),
            (FailureType.LATE_ENTRY, 0.25),
            (FailureType.MTF_CONFLICT, 0.15),
            (FailureType.REGIME_MISMATCH, 0.15),
            (FailureType.MEMORY_MISLEAD, 0.10)
        ]
        
        rand = random.random()
        cumulative = 0
        for ft, weight in failure_weights:
            cumulative += weight
            if rand < cumulative:
                return ft
        
        return FailureType.WRONG_SCENARIO
    
    def _calculate_metrics(self, trades: List[Trade], config: SimulationConfig) -> Dict[str, Any]:
        """Calculate simulation metrics"""
        if not trades:
            return {
                "wins": 0, "losses": 0, "win_rate": 0, "profit_factor": 0,
                "total_pnl": 0, "total_r": 0, "avg_r": 0, "max_drawdown": 0,
                "sharpe_ratio": 0, "max_consecutive_wins": 0, "max_consecutive_losses": 0,
                "avg_trade_duration": 0, "best_trade_r": 0, "worst_trade_r": 0
            }
        
        wins = [t for t in trades if t.outcome == TradeOutcome.WIN]
        losses = [t for t in trades if t.outcome == TradeOutcome.LOSS]
        
        win_rate = len(wins) / len(trades) if trades else 0
        
        total_win_r = sum(t.r_multiple for t in wins)
        total_loss_r = abs(sum(t.r_multiple for t in losses))
        
        profit_factor = total_win_r / max(0.01, total_loss_r)
        
        total_pnl = sum(t.pnl for t in trades)
        total_r = sum(t.r_multiple for t in trades)
        avg_r = total_r / len(trades) if trades else 0
        
        # Calculate max drawdown
        equity_curve = []
        equity = config.initial_capital
        peak = equity
        max_dd = 0
        
        for t in trades:
            equity += t.pnl
            equity_curve.append(equity)
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        # Calculate Sharpe
        returns = [t.r_multiple for t in trades]
        if len(returns) > 1:
            avg_return = sum(returns) / len(returns)
            std_return = math.sqrt(sum((r - avg_return) ** 2 for r in returns) / len(returns))
            sharpe = (avg_return / std_return) * math.sqrt(252 / 4) if std_return > 0 else 0
        else:
            sharpe = 0
        
        # Consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        current_wins = 0
        current_losses = 0
        
        for t in trades:
            if t.outcome == TradeOutcome.WIN:
                current_wins += 1
                current_losses = 0
                max_consec_wins = max(max_consec_wins, current_wins)
            elif t.outcome == TradeOutcome.LOSS:
                current_losses += 1
                current_wins = 0
                max_consec_losses = max(max_consec_losses, current_losses)
        
        return {
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "total_pnl": round(total_pnl, 2),
            "total_r": round(total_r, 2),
            "avg_r": round(avg_r, 4),
            "max_drawdown": round(max_dd, 4),
            "sharpe_ratio": round(sharpe, 2),
            "max_consecutive_wins": max_consec_wins,
            "max_consecutive_losses": max_consec_losses,
            "avg_trade_duration": round((trades[-1].exit_time - trades[0].entry_time) / len(trades) / 3600000, 1) if trades else 0,
            "best_trade_r": round(max(t.r_multiple for t in trades), 2) if trades else 0,
            "worst_trade_r": round(min(t.r_multiple for t in trades), 2) if trades else 0
        }
    
    def _calculate_regime_breakdown(self, trades: List[Trade], candles: List[Dict]) -> Dict[str, Dict]:
        """Calculate performance by market regime"""
        regimes = {"TREND_UP": [], "TREND_DOWN": [], "RANGE": []}
        
        for t in trades:
            for note in t.notes:
                if "Regime:" in note:
                    regime = note.split(":")[1].strip()
                    if regime in regimes:
                        regimes[regime].append(t)
                    break
        
        breakdown = {}
        for regime, regime_trades in regimes.items():
            if regime_trades:
                wins = len([t for t in regime_trades if t.outcome == TradeOutcome.WIN])
                breakdown[regime] = {
                    "trades": len(regime_trades),
                    "wins": wins,
                    "winRate": round(wins / len(regime_trades), 4),
                    "totalR": round(sum(t.r_multiple for t in regime_trades), 2),
                    "avgR": round(sum(t.r_multiple for t in regime_trades) / len(regime_trades), 4)
                }
            else:
                breakdown[regime] = {"trades": 0, "wins": 0, "winRate": 0, "totalR": 0, "avgR": 0}
        
        return breakdown
    
    def _calculate_strategy_breakdown(self, trades: List[Trade]) -> Dict[str, Dict]:
        """Calculate performance by strategy"""
        strategies: Dict[str, List[Trade]] = {}
        
        for t in trades:
            if t.strategy_id not in strategies:
                strategies[t.strategy_id] = []
            strategies[t.strategy_id].append(t)
        
        breakdown = {}
        for strategy, strategy_trades in strategies.items():
            wins = len([t for t in strategy_trades if t.outcome == TradeOutcome.WIN])
            losses = len([t for t in strategy_trades if t.outcome == TradeOutcome.LOSS])
            total_r = sum(t.r_multiple for t in strategy_trades)
            
            breakdown[strategy] = {
                "trades": len(strategy_trades),
                "wins": wins,
                "losses": losses,
                "winRate": round(wins / len(strategy_trades), 4) if strategy_trades else 0,
                "totalR": round(total_r, 2),
                "avgR": round(total_r / len(strategy_trades), 4) if strategy_trades else 0,
                "profitFactor": round(
                    sum(t.r_multiple for t in strategy_trades if t.r_multiple > 0) / 
                    max(0.01, abs(sum(t.r_multiple for t in strategy_trades if t.r_multiple < 0))),
                    2
                )
            }
        
        return breakdown


# Global instance
real_simulator = RealDataSimulator()
