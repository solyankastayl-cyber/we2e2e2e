"""
Stress Lab Service
==================

Phase 9.30B - Service layer for stress testing.
"""

import time
from typing import Dict, List, Optional, Any

from .types import (
    StressRun, StressRunMode, StressRunStatus,
    StressBatchResult
)
from .scenarios import ALL_SCENARIOS
from .runner import stress_runner


class StressLabService:
    """Service for stress lab operations"""

    def __init__(self):
        self.runner = stress_runner

    # ============================================
    # Scenarios
    # ============================================

    def get_scenarios(self, asset_class: str = None) -> Dict:
        """Get available stress scenarios"""
        scenarios = list(ALL_SCENARIOS.values())

        if asset_class:
            scenarios = [s for s in scenarios if s.asset_class.value == asset_class.upper()]

        return {
            "total": len(scenarios),
            "scenarios": [
                {
                    "scenario_id": s.scenario_id,
                    "name": s.name,
                    "description": s.description,
                    "asset_class": s.asset_class.value,
                    "tags": s.tags,
                    "start_date": s.start_date,
                    "end_date": s.end_date,
                    "total_bars": s.total_bars,
                    "crisis_profile": {
                        "peak_drawdown": s.crisis_profile.peak_drawdown,
                        "drawdown_duration_bars": s.crisis_profile.drawdown_duration_bars,
                        "recovery_duration_bars": s.crisis_profile.recovery_duration_bars,
                        "volatility_multiplier": s.crisis_profile.volatility_multiplier,
                        "correlation_spike": s.crisis_profile.correlation_spike,
                        "mean_reversion_after": s.crisis_profile.mean_reversion_after
                    },
                    "affected_assets": s.affected_assets
                }
                for s in scenarios
            ]
        }

    # ============================================
    # Run Stress Tests
    # ============================================

    def run_scenario(
        self,
        scenario_id: str,
        mode: str = "FULL_SYSTEM",
        initial_capital: float = 100000.0
    ) -> Dict:
        """Run a single stress scenario"""
        run_mode = StressRunMode(mode)
        run = self.runner.run_scenario(scenario_id, run_mode, initial_capital=initial_capital)
        return self._run_to_dict(run)

    def run_batch(
        self,
        scenario_ids: Optional[List[str]] = None,
        mode: str = "FULL_SYSTEM",
        initial_capital: float = 100000.0
    ) -> Dict:
        """Run multiple scenarios"""
        run_mode = StressRunMode(mode)
        batch = self.runner.run_batch(scenario_ids, run_mode, initial_capital=initial_capital)
        return self._batch_to_dict(batch)

    # ============================================
    # Query Results
    # ============================================

    def get_run(self, run_id: str) -> Optional[Dict]:
        run = self.runner.get_run(run_id)
        if not run:
            return None
        return self._run_to_dict(run)

    def get_report(self, run_id: str) -> Optional[Dict]:
        """Get condensed report for a run"""
        run = self.runner.get_run(run_id)
        if not run:
            return None

        return {
            "run_id": run.run_id,
            "scenario": run.scenario_name,
            "mode": run.mode.value,
            "verdict": run.verdict,
            "verdict_details": run.verdict_details,
            "survived": run.survived,
            "performance": {
                "total_return": run.metrics.total_return,
                "total_return_pct": run.metrics.total_return_pct,
                "max_drawdown_pct": run.metrics.max_drawdown_pct,
                "recovery_bars": run.metrics.recovery_bars,
                "stress_sharpe": run.metrics.stress_sharpe,
                "calmar": run.metrics.calmar,
                "capital_preserved_pct": run.metrics.capital_preserved_pct
            },
            "governance": {
                "regime_switches": run.metrics.regime_switches,
                "healing_events": run.metrics.healing_events,
                "demotions": run.metrics.demotions,
                "overlay_reductions": run.metrics.overlay_reductions
            },
            "survival": {
                "strategies_survived": run.metrics.strategies_survived,
                "strategies_paused": run.metrics.strategies_paused,
                "strategies_disabled": run.metrics.strategies_disabled,
                "family_collapses": run.metrics.family_collapses
            },
            "strategy_results": [
                {
                    "name": sr.name,
                    "family": sr.family,
                    "survived": sr.survived,
                    "pnl": sr.total_pnl,
                    "trades": sr.trades,
                    "was_paused": sr.was_paused
                }
                for sr in run.strategy_results
            ]
        }

    def get_events(self, run_id: str) -> Optional[Dict]:
        """Get timeline events for a run"""
        run = self.runner.get_run(run_id)
        if not run:
            return None

        return {
            "run_id": run.run_id,
            "scenario": run.scenario_name,
            "total_events": len(run.timeline),
            "timeline": [
                {
                    "bar": e.bar,
                    "event_type": e.event_type,
                    "description": e.description,
                    "severity": e.severity,
                    "details": e.details
                }
                for e in run.timeline
            ]
        }

    def get_metrics(self, run_id: str) -> Optional[Dict]:
        """Get detailed metrics for a run"""
        run = self.runner.get_run(run_id)
        if not run:
            return None

        m = run.metrics
        return {
            "run_id": run.run_id,
            "scenario": run.scenario_name,
            "performance": {
                "total_return": m.total_return,
                "total_return_pct": m.total_return_pct,
                "max_drawdown": m.max_drawdown,
                "max_drawdown_pct": m.max_drawdown_pct,
                "recovery_bars": m.recovery_bars,
                "tail_loss": m.tail_loss,
                "stress_sharpe": m.stress_sharpe,
                "calmar": m.calmar
            },
            "governance": {
                "regime_switches": m.regime_switches,
                "healing_events": m.healing_events,
                "demotions": m.demotions,
                "overlay_reductions": m.overlay_reductions,
                "blocked_signals": m.blocked_signals,
                "total_governance_events": m.total_governance_events
            },
            "survival": {
                "strategies_survived": m.strategies_survived,
                "strategies_paused": m.strategies_paused,
                "strategies_disabled": m.strategies_disabled,
                "capital_preserved_pct": m.capital_preserved_pct,
                "family_collapses": m.family_collapses
            },
            "activity": {
                "total_cycles": m.total_cycles,
                "total_trades": m.total_trades
            }
        }

    def list_runs(self, limit: int = 20) -> Dict:
        """List all stress runs"""
        runs = self.runner.list_runs(limit)
        return {
            "total": len(self.runner.runs),
            "runs": [
                {
                    "run_id": r.run_id,
                    "scenario": r.scenario_name,
                    "mode": r.mode.value,
                    "status": r.status.value,
                    "verdict": r.verdict,
                    "survived": r.survived,
                    "max_drawdown_pct": r.metrics.max_drawdown_pct,
                    "capital_preserved_pct": r.metrics.capital_preserved_pct,
                    "completed_at": r.completed_at
                }
                for r in runs
            ]
        }

    # ============================================
    # Health
    # ============================================

    def get_health(self) -> Dict:
        return {
            "enabled": True,
            "version": "phase9.30B",
            "status": "ok",
            "total_scenarios": len(ALL_SCENARIOS),
            "total_runs": len(self.runner.runs),
            "total_batches": len(self.runner.batches),
            "timestamp": int(time.time() * 1000)
        }

    # ============================================
    # Serialization
    # ============================================

    def _run_to_dict(self, run: StressRun) -> Dict:
        return {
            "run_id": run.run_id,
            "scenario_id": run.scenario_id,
            "scenario_name": run.scenario_name,
            "mode": run.mode.value,
            "status": run.status.value,
            "initial_equity": run.initial_equity,
            "final_equity": run.final_equity,
            "survived": run.survived,
            "verdict": run.verdict,
            "verdict_details": run.verdict_details,
            "metrics": {
                "total_return": run.metrics.total_return,
                "total_return_pct": run.metrics.total_return_pct,
                "max_drawdown_pct": run.metrics.max_drawdown_pct,
                "recovery_bars": run.metrics.recovery_bars,
                "tail_loss": run.metrics.tail_loss,
                "stress_sharpe": run.metrics.stress_sharpe,
                "calmar": run.metrics.calmar,
                "capital_preserved_pct": run.metrics.capital_preserved_pct,
                "regime_switches": run.metrics.regime_switches,
                "healing_events": run.metrics.healing_events,
                "strategies_survived": run.metrics.strategies_survived,
                "strategies_paused": run.metrics.strategies_paused,
                "family_collapses": run.metrics.family_collapses,
                "total_trades": run.metrics.total_trades
            },
            "strategy_results": [
                {
                    "strategy_id": sr.strategy_id,
                    "alpha_id": sr.alpha_id,
                    "name": sr.name,
                    "family": sr.family,
                    "survived": sr.survived,
                    "total_pnl": sr.total_pnl,
                    "trades": sr.trades,
                    "winning_trades": sr.winning_trades,
                    "was_paused": sr.was_paused,
                    "was_disabled": sr.was_disabled
                }
                for sr in run.strategy_results
            ],
            "timeline_events": len(run.timeline),
            "equity_curve_points": len(run.equity_curve),
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "duration_ms": run.duration_ms
        }

    def _batch_to_dict(self, batch: StressBatchResult) -> Dict:
        return {
            "batch_id": batch.batch_id,
            "mode": batch.mode,
            "total_scenarios": batch.total_scenarios,
            "scenarios_survived": batch.scenarios_survived,
            "scenarios_failed": batch.scenarios_failed,
            "survival_rate": round(
                batch.scenarios_survived / max(1, batch.total_scenarios), 4
            ),
            "avg_drawdown": batch.avg_drawdown,
            "avg_recovery_bars": batch.avg_recovery,
            "weakest_scenario": batch.weakest_scenario,
            "strongest_scenario": batch.strongest_scenario,
            "family_vulnerability": batch.family_vulnerability,
            "run_ids": batch.runs,
            "started_at": batch.started_at,
            "completed_at": batch.completed_at
        }


# Singleton
stress_service = StressLabService()
