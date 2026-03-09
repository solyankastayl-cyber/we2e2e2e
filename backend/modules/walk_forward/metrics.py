"""
Walk-Forward Metrics Calculator
===============================

Calculates all performance metrics:
- Global: PF, WR, Sharpe, Sortino, Calmar, CAGR
- Per-decade breakdown
- Per-regime breakdown
- Per-strategy breakdown
"""

import math
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict

from .types import (
    Trade, DecadeMetrics, RegimeMetrics, StrategyMetrics,
    WalkForwardResult, FailureEvent
)


class WalkForwardMetrics:
    """Metrics calculator for walk-forward simulation"""
    
    @staticmethod
    def calculate_global_metrics(
        trades: List[Trade],
        equity_curve: List[Dict[str, Any]],
        initial_capital: float,
        years: float
    ) -> Dict[str, Any]:
        """Calculate global performance metrics"""
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe": 0.0,
                "sortino": 0.0,
                "calmar": 0.0,
                "max_drawdown": 0.0,
                "max_drawdown_pct": 0.0,
                "total_return": 0.0,
                "cagr": 0.0,
                "expectancy": 0.0,
                "max_losing_streak": 0,
                "avg_recovery_bars": 0,
                "avg_r": 0.0
            }
        
        # Basic counts
        total_trades = len(trades)
        wins = [t for t in trades if t.outcome == "WIN"]
        losses = [t for t in trades if t.outcome == "LOSS"]
        
        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        
        # Profit Factor
        gross_profit = sum(t.pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Returns for Sharpe/Sortino
        if equity_curve and len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                prev_eq = equity_curve[i-1]["equity"]
                curr_eq = equity_curve[i]["equity"]
                if prev_eq > 0:
                    returns.append((curr_eq - prev_eq) / prev_eq)
            
            if returns:
                avg_return = sum(returns) / len(returns)
                std_return = math.sqrt(sum((r - avg_return)**2 for r in returns) / len(returns)) if len(returns) > 1 else 0
                
                # Annualized Sharpe (assuming daily returns)
                sharpe = (avg_return * 252) / (std_return * math.sqrt(252)) if std_return > 0 else 0
                
                # Sortino (downside deviation)
                negative_returns = [r for r in returns if r < 0]
                if negative_returns:
                    downside_std = math.sqrt(sum(r**2 for r in negative_returns) / len(negative_returns))
                    sortino = (avg_return * 252) / (downside_std * math.sqrt(252)) if downside_std > 0 else 0
                else:
                    sortino = sharpe * 2  # No downside = very good
            else:
                sharpe = 0
                sortino = 0
        else:
            sharpe = 0
            sortino = 0
        
        # Max Drawdown
        max_dd = 0.0
        max_dd_pct = 0.0
        peak = initial_capital
        
        for point in equity_curve:
            eq = point["equity"]
            if eq > peak:
                peak = eq
            dd = peak - eq
            dd_pct = dd / peak if peak > 0 else 0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                max_dd = dd
        
        # Total Return and CAGR
        final_equity = equity_curve[-1]["equity"] if equity_curve else initial_capital
        total_return = (final_equity - initial_capital) / initial_capital if initial_capital > 0 else 0
        
        if years > 0 and total_return > -1:
            cagr = ((1 + total_return) ** (1/years)) - 1
        else:
            cagr = 0
        
        # Calmar Ratio
        calmar = cagr / max_dd_pct if max_dd_pct > 0 else 0
        
        # Expectancy (avg R-multiple)
        r_multiples = [t.r_multiple for t in trades if t.r_multiple != 0]
        expectancy = sum(r_multiples) / len(r_multiples) if r_multiples else 0
        avg_r = expectancy
        
        # Max losing streak
        max_losing_streak = 0
        current_streak = 0
        for t in trades:
            if t.outcome == "LOSS":
                current_streak += 1
                max_losing_streak = max(max_losing_streak, current_streak)
            else:
                current_streak = 0
        
        # Average recovery time (bars from drawdown to new high)
        recovery_bars = []
        in_drawdown = False
        drawdown_start = 0
        
        for i, point in enumerate(equity_curve):
            if point.get("drawdown_pct", 0) > 0.01:
                if not in_drawdown:
                    in_drawdown = True
                    drawdown_start = i
            else:
                if in_drawdown:
                    recovery_bars.append(i - drawdown_start)
                    in_drawdown = False
        
        avg_recovery = sum(recovery_bars) / len(recovery_bars) if recovery_bars else 0
        
        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2),
            "calmar": round(calmar, 2),
            "max_drawdown": round(max_dd, 2),
            "max_drawdown_pct": round(max_dd_pct, 4),
            "total_return": round(total_return, 4),
            "cagr": round(cagr, 4),
            "expectancy": round(expectancy, 3),
            "max_losing_streak": max_losing_streak,
            "avg_recovery_bars": int(avg_recovery),
            "avg_r": round(avg_r, 3)
        }
    
    @staticmethod
    def calculate_decade_metrics(trades: List[Trade]) -> List[DecadeMetrics]:
        """Calculate per-decade breakdown"""
        decade_trades: Dict[str, List[Trade]] = defaultdict(list)
        
        for trade in trades:
            decade_trades[trade.decade].append(trade)
        
        results = []
        for decade, dtrades in sorted(decade_trades.items()):
            if not dtrades:
                continue
            
            wins = [t for t in dtrades if t.outcome == "WIN"]
            losses = [t for t in dtrades if t.outcome == "LOSS"]
            
            win_rate = len(wins) / len(dtrades) if dtrades else 0
            
            gross_profit = sum(t.pnl for t in wins) if wins else 0
            gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            r_multiples = [t.r_multiple for t in dtrades if t.r_multiple != 0]
            avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0
            
            total_return = sum(t.pnl for t in dtrades)
            
            # Best/worst strategy by contribution
            strategy_pnl: Dict[str, float] = defaultdict(float)
            for t in dtrades:
                strategy_pnl[t.strategy_id] += t.pnl
            
            best_strategy = max(strategy_pnl.items(), key=lambda x: x[1])[0] if strategy_pnl else ""
            worst_strategy = min(strategy_pnl.items(), key=lambda x: x[1])[0] if strategy_pnl else ""
            
            # Parse decade string for years
            try:
                start_year = int(decade.rstrip('s'))
                end_year = start_year + 9
            except:
                start_year = 0
                end_year = 0
            
            results.append(DecadeMetrics(
                decade=decade,
                start_year=start_year,
                end_year=end_year,
                trades=len(dtrades),
                win_rate=round(win_rate, 4),
                profit_factor=round(profit_factor, 2),
                sharpe=0,  # Would need daily returns per decade
                max_drawdown=0,  # Would need equity curve per decade
                total_return=round(total_return, 2),
                avg_r=round(avg_r, 3),
                best_strategy=best_strategy,
                worst_strategy=worst_strategy
            ))
        
        return results
    
    @staticmethod
    def calculate_regime_metrics(trades: List[Trade]) -> List[RegimeMetrics]:
        """Calculate per-regime breakdown"""
        regime_trades: Dict[str, List[Trade]] = defaultdict(list)
        
        for trade in trades:
            if trade.regime:
                regime_trades[trade.regime].append(trade)
        
        results = []
        for regime, rtrades in sorted(regime_trades.items()):
            if not rtrades:
                continue
            
            wins = [t for t in rtrades if t.outcome == "WIN"]
            losses = [t for t in rtrades if t.outcome == "LOSS"]
            
            win_rate = len(wins) / len(rtrades) if rtrades else 0
            
            gross_profit = sum(t.pnl for t in wins) if wins else 0
            gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            r_multiples = [t.r_multiple for t in rtrades if t.r_multiple != 0]
            avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0
            
            # Active strategies in this regime
            active_strategies = list(set(t.strategy_id for t in rtrades))
            
            # Family performance
            family_pnl: Dict[str, float] = defaultdict(float)
            # Map strategy to family (simplified)
            for t in rtrades:
                family = "core"  # Default family
                if "BREAKOUT" in t.strategy_id:
                    family = "breakout"
                elif "REVERSAL" in t.strategy_id:
                    family = "reversal"
                elif "HARMONIC" in t.strategy_id:
                    family = "harmonic"
                family_pnl[family] += t.pnl
            
            results.append(RegimeMetrics(
                regime=regime,
                trades=len(rtrades),
                win_rate=round(win_rate, 4),
                profit_factor=round(profit_factor, 2),
                sharpe=0,  # Would need returns per regime
                max_drawdown=0,
                avg_r=round(avg_r, 3),
                active_strategies=active_strategies,
                family_performance={k: round(v, 2) for k, v in family_pnl.items()}
            ))
        
        return results
    
    @staticmethod
    def calculate_strategy_metrics(
        trades: List[Trade],
        healing_events: List[Dict[str, Any]] = None
    ) -> List[StrategyMetrics]:
        """Calculate per-strategy breakdown"""
        strategy_trades: Dict[str, List[Trade]] = defaultdict(list)
        
        for trade in trades:
            strategy_trades[trade.strategy_id].append(trade)
        
        # Count healing events per strategy
        healing_counts: Dict[str, int] = defaultdict(int)
        demotion_counts: Dict[str, int] = defaultdict(int)
        promotion_counts: Dict[str, int] = defaultdict(int)
        
        if healing_events:
            for event in healing_events:
                sid = event.get("strategy_id", "")
                etype = event.get("type", "")
                healing_counts[sid] += 1
                if "DEMOT" in etype.upper():
                    demotion_counts[sid] += 1
                elif "PROMOT" in etype.upper():
                    promotion_counts[sid] += 1
        
        # Total PnL for contribution calculation
        total_pnl = sum(t.pnl for t in trades)
        
        results = []
        for strategy_id, strades in sorted(strategy_trades.items()):
            if not strades:
                continue
            
            wins = [t for t in strades if t.outcome == "WIN"]
            losses = [t for t in strades if t.outcome == "LOSS"]
            
            win_rate = len(wins) / len(strades) if strades else 0
            
            gross_profit = sum(t.pnl for t in wins) if wins else 0
            gross_loss = abs(sum(t.pnl for t in losses)) if losses else 1
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            r_multiples = [t.r_multiple for t in strades if t.r_multiple != 0]
            avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0
            
            strategy_pnl = sum(t.pnl for t in strades)
            contribution = strategy_pnl / total_pnl if total_pnl != 0 else 0
            
            # Determine status based on metrics
            if profit_factor >= 1.5 and win_rate >= 0.55:
                status = "APPROVED"
            elif profit_factor >= 1.0 and win_rate >= 0.45:
                status = "LIMITED"
            else:
                status = "DEPRECATED"
            
            results.append(StrategyMetrics(
                strategy_id=strategy_id,
                status=status,
                trades=len(strades),
                win_rate=round(win_rate, 4),
                profit_factor=round(profit_factor, 2),
                avg_r=round(avg_r, 3),
                max_drawdown=0,  # Would need per-strategy equity
                contribution_pct=round(contribution, 4),
                demotions=demotion_counts.get(strategy_id, 0),
                promotions=promotion_counts.get(strategy_id, 0),
                healing_events=healing_counts.get(strategy_id, 0)
            ))
        
        # Sort by contribution
        results.sort(key=lambda x: x.contribution_pct, reverse=True)
        
        return results
    
    @staticmethod
    def detect_failures(trades: List[Trade]) -> List[FailureEvent]:
        """Detect failure events from trades"""
        failures = []
        
        for trade in trades:
            if trade.outcome != "LOSS":
                continue
            
            failure_type = None
            description = ""
            
            # False breakout detection
            if "BREAKOUT" in trade.strategy_id.upper():
                if trade.r_multiple < -1.0:
                    failure_type = "FALSE_BREAKOUT"
                    description = f"False breakout: entered at {trade.entry_price}, stopped at {trade.exit_price}"
            
            # Early exit (MFE >> MAE but still lost)
            if trade.max_favorable > abs(trade.pnl) * 2:
                failure_type = "EARLY_EXIT"
                description = f"Had {trade.max_favorable:.2f} favorable move but exited with {trade.pnl:.2f} loss"
            
            # Wide stop (MAE very large)
            if trade.max_adverse > abs(trade.entry_price * 0.05):
                if failure_type is None:
                    failure_type = "WIDE_STOP"
                    description = f"Stop too wide: MAE was {trade.max_adverse:.2f}"
            
            # Counter-trend trade in strong regime
            if trade.regime in ["TREND_UP", "TREND_DOWN"]:
                if (trade.regime == "TREND_UP" and trade.direction == "SHORT") or \
                   (trade.regime == "TREND_DOWN" and trade.direction == "LONG"):
                    failure_type = "COUNTER_TREND"
                    description = f"Counter-trend {trade.direction} in {trade.regime}"
            
            if failure_type:
                failures.append(FailureEvent(
                    timestamp=trade.exit_time,
                    type=failure_type,
                    strategy_id=trade.strategy_id,
                    trade_id=trade.id,
                    description=description,
                    loss_amount=abs(trade.pnl),
                    regime=trade.regime,
                    decade=trade.decade,
                    meta={
                        "r_multiple": trade.r_multiple,
                        "mfe": trade.max_favorable,
                        "mae": trade.max_adverse,
                        "bars_held": trade.bars_held
                    }
                ))
        
        return failures
