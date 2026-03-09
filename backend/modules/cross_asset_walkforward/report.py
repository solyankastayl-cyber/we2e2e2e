"""
Report Layer
============

Generates JSON and Markdown reports for walk-forward runs.
"""

import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from .types import (
    WalkForwardRun, WalkForwardReport, SimulatedTrade,
    TradeMetrics, PortfolioMetrics, GovernanceMetrics,
    StrategyMetrics, RegimeBreakdown, DecadeBreakdown,
    CrossAssetComparison
)


class ReportGenerator:
    """
    Generates human-readable and machine-readable reports.
    
    Outputs:
    - JSON for programmatic consumption
    - Markdown for human review
    """
    
    @staticmethod
    def generate_report(
        run: WalkForwardRun,
        trade_metrics: TradeMetrics,
        portfolio_metrics: PortfolioMetrics,
        governance_metrics: GovernanceMetrics,
        strategy_breakdown: List[StrategyMetrics],
        regime_breakdown: List[RegimeBreakdown],
        decade_breakdown: List[DecadeBreakdown]
    ) -> WalkForwardReport:
        """Generate complete report object"""
        
        # Calculate years
        try:
            start = datetime.strptime(run.start_date, "%Y-%m-%d")
            end = datetime.strptime(run.end_date, "%Y-%m-%d")
            years = (end - start).days / 365.25
        except:
            years = 0
        
        return WalkForwardReport(
            run_id=run.run_id,
            asset=run.asset,
            asset_class=run.asset_class.value,
            mode=run.mode.value,
            start_date=run.start_date,
            end_date=run.end_date,
            total_bars=run.total_bars,
            years_simulated=years,
            trade_metrics=trade_metrics,
            portfolio_metrics=portfolio_metrics,
            governance_metrics=governance_metrics,
            strategy_breakdown=strategy_breakdown,
            regime_breakdown=regime_breakdown,
            decade_breakdown=decade_breakdown,
            generated_at=int(time.time() * 1000),
            dataset_version=run.dataset_version,
            policy_snapshot_id=run.policy_snapshot_id
        )
    
    @staticmethod
    def to_json(report: WalkForwardReport) -> Dict:
        """Export report as JSON"""
        return {
            "run_id": report.run_id,
            "asset": report.asset,
            "asset_class": report.asset_class,
            "mode": report.mode,
            
            "period": {
                "start_date": report.start_date,
                "end_date": report.end_date,
                "total_bars": report.total_bars,
                "years_simulated": round(report.years_simulated, 2)
            },
            
            "trade_metrics": {
                "total_trades": report.trade_metrics.total_trades,
                "winning_trades": report.trade_metrics.winning_trades,
                "losing_trades": report.trade_metrics.losing_trades,
                "win_rate": round(report.trade_metrics.win_rate, 4),
                "profit_factor": round(report.trade_metrics.profit_factor, 2),
                "expectancy": round(report.trade_metrics.expectancy, 4),
                "avg_win": round(report.trade_metrics.avg_win, 2),
                "avg_loss": round(report.trade_metrics.avg_loss, 2),
                "avg_r_multiple": round(report.trade_metrics.avg_r_multiple, 2),
                "max_winning_streak": report.trade_metrics.max_winning_streak,
                "max_losing_streak": report.trade_metrics.max_losing_streak
            },
            
            "portfolio_metrics": {
                "total_return": round(report.portfolio_metrics.total_return, 2),
                "total_return_pct": round(report.portfolio_metrics.total_return_pct, 4),
                "cagr": round(report.portfolio_metrics.cagr, 4),
                "sharpe": round(report.portfolio_metrics.sharpe, 2),
                "sortino": round(report.portfolio_metrics.sortino, 2),
                "calmar": round(report.portfolio_metrics.calmar, 2),
                "max_drawdown_pct": round(report.portfolio_metrics.max_drawdown_pct, 4),
                "volatility": round(report.portfolio_metrics.volatility, 4),
                "final_equity": round(report.portfolio_metrics.final_equity, 2),
                "ulcer_index": round(report.portfolio_metrics.ulcer_index, 4)
            },
            
            "governance_metrics": {
                "total_events": report.governance_metrics.total_events,
                "healing_events": report.governance_metrics.healing_events,
                "meta_reallocations": report.governance_metrics.meta_reallocations,
                "regime_changes": report.governance_metrics.regime_changes,
                "overlay_triggers": report.governance_metrics.overlay_triggers,
                "kill_switch_events": report.governance_metrics.kill_switch_events,
                "blocked_trades": report.governance_metrics.blocked_trades
            },
            
            "strategy_breakdown": [
                {
                    "strategy_id": s.strategy_id,
                    "trades": s.trades,
                    "win_rate": round(s.win_rate, 4),
                    "profit_factor": round(s.profit_factor, 2),
                    "contribution_pct": round(s.contribution_pct, 4),
                    "survival_rate": round(s.survival_rate, 2),
                    "demotion_count": s.demotion_count,
                    "recovery_count": s.recovery_count
                }
                for s in report.strategy_breakdown
            ],
            
            "regime_breakdown": [
                {
                    "regime": r.regime,
                    "trades": r.trades,
                    "win_rate": round(r.win_rate, 4),
                    "profit_factor": round(r.profit_factor, 2),
                    "avg_r": round(r.avg_r, 2),
                    "best_families": r.best_families
                }
                for r in report.regime_breakdown
            ],
            
            "decade_breakdown": [
                {
                    "decade": d.decade,
                    "trades": d.trades,
                    "profit_factor": round(d.profit_factor, 2),
                    "dominant_regime": d.dominant_regime
                }
                for d in report.decade_breakdown
            ],
            
            "metadata": {
                "generated_at": report.generated_at,
                "dataset_version": report.dataset_version,
                "policy_snapshot_id": report.policy_snapshot_id
            }
        }
    
    @staticmethod
    def to_markdown(report: WalkForwardReport) -> str:
        """Generate markdown report"""
        lines = []
        
        # Header
        lines.append(f"# Cross-Asset Walk-Forward Report")
        lines.append(f"")
        lines.append(f"**Asset:** {report.asset} ({report.asset_class})")
        lines.append(f"**Mode:** {report.mode}")
        lines.append(f"**Period:** {report.start_date} to {report.end_date}")
        lines.append(f"**Years:** {report.years_simulated:.1f}")
        lines.append(f"")
        
        # Summary metrics
        lines.append(f"## Summary Metrics")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Trades | {report.trade_metrics.total_trades} |")
        lines.append(f"| Win Rate | {report.trade_metrics.win_rate:.2%} |")
        lines.append(f"| Profit Factor | {report.trade_metrics.profit_factor:.2f} |")
        lines.append(f"| Sharpe | {report.portfolio_metrics.sharpe:.2f} |")
        lines.append(f"| CAGR | {report.portfolio_metrics.cagr:.2%} |")
        lines.append(f"| Max DD | {report.portfolio_metrics.max_drawdown_pct:.2%} |")
        lines.append(f"| Final Equity | ${report.portfolio_metrics.final_equity:,.2f} |")
        lines.append(f"")
        
        # Governance
        lines.append(f"## Governance Events")
        lines.append(f"")
        lines.append(f"| Event Type | Count |")
        lines.append(f"|------------|-------|")
        lines.append(f"| Total | {report.governance_metrics.total_events} |")
        lines.append(f"| Self-Healing | {report.governance_metrics.healing_events} |")
        lines.append(f"| Meta Reallocations | {report.governance_metrics.meta_reallocations} |")
        lines.append(f"| Regime Changes | {report.governance_metrics.regime_changes} |")
        lines.append(f"| Overlay Triggers | {report.governance_metrics.overlay_triggers} |")
        lines.append(f"| Kill Switch | {report.governance_metrics.kill_switch_events} |")
        lines.append(f"")
        
        # Strategy breakdown
        if report.strategy_breakdown:
            lines.append(f"## Strategy Breakdown")
            lines.append(f"")
            lines.append(f"| Strategy | Trades | WR | PF | Contribution | Survival |")
            lines.append(f"|----------|--------|----|----|--------------|----------|")
            for s in report.strategy_breakdown[:10]:  # Top 10
                lines.append(
                    f"| {s.strategy_id[:20]} | {s.trades} | "
                    f"{s.win_rate:.2%} | {s.profit_factor:.2f} | "
                    f"{s.contribution_pct:.2%} | {s.survival_rate:.2f} |"
                )
            lines.append(f"")
        
        # Regime breakdown
        if report.regime_breakdown:
            lines.append(f"## Regime Breakdown")
            lines.append(f"")
            lines.append(f"| Regime | Trades | WR | PF | Best Families |")
            lines.append(f"|--------|--------|----|----|---------------|")
            for r in report.regime_breakdown:
                best = ", ".join(r.best_families) if r.best_families else "-"
                lines.append(
                    f"| {r.regime} | {r.trades} | "
                    f"{r.win_rate:.2%} | {r.profit_factor:.2f} | {best} |"
                )
            lines.append(f"")
        
        # Decade breakdown
        if report.decade_breakdown:
            lines.append(f"## Decade Breakdown")
            lines.append(f"")
            lines.append(f"| Decade | Trades | PF | Dominant Regime |")
            lines.append(f"|--------|--------|-----|-----------------|")
            for d in report.decade_breakdown:
                lines.append(
                    f"| {d.decade} | {d.trades} | "
                    f"{d.profit_factor:.2f} | {d.dominant_regime} |"
                )
            lines.append(f"")
        
        # Footer
        lines.append(f"---")
        lines.append(f"")
        lines.append(f"*Generated: {datetime.utcfromtimestamp(report.generated_at/1000).isoformat()}*")
        lines.append(f"*Dataset: {report.dataset_version}*")
        
        return "\n".join(lines)
    
    @staticmethod
    def generate_comparison_report(
        reports: List[WalkForwardReport],
        mode: str
    ) -> CrossAssetComparison:
        """Generate cross-asset comparison report"""
        comparison_id = f"comp_{int(time.time())}"
        
        assets = [r.asset for r in reports]
        
        # Build metrics matrix
        metrics_matrix = []
        for report in reports:
            metrics_matrix.append({
                "asset": report.asset,
                "asset_class": report.asset_class,
                "years": round(report.years_simulated, 1),
                "trades": report.trade_metrics.total_trades,
                "win_rate": round(report.trade_metrics.win_rate, 4),
                "profit_factor": round(report.trade_metrics.profit_factor, 2),
                "sharpe": round(report.portfolio_metrics.sharpe, 2),
                "cagr": round(report.portfolio_metrics.cagr, 4),
                "max_dd": round(report.portfolio_metrics.max_drawdown_pct, 4),
                "calmar": round(report.portfolio_metrics.calmar, 2),
                "final_equity": round(report.portfolio_metrics.final_equity, 2),
                "governance_events": report.governance_metrics.total_events
            })
        
        # Rankings
        sharpe_ranking = sorted(
            metrics_matrix, 
            key=lambda x: x["sharpe"], 
            reverse=True
        )
        sharpe_ranking = [m["asset"] for m in sharpe_ranking]
        
        pf_ranking = sorted(
            metrics_matrix,
            key=lambda x: x["profit_factor"],
            reverse=True
        )
        pf_ranking = [m["asset"] for m in pf_ranking]
        
        cagr_ranking = sorted(
            metrics_matrix,
            key=lambda x: x["cagr"],
            reverse=True
        )
        cagr_ranking = [m["asset"] for m in cagr_ranking]
        
        # Universal edge check
        # Edge is universal if PF > 1 for majority of assets
        pf_positive = sum(1 for m in metrics_matrix if m["profit_factor"] > 1)
        universal_edge = pf_positive >= len(metrics_matrix) * 0.7
        confidence = pf_positive / len(metrics_matrix) if metrics_matrix else 0
        
        return CrossAssetComparison(
            comparison_id=comparison_id,
            assets=assets,
            mode=mode,
            metrics_matrix=metrics_matrix,
            sharpe_ranking=sharpe_ranking,
            pf_ranking=pf_ranking,
            cagr_ranking=cagr_ranking,
            universal_edge=universal_edge,
            universal_edge_confidence=confidence,
            generated_at=int(time.time() * 1000)
        )
    
    @staticmethod
    def comparison_to_markdown(comparison: CrossAssetComparison) -> str:
        """Generate markdown comparison report"""
        lines = []
        
        lines.append(f"# Cross-Asset Comparison Report")
        lines.append(f"")
        lines.append(f"**Mode:** {comparison.mode}")
        lines.append(f"**Assets:** {', '.join(comparison.assets)}")
        lines.append(f"**Universal Edge:** {'YES' if comparison.universal_edge else 'NO'} ({comparison.universal_edge_confidence:.0%} confidence)")
        lines.append(f"")
        
        # Metrics table
        lines.append(f"## Performance Matrix")
        lines.append(f"")
        lines.append(f"| Asset | Class | Years | Trades | WR | PF | Sharpe | CAGR | MaxDD |")
        lines.append(f"|-------|-------|-------|--------|----|----|--------|------|-------|")
        
        for m in comparison.metrics_matrix:
            lines.append(
                f"| {m['asset']} | {m['asset_class']} | {m['years']} | {m['trades']} | "
                f"{m['win_rate']:.2%} | {m['profit_factor']:.2f} | {m['sharpe']:.2f} | "
                f"{m['cagr']:.2%} | {m['max_dd']:.2%} |"
            )
        lines.append(f"")
        
        # Rankings
        lines.append(f"## Rankings")
        lines.append(f"")
        lines.append(f"**By Sharpe:** {' > '.join(comparison.sharpe_ranking)}")
        lines.append(f"**By PF:** {' > '.join(comparison.pf_ranking)}")
        lines.append(f"**By CAGR:** {' > '.join(comparison.cagr_ranking)}")
        lines.append(f"")
        
        # Verdict
        lines.append(f"## Verdict")
        lines.append(f"")
        if comparison.universal_edge:
            lines.append(f"**UNIVERSAL EDGE DETECTED** - System shows positive profit factor on {comparison.universal_edge_confidence:.0%} of assets.")
        else:
            lines.append(f"**NO UNIVERSAL EDGE** - System does not show consistent profitability across all asset classes.")
        
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"*Generated: {datetime.utcfromtimestamp(comparison.generated_at/1000).isoformat()}*")
        
        return "\n".join(lines)
