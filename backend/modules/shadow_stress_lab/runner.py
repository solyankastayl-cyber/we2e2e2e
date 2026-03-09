"""
Stress Lab Runner
=================

Phase 9.30B - Drives Shadow Portfolio through crisis scenarios.

The runner:
1. Creates a fresh shadow portfolio instance
2. Seeds it with test strategies
3. Applies crisis price dynamics bar-by-bar
4. Tracks governance reactions, regime switches, survival
5. Produces full stress report with timeline
"""

import time
import math
import uuid
from typing import Dict, List, Optional, Tuple

from .types import (
    StressScenario, StressRun, StressRunStatus, StressRunMode,
    StressPortfolioMetrics, StrategyStressResult, StressTimelineEvent,
    StressBatchResult
)
from .scenarios import ALL_SCENARIOS

from modules.shadow_portfolio.types import (
    ShadowPortfolioConfig, PositionDirection, PositionStatus,
    StrategyStatus, GovernanceEventType, RiskRegime
)
from modules.shadow_portfolio.engine import ShadowPortfolioEngine


# ============================================
# Default test strategies for stress runs
# ============================================

DEFAULT_STRESS_STRATEGIES = [
    {
        "alpha_id": "stress_trend_btc",
        "name": "TREND_BTC_STRESS",
        "family": "TREND",
        "asset_classes": ["CRYPTO"],
        "tournament_score": 0.80,
        "confidence": 0.70
    },
    {
        "alpha_id": "stress_breakout_spx",
        "name": "BREAKOUT_SPX_STRESS",
        "family": "BREAKOUT",
        "asset_classes": ["EQUITY"],
        "tournament_score": 0.75,
        "confidence": 0.68
    },
    {
        "alpha_id": "stress_momentum_multi",
        "name": "MOMENTUM_MULTI_STRESS",
        "family": "MOMENTUM",
        "asset_classes": ["CRYPTO"],
        "tournament_score": 0.72,
        "confidence": 0.65
    },
    {
        "alpha_id": "stress_reversal_fx",
        "name": "REVERSAL_FX_STRESS",
        "family": "REVERSAL",
        "asset_classes": ["FX"],
        "tournament_score": 0.70,
        "confidence": 0.62
    },
    {
        "alpha_id": "stress_cross_asset",
        "name": "CROSS_ASSET_HEDGE_STRESS",
        "family": "CROSS_ASSET",
        "asset_classes": ["EQUITY"],
        "tournament_score": 0.68,
        "confidence": 0.60
    },
]


class StressLabRunner:
    """
    Runs Shadow Portfolio through crisis scenarios.

    Creates an isolated portfolio instance per run,
    applies synthetic crisis dynamics, and measures
    system response.
    """

    def __init__(self):
        self.runs: Dict[str, StressRun] = {}
        self.batches: Dict[str, StressBatchResult] = {}

    def run_scenario(
        self,
        scenario_id: str,
        mode: StressRunMode = StressRunMode.FULL_SYSTEM,
        custom_strategies: Optional[List[Dict]] = None,
        initial_capital: float = 100000.0
    ) -> StressRun:
        """Run a single stress scenario"""

        scenario = ALL_SCENARIOS.get(scenario_id)
        if not scenario:
            run = StressRun(
                run_id=f"stress_{int(time.time())}",
                scenario_id=scenario_id,
                scenario_name="UNKNOWN",
                status=StressRunStatus.FAILED
            )
            run.verdict = "Scenario not found"
            return run

        run_id = f"stress_{scenario_id}_{int(time.time())}"

        run = StressRun(
            run_id=run_id,
            scenario_id=scenario_id,
            scenario_name=scenario.name,
            mode=mode,
            status=StressRunStatus.RUNNING,
            initial_equity=initial_capital,
            started_at=int(time.time() * 1000)
        )

        # Create isolated portfolio
        config = ShadowPortfolioConfig(initial_capital=initial_capital)
        self._apply_mode_config(config, mode)
        engine = ShadowPortfolioEngine(config)

        # Seed strategies
        strategies = custom_strategies or DEFAULT_STRESS_STRATEGIES
        strategy_map = {}
        for s in strategies:
            strat = engine.add_strategy(
                alpha_id=s["alpha_id"],
                name=s["name"],
                family=s["family"],
                asset_classes=s.get("asset_classes", ["CRYPTO"]),
                tournament_run_id="stress_test",
                tournament_score=s.get("tournament_score", 0.7),
                confidence=s.get("confidence", 0.6)
            )
            if strat:
                strategy_map[strat.strategy_id] = s

        # Run crisis simulation
        crisis = scenario.crisis_profile
        total_bars = scenario.total_bars
        timeline = []

        # Phase 1: Pre-crisis calm (10% of bars)
        calm_bars = max(2, int(total_bars * 0.1))
        # Phase 2: Crisis drawdown
        dd_bars = crisis.drawdown_duration_bars
        # Phase 3: Recovery (or continued decline)
        recovery_bars = total_bars - calm_bars - dd_bars

        peak_equity_during = initial_capital
        max_dd_during = 0.0
        trough_bar = 0

        for bar in range(total_bars):
            # Determine crisis phase and apply price dynamics
            self._apply_crisis_dynamics(engine, bar, calm_bars, dd_bars, crisis, scenario)

            # Run portfolio cycle
            engine.run_cycle()

            # Track equity
            eq = engine.equity
            if eq > peak_equity_during:
                peak_equity_during = eq

            current_dd = (peak_equity_during - eq) / peak_equity_during if peak_equity_during > 0 else 0
            if current_dd > max_dd_during:
                max_dd_during = current_dd
                trough_bar = bar

            # Record equity point
            run.equity_curve.append({
                "bar": bar,
                "equity": round(eq, 2),
                "drawdown_pct": round(current_dd, 6),
                "regime": engine.current_regime.value,
                "exposure": round(engine._get_total_exposure(), 4),
                "open_positions": len(engine.get_open_positions())
            })

            # Detect timeline events
            self._detect_timeline_events(timeline, engine, bar, calm_bars, dd_bars, crisis)

        # Collect results
        run.final_equity = round(engine.equity, 2)
        run.timeline = timeline

        # Build metrics
        metrics = self._compute_stress_metrics(
            engine, initial_capital, max_dd_during, trough_bar, total_bars
        )
        run.metrics = metrics

        # Per-strategy results
        for sid, strat in engine.strategies.items():
            s_info = strategy_map.get(sid, {})
            run.strategy_results.append(StrategyStressResult(
                strategy_id=sid,
                alpha_id=strat.alpha_id,
                name=strat.name,
                family=strat.family,
                survived=strat.status == StrategyStatus.ACTIVE,
                total_pnl=round(strat.total_pnl, 2),
                max_drawdown=0,
                trades=strat.total_trades,
                winning_trades=strat.winning_trades,
                was_paused=strat.status == StrategyStatus.PAUSED,
                was_disabled=strat.status == StrategyStatus.DISABLED,
                bars_active=total_bars,
                regime_at_failure=engine.current_regime.value if strat.status != StrategyStatus.ACTIVE else ""
            ))

        # Verdict
        run.survived = engine.equity > initial_capital * 0.5  # Survived if > 50% capital preserved
        run.verdict = self._compute_verdict(run, scenario)
        run.verdict_details = self._compute_verdict_details(run, scenario, engine)

        run.status = StressRunStatus.COMPLETED
        run.completed_at = int(time.time() * 1000)
        run.duration_ms = run.completed_at - run.started_at

        self.runs[run_id] = run
        return run

    def run_batch(
        self,
        scenario_ids: Optional[List[str]] = None,
        mode: StressRunMode = StressRunMode.FULL_SYSTEM,
        initial_capital: float = 100000.0
    ) -> StressBatchResult:
        """Run multiple scenarios"""

        if not scenario_ids:
            scenario_ids = list(ALL_SCENARIOS.keys())

        batch_id = f"batch_{int(time.time())}"
        batch = StressBatchResult(
            batch_id=batch_id,
            mode=mode.value,
            total_scenarios=len(scenario_ids),
            started_at=int(time.time() * 1000)
        )

        worst_dd = 0.0
        best_return = -999.0
        family_failures: Dict[str, int] = {}
        total_dd = 0.0
        total_recovery = 0

        for sid in scenario_ids:
            run = self.run_scenario(sid, mode, initial_capital=initial_capital)
            batch.runs.append(run.run_id)

            if run.status == StressRunStatus.COMPLETED:
                if run.survived:
                    batch.scenarios_survived += 1
                else:
                    batch.scenarios_failed += 1

                dd = run.metrics.max_drawdown_pct
                total_dd += dd
                total_recovery += run.metrics.recovery_bars

                if dd > worst_dd:
                    worst_dd = dd
                    batch.weakest_scenario = run.scenario_name

                ret = run.metrics.total_return_pct
                if ret > best_return:
                    best_return = ret
                    batch.strongest_scenario = run.scenario_name

                # Track family collapses
                for sr in run.strategy_results:
                    if not sr.survived:
                        family_failures[sr.family] = family_failures.get(sr.family, 0) + 1

        batch.avg_drawdown = round(total_dd / max(1, len(scenario_ids)), 6)
        batch.avg_recovery = int(total_recovery / max(1, len(scenario_ids)))
        batch.family_vulnerability = family_failures
        batch.completed_at = int(time.time() * 1000)

        self.batches[batch_id] = batch
        return batch

    # ============================================
    # Crisis Dynamics
    # ============================================

    def _apply_crisis_dynamics(
        self,
        engine: ShadowPortfolioEngine,
        bar: int,
        calm_bars: int,
        dd_bars: int,
        crisis,
        scenario: StressScenario
    ):
        """
        Apply crisis price dynamics to the engine.

        We override the engine's mock price function to inject
        crisis-appropriate returns.
        """
        # Store crisis context on engine for price generation
        if bar < calm_bars:
            # Pre-crisis: normal markets
            engine._crisis_phase = "CALM"
            engine._crisis_multiplier = 1.0
        elif bar < calm_bars + dd_bars:
            # Crisis drawdown phase
            progress = (bar - calm_bars) / dd_bars
            engine._crisis_phase = "DRAWDOWN"
            # Accelerating drawdown
            engine._crisis_multiplier = 1.0 - (crisis.peak_drawdown * self._crisis_curve(progress))
        else:
            # Recovery or continued decline
            if crisis.mean_reversion_after:
                recovery_progress = (bar - calm_bars - dd_bars) / max(1, crisis.recovery_duration_bars)
                recovery = min(1.0, recovery_progress)
                engine._crisis_phase = "RECOVERY"
                engine._crisis_multiplier = (1.0 - crisis.peak_drawdown) + (crisis.peak_drawdown * 0.6 * recovery)
            else:
                # Continued slow bleed
                extra_dd = 0.05 * ((bar - calm_bars - dd_bars) / max(1, crisis.recovery_duration_bars))
                engine._crisis_phase = "CONTINUED_DECLINE"
                engine._crisis_multiplier = (1.0 - crisis.peak_drawdown) - extra_dd

        # Override engine regime based on crisis severity
        if hasattr(engine, '_crisis_multiplier'):
            loss = 1.0 - engine._crisis_multiplier
            if loss > crisis.peak_drawdown * 0.8:
                engine.current_regime = RiskRegime.CRISIS
            elif loss > crisis.peak_drawdown * 0.5:
                engine.current_regime = RiskRegime.STRESS
            elif loss > crisis.peak_drawdown * 0.2:
                engine.current_regime = RiskRegime.ELEVATED

    def _crisis_curve(self, progress: float) -> float:
        """Non-linear crisis drawdown curve (fast initial drop, then slower)"""
        # S-curve: fast drop in first 30%, then slower grind
        if progress < 0.3:
            return progress * 2.5 * 0.3  # Fast initial
        else:
            return 0.75 + 0.25 * ((progress - 0.3) / 0.7)

    def _apply_mode_config(self, config: ShadowPortfolioConfig, mode: StressRunMode):
        """Apply mode-specific configuration"""
        if mode == StressRunMode.CORE_ONLY:
            # Minimal risk management
            config.drawdown_warning = 0.50
            config.drawdown_stress = 0.70
            config.drawdown_crisis = 0.90
            config.regime_exposure = {
                "NORMAL": 1.0, "ELEVATED": 1.0,
                "STRESS": 0.8, "CRISIS": 0.5
            }
        elif mode == StressRunMode.FULL_STRESS_POLICIES:
            # Aggressive risk management
            config.drawdown_warning = 0.05
            config.drawdown_stress = 0.10
            config.drawdown_crisis = 0.15
            config.regime_exposure = {
                "NORMAL": 1.0, "ELEVATED": 0.5,
                "STRESS": 0.2, "CRISIS": 0.0
            }
            config.stop_loss_pct = 0.01
            config.take_profit_pct = 0.03
        # FULL_SYSTEM uses default config

    # ============================================
    # Timeline Events
    # ============================================

    def _detect_timeline_events(
        self,
        timeline: List[StressTimelineEvent],
        engine: ShadowPortfolioEngine,
        bar: int,
        calm_bars: int,
        dd_bars: int,
        crisis
    ):
        """Detect and record timeline events"""

        ts = int(time.time() * 1000)

        # Crisis onset
        if bar == calm_bars:
            timeline.append(StressTimelineEvent(
                bar=bar, timestamp=ts,
                event_type="CRISIS_ONSET",
                description="Crisis drawdown begins",
                severity=0.8
            ))

        # Volatility spike at crisis start
        if bar == calm_bars + 1:
            timeline.append(StressTimelineEvent(
                bar=bar, timestamp=ts,
                event_type="VOLATILITY_SPIKE",
                description=f"Volatility multiplier: {crisis.volatility_multiplier}x",
                severity=min(1.0, crisis.volatility_multiplier / 7.0),
                details={"multiplier": crisis.volatility_multiplier}
            ))

        # Regime changes
        if bar > 0 and len(engine.events) > 0:
            recent = [e for e in engine.events if e.event_type == GovernanceEventType.REGIME_SWITCH]
            if recent:
                last_switch = recent[-1]
                timeline.append(StressTimelineEvent(
                    bar=bar, timestamp=ts,
                    event_type="REGIME_SWITCH",
                    description=f"Risk regime: {last_switch.details.get('new_regime', '')}",
                    severity=0.7,
                    details=last_switch.details
                ))
                # Clear to avoid duplicates
                engine.events = [e for e in engine.events if e.event_type != GovernanceEventType.REGIME_SWITCH or e != last_switch]

        # Strategy events
        paused = [e for e in engine.events if e.event_type == GovernanceEventType.STRATEGY_PAUSED]
        for evt in paused:
            timeline.append(StressTimelineEvent(
                bar=bar, timestamp=ts,
                event_type="STRATEGY_PAUSED",
                description=f"Strategy paused: {evt.strategy_id[:30]}",
                severity=0.6,
                details=evt.details
            ))

        # Peak crisis bar
        if bar == calm_bars + dd_bars:
            timeline.append(StressTimelineEvent(
                bar=bar, timestamp=ts,
                event_type="CRISIS_TROUGH",
                description="Crisis trough reached, drawdown peak",
                severity=1.0,
                details={"equity": engine.equity}
            ))

        # Recovery start
        if bar == calm_bars + dd_bars + 1 and crisis.mean_reversion_after:
            timeline.append(StressTimelineEvent(
                bar=bar, timestamp=ts,
                event_type="RECOVERY_START",
                description="Recovery phase begins",
                severity=0.3
            ))

    # ============================================
    # Metrics
    # ============================================

    def _compute_stress_metrics(
        self,
        engine: ShadowPortfolioEngine,
        initial_capital: float,
        max_dd: float,
        trough_bar: int,
        total_bars: int
    ) -> StressPortfolioMetrics:
        """Compute stress-specific metrics"""

        metrics = StressPortfolioMetrics()

        metrics.total_return = round(engine.equity - initial_capital, 2)
        metrics.total_return_pct = round(metrics.total_return / initial_capital, 6) if initial_capital > 0 else 0
        metrics.max_drawdown = round(max_dd * initial_capital, 2)
        metrics.max_drawdown_pct = round(max_dd, 6)

        # Recovery bars
        recovered = False
        for i, snap in enumerate(engine.equity_curve):
            if i > trough_bar and snap.equity >= initial_capital:
                metrics.recovery_bars = i - trough_bar
                recovered = True
                break
        if not recovered:
            metrics.recovery_bars = total_bars - trough_bar

        # Tail loss (worst single-cycle loss)
        if len(engine.equity_curve) >= 2:
            returns = []
            for i in range(1, len(engine.equity_curve)):
                prev = engine.equity_curve[i-1].equity
                curr = engine.equity_curve[i].equity
                if prev > 0:
                    returns.append((curr - prev) / prev)

            if returns:
                metrics.tail_loss = round(min(returns), 6)

                avg_ret = sum(returns) / len(returns)
                if len(returns) >= 2:
                    std = math.sqrt(sum((r - avg_ret)**2 for r in returns) / (len(returns)-1))
                    if std > 0:
                        metrics.stress_sharpe = round(avg_ret / std * math.sqrt(252), 4)

        # Calmar
        if metrics.max_drawdown_pct > 0:
            ann = metrics.total_return_pct * (252 / max(1, total_bars))
            metrics.calmar = round(ann / metrics.max_drawdown_pct, 4)

        # Governance metrics
        metrics.total_governance_events = len(engine.events)
        for evt in engine.events:
            if evt.event_type == GovernanceEventType.REGIME_SWITCH:
                metrics.regime_switches += 1
            elif evt.event_type == GovernanceEventType.STRATEGY_PAUSED:
                metrics.healing_events += 1
            elif evt.event_type == GovernanceEventType.STRATEGY_DISABLED:
                metrics.demotions += 1
            elif evt.event_type == GovernanceEventType.EXPOSURE_REDUCED:
                metrics.overlay_reductions += 1

        # Survival
        for strat in engine.strategies.values():
            if strat.status == StrategyStatus.ACTIVE:
                metrics.strategies_survived += 1
            elif strat.status == StrategyStatus.PAUSED:
                metrics.strategies_paused += 1
            elif strat.status == StrategyStatus.DISABLED:
                metrics.strategies_disabled += 1

        metrics.capital_preserved_pct = round(engine.equity / initial_capital, 6) if initial_capital > 0 else 0

        # Family collapses
        family_active: Dict[str, bool] = {}
        for strat in engine.strategies.values():
            fam = strat.family
            if fam not in family_active:
                family_active[fam] = False
            if strat.status == StrategyStatus.ACTIVE:
                family_active[fam] = True

        metrics.family_collapses = [f for f, alive in family_active.items() if not alive]

        metrics.total_cycles = engine.cycle_count
        metrics.total_trades = len(engine.trades)

        return metrics

    # ============================================
    # Verdict
    # ============================================

    def _compute_verdict(self, run: StressRun, scenario: StressScenario) -> str:
        """Compute verdict string"""
        m = run.metrics

        if m.capital_preserved_pct >= 0.95:
            return "EXCELLENT"
        elif m.capital_preserved_pct >= 0.85:
            return "GOOD"
        elif m.capital_preserved_pct >= 0.70:
            return "ACCEPTABLE"
        elif m.capital_preserved_pct >= 0.50:
            return "WEAK"
        else:
            return "FAILED"

    def _compute_verdict_details(
        self, run: StressRun, scenario: StressScenario, engine: ShadowPortfolioEngine
    ) -> List[str]:
        """Compute detailed verdict"""
        details = []
        m = run.metrics

        benchmark_dd = scenario.crisis_profile.peak_drawdown
        if m.max_drawdown_pct < benchmark_dd * 0.5:
            details.append(f"System drawdown ({m.max_drawdown_pct:.2%}) significantly less than market ({benchmark_dd:.0%})")
        elif m.max_drawdown_pct < benchmark_dd:
            details.append(f"System drawdown ({m.max_drawdown_pct:.2%}) less than market ({benchmark_dd:.0%})")
        else:
            details.append(f"System drawdown ({m.max_drawdown_pct:.2%}) exceeded market crisis ({benchmark_dd:.0%})")

        if m.regime_switches > 0:
            details.append(f"Risk regime switched {m.regime_switches} times")

        if m.healing_events > 0:
            details.append(f"Self-healing: {m.healing_events} strategies paused")

        if m.family_collapses:
            details.append(f"Family collapses: {', '.join(m.family_collapses)}")

        survived_pct = m.strategies_survived / max(1, m.strategies_survived + m.strategies_paused + m.strategies_disabled)
        details.append(f"Strategy survival rate: {survived_pct:.0%}")

        details.append(f"Capital preserved: {m.capital_preserved_pct:.2%}")

        return details

    # ============================================
    # Query Methods
    # ============================================

    def get_run(self, run_id: str) -> Optional[StressRun]:
        return self.runs.get(run_id)

    def get_batch(self, batch_id: str) -> Optional[StressBatchResult]:
        return self.batches.get(batch_id)

    def list_runs(self, limit: int = 20) -> List[StressRun]:
        runs = sorted(self.runs.values(), key=lambda r: r.completed_at, reverse=True)
        return runs[:limit]


# Singleton
stress_runner = StressLabRunner()
