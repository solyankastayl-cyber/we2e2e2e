"""
Autopsy Engine Service
======================

Phase 9.30C - Service layer for autopsy operations.
"""

import time
from typing import Dict, List, Optional, Any

from .types import AutopsyReport, FailurePattern, AutopsyDigest
from .engine import autopsy_engine


class AutopsyService:
    """Service for autopsy engine operations"""

    def __init__(self):
        self.engine = autopsy_engine

    # ============================================
    # Run Autopsies
    # ============================================

    def run_strategy_autopsy(
        self,
        strategy_id: str,
        alpha_id: str,
        name: str,
        family: str,
        asset_class: str = "",
        total_pnl: float = 0.0,
        trades: int = 0,
        winning_trades: int = 0,
        regime: str = "NORMAL",
        was_paused: bool = False,
        was_disabled: bool = False,
        drawdown_pct: float = 0.0
    ) -> Dict:
        """Run autopsy on a failed strategy"""
        report = self.engine.autopsy_strategy(
            strategy_id=strategy_id,
            alpha_id=alpha_id,
            name=name,
            family=family,
            asset_class=asset_class,
            total_pnl=total_pnl,
            trades=trades,
            winning_trades=winning_trades,
            regime=regime,
            was_paused=was_paused,
            was_disabled=was_disabled,
            drawdown_pct=drawdown_pct
        )
        return self._report_to_dict(report)

    def run_portfolio_autopsy(
        self,
        portfolio_id: str,
        equity: float = 0.0,
        initial_capital: float = 100000.0,
        drawdown_pct: float = 0.0,
        regime: str = "NORMAL",
        strategies: List[Dict] = None,
        trades: int = 0
    ) -> Dict:
        """Run autopsy on portfolio drawdown"""
        report = self.engine.autopsy_portfolio(
            portfolio_id=portfolio_id,
            equity=equity,
            initial_capital=initial_capital,
            drawdown_pct=drawdown_pct,
            regime=regime,
            strategies=strategies,
            trades=trades
        )
        return self._report_to_dict(report)

    def run_stress_autopsy(
        self,
        run_id: str,
        scenario_name: str,
        scenario_tags: List[str] = None,
        max_drawdown_pct: float = 0.0,
        capital_preserved_pct: float = 1.0,
        regime: str = "NORMAL",
        strategy_results: List[Dict] = None,
        governance_events: int = 0,
        healing_events: int = 0,
        family_collapses: List[str] = None
    ) -> Dict:
        """Run autopsy on stress test results"""
        report = self.engine.autopsy_stress_run(
            run_id=run_id,
            scenario_name=scenario_name,
            scenario_tags=scenario_tags,
            max_drawdown_pct=max_drawdown_pct,
            capital_preserved_pct=capital_preserved_pct,
            regime=regime,
            strategy_results=strategy_results,
            governance_events=governance_events,
            healing_events=healing_events,
            family_collapses=family_collapses
        )
        return self._report_to_dict(report)

    # ============================================
    # Queries
    # ============================================

    def get_reports(
        self,
        entity_type: str = None,
        family: str = None,
        severity: str = None,
        limit: int = 50
    ) -> Dict:
        """Get autopsy reports with filters"""
        reports = self.engine.get_reports(entity_type, family, severity, limit)
        return {
            "total": len(self.engine.reports),
            "returned": len(reports),
            "reports": [self._report_to_dict(r) for r in reports]
        }

    def get_report(self, report_id: str) -> Optional[Dict]:
        """Get single report"""
        report = self.engine.reports.get(report_id)
        if not report:
            return None
        return self._report_to_dict(report)

    def get_patterns(self, min_frequency: int = 1) -> Dict:
        """Get failure patterns"""
        patterns = self.engine.get_patterns(min_frequency)
        return {
            "total": len(patterns),
            "patterns": [self._pattern_to_dict(p) for p in patterns]
        }

    def get_root_causes(self) -> Dict:
        """Get aggregated root cause summary"""
        causes = self.engine.get_root_causes_summary()
        return {
            "total_causes": len(causes),
            "root_causes": [
                {"cause": c, "count": n} for c, n in causes.items()
            ]
        }

    def get_digest(self) -> Dict:
        """Get full autopsy digest"""
        digest = self.engine.compute_digest()
        return {
            "total_reports": digest.total_reports,
            "total_patterns": digest.total_patterns,
            "top_root_causes": digest.top_root_causes,
            "family_vulnerability": {
                fam: {
                    "failures": data["failures"],
                    "total_pnl": round(data["total_pnl"], 2),
                    "root_causes": list(set(data["root_causes"]))
                }
                for fam, data in digest.family_vulnerability.items()
            },
            "regime_risk_map": digest.regime_risk_map,
            "most_fragile_families": digest.most_fragile_families,
            "most_resilient_families": digest.most_resilient_families,
            "computed_at": digest.computed_at
        }

    # ============================================
    # Health
    # ============================================

    def get_health(self) -> Dict:
        return {
            "enabled": True,
            "version": "phase9.30C",
            "status": "ok",
            "total_reports": len(self.engine.reports),
            "total_patterns": len(self.engine.patterns),
            "timestamp": int(time.time() * 1000)
        }

    # ============================================
    # Serialization
    # ============================================

    def _report_to_dict(self, r: AutopsyReport) -> Dict:
        return {
            "report_id": r.report_id,
            "entity_type": r.entity_type.value,
            "entity_id": r.entity_id,
            "event_type": r.event_type.value,
            "root_causes": r.root_causes,
            "contributing_factors": r.contributing_factors,
            "regime_context": r.regime_context,
            "severity": r.severity,
            "family": r.family,
            "asset_class": r.asset_class,
            "summary": r.summary,
            "recommendations": r.recommendations,
            "drawdown_pct": r.drawdown_pct,
            "pnl_at_failure": r.pnl_at_failure,
            "trades_at_failure": r.trades_at_failure,
            "win_rate_at_failure": r.win_rate_at_failure,
            "timeline": r.timeline,
            "created_at": r.created_at
        }

    def _pattern_to_dict(self, p: FailurePattern) -> Dict:
        return {
            "pattern_id": p.pattern_id,
            "root_cause": p.root_cause,
            "family": p.family,
            "asset_class": p.asset_class,
            "regime": p.regime,
            "frequency": p.frequency,
            "avg_severity": p.avg_severity,
            "affected_strategies": p.affected_strategies,
            "affected_scenarios": p.affected_scenarios,
            "description": p.description,
            "first_seen": p.first_seen,
            "last_seen": p.last_seen
        }


# Singleton
autopsy_service = AutopsyService()
