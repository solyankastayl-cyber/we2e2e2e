"""
Autopsy Engine Core
===================

Phase 9.30C - Analyzes failures from Shadow Portfolio and Stress Lab.

Turns every failure into structured knowledge:
- Root cause identification
- Contributing factor analysis
- Pattern extraction
- Recommendations generation

Phase D: Integrated with Event Bus for automatic trigger on alpha events.
"""

import time
import uuid
import math
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .types import (
    AutopsyReport, FailurePattern, AutopsyDigest,
    AutopsyEntityType, AutopsyEventType, RootCause, Severity
)

# Event Bus integration
try:
    from modules.event_bus import create_publisher, create_subscriber, EventType
    _event_publisher = create_publisher("autopsy_engine")
    _event_subscriber = create_subscriber("autopsy_engine")
    EVENT_BUS_ENABLED = True
except ImportError:
    _event_publisher = None
    _event_subscriber = None
    EVENT_BUS_ENABLED = False


class AutopsyEngine:
    """
    Analyzes Shadow Portfolio and Stress Lab results
    to produce structured failure knowledge.
    """

    def __init__(self):
        self.reports: Dict[str, AutopsyReport] = {}
        self.patterns: Dict[str, FailurePattern] = {}
        self._init_event_subscriptions()
    
    def _init_event_subscriptions(self):
        """Subscribe to alpha events for automatic autopsy trigger"""
        if not EVENT_BUS_ENABLED or not _event_subscriber:
            return
        
        def on_alpha_demoted(event):
            """Auto-trigger autopsy when alpha is demoted"""
            payload = event.payload
            alpha_id = payload.get("alpha_id", "")
            reason = payload.get("reason", "unknown")
            if alpha_id:
                self.autopsy_strategy(
                    strategy_id=f"auto_{alpha_id}",
                    alpha_id=alpha_id,
                    name=alpha_id,
                    family=payload.get("family", "UNKNOWN"),
                    was_disabled=True,
                    context={"trigger": "event_bus", "reason": reason}
                )
        
        try:
            _event_subscriber.subscribe(
                ["alpha_demoted", "alpha_rejected"],
                on_alpha_demoted
            )
            print("[AutopsyEngine] Subscribed to alpha events")
        except Exception as e:
            print(f"[AutopsyEngine] Event subscription failed: {e}")

    # ============================================
    # Strategy Autopsy
    # ============================================

    def autopsy_strategy(
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
        drawdown_pct: float = 0.0,
        context: Dict = None
    ) -> AutopsyReport:
        """Analyze why a strategy failed"""

        report_id = f"autopsy_strat_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)

        root_causes = []
        contributing_factors = []
        recommendations = []
        timeline = []

        win_rate = winning_trades / trades if trades > 0 else 0.0

        # Root cause analysis
        # 1. Low edge detection
        if trades >= 5 and win_rate < 0.45:
            root_causes.append(RootCause.LOW_EDGE.value)
            contributing_factors.append(f"Win rate {win_rate:.1%} below threshold")
            recommendations.append("Review signal generation logic for this alpha family")

        # 2. Regime mismatch
        if regime in ("STRESS", "CRISIS"):
            if family in ("TREND", "BREAKOUT", "MOMENTUM"):
                root_causes.append(RootCause.REGIME_MISMATCH.value)
                contributing_factors.append(f"Trend/Breakout family in {regime} regime")
                recommendations.append(f"Add regime filter: disable {family} in {regime}")

        # 3. Overfitting signals
        if trades >= 10 and total_pnl < 0 and win_rate > 0.5:
            root_causes.append(RootCause.OVERFITTED_ALPHA.value)
            contributing_factors.append("Positive win rate but negative PnL — oversized losers")
            recommendations.append("Review position sizing and stop-loss configuration")

        # 4. Signal degradation
        if was_paused or was_disabled:
            contributing_factors.append("Strategy was paused/disabled by governance")
            if total_pnl < 0:
                root_causes.append(RootCause.SIGNAL_DEGRADATION.value)
                recommendations.append("Consider removing alpha from registry")

        # 5. False breakout pattern
        if family == "BREAKOUT" and trades >= 3 and win_rate < 0.35:
            root_causes.append(RootCause.FALSE_BREAKOUT.value)
            contributing_factors.append("Breakout family with very low win rate")
            recommendations.append("Add volume confirmation filter to breakout signals")

        # 6. Late entry
        if family in ("MOMENTUM", "TREND") and total_pnl < 0:
            root_causes.append(RootCause.LATE_ENTRY.value)
            contributing_factors.append(f"{family} strategy may be entering after move exhaustion")

        # Default if no specific cause found
        if not root_causes:
            root_causes.append(RootCause.LOW_EDGE.value)
            contributing_factors.append("General underperformance")

        # Severity
        severity = self._compute_severity(total_pnl, drawdown_pct, trades)

        # Timeline
        timeline.append({
            "event": "strategy_created",
            "description": f"Strategy {name} entered shadow portfolio"
        })
        if was_paused:
            timeline.append({
                "event": "strategy_paused",
                "description": f"Governance paused strategy in {regime} regime"
            })
        if total_pnl < 0:
            timeline.append({
                "event": "pnl_negative",
                "description": f"PnL reached {total_pnl:.2f}"
            })

        summary = (
            f"Strategy {name} ({family}) failed with PnL={total_pnl:.2f}, "
            f"WR={win_rate:.1%}, in {regime} regime. "
            f"Primary causes: {', '.join(root_causes)}"
        )

        report = AutopsyReport(
            report_id=report_id,
            entity_type=AutopsyEntityType.STRATEGY,
            entity_id=strategy_id,
            event_type=AutopsyEventType.STRATEGY_FAILURE,
            root_causes=root_causes,
            contributing_factors=contributing_factors,
            regime_context=regime,
            severity=severity,
            family=family,
            asset_class=asset_class,
            summary=summary,
            recommendations=recommendations,
            drawdown_pct=drawdown_pct,
            pnl_at_failure=total_pnl,
            trades_at_failure=trades,
            win_rate_at_failure=round(win_rate, 4),
            timeline=timeline,
            created_at=now
        )

        self.reports[report_id] = report
        self._update_patterns(report)
        return report

    # ============================================
    # Portfolio Autopsy
    # ============================================

    def autopsy_portfolio(
        self,
        portfolio_id: str,
        equity: float = 0.0,
        initial_capital: float = 100000.0,
        drawdown_pct: float = 0.0,
        regime: str = "NORMAL",
        strategies: List[Dict] = None,
        trades: int = 0,
        context: Dict = None
    ) -> AutopsyReport:
        """Analyze why a portfolio experienced drawdown"""

        report_id = f"autopsy_port_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)

        root_causes = []
        contributing_factors = []
        recommendations = []
        timeline = []

        strategies = strategies or []
        total_pnl = equity - initial_capital

        # 1. Family concentration
        family_counts = defaultdict(int)
        family_pnl = defaultdict(float)
        for s in strategies:
            fam = s.get("family", "UNKNOWN")
            family_counts[fam] += 1
            family_pnl[fam] += s.get("total_pnl", 0)

        if family_counts:
            max_fam = max(family_counts.values())
            total_strats = sum(family_counts.values())
            if max_fam / total_strats > 0.4:
                concentrated_fam = max(family_counts, key=family_counts.get)
                root_causes.append(RootCause.FAMILY_CONCENTRATION.value)
                contributing_factors.append(f"Family concentration: {concentrated_fam} = {max_fam}/{total_strats}")
                recommendations.append("Diversify strategy families to reduce concentration risk")

        # 2. Correlation spike (implied from family overlap)
        negative_families = [f for f, p in family_pnl.items() if p < 0]
        if len(negative_families) >= 3:
            root_causes.append(RootCause.CORRELATION_SPIKE.value)
            contributing_factors.append(f"Multiple families losing: {', '.join(negative_families)}")
            recommendations.append("Add orthogonality check between strategy families")

        # 3. Regime mismatch
        if regime in ("STRESS", "CRISIS") and drawdown_pct > 0.10:
            root_causes.append(RootCause.REGIME_MISMATCH.value)
            contributing_factors.append(f"High drawdown ({drawdown_pct:.1%}) in {regime}")
            recommendations.append("Review regime-based exposure reduction thresholds")

        # 4. Volatility spike
        if drawdown_pct > 0.20:
            root_causes.append(RootCause.VOLATILITY_SPIKE.value)
            contributing_factors.append(f"Extreme drawdown: {drawdown_pct:.1%}")
            recommendations.append("Consider tighter stop-losses in high-vol regimes")

        # 5. Governance delay
        paused_count = sum(1 for s in strategies if s.get("was_paused"))
        disabled_count = sum(1 for s in strategies if s.get("was_disabled"))
        if paused_count == 0 and drawdown_pct > 0.15:
            root_causes.append(RootCause.GOVERNANCE_DELAY.value)
            contributing_factors.append("No strategies paused despite significant drawdown")
            recommendations.append("Tune governance thresholds for faster reaction")

        if not root_causes:
            root_causes.append(RootCause.LOW_EDGE.value)

        severity = self._compute_severity(total_pnl, drawdown_pct, trades)

        summary = (
            f"Portfolio drawdown {drawdown_pct:.1%} (PnL={total_pnl:.2f}). "
            f"Regime={regime}. Causes: {', '.join(root_causes)}"
        )

        report = AutopsyReport(
            report_id=report_id,
            entity_type=AutopsyEntityType.PORTFOLIO,
            entity_id=portfolio_id,
            event_type=AutopsyEventType.PORTFOLIO_DRAWDOWN,
            root_causes=root_causes,
            contributing_factors=contributing_factors,
            regime_context=regime,
            severity=severity,
            summary=summary,
            recommendations=recommendations,
            drawdown_pct=round(drawdown_pct, 6),
            pnl_at_failure=round(total_pnl, 2),
            trades_at_failure=trades,
            timeline=timeline,
            created_at=now
        )

        self.reports[report_id] = report
        self._update_patterns(report)
        return report

    # ============================================
    # Stress Run Autopsy
    # ============================================

    def autopsy_stress_run(
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
        family_collapses: List[str] = None,
        context: Dict = None
    ) -> AutopsyReport:
        """Analyze results of a stress test run"""

        report_id = f"autopsy_stress_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)

        root_causes = []
        contributing_factors = []
        recommendations = []
        timeline = []

        strategy_results = strategy_results or []
        family_collapses = family_collapses or []
        scenario_tags = scenario_tags or []

        loss_pct = 1.0 - capital_preserved_pct

        # 1. Family collapses
        if family_collapses:
            root_causes.append(RootCause.FAMILY_CONCENTRATION.value)
            contributing_factors.append(f"Family collapses: {', '.join(family_collapses)}")
            recommendations.append(f"Avoid heavy allocation to: {', '.join(family_collapses)}")

            for fam in family_collapses:
                timeline.append({
                    "event": "family_collapse",
                    "description": f"{fam} family collapsed in {scenario_name}"
                })

        # 2. Regime context
        if "CRASH" in scenario_tags or "VOL_SPIKE" in scenario_tags:
            root_causes.append(RootCause.VOLATILITY_SPIKE.value)
            contributing_factors.append("Scenario involved extreme volatility")

        if "LIQUIDITY" in scenario_tags:
            root_causes.append(RootCause.LIQUIDITY_SHOCK.value)
            contributing_factors.append("Scenario involved liquidity stress")

        if "CORRELATION" in scenario_tags:
            root_causes.append(RootCause.CORRELATION_SPIKE.value)
            contributing_factors.append("Scenario involved correlation spike")

        # 3. Governance analysis
        if healing_events == 0 and loss_pct > 0.10:
            root_causes.append(RootCause.GOVERNANCE_DELAY.value)
            contributing_factors.append("No healing events despite significant losses")
            recommendations.append("Review self-healing sensitivity thresholds")

        # 4. Strategy-level analysis
        survivors = [s for s in strategy_results if s.get("survived", True)]
        failures = [s for s in strategy_results if not s.get("survived", True)]

        if failures:
            failed_families = set(s.get("family", "") for s in failures)
            contributing_factors.append(f"Failed families: {', '.join(failed_families)}")

        survivor_families = set(s.get("family", "") for s in survivors)
        if survivor_families:
            recommendations.append(f"Resilient families: {', '.join(survivor_families)}")

        if not root_causes:
            if loss_pct > 0.15:
                root_causes.append(RootCause.LOW_EDGE.value)
            else:
                root_causes.append("WITHIN_TOLERANCE")

        severity = self._compute_severity(
            -(loss_pct * 100000), max_drawdown_pct, 0
        )

        summary = (
            f"Stress: {scenario_name}. Capital preserved: {capital_preserved_pct:.1%}. "
            f"MaxDD: {max_drawdown_pct:.1%}. "
            f"{'Family collapses: ' + ', '.join(family_collapses) if family_collapses else 'No family collapses'}. "
            f"Causes: {', '.join(root_causes)}"
        )

        report = AutopsyReport(
            report_id=report_id,
            entity_type=AutopsyEntityType.STRESS_RUN,
            entity_id=run_id,
            event_type=AutopsyEventType.STRESS_COLLAPSE,
            root_causes=root_causes,
            contributing_factors=contributing_factors,
            regime_context=regime,
            severity=severity,
            summary=summary,
            recommendations=recommendations,
            drawdown_pct=round(max_drawdown_pct, 6),
            pnl_at_failure=round(-(1 - capital_preserved_pct) * 100000, 2),
            timeline=timeline,
            created_at=now
        )

        self.reports[report_id] = report
        self._update_patterns(report)
        return report

    # ============================================
    # Pattern Extraction
    # ============================================

    def _update_patterns(self, report: AutopsyReport):
        """Extract and update failure patterns from report"""
        now = int(time.time() * 1000)

        for cause in report.root_causes:
            pattern_key = f"{cause}_{report.family}_{report.regime_context}"
            pattern = self.patterns.get(pattern_key)

            if not pattern:
                pattern = FailurePattern(
                    pattern_id=pattern_key,
                    root_cause=cause,
                    family=report.family,
                    regime=report.regime_context,
                    asset_class=report.asset_class,
                    first_seen=now,
                    description=f"{cause} in {report.family or 'portfolio'} during {report.regime_context}"
                )
                self.patterns[pattern_key] = pattern

            pattern.frequency += 1
            pattern.last_seen = now

            sev_map = {"LOW": 0.25, "MEDIUM": 0.5, "HIGH": 0.75, "CRITICAL": 1.0}
            current_sev = sev_map.get(report.severity, 0.5)
            pattern.avg_severity = round(
                (pattern.avg_severity * (pattern.frequency - 1) + current_sev) / pattern.frequency, 3
            )

            if report.entity_id not in pattern.affected_strategies:
                pattern.affected_strategies.append(report.entity_id)

    def get_patterns(self, min_frequency: int = 1) -> List[FailurePattern]:
        """Get failure patterns sorted by frequency"""
        patterns = [
            p for p in self.patterns.values()
            if p.frequency >= min_frequency
        ]
        return sorted(patterns, key=lambda p: p.frequency, reverse=True)

    def get_root_causes_summary(self) -> Dict[str, int]:
        """Get aggregated root cause frequency"""
        causes: Dict[str, int] = defaultdict(int)
        for report in self.reports.values():
            for cause in report.root_causes:
                causes[cause] += 1
        return dict(sorted(causes.items(), key=lambda x: x[1], reverse=True))

    # ============================================
    # Digest
    # ============================================

    def compute_digest(self) -> AutopsyDigest:
        """Compute summary digest of all autopsy findings"""

        digest = AutopsyDigest(
            total_reports=len(self.reports),
            total_patterns=len(self.patterns),
            computed_at=int(time.time() * 1000)
        )

        # Top root causes
        causes = self.get_root_causes_summary()
        digest.top_root_causes = [
            {"cause": c, "count": n} for c, n in list(causes.items())[:10]
        ]

        # Family vulnerability
        family_data: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"failures": 0, "total_pnl": 0.0, "root_causes": []}
        )
        for report in self.reports.values():
            if report.family:
                fam = report.family
                family_data[fam]["failures"] += 1
                family_data[fam]["total_pnl"] += report.pnl_at_failure
                family_data[fam]["root_causes"].extend(report.root_causes)

        digest.family_vulnerability = dict(family_data)

        # Regime risk map
        regime_map: Dict[str, List[str]] = defaultdict(list)
        for report in self.reports.values():
            if report.regime_context:
                for cause in report.root_causes:
                    if cause not in regime_map[report.regime_context]:
                        regime_map[report.regime_context].append(cause)

        digest.regime_risk_map = dict(regime_map)

        # Most fragile / resilient families
        family_loss = {}
        for fam, data in family_data.items():
            family_loss[fam] = data["total_pnl"]

        if family_loss:
            sorted_fams = sorted(family_loss.items(), key=lambda x: x[1])
            digest.most_fragile_families = [f[0] for f in sorted_fams[:3]]
            digest.most_resilient_families = [f[0] for f in sorted_fams[-3:]]

        return digest

    # ============================================
    # Helpers
    # ============================================

    def _compute_severity(self, pnl: float, dd: float, trades: int) -> str:
        score = 0
        if pnl < -5000:
            score += 3
        elif pnl < -1000:
            score += 2
        elif pnl < 0:
            score += 1

        if dd > 0.20:
            score += 3
        elif dd > 0.10:
            score += 2
        elif dd > 0.05:
            score += 1

        if score >= 5:
            return Severity.CRITICAL.value
        elif score >= 3:
            return Severity.HIGH.value
        elif score >= 2:
            return Severity.MEDIUM.value
        return Severity.LOW.value

    def get_reports(
        self,
        entity_type: str = None,
        family: str = None,
        severity: str = None,
        limit: int = 50
    ) -> List[AutopsyReport]:
        """Query reports with filters"""
        results = list(self.reports.values())

        if entity_type:
            results = [r for r in results if r.entity_type.value == entity_type]
        if family:
            results = [r for r in results if r.family == family]
        if severity:
            results = [r for r in results if r.severity == severity]

        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:limit]


# Singleton
autopsy_engine = AutopsyEngine()
