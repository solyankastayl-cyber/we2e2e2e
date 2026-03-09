"""
Metrics Engine
==============

4-level metrics calculation:
1. Trade-level (WR, PF, expectancy)
2. Portfolio-level (Sharpe, Calmar, CAGR)
3. Strategy-level (contribution, survival)
4. Governance-level (events, blocked trades)
"""

import math
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict

from .types import (
    SimulatedTrade, TradeMetrics, PortfolioMetrics,
    StrategyMetrics, GovernanceMetrics, RegimeBreakdown,
    DecadeBreakdown, GovernanceEvent
)


class MetricsEngine:
    """
    Comprehensive metrics calculation engine.
    
    Calculates all metrics needed for cross-asset analysis:
    - Per-trade statistics
    - Portfolio performance metrics  
    - Strategy contribution analysis
    - Regime breakdowns
    - Decade breakdowns (for long histories)
    """
    
    @staticmethod
    def calculate_trade_metrics(trades: List[SimulatedTrade]) -> TradeMetrics:
        """Calculate trade-level metrics"""
        if not trades:
            return TradeMetrics()
        
        wins = [t for t in trades if t.outcome == "WIN"]
        losses = [t for t in trades if t.outcome == "LOSS"]
        
        total = len(trades)
        winning = len(wins)
        losing = len(losses)
        
        win_rate = winning / total if total > 0 else 0
        
        # P&L calculations
        gross_profit = sum(t.pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0 if gross_profit == 0 else float('inf')
        
        avg_win = gross_profit / winning if winning > 0 else 0
        avg_loss = gross_loss / losing if losing > 0 else 0
        
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        # R-multiples
        r_multiples = [t.r_multiple for t in trades if t.r_multiple != 0]
        avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0
        
        # Extremes
        pnls = [t.pnl for t in trades]
        max_win = max(pnls) if pnls else 0
        max_loss = min(pnls) if pnls else 0
        
        # Streaks
        max_winning_streak = 0
        max_losing_streak = 0
        current_streak = 0
        last_outcome = None
        
        for trade in trades:
            if trade.outcome == last_outcome:
                current_streak += 1
            else:
                if last_outcome == "WIN":
                    max_winning_streak = max(max_winning_streak, current_streak)
                elif last_outcome == "LOSS":
                    max_losing_streak = max(max_losing_streak, current_streak)
                current_streak = 1
                last_outcome = trade.outcome
        
        # Final streak
        if last_outcome == "WIN":
            max_winning_streak = max(max_winning_streak, current_streak)
        elif last_outcome == "LOSS":
            max_losing_streak = max(max_losing_streak, current_streak)
        
        return TradeMetrics(
            total_trades=total,
            winning_trades=winning,
            losing_trades=losing,
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_r_multiple=avg_r,
            max_win=max_win,
            max_loss=max_loss,
            max_winning_streak=max_winning_streak,
            max_losing_streak=max_losing_streak
        )
    
    @staticmethod
    def calculate_portfolio_metrics(
        equity_curve: List[Dict],
        trades: List[SimulatedTrade],
        initial_capital: float,
        years: float
    ) -> PortfolioMetrics:
        """Calculate portfolio-level metrics"""
        if not equity_curve:
            return PortfolioMetrics(final_equity=initial_capital)
        
        equities = [e["equity"] for e in equity_curve]
        
        final_equity = equities[-1] if equities else initial_capital
        peak_equity = max(equities) if equities else initial_capital
        
        # Returns
        total_return = final_equity - initial_capital
        total_return_pct = total_return / initial_capital if initial_capital > 0 else 0
        
        # CAGR
        if years > 0 and final_equity > 0 and initial_capital > 0:
            cagr = (final_equity / initial_capital) ** (1 / years) - 1
        else:
            cagr = 0
        
        # Daily returns
        daily_returns = []
        for i in range(1, len(equities)):
            if equities[i-1] > 0:
                ret = (equities[i] - equities[i-1]) / equities[i-1]
                daily_returns.append(ret)
        
        # Volatility
        if len(daily_returns) > 1:
            mean_ret = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            volatility = math.sqrt(variance) * math.sqrt(252)  # Annualized
        else:
            volatility = 0
        
        # Downside volatility (for Sortino)
        negative_returns = [r for r in daily_returns if r < 0]
        if len(negative_returns) > 1:
            mean_neg = sum(negative_returns) / len(negative_returns)
            downside_var = sum((r - mean_neg) ** 2 for r in negative_returns) / (len(negative_returns) - 1)
            downside_volatility = math.sqrt(downside_var) * math.sqrt(252)
        else:
            downside_volatility = volatility
        
        # Sharpe (assuming 0% risk-free rate)
        sharpe = (cagr / volatility) if volatility > 0 else 0
        
        # Sortino
        sortino = (cagr / downside_volatility) if downside_volatility > 0 else 0
        
        # Drawdown
        max_dd = 0
        max_dd_pct = 0
        total_dd = 0
        running_peak = initial_capital
        
        for eq in equities:
            if eq > running_peak:
                running_peak = eq
            dd = running_peak - eq
            dd_pct = dd / running_peak if running_peak > 0 else 0
            
            total_dd += dd_pct
            
            if dd > max_dd:
                max_dd = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
        
        avg_dd = total_dd / len(equities) if equities else 0
        
        # Calmar
        calmar = cagr / max_dd_pct if max_dd_pct > 0 else 0
        
        # Ulcer Index (root mean square of drawdowns)
        if equities:
            dd_squared_sum = 0
            running_peak = initial_capital
            for eq in equities:
                if eq > running_peak:
                    running_peak = eq
                dd_pct = (running_peak - eq) / running_peak if running_peak > 0 else 0
                dd_squared_sum += dd_pct ** 2
            ulcer_index = math.sqrt(dd_squared_sum / len(equities))
        else:
            ulcer_index = 0
        
        return PortfolioMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            cagr=cagr,
            sharpe=sharpe,
            sortino=sortino,
            calmar=calmar,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            avg_drawdown=avg_dd,
            volatility=volatility,
            downside_volatility=downside_volatility,
            final_equity=final_equity,
            peak_equity=peak_equity,
            ulcer_index=ulcer_index
        )
    
    @staticmethod
    def calculate_strategy_metrics(
        trades: List[SimulatedTrade],
        events: List[GovernanceEvent]
    ) -> List[StrategyMetrics]:
        """Calculate per-strategy metrics"""
        # Group trades by strategy
        by_strategy: Dict[str, List[SimulatedTrade]] = defaultdict(list)
        for trade in trades:
            by_strategy[trade.strategy_id].append(trade)
        
        # Count governance events per strategy
        demotions: Dict[str, int] = defaultdict(int)
        recoveries: Dict[str, int] = defaultdict(int)
        health_scores: Dict[str, List[float]] = defaultdict(list)
        
        for event in events:
            if event.layer.value == "SELF_HEALING":
                sid = event.metadata.get("strategy_id", "")
                if event.action == "DEMOTION":
                    demotions[sid] += 1
                elif event.action == "RECOVERY":
                    recoveries[sid] += 1
                if "new_health" in event.metadata:
                    health_scores[sid].append(event.metadata["new_health"])
        
        # Calculate total P&L for contribution
        total_pnl = sum(t.pnl for t in trades)
        
        results = []
        for sid, strat_trades in by_strategy.items():
            wins = [t for t in strat_trades if t.outcome == "WIN"]
            losses = [t for t in strat_trades if t.outcome == "LOSS"]
            
            win_rate = len(wins) / len(strat_trades) if strat_trades else 0
            
            gross_profit = sum(t.pnl for t in wins) if wins else 0
            gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0
            pf = gross_profit / gross_loss if gross_loss > 0 else 0 if gross_profit == 0 else float('inf')
            
            strat_pnl = sum(t.pnl for t in strat_trades)
            contribution = strat_pnl / total_pnl if total_pnl != 0 else 0
            
            # Health scores
            scores = health_scores.get(sid, [1.0])
            avg_health = sum(scores) / len(scores) if scores else 1.0
            min_health = min(scores) if scores else 1.0
            
            # Survival rate
            demotion_count = demotions.get(sid, 0)
            recovery_count = recoveries.get(sid, 0)
            survival = 1.0 - (demotion_count * 0.1) + (recovery_count * 0.05)
            survival = max(0, min(1, survival))
            
            results.append(StrategyMetrics(
                strategy_id=sid,
                trades=len(strat_trades),
                win_rate=win_rate,
                profit_factor=pf,
                contribution_pct=contribution,
                demotion_count=demotion_count,
                recovery_count=recovery_count,
                survival_rate=survival,
                avg_health_score=avg_health,
                min_health_score=min_health
            ))
        
        # Sort by contribution
        results.sort(key=lambda x: x.contribution_pct, reverse=True)
        return results
    
    @staticmethod
    def calculate_regime_breakdown(trades: List[SimulatedTrade]) -> List[RegimeBreakdown]:
        """Calculate per-regime performance breakdown"""
        by_regime: Dict[str, List[SimulatedTrade]] = defaultdict(list)
        
        for trade in trades:
            regime = trade.regime_at_entry or "UNKNOWN"
            by_regime[regime].append(trade)
        
        results = []
        for regime, regime_trades in by_regime.items():
            if not regime_trades:
                continue
            
            wins = [t for t in regime_trades if t.outcome == "WIN"]
            losses = [t for t in regime_trades if t.outcome == "LOSS"]
            
            win_rate = len(wins) / len(regime_trades) if regime_trades else 0
            
            gross_profit = sum(t.pnl for t in wins) if wins else 0
            gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0
            pf = gross_profit / gross_loss if gross_loss > 0 else 0 if gross_profit == 0 else float('inf')
            
            r_multiples = [t.r_multiple for t in regime_trades if t.r_multiple != 0]
            avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0
            
            # Best families in this regime
            family_pnl: Dict[str, float] = defaultdict(float)
            for trade in regime_trades:
                # Extract family from strategy_id (simplified)
                sid = trade.strategy_id
                if "BREAKOUT" in sid:
                    family = "breakout"
                elif "REVERSAL" in sid or "DOUBLE" in sid or "HEAD" in sid:
                    family = "reversal"
                elif "MOMENTUM" in sid or "CONTINUATION" in sid:
                    family = "momentum"
                else:
                    family = "other"
                family_pnl[family] += trade.pnl
            
            best_families = sorted(family_pnl.keys(), key=lambda f: family_pnl[f], reverse=True)[:3]
            
            results.append(RegimeBreakdown(
                regime=regime,
                trades=len(regime_trades),
                win_rate=win_rate,
                profit_factor=pf,
                avg_r=avg_r,
                max_dd=0,  # Would need more data
                best_families=best_families
            ))
        
        return results
    
    @staticmethod
    def calculate_decade_breakdown(trades: List[SimulatedTrade]) -> List[DecadeBreakdown]:
        """Calculate per-decade performance breakdown"""
        by_decade: Dict[str, List[SimulatedTrade]] = defaultdict(list)
        
        for trade in trades:
            try:
                # Parse exit timestamp
                if trade.exit_timestamp > 0:
                    dt = datetime.utcfromtimestamp(trade.exit_timestamp / 1000)
                    decade = f"{(dt.year // 10) * 10}s"
                    by_decade[decade].append(trade)
            except:
                continue
        
        results = []
        for decade in sorted(by_decade.keys()):
            decade_trades = by_decade[decade]
            if not decade_trades:
                continue
            
            wins = [t for t in decade_trades if t.outcome == "WIN"]
            losses = [t for t in decade_trades if t.outcome == "LOSS"]
            
            gross_profit = sum(t.pnl for t in wins) if wins else 0
            gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0
            pf = gross_profit / gross_loss if gross_loss > 0 else 0 if gross_profit == 0 else float('inf')
            
            # Dominant regime
            regime_counts: Dict[str, int] = defaultdict(int)
            for trade in decade_trades:
                regime_counts[trade.regime_at_entry or "UNKNOWN"] += 1
            dominant = max(regime_counts.keys(), key=lambda r: regime_counts[r]) if regime_counts else "UNKNOWN"
            
            results.append(DecadeBreakdown(
                decade=decade,
                trades=len(decade_trades),
                profit_factor=pf,
                cagr=0,  # Would need equity curve per decade
                max_dd=0,
                dominant_regime=dominant,
                notes=""
            ))
        
        return results
    
    @staticmethod
    def metrics_to_dict(
        trade_metrics: TradeMetrics,
        portfolio_metrics: PortfolioMetrics,
        strategy_metrics: List[StrategyMetrics],
        governance_metrics: GovernanceMetrics,
        regime_breakdown: List[RegimeBreakdown],
        decade_breakdown: List[DecadeBreakdown]
    ) -> Dict[str, Any]:
        """Convert all metrics to dictionary"""
        return {
            "trade_metrics": {
                "total_trades": trade_metrics.total_trades,
                "winning_trades": trade_metrics.winning_trades,
                "losing_trades": trade_metrics.losing_trades,
                "win_rate": round(trade_metrics.win_rate, 4),
                "profit_factor": round(trade_metrics.profit_factor, 2),
                "expectancy": round(trade_metrics.expectancy, 4),
                "avg_win": round(trade_metrics.avg_win, 2),
                "avg_loss": round(trade_metrics.avg_loss, 2),
                "avg_r_multiple": round(trade_metrics.avg_r_multiple, 2),
                "max_winning_streak": trade_metrics.max_winning_streak,
                "max_losing_streak": trade_metrics.max_losing_streak
            },
            "portfolio_metrics": {
                "total_return": round(portfolio_metrics.total_return, 2),
                "total_return_pct": round(portfolio_metrics.total_return_pct, 4),
                "cagr": round(portfolio_metrics.cagr, 4),
                "sharpe": round(portfolio_metrics.sharpe, 2),
                "sortino": round(portfolio_metrics.sortino, 2),
                "calmar": round(portfolio_metrics.calmar, 2),
                "max_drawdown": round(portfolio_metrics.max_drawdown, 2),
                "max_drawdown_pct": round(portfolio_metrics.max_drawdown_pct, 4),
                "volatility": round(portfolio_metrics.volatility, 4),
                "final_equity": round(portfolio_metrics.final_equity, 2),
                "peak_equity": round(portfolio_metrics.peak_equity, 2),
                "ulcer_index": round(portfolio_metrics.ulcer_index, 4)
            },
            "strategy_breakdown": [
                {
                    "strategy_id": s.strategy_id,
                    "trades": s.trades,
                    "win_rate": round(s.win_rate, 4),
                    "profit_factor": round(s.profit_factor, 2),
                    "contribution_pct": round(s.contribution_pct, 4),
                    "demotion_count": s.demotion_count,
                    "recovery_count": s.recovery_count,
                    "survival_rate": round(s.survival_rate, 2)
                }
                for s in strategy_metrics
            ],
            "governance_metrics": {
                "total_events": governance_metrics.total_events,
                "healing_events": governance_metrics.healing_events,
                "meta_reallocations": governance_metrics.meta_reallocations,
                "regime_changes": governance_metrics.regime_changes,
                "overlay_triggers": governance_metrics.overlay_triggers,
                "kill_switch_events": governance_metrics.kill_switch_events,
                "bias_rejections": governance_metrics.bias_rejections,
                "blocked_trades": governance_metrics.blocked_trades
            },
            "regime_breakdown": [
                {
                    "regime": r.regime,
                    "trades": r.trades,
                    "win_rate": round(r.win_rate, 4),
                    "profit_factor": round(r.profit_factor, 2),
                    "avg_r": round(r.avg_r, 2),
                    "best_families": r.best_families
                }
                for r in regime_breakdown
            ],
            "decade_breakdown": [
                {
                    "decade": d.decade,
                    "trades": d.trades,
                    "profit_factor": round(d.profit_factor, 2),
                    "dominant_regime": d.dominant_regime
                }
                for d in decade_breakdown
            ]
        }
