"""
Phase 8: Historical Simulation Engine
Runs full backtest over historical data.
"""
import time
import random
import math
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


class SimulationEngine:
    """
    Historical Simulation Engine.
    
    Pipeline:
    candles → indicators → structure → scenarios → 
    discovery strategies → portfolio → execution
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or VALIDATION_CONFIG
        self._active_runs: Dict[str, SimulationResult] = {}
    
    def run(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        start_date: str = "2019-01-01",
        end_date: str = "2024-01-01",
        initial_capital: float = 100000.0,
        isolation_run_id: Optional[str] = None
    ) -> SimulationResult:
        """
        Run historical simulation.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_capital: Starting capital
            isolation_run_id: Optional validation isolation context
            
        Returns:
            SimulationResult with full backtest results
        """
        run_id = self._generate_run_id(symbol, timeframe)
        started_at = int(time.time() * 1000)
        
        config = SimulationConfig(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            isolation_run_id=isolation_run_id
        )
        
        # Generate simulated trades (mock for now)
        trades = self._simulate_trades(config)
        
        # Calculate metrics
        metrics = self._calculate_metrics(trades, config)
        
        # Calculate regime breakdown
        regime_breakdown = self._calculate_regime_breakdown(trades)
        
        # Calculate strategy breakdown
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
        
        self._active_runs[run_id] = result
        
        if self.db:
            self._store_result(result)
        
        return result
    
    def get_run(self, run_id: str) -> Optional[SimulationResult]:
        """Get a simulation run by ID"""
        if run_id in self._active_runs:
            return self._active_runs[run_id]
        
        if self.db:
            return self._load_result(run_id)
        
        return None
    
    def list_runs(self, symbol: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """List simulation runs"""
        runs = list(self._active_runs.values())
        if symbol:
            runs = [r for r in runs if r.config.symbol == symbol]
        runs = sorted(runs, key=lambda r: r.started_at, reverse=True)[:limit]
        
        return [
            {
                "runId": r.run_id,
                "symbol": r.config.symbol,
                "timeframe": r.config.timeframe,
                "trades": r.trades,
                "winRate": r.win_rate,
                "profitFactor": r.profit_factor,
                "startedAt": r.started_at
            }
            for r in runs
        ]
    
    # ==================
    # Private methods
    # ==================
    
    def _generate_run_id(self, symbol: str, timeframe: str) -> str:
        """Generate unique run ID"""
        return f"sim_{symbol}_{timeframe}_{int(time.time() * 1000)}"
    
    def _simulate_trades(self, config: SimulationConfig) -> List[Trade]:
        """
        Simulate trades based on configuration.
        In production, this would use actual historical data and signals.
        """
        trades = []
        strategies = ["MTF_BREAKOUT", "LIQUIDITY_SWEEP", "RANGE_REVERSAL", "MOMENTUM_CONTINUATION"]
        regimes = ["TREND_UP", "TREND_DOWN", "RANGE"]
        
        # Simulate 300-500 trades over the period
        num_trades = random.randint(300, 500)
        
        for i in range(num_trades):
            # Randomize trade parameters with slight positive edge
            direction = random.choice(["LONG", "SHORT"])
            strategy = random.choice(strategies)
            regime = random.choice(regimes)
            
            # Win probability based on strategy (slight edge)
            base_win_prob = 0.55 + random.uniform(-0.05, 0.10)
            
            # Adjust based on regime
            if regime == "TREND_UP" and direction == "LONG":
                base_win_prob += 0.05
            elif regime == "TREND_DOWN" and direction == "SHORT":
                base_win_prob += 0.05
            elif regime == "RANGE":
                base_win_prob -= 0.03
            
            is_win = random.random() < base_win_prob
            
            # Generate R-multiple
            if is_win:
                r_multiple = random.uniform(0.5, 3.5)  # Winners: 0.5R to 3.5R
                outcome = TradeOutcome.WIN
            else:
                r_multiple = -random.uniform(0.5, 1.5)  # Losers: -0.5R to -1.5R
                outcome = TradeOutcome.LOSS
            
            # Assign failure type for losses
            failure_type = None
            if outcome == TradeOutcome.LOSS:
                failure_type = random.choice(list(FailureType))
            
            entry_price = 40000 + random.uniform(-10000, 20000)
            pnl_percent = r_multiple * 0.02  # 2% risk per trade
            exit_price = entry_price * (1 + pnl_percent) if direction == "LONG" else entry_price * (1 - pnl_percent)
            
            trade = Trade(
                trade_id=f"trade_{i+1}",
                symbol=config.symbol,
                timeframe=config.timeframe,
                direction=direction,
                entry_price=round(entry_price, 2),
                exit_price=round(exit_price, 2),
                entry_time=int(time.time() * 1000) - (num_trades - i) * 3600000 * 4,
                exit_time=int(time.time() * 1000) - (num_trades - i - 1) * 3600000 * 4,
                size=config.max_position_size,
                pnl=round(pnl_percent * config.initial_capital, 2),
                r_multiple=round(r_multiple, 2),
                outcome=outcome,
                strategy_id=strategy,
                scenario_id=f"scenario_{regime.lower()}",
                confidence=round(0.5 + random.uniform(0, 0.4), 2),
                failure_type=failure_type
            )
            trade.notes.append(f"Regime: {regime}")
            trades.append(trade)
        
        return trades
    
    def _calculate_metrics(
        self,
        trades: List[Trade],
        config: SimulationConfig
    ) -> Dict[str, Any]:
        """Calculate simulation metrics"""
        if not trades:
            return self._empty_metrics()
        
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
        
        # Calculate Sharpe (simplified)
        returns = [t.r_multiple for t in trades]
        if len(returns) > 1:
            avg_return = sum(returns) / len(returns)
            std_return = math.sqrt(sum((r - avg_return) ** 2 for r in returns) / len(returns))
            sharpe = (avg_return / std_return) * math.sqrt(252 / 4) if std_return > 0 else 0  # Annualized for 4h
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
            else:
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
            "avg_trade_duration": round(random.uniform(4, 24), 1),  # hours
            "best_trade_r": round(max(t.r_multiple for t in trades), 2),
            "worst_trade_r": round(min(t.r_multiple for t in trades), 2)
        }
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics"""
        return {
            "wins": 0, "losses": 0, "win_rate": 0, "profit_factor": 0,
            "total_pnl": 0, "total_r": 0, "avg_r": 0, "max_drawdown": 0,
            "sharpe_ratio": 0, "max_consecutive_wins": 0, "max_consecutive_losses": 0,
            "avg_trade_duration": 0, "best_trade_r": 0, "worst_trade_r": 0
        }
    
    def _calculate_regime_breakdown(self, trades: List[Trade]) -> Dict[str, Dict]:
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
                    "totalR": round(sum(t.r_multiple for t in regime_trades), 2)
                }
            else:
                breakdown[regime] = {"trades": 0, "wins": 0, "winRate": 0, "totalR": 0}
        
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
            breakdown[strategy] = {
                "trades": len(strategy_trades),
                "wins": wins,
                "winRate": round(wins / len(strategy_trades), 4) if strategy_trades else 0,
                "totalR": round(sum(t.r_multiple for t in strategy_trades), 2),
                "avgR": round(sum(t.r_multiple for t in strategy_trades) / len(strategy_trades), 4) if strategy_trades else 0
            }
        
        return breakdown
    
    def _store_result(self, result: SimulationResult):
        """Store result in MongoDB"""
        collection = self.config.get("collections", {}).get("simulation_runs", "ta_simulation_runs")
        # Simplified storage - in production would serialize properly
        doc = {
            "run_id": result.run_id,
            "trades": result.trades,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "started_at": result.started_at,
            "completed_at": result.completed_at
        }
        self.db[collection].insert_one(doc)
    
    def _load_result(self, run_id: str) -> Optional[SimulationResult]:
        """Load result from MongoDB"""
        collection = self.config.get("collections", {}).get("simulation_runs", "ta_simulation_runs")
        doc = self.db[collection].find_one({"run_id": run_id})
        if doc:
            # Would reconstruct full result in production
            return None
        return None
