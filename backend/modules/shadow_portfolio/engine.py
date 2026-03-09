"""
Shadow Portfolio Engine
=======================

Phase 9.30 - Core engine for shadow portfolio management.

Manages the full lifecycle:
1. Accept tournament winners
2. Allocate capital weights
3. Generate signals per cycle
4. Open/close positions with risk checks
5. Track equity curve
6. Log trades and governance events
7. Compute portfolio metrics
"""

import time
import uuid
import math
import random
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .types import (
    ShadowStrategy, ShadowPosition, ShadowTrade,
    EquitySnapshot, GovernanceEvent, ShadowPortfolioMetrics,
    CycleResult, ShadowPortfolioConfig,
    PositionDirection, PositionStatus, StrategyStatus,
    GovernanceEventType, CycleStatus, RiskRegime
)


class ShadowPortfolioEngine:
    """
    Core engine for shadow portfolio.

    Cycle pipeline:
    new market data -> update features -> generate signals ->
    apply allocator -> risk checks -> open/close positions ->
    update equity -> log trades -> log governance events
    """

    def __init__(self, config: Optional[ShadowPortfolioConfig] = None):
        self.config = config or ShadowPortfolioConfig()

        # Portfolio state
        self.portfolio_id = f"shadow_{int(time.time())}"
        self.equity = self.config.initial_capital
        self.cash = self.config.initial_capital
        self.peak_equity = self.config.initial_capital
        self.current_regime = RiskRegime.NORMAL

        # Strategy pool
        self.strategies: Dict[str, ShadowStrategy] = {}

        # Positions
        self.positions: Dict[str, ShadowPosition] = {}

        # Trade log
        self.trades: List[ShadowTrade] = []

        # Equity curve
        self.equity_curve: List[EquitySnapshot] = []

        # Governance events
        self.events: List[GovernanceEvent] = []

        # Cycles
        self.cycles: List[CycleResult] = []
        self.cycle_count = 0

        # Initial equity snapshot
        self._record_equity_snapshot()

    # ============================================
    # Strategy Management
    # ============================================

    def add_strategy(
        self,
        alpha_id: str,
        name: str,
        family: str = "EXPERIMENTAL",
        asset_classes: List[str] = None,
        timeframes: List[str] = None,
        tournament_run_id: str = "",
        tournament_score: float = 0.0,
        confidence: float = 0.5
    ) -> Optional[ShadowStrategy]:
        """Add a tournament winner to shadow portfolio"""

        if len(self.strategies) >= self.config.max_strategies:
            self._log_event(
                GovernanceEventType.STRATEGY_ADDED,
                reason=f"Rejected: max strategies ({self.config.max_strategies}) reached"
            )
            return None

        strategy_id = f"shd_{alpha_id}_{int(time.time())}"

        strategy = ShadowStrategy(
            strategy_id=strategy_id,
            alpha_id=alpha_id,
            name=name,
            family=family,
            asset_classes=asset_classes or ["CRYPTO"],
            timeframes=timeframes or ["1D"],
            confidence=confidence,
            tournament_run_id=tournament_run_id,
            tournament_score=tournament_score,
            added_at=int(time.time() * 1000)
        )

        # Compute initial weight
        self._rebalance_weights(new_strategy=strategy)

        self.strategies[strategy_id] = strategy

        self._log_event(
            GovernanceEventType.STRATEGY_ADDED,
            strategy_id=strategy_id,
            details={
                "alpha_id": alpha_id,
                "family": family,
                "weight": strategy.weight,
                "tournament_score": tournament_score
            },
            reason=f"Tournament winner added to shadow portfolio"
        )

        return strategy

    def remove_strategy(self, strategy_id: str, reason: str = "Manual removal") -> bool:
        """Remove a strategy from shadow portfolio"""

        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return False

        # Close any open positions for this strategy
        self._close_strategy_positions(strategy_id, "Strategy removed")

        strategy.status = StrategyStatus.REMOVED

        self._log_event(
            GovernanceEventType.STRATEGY_REMOVED,
            strategy_id=strategy_id,
            details={"alpha_id": strategy.alpha_id, "total_pnl": strategy.total_pnl},
            reason=reason
        )

        del self.strategies[strategy_id]
        self._rebalance_weights()

        return True

    def _rebalance_weights(self, new_strategy: Optional[ShadowStrategy] = None):
        """Rebalance strategy weights"""

        active = [s for s in self.strategies.values() if s.status == StrategyStatus.ACTIVE]
        if new_strategy:
            active.append(new_strategy)

        if not active:
            return

        if self.config.equal_weight:
            w = round(1.0 / len(active), 4)
            for s in active:
                s.weight = min(w, self.config.max_strategy_weight)
        else:
            # Score-based allocation
            total_score = sum(s.tournament_score for s in active) or 1.0
            for s in active:
                raw_w = s.tournament_score / total_score
                s.weight = round(
                    max(self.config.min_strategy_weight,
                        min(self.config.max_strategy_weight, raw_w)),
                    4
                )

    # ============================================
    # Signal Generation (mock for shadow)
    # ============================================

    def _generate_signals(self, market_data: Optional[Dict] = None) -> List[Dict]:
        """
        Generate trading signals from active strategies.

        In production this would call actual alpha logic.
        Here we use a deterministic mock based on strategy properties.
        """
        signals = []

        for sid, strat in self.strategies.items():
            if strat.status != StrategyStatus.ACTIVE:
                continue

            # Deterministic pseudo-random based on cycle + strategy id
            seed = hash(f"{self.cycle_count}_{sid}") % 1000
            signal_prob = 0.25 + (strat.confidence * 0.15)

            if (seed / 1000.0) < signal_prob:
                # Pick asset
                asset = strat.asset_classes[0] if strat.asset_classes else "BTC"

                # Direction from family bias
                direction = PositionDirection.LONG
                if strat.family in ("REVERSAL", "MEAN_REVERSION"):
                    direction = PositionDirection.SHORT if seed % 2 == 0 else PositionDirection.LONG
                elif strat.family in ("TREND", "MOMENTUM", "BREAKOUT"):
                    direction = PositionDirection.LONG if seed % 3 != 0 else PositionDirection.SHORT

                # Confidence
                sig_confidence = 0.5 + (strat.tournament_score * 0.3) + (seed % 100) / 500.0
                sig_confidence = min(0.95, sig_confidence)

                signals.append({
                    "strategy_id": sid,
                    "alpha_id": strat.alpha_id,
                    "asset": asset,
                    "direction": direction,
                    "confidence": round(sig_confidence, 3),
                    "family": strat.family,
                    "weight": strat.weight
                })

                strat.last_signal_at = int(time.time() * 1000)

        return signals

    # ============================================
    # Position Management
    # ============================================

    def _open_position(self, signal: Dict) -> Optional[ShadowPosition]:
        """Open a new position from signal"""

        strategy_id = signal["strategy_id"]
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None

        # Check existing positions for this strategy
        open_for_strategy = [
            p for p in self.positions.values()
            if p.strategy_id == strategy_id and p.status == PositionStatus.OPEN
        ]
        if open_for_strategy:
            return None  # One position per strategy

        # Risk check: regime exposure
        regime_mult = self.config.regime_exposure.get(
            self.current_regime.value, 0.5
        )

        # Position sizing
        max_notional = self.equity * strategy.weight * regime_mult
        max_notional = min(max_notional, self.equity * self.config.max_position_per_strategy)

        if max_notional <= 0 or self.cash < max_notional * 0.1:
            return None

        # Check total exposure
        current_exposure = self._get_total_exposure()
        max_allowed = self.config.max_total_exposure * regime_mult
        if current_exposure + (max_notional / self.equity) > max_allowed:
            self._log_event(
                GovernanceEventType.EXPOSURE_REDUCED,
                strategy_id=strategy_id,
                details={
                    "current_exposure": current_exposure,
                    "max_allowed": max_allowed
                },
                reason="Exposure limit reached"
            )
            return None

        # Mock entry price
        asset = signal["asset"]
        entry_price = self._get_mock_price(asset)

        position_size = max_notional / entry_price if entry_price > 0 else 0
        if position_size <= 0:
            return None

        # Stop loss / take profit
        direction = signal["direction"]
        if direction == PositionDirection.LONG:
            stop_loss = entry_price * (1 - self.config.stop_loss_pct)
            take_profit = entry_price * (1 + self.config.take_profit_pct)
        else:
            stop_loss = entry_price * (1 + self.config.stop_loss_pct)
            take_profit = entry_price * (1 - self.config.take_profit_pct)

        position_id = f"pos_{uuid.uuid4().hex[:12]}"

        position = ShadowPosition(
            position_id=position_id,
            strategy_id=strategy_id,
            alpha_id=signal["alpha_id"],
            asset=asset,
            direction=direction,
            entry_price=round(entry_price, 6),
            position_size=round(position_size, 8),
            notional_value=round(max_notional, 2),
            stop_loss=round(stop_loss, 6),
            take_profit=round(take_profit, 6),
            regime_at_entry=self.current_regime.value,
            opened_at=int(time.time() * 1000)
        )

        self.positions[position_id] = position
        self.cash -= max_notional

        return position

    def _update_positions(self) -> Tuple[int, int]:
        """Update open positions with current prices, close if TP/SL hit"""

        closed_count = 0
        open_count = 0

        for pos in list(self.positions.values()):
            if pos.status != PositionStatus.OPEN:
                continue

            current_price = self._get_mock_price(pos.asset, drift=True)
            pos.holding_bars += 1

            # Calculate unrealized PnL
            if pos.direction == PositionDirection.LONG:
                pos.pnl = (current_price - pos.entry_price) * pos.position_size
                pos.pnl_pct = (current_price / pos.entry_price - 1) if pos.entry_price > 0 else 0
            else:
                pos.pnl = (pos.entry_price - current_price) * pos.position_size
                pos.pnl_pct = (1 - current_price / pos.entry_price) if pos.entry_price > 0 else 0

            # Check stop loss
            if pos.direction == PositionDirection.LONG and current_price <= pos.stop_loss:
                self._close_position(pos, current_price, PositionStatus.STOPPED)
                closed_count += 1
                continue

            if pos.direction == PositionDirection.SHORT and current_price >= pos.stop_loss:
                self._close_position(pos, current_price, PositionStatus.STOPPED)
                closed_count += 1
                continue

            # Check take profit
            if pos.direction == PositionDirection.LONG and current_price >= pos.take_profit:
                self._close_position(pos, current_price, PositionStatus.TAKE_PROFIT)
                closed_count += 1
                continue

            if pos.direction == PositionDirection.SHORT and current_price <= pos.take_profit:
                self._close_position(pos, current_price, PositionStatus.TAKE_PROFIT)
                closed_count += 1
                continue

            # Max holding period (30 bars)
            if pos.holding_bars >= 30:
                self._close_position(pos, current_price, PositionStatus.CLOSED)
                closed_count += 1
                continue

            open_count += 1

        return open_count, closed_count

    def _close_position(
        self, pos: ShadowPosition, exit_price: float, status: PositionStatus
    ):
        """Close a position and log the trade"""

        pos.exit_price = round(exit_price, 6)
        pos.status = status
        pos.regime_at_exit = self.current_regime.value
        pos.closed_at = int(time.time() * 1000)

        # Recalculate final PnL
        if pos.direction == PositionDirection.LONG:
            pos.pnl = (exit_price - pos.entry_price) * pos.position_size
            pos.pnl_pct = (exit_price / pos.entry_price - 1) if pos.entry_price > 0 else 0
        else:
            pos.pnl = (pos.entry_price - exit_price) * pos.position_size
            pos.pnl_pct = (1 - exit_price / pos.entry_price) if pos.entry_price > 0 else 0

        pos.pnl = round(pos.pnl, 2)
        pos.pnl_pct = round(pos.pnl_pct, 6)

        # Return notional to cash
        self.cash += pos.notional_value + pos.pnl

        # Record trade
        trade = ShadowTrade(
            trade_id=f"trd_{uuid.uuid4().hex[:12]}",
            position_id=pos.position_id,
            strategy_id=pos.strategy_id,
            alpha_id=pos.alpha_id,
            asset=pos.asset,
            direction=pos.direction.value,
            entry_price=pos.entry_price,
            exit_price=pos.exit_price,
            position_size=pos.position_size,
            pnl=pos.pnl,
            pnl_pct=pos.pnl_pct,
            holding_bars=pos.holding_bars,
            regime_at_entry=pos.regime_at_entry,
            regime_at_exit=pos.regime_at_exit,
            family=self.strategies.get(pos.strategy_id, ShadowStrategy(strategy_id="", alpha_id="")).family,
            opened_at=pos.opened_at,
            closed_at=pos.closed_at
        )
        self.trades.append(trade)

        # Update strategy stats
        strat = self.strategies.get(pos.strategy_id)
        if strat:
            strat.total_trades += 1
            strat.total_pnl += pos.pnl
            if pos.pnl > 0:
                strat.winning_trades += 1

    def _close_strategy_positions(self, strategy_id: str, reason: str):
        """Force close all positions for a strategy"""
        for pos in list(self.positions.values()):
            if pos.strategy_id == strategy_id and pos.status == PositionStatus.OPEN:
                current_price = self._get_mock_price(pos.asset)
                self._close_position(pos, current_price, PositionStatus.FORCE_CLOSED)
                self._log_event(
                    GovernanceEventType.POSITION_FORCE_CLOSED,
                    strategy_id=strategy_id,
                    details={"position_id": pos.position_id, "pnl": pos.pnl},
                    reason=reason
                )

    # ============================================
    # Risk Engine
    # ============================================

    def _check_regime(self):
        """Check and update risk regime based on portfolio state"""

        dd_pct = self._get_current_drawdown_pct()

        old_regime = self.current_regime

        if dd_pct >= self.config.drawdown_crisis:
            self.current_regime = RiskRegime.CRISIS
        elif dd_pct >= self.config.drawdown_stress:
            self.current_regime = RiskRegime.STRESS
        elif dd_pct >= self.config.drawdown_warning:
            self.current_regime = RiskRegime.ELEVATED
        else:
            self.current_regime = RiskRegime.NORMAL

        if self.current_regime != old_regime:
            self._log_event(
                GovernanceEventType.REGIME_SWITCH,
                details={
                    "old_regime": old_regime.value,
                    "new_regime": self.current_regime.value,
                    "drawdown_pct": round(dd_pct, 4)
                },
                reason=f"Drawdown {dd_pct:.2%} triggered regime change"
            )

            # Drawdown warnings
            if self.current_regime in (RiskRegime.STRESS, RiskRegime.CRISIS):
                self._log_event(
                    GovernanceEventType.DRAWDOWN_BREACH,
                    details={"drawdown_pct": round(dd_pct, 4), "regime": self.current_regime.value},
                    reason=f"Drawdown breach: {dd_pct:.2%}"
                )

    def _apply_governance(self):
        """Apply governance rules: pause/disable weak strategies in stress"""

        if self.current_regime in (RiskRegime.STRESS, RiskRegime.CRISIS):
            for strat in self.strategies.values():
                if strat.status != StrategyStatus.ACTIVE:
                    continue

                # Disable strategies with negative PnL in stress
                if strat.total_pnl < 0 and strat.total_trades >= 3:
                    strat.status = StrategyStatus.PAUSED
                    self._close_strategy_positions(strat.strategy_id, "Governance pause in stress regime")
                    self._log_event(
                        GovernanceEventType.STRATEGY_PAUSED,
                        strategy_id=strat.strategy_id,
                        details={"pnl": strat.total_pnl, "regime": self.current_regime.value},
                        reason=f"Negative PnL in {self.current_regime.value} regime"
                    )

        elif self.current_regime == RiskRegime.NORMAL:
            # Resume paused strategies in normal regime
            for strat in self.strategies.values():
                if strat.status == StrategyStatus.PAUSED:
                    strat.status = StrategyStatus.ACTIVE
                    self._log_event(
                        GovernanceEventType.STRATEGY_RESUMED,
                        strategy_id=strat.strategy_id,
                        reason="Regime returned to NORMAL"
                    )

    # ============================================
    # Equity Tracking
    # ============================================

    def _update_equity(self):
        """Recalculate equity from cash + open position values"""

        open_value = sum(
            p.notional_value + p.pnl
            for p in self.positions.values()
            if p.status == PositionStatus.OPEN
        )

        self.equity = round(self.cash + open_value, 2)

        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

    def _record_equity_snapshot(self):
        """Record equity curve data point"""

        dd = self.peak_equity - self.equity
        dd_pct = dd / self.peak_equity if self.peak_equity > 0 else 0

        open_count = sum(
            1 for p in self.positions.values()
            if p.status == PositionStatus.OPEN
        )

        snapshot = EquitySnapshot(
            timestamp=int(time.time() * 1000),
            equity=round(self.equity, 2),
            cash=round(self.cash, 2),
            exposure=round(self._get_total_exposure(), 4),
            drawdown=round(dd, 2),
            drawdown_pct=round(dd_pct, 6),
            regime=self.current_regime.value,
            open_positions=open_count,
            cycle_number=self.cycle_count
        )
        self.equity_curve.append(snapshot)

    def _get_current_drawdown_pct(self) -> float:
        if self.peak_equity <= 0:
            return 0
        return (self.peak_equity - self.equity) / self.peak_equity

    def _get_total_exposure(self) -> float:
        if self.equity <= 0:
            return 0
        total_notional = sum(
            p.notional_value
            for p in self.positions.values()
            if p.status == PositionStatus.OPEN
        )
        return total_notional / self.equity

    # ============================================
    # Metrics Engine
    # ============================================

    def compute_metrics(self) -> ShadowPortfolioMetrics:
        """Compute comprehensive portfolio metrics"""

        metrics = ShadowPortfolioMetrics(computed_at=int(time.time() * 1000))

        if not self.trades:
            metrics.total_return = self.equity - self.config.initial_capital
            metrics.total_return_pct = metrics.total_return / self.config.initial_capital if self.config.initial_capital > 0 else 0
            return metrics

        # Basic
        metrics.total_return = round(self.equity - self.config.initial_capital, 2)
        metrics.total_return_pct = round(metrics.total_return / self.config.initial_capital, 6)
        metrics.total_trades = len(self.trades)

        # Win / Loss
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        metrics.winning_trades = len(wins)
        metrics.losing_trades = len(losses)
        metrics.win_rate = round(len(wins) / len(self.trades), 4) if self.trades else 0

        metrics.avg_win = round(sum(t.pnl for t in wins) / len(wins), 2) if wins else 0
        metrics.avg_loss = round(sum(t.pnl for t in losses) / len(losses), 2) if losses else 0

        # Profit Factor
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        metrics.profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else 999.0

        # Drawdown
        metrics.max_drawdown = round(max((s.drawdown for s in self.equity_curve), default=0), 2)
        metrics.max_drawdown_pct = round(max((s.drawdown_pct for s in self.equity_curve), default=0), 6)

        # Sharpe (simplified daily returns)
        if len(self.equity_curve) >= 2:
            returns = []
            for i in range(1, len(self.equity_curve)):
                prev = self.equity_curve[i - 1].equity
                curr = self.equity_curve[i].equity
                if prev > 0:
                    returns.append((curr - prev) / prev)

            if returns and len(returns) >= 2:
                avg_ret = sum(returns) / len(returns)
                std_ret = math.sqrt(sum((r - avg_ret) ** 2 for r in returns) / (len(returns) - 1))

                if std_ret > 0:
                    metrics.sharpe_ratio = round(avg_ret / std_ret * math.sqrt(252), 4)

                # Sortino (only downside deviation)
                downside = [r for r in returns if r < 0]
                if downside:
                    down_std = math.sqrt(sum(r ** 2 for r in downside) / len(downside))
                    if down_std > 0:
                        metrics.sortino_ratio = round(avg_ret / down_std * math.sqrt(252), 4)

        # Calmar
        if metrics.max_drawdown_pct > 0:
            ann_return = metrics.total_return_pct * (252 / max(1, len(self.equity_curve)))
            metrics.calmar_ratio = round(ann_return / metrics.max_drawdown_pct, 4)

        # Avg holding
        metrics.avg_holding_bars = round(
            sum(t.holding_bars for t in self.trades) / len(self.trades), 1
        )

        # Turnover
        total_volume = sum(abs(t.pnl) + t.position_size * t.entry_price for t in self.trades)
        metrics.turnover = round(total_volume / self.config.initial_capital, 4) if self.config.initial_capital > 0 else 0

        # Average exposure
        if self.equity_curve:
            metrics.exposure_avg = round(
                sum(s.exposure for s in self.equity_curve) / len(self.equity_curve), 4
            )

        # Strategy contributions
        for strat in self.strategies.values():
            if strat.total_trades > 0:
                metrics.strategy_contributions[strat.strategy_id] = round(strat.total_pnl, 2)
                family = strat.family
                metrics.family_contributions[family] = round(
                    metrics.family_contributions.get(family, 0) + strat.total_pnl, 2
                )

        return metrics

    # ============================================
    # Cycle Execution
    # ============================================

    def run_cycle(self, market_data: Optional[Dict] = None) -> CycleResult:
        """
        Execute one portfolio cycle.

        Pipeline:
        1. Check regime
        2. Apply governance
        3. Update existing positions
        4. Generate new signals
        5. Open new positions
        6. Update equity
        7. Record snapshot
        """
        start_ms = int(time.time() * 1000)
        self.cycle_count += 1

        equity_before = self.equity

        # 1. Check and update risk regime
        self._check_regime()

        # 2. Apply governance rules
        self._apply_governance()

        # 3. Update existing positions (TP/SL checks)
        open_count, closed_count = self._update_positions()

        # 4. Generate signals from active strategies
        signals = self._generate_signals(market_data)

        # 5. Open new positions from signals
        opened = 0
        for signal in signals:
            pos = self._open_position(signal)
            if pos:
                opened += 1

        # 6. Update equity
        self._update_equity()

        # 7. Record equity snapshot
        self._record_equity_snapshot()

        # Build cycle result
        cycle_id = f"cycle_{self.cycle_count}"
        duration_ms = int(time.time() * 1000) - start_ms

        governance_events_in_cycle = sum(
            1 for e in self.events
            if e.timestamp >= start_ms
        )

        result = CycleResult(
            cycle_id=cycle_id,
            cycle_number=self.cycle_count,
            timestamp=int(time.time() * 1000),
            status=CycleStatus.COMPLETED,
            signals_generated=len(signals),
            positions_opened=opened,
            positions_closed=closed_count,
            equity_before=round(equity_before, 2),
            equity_after=round(self.equity, 2),
            cycle_pnl=round(self.equity - equity_before, 2),
            exposure_after=round(self._get_total_exposure(), 4),
            regime=self.current_regime.value,
            governance_events=governance_events_in_cycle,
            duration_ms=duration_ms
        )

        self._log_event(
            GovernanceEventType.CYCLE_COMPLETED,
            details={
                "cycle_number": self.cycle_count,
                "pnl": result.cycle_pnl,
                "equity": self.equity,
                "positions_opened": opened,
                "positions_closed": closed_count
            }
        )

        self.cycles.append(result)
        return result

    # ============================================
    # Portfolio Reset
    # ============================================

    def reset(self):
        """Full portfolio reset"""

        self.equity = self.config.initial_capital
        self.cash = self.config.initial_capital
        self.peak_equity = self.config.initial_capital
        self.current_regime = RiskRegime.NORMAL

        self.strategies.clear()
        self.positions.clear()
        self.trades.clear()
        self.equity_curve.clear()
        self.events.clear()
        self.cycles.clear()
        self.cycle_count = 0

        self.portfolio_id = f"shadow_{int(time.time())}"

        self._log_event(GovernanceEventType.PORTFOLIO_RESET, reason="Full portfolio reset")
        self._record_equity_snapshot()

    # ============================================
    # Helpers
    # ============================================

    def _get_mock_price(self, asset: str, drift: bool = False) -> float:
        """Get a mock price for asset. Deterministic based on cycle count.
        Supports crisis_multiplier overlay from Stress Lab."""

        base_prices = {
            "CRYPTO": 45000.0,
            "BTC": 45000.0,
            "EQUITY": 5200.0,
            "SPX": 5200.0,
            "FX": 104.0,
            "DXY": 104.0,
            "COMMODITY": 2050.0,
            "GOLD": 2050.0
        }
        base = base_prices.get(asset, 100.0)

        # Apply crisis multiplier if set by Stress Lab
        crisis_mult = getattr(self, '_crisis_multiplier', 1.0)
        base = base * crisis_mult

        # Deterministic variation
        seed = hash(f"{asset}_{self.cycle_count}") % 10000
        variation = (seed - 5000) / 50000.0  # -10% to +10%

        if drift:
            # Slight drift for position updates
            drift_seed = hash(f"{asset}_{self.cycle_count}_drift") % 10000
            variation += (drift_seed - 5000) / 100000.0

        return round(base * (1 + variation), 6)

    def _log_event(
        self,
        event_type: GovernanceEventType,
        strategy_id: str = "",
        details: Dict = None,
        reason: str = ""
    ):
        event = GovernanceEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            timestamp=int(time.time() * 1000),
            strategy_id=strategy_id,
            details=details or {},
            reason=reason
        )
        self.events.append(event)

    # ============================================
    # Query Methods
    # ============================================

    def get_open_positions(self) -> List[ShadowPosition]:
        return [p for p in self.positions.values() if p.status == PositionStatus.OPEN]

    def get_closed_positions(self) -> List[ShadowPosition]:
        return [p for p in self.positions.values() if p.status != PositionStatus.OPEN]

    def get_active_strategies(self) -> List[ShadowStrategy]:
        return [s for s in self.strategies.values() if s.status == StrategyStatus.ACTIVE]

    def get_portfolio_state(self) -> Dict:
        return {
            "portfolio_id": self.portfolio_id,
            "equity": self.equity,
            "cash": self.cash,
            "peak_equity": self.peak_equity,
            "drawdown": round(self.peak_equity - self.equity, 2),
            "drawdown_pct": round(self._get_current_drawdown_pct(), 6),
            "exposure": round(self._get_total_exposure(), 4),
            "regime": self.current_regime.value,
            "strategies_count": len(self.strategies),
            "active_strategies": len(self.get_active_strategies()),
            "open_positions": len(self.get_open_positions()),
            "total_trades": len(self.trades),
            "cycle_count": self.cycle_count
        }


# Singleton instance
shadow_engine = ShadowPortfolioEngine()
