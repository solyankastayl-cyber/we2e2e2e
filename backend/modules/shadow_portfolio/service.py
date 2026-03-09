"""
Shadow Portfolio Service
========================

Phase 9.30 - Service layer for shadow portfolio operations.
"""

import time
from typing import Dict, List, Optional, Any

from .types import (
    ShadowStrategy, ShadowPosition, ShadowTrade,
    EquitySnapshot, GovernanceEvent, ShadowPortfolioMetrics,
    CycleResult, ShadowPortfolioConfig,
    PositionStatus, StrategyStatus, GovernanceEventType
)
from .engine import shadow_engine


class ShadowPortfolioService:
    """
    Service for managing the shadow portfolio.

    Provides:
    - Strategy management (add/remove tournament winners)
    - Cycle execution
    - Position/trade queries
    - Equity curve
    - Metrics computation
    - Governance event log
    """

    def __init__(self):
        self.engine = shadow_engine

    # ============================================
    # Portfolio State
    # ============================================

    def get_portfolio(self) -> Dict:
        """Get full portfolio state"""
        state = self.engine.get_portfolio_state()
        strategies = [
            self._strategy_to_dict(s)
            for s in self.engine.strategies.values()
        ]
        state["strategies"] = strategies
        return state

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
    ) -> Dict:
        """Add a tournament winner to shadow portfolio"""

        strategy = self.engine.add_strategy(
            alpha_id=alpha_id,
            name=name,
            family=family,
            asset_classes=asset_classes,
            timeframes=timeframes,
            tournament_run_id=tournament_run_id,
            tournament_score=tournament_score,
            confidence=confidence
        )

        if not strategy:
            return {"error": "Cannot add strategy. Max strategies reached."}

        return {
            "added": True,
            "strategy": self._strategy_to_dict(strategy)
        }

    def remove_strategy(self, strategy_id: str, reason: str = "Manual removal") -> Dict:
        """Remove a strategy from shadow portfolio"""
        success = self.engine.remove_strategy(strategy_id, reason)
        if not success:
            return {"error": f"Strategy {strategy_id} not found"}
        return {"removed": True, "strategy_id": strategy_id}

    # ============================================
    # Cycle Execution
    # ============================================

    def run_cycle(self, market_data: Optional[Dict] = None) -> Dict:
        """Execute one portfolio cycle"""
        result = self.engine.run_cycle(market_data)
        return self._cycle_to_dict(result)

    def run_multiple_cycles(self, count: int = 10, market_data: Optional[Dict] = None) -> Dict:
        """Run multiple cycles"""
        results = []
        for _ in range(min(count, 100)):
            result = self.engine.run_cycle(market_data)
            results.append(self._cycle_to_dict(result))

        return {
            "cycles_run": len(results),
            "final_equity": self.engine.equity,
            "total_pnl": round(self.engine.equity - self.engine.config.initial_capital, 2),
            "regime": self.engine.current_regime.value,
            "cycles": results
        }

    # ============================================
    # Positions
    # ============================================

    def get_positions(self, status: str = None) -> Dict:
        """Get positions, optionally filtered by status"""

        if status == "open":
            positions = self.engine.get_open_positions()
        elif status == "closed":
            positions = self.engine.get_closed_positions()
        else:
            positions = list(self.engine.positions.values())

        return {
            "total": len(positions),
            "positions": [self._position_to_dict(p) for p in positions]
        }

    # ============================================
    # Trades
    # ============================================

    def get_trades(self, strategy_id: str = None, limit: int = 100) -> Dict:
        """Get trade log"""

        trades = self.engine.trades
        if strategy_id:
            trades = [t for t in trades if t.strategy_id == strategy_id]

        trades = trades[-limit:]

        return {
            "total": len(self.engine.trades),
            "returned": len(trades),
            "trades": [self._trade_to_dict(t) for t in trades]
        }

    # ============================================
    # Equity
    # ============================================

    def get_equity(self, limit: int = 500) -> Dict:
        """Get equity curve"""

        curve = self.engine.equity_curve[-limit:]

        return {
            "total_points": len(self.engine.equity_curve),
            "returned": len(curve),
            "current_equity": self.engine.equity,
            "initial_capital": self.engine.config.initial_capital,
            "peak_equity": self.engine.peak_equity,
            "curve": [self._equity_snapshot_to_dict(s) for s in curve]
        }

    # ============================================
    # Metrics
    # ============================================

    def get_metrics(self) -> Dict:
        """Compute and return portfolio metrics"""
        metrics = self.engine.compute_metrics()
        return self._metrics_to_dict(metrics)

    # ============================================
    # Events
    # ============================================

    def get_events(self, event_type: str = None, limit: int = 100) -> Dict:
        """Get governance events"""

        events = self.engine.events
        if event_type:
            events = [e for e in events if e.event_type.value == event_type]

        events = events[-limit:]

        return {
            "total": len(self.engine.events),
            "returned": len(events),
            "events": [self._event_to_dict(e) for e in events]
        }

    # ============================================
    # Management
    # ============================================

    def reset(self) -> Dict:
        """Reset portfolio"""
        self.engine.reset()
        return {
            "reset": True,
            "portfolio_id": self.engine.portfolio_id,
            "equity": self.engine.equity
        }

    def get_config(self) -> Dict:
        """Get current configuration"""
        c = self.engine.config
        return {
            "initial_capital": c.initial_capital,
            "max_strategies": c.max_strategies,
            "max_position_per_strategy": c.max_position_per_strategy,
            "max_total_exposure": c.max_total_exposure,
            "stop_loss_pct": c.stop_loss_pct,
            "take_profit_pct": c.take_profit_pct,
            "drawdown_limits": {
                "warning": c.drawdown_warning,
                "stress": c.drawdown_stress,
                "crisis": c.drawdown_crisis
            },
            "regime_exposure": c.regime_exposure,
            "allocation": {
                "equal_weight": c.equal_weight,
                "min_weight": c.min_strategy_weight,
                "max_weight": c.max_strategy_weight
            }
        }

    def update_config(
        self,
        initial_capital: float = None,
        max_strategies: int = None,
        max_total_exposure: float = None,
        stop_loss_pct: float = None,
        take_profit_pct: float = None
    ) -> Dict:
        """Update configuration"""
        c = self.engine.config
        if initial_capital is not None:
            c.initial_capital = initial_capital
        if max_strategies is not None:
            c.max_strategies = max_strategies
        if max_total_exposure is not None:
            c.max_total_exposure = max_total_exposure
        if stop_loss_pct is not None:
            c.stop_loss_pct = stop_loss_pct
        if take_profit_pct is not None:
            c.take_profit_pct = take_profit_pct

        return {"updated": True, "config": self.get_config()}

    # ============================================
    # Health Check
    # ============================================

    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.30",
            "status": "ok",
            "portfolio_id": self.engine.portfolio_id,
            "equity": self.engine.equity,
            "strategies": len(self.engine.strategies),
            "open_positions": len(self.engine.get_open_positions()),
            "total_trades": len(self.engine.trades),
            "cycles": self.engine.cycle_count,
            "regime": self.engine.current_regime.value,
            "timestamp": int(time.time() * 1000)
        }

    def get_stats(self) -> Dict:
        """Get portfolio statistics summary"""
        state = self.engine.get_portfolio_state()
        metrics = self.engine.compute_metrics()

        return {
            "portfolio": state,
            "performance": {
                "total_return": metrics.total_return,
                "total_return_pct": metrics.total_return_pct,
                "sharpe": metrics.sharpe_ratio,
                "profit_factor": metrics.profit_factor,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "win_rate": metrics.win_rate,
                "total_trades": metrics.total_trades
            },
            "strategy_contributions": metrics.strategy_contributions,
            "family_contributions": metrics.family_contributions
        }

    # ============================================
    # Serialization Helpers
    # ============================================

    def _strategy_to_dict(self, s: ShadowStrategy) -> Dict:
        return {
            "strategy_id": s.strategy_id,
            "alpha_id": s.alpha_id,
            "name": s.name,
            "family": s.family,
            "asset_classes": s.asset_classes,
            "timeframes": s.timeframes,
            "weight": s.weight,
            "health": s.health,
            "confidence": s.confidence,
            "regime_fit": s.regime_fit,
            "status": s.status.value,
            "tournament_run_id": s.tournament_run_id,
            "tournament_score": s.tournament_score,
            "total_trades": s.total_trades,
            "winning_trades": s.winning_trades,
            "total_pnl": round(s.total_pnl, 2),
            "added_at": s.added_at,
            "last_signal_at": s.last_signal_at
        }

    def _position_to_dict(self, p: ShadowPosition) -> Dict:
        return {
            "position_id": p.position_id,
            "strategy_id": p.strategy_id,
            "alpha_id": p.alpha_id,
            "asset": p.asset,
            "direction": p.direction.value if hasattr(p.direction, 'value') else p.direction,
            "status": p.status.value if hasattr(p.status, 'value') else p.status,
            "entry_price": p.entry_price,
            "exit_price": p.exit_price,
            "position_size": p.position_size,
            "notional_value": p.notional_value,
            "stop_loss": p.stop_loss,
            "take_profit": p.take_profit,
            "pnl": p.pnl,
            "pnl_pct": p.pnl_pct,
            "holding_bars": p.holding_bars,
            "regime_at_entry": p.regime_at_entry,
            "regime_at_exit": p.regime_at_exit,
            "opened_at": p.opened_at,
            "closed_at": p.closed_at
        }

    def _trade_to_dict(self, t: ShadowTrade) -> Dict:
        return {
            "trade_id": t.trade_id,
            "position_id": t.position_id,
            "strategy_id": t.strategy_id,
            "alpha_id": t.alpha_id,
            "asset": t.asset,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "position_size": t.position_size,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "holding_bars": t.holding_bars,
            "regime_at_entry": t.regime_at_entry,
            "regime_at_exit": t.regime_at_exit,
            "family": t.family,
            "opened_at": t.opened_at,
            "closed_at": t.closed_at
        }

    def _equity_snapshot_to_dict(self, s: EquitySnapshot) -> Dict:
        return {
            "timestamp": s.timestamp,
            "equity": s.equity,
            "cash": s.cash,
            "exposure": s.exposure,
            "drawdown": s.drawdown,
            "drawdown_pct": s.drawdown_pct,
            "regime": s.regime,
            "open_positions": s.open_positions,
            "cycle_number": s.cycle_number
        }

    def _metrics_to_dict(self, m: ShadowPortfolioMetrics) -> Dict:
        return {
            "total_return": m.total_return,
            "total_return_pct": m.total_return_pct,
            "sharpe_ratio": m.sharpe_ratio,
            "sortino_ratio": m.sortino_ratio,
            "profit_factor": m.profit_factor,
            "max_drawdown": m.max_drawdown,
            "max_drawdown_pct": m.max_drawdown_pct,
            "calmar_ratio": m.calmar_ratio,
            "win_rate": m.win_rate,
            "avg_win": m.avg_win,
            "avg_loss": m.avg_loss,
            "total_trades": m.total_trades,
            "winning_trades": m.winning_trades,
            "losing_trades": m.losing_trades,
            "avg_holding_bars": m.avg_holding_bars,
            "turnover": m.turnover,
            "exposure_avg": m.exposure_avg,
            "strategy_contributions": m.strategy_contributions,
            "family_contributions": m.family_contributions,
            "computed_at": m.computed_at
        }

    def _event_to_dict(self, e: GovernanceEvent) -> Dict:
        return {
            "event_id": e.event_id,
            "event_type": e.event_type.value,
            "timestamp": e.timestamp,
            "strategy_id": e.strategy_id,
            "details": e.details,
            "reason": e.reason
        }

    def _cycle_to_dict(self, c: CycleResult) -> Dict:
        return {
            "cycle_id": c.cycle_id,
            "cycle_number": c.cycle_number,
            "timestamp": c.timestamp,
            "status": c.status.value,
            "signals_generated": c.signals_generated,
            "positions_opened": c.positions_opened,
            "positions_closed": c.positions_closed,
            "equity_before": c.equity_before,
            "equity_after": c.equity_after,
            "cycle_pnl": c.cycle_pnl,
            "exposure_after": c.exposure_after,
            "regime": c.regime,
            "governance_events": c.governance_events,
            "duration_ms": c.duration_ms
        }


# Singleton instance
shadow_service = ShadowPortfolioService()
