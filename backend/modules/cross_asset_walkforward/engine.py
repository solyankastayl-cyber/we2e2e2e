"""
Cross-Asset Walk-Forward Core Engine
====================================

The heart of the simulation - processes bar by bar with:
- Time-sealed execution (no future leakage)
- Asset-agnostic core
- Full layer integration
- Governance event logging
"""

import uuid
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict

from .types import (
    WalkForwardRun, SimMode, RunStatus, AssetClass,
    SimulatedTrade, GovernanceEvent, GovernanceLayer,
    WalkForwardReport
)
from .dataset_registry import dataset_registry
from .asset_adapter import asset_adapter_factory
from .trade_simulator import TradeSimulator
from .events import GovernanceEventLogger
from .metrics import MetricsEngine
from .report import ReportGenerator


class CrossAssetWalkForwardEngine:
    """
    Universal cross-asset walk-forward simulation engine.
    
    This engine:
    1. Processes data bar-by-bar in forward-only manner
    2. Integrates all governance layers
    3. Uses asset-specific adapters for calibration
    4. Logs all decisions for audit trail
    5. Generates comprehensive reports
    """
    
    def __init__(self):
        self.runs: Dict[str, WalkForwardRun] = {}
        self.reports: Dict[str, WalkForwardReport] = {}
    
    def create_run(
        self,
        asset: str,
        mode: SimMode = SimMode.FULL_SYSTEM,
        start_date: str = "",
        end_date: str = "",
        initial_capital: float = 100000.0,
        warmup_bars: int = 200
    ) -> WalkForwardRun:
        """Create a new walk-forward run"""
        
        # Get dataset info
        dataset = dataset_registry.get(asset)
        if not dataset:
            raise ValueError(f"Unknown asset: {asset}")
        
        # Get adapter
        adapter = asset_adapter_factory.get_or_default(asset)
        
        # Validate/adjust dates
        if not start_date:
            start_date = dataset.start_date
        if not end_date:
            end_date = dataset.end_date
        
        validation = dataset_registry.validate_date_range(asset, start_date, end_date)
        if not validation["valid"]:
            if "adjusted_start" in validation:
                start_date = validation["adjusted_start"]
            if "adjusted_end" in validation:
                end_date = validation["adjusted_end"]
        
        run_id = f"cwf_{asset}_{int(time.time())}"
        
        run = WalkForwardRun(
            run_id=run_id,
            asset=asset,
            asset_class=adapter.asset_class,
            timeframe="1D",
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            warmup_bars=warmup_bars,
            initial_capital=initial_capital,
            dataset_version=dataset.dataset_version,
            status=RunStatus.PENDING,
            created_at=int(time.time() * 1000)
        )
        
        self.runs[run_id] = run
        return run
    
    async def execute_run(self, run_id: str) -> WalkForwardReport:
        """Execute a walk-forward run"""
        
        run = self.runs.get(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")
        
        # Update status
        run.status = RunStatus.RUNNING
        run.started_at = int(time.time() * 1000)
        
        try:
            # Get adapter
            adapter = asset_adapter_factory.get_or_default(run.asset)
            
            # Initialize components
            simulator = TradeSimulator(adapter, run.initial_capital)
            event_logger = GovernanceEventLogger(run_id)
            
            # Load market data
            candles = await self._load_candles(
                run.asset, run.start_date, run.end_date
            )
            
            if len(candles) < run.warmup_bars + 100:
                raise ValueError(
                    f"Not enough candles: {len(candles)} < {run.warmup_bars + 100}"
                )
            
            run.total_bars = len(candles)
            
            # Initialize strategy state
            strategy_weights = {}
            strategy_health = {}
            family_budgets = {
                "breakout": 0.25,
                "reversal": 0.15,
                "momentum": 0.25,
                "harmonic": 0.10,
                "pattern": 0.10,
                "continuation": 0.15
            }
            
            current_regime = "UNKNOWN"
            overlay_multiplier = 1.0
            
            # Get strategies
            strategies = await self._get_strategies(run.mode)
            
            for s in strategies:
                strategy_weights[s["id"]] = 0.5
                strategy_health[s["id"]] = 1.0
            
            # Main simulation loop
            for i in range(run.warmup_bars, len(candles)):
                bar = candles[i]
                run.current_bar = i
                run.progress_pct = (i - run.warmup_bars) / (len(candles) - run.warmup_bars)
                
                # Extract bar data
                bar_open = bar.get("open", 0)
                bar_high = bar.get("high", 0)
                bar_low = bar.get("low", 0)
                bar_close = bar.get("close", 0)
                bar_time = bar.get("timestamp", 0)
                bar_date = bar.get("date", "")
                
                # 1. Detect regime
                new_regime = self._detect_regime(candles[:i+1])
                if new_regime != current_regime:
                    event_logger.log_regime_change(
                        i, run.asset, current_regime, new_regime, 0.8
                    )
                    current_regime = new_regime
                
                # 2. Check exits for open positions
                closed_trades = simulator.check_exits(
                    run_id, run.asset, i, bar_time,
                    bar_high, bar_low, bar_close, bar_date
                )
                
                # 3. Apply self-healing
                if run.mode != SimMode.CORE_ONLY:
                    healing_events = self._apply_self_healing(
                        i, run.asset, adapter,
                        simulator.trade_history[-50:],
                        strategy_weights, strategy_health,
                        event_logger
                    )
                
                # 4. Apply meta-strategy (budget reallocation)
                if run.mode in [SimMode.FULL_SYSTEM, SimMode.FULL_HIERARCHICAL]:
                    meta_events = self._apply_meta_strategy(
                        i, run.asset, current_regime,
                        family_budgets, event_logger
                    )
                
                # 5. Calculate overlay multiplier
                overlay_multiplier = self._calculate_overlay(
                    simulator.drawdown_pct,
                    current_regime,
                    i, run.asset, event_logger
                )
                
                # 6. Check kill switch
                if simulator.drawdown_pct > adapter.max_drawdown_trigger:
                    if not simulator.kill_switch_active:
                        simulator.activate_kill_switch()
                        event_logger.log_kill_switch(
                            i, run.asset, "ACTIVATED",
                            f"Drawdown {simulator.drawdown_pct:.2%}",
                            simulator.drawdown_pct
                        )
                elif simulator.kill_switch_active and simulator.drawdown_pct < 0.15:
                    simulator.deactivate_kill_switch()
                    event_logger.log_kill_switch(
                        i, run.asset, "DEACTIVATED",
                        "Drawdown recovered"
                    )
                
                # 7. Generate signals and open positions
                for strategy in strategies:
                    sid = strategy["id"]
                    family = strategy.get("family", "breakout")
                    
                    # Check if strategy is allowed in current mode
                    if run.mode == SimMode.CORE_ONLY and strategy.get("status") != "APPROVED":
                        continue
                    
                    # Check family budget
                    if family_budgets.get(family, 0) < 0.05:
                        continue
                    
                    # Generate signal
                    signal = self._generate_signal(
                        strategy, candles[:i+1], current_regime
                    )
                    
                    if signal and signal.get("confidence", 0) > 0.3:
                        # Apply structural bias filter
                        if adapter.structural_bias_allowed:
                            if not self._check_bias_alignment(
                                signal["direction"], current_regime
                            ):
                                event_logger.log_bias_rejection(
                                    i, run.asset, signal["direction"],
                                    current_regime,
                                    "Signal against structural bias"
                                )
                                continue
                        
                        # Calculate effective weight
                        effective_weight = (
                            strategy_weights.get(sid, 0.5) *
                            strategy_health.get(sid, 1.0) *
                            family_budgets.get(family, 0.25)
                        )
                        
                        # Open position
                        position = simulator.open_position(
                            run_id=run_id,
                            asset=run.asset,
                            strategy_id=sid,
                            side=signal["direction"],
                            entry_price=bar_close,
                            stop_loss=signal.get("stop_loss", bar_close * 0.95),
                            take_profit=signal.get("take_profit", bar_close * 1.10),
                            bar_index=i,
                            timestamp=bar_time,
                            signal_confidence=signal["confidence"],
                            strategy_weight=effective_weight,
                            overlay_multiplier=overlay_multiplier,
                            regime=current_regime,
                            risk_state="NORMAL" if not simulator.kill_switch_active else "KILL_SWITCH"
                        )
                
                # 8. Record equity point
                simulator.record_equity_point(i, bar_time, current_regime)
            
            # Close all remaining positions
            if candles:
                last_bar = candles[-1]
                simulator.close_all_positions(
                    run_id, run.asset,
                    last_bar.get("close", 0),
                    last_bar.get("timestamp", 0),
                    last_bar.get("date", ""),
                    "END"
                )
            
            # Calculate metrics
            years = run.total_bars / 252 if run.total_bars > 0 else 1
            
            trade_metrics = MetricsEngine.calculate_trade_metrics(simulator.trade_history)
            portfolio_metrics = MetricsEngine.calculate_portfolio_metrics(
                simulator.equity_history,
                simulator.trade_history,
                run.initial_capital,
                years
            )
            strategy_metrics = MetricsEngine.calculate_strategy_metrics(
                simulator.trade_history,
                event_logger.events
            )
            governance_metrics = event_logger.get_metrics()
            regime_breakdown = MetricsEngine.calculate_regime_breakdown(simulator.trade_history)
            decade_breakdown = MetricsEngine.calculate_decade_breakdown(simulator.trade_history)
            
            # Generate report
            report = ReportGenerator.generate_report(
                run, trade_metrics, portfolio_metrics, governance_metrics,
                strategy_metrics, regime_breakdown, decade_breakdown
            )
            
            # Store report
            self.reports[run_id] = report
            
            # Update run status
            run.status = RunStatus.COMPLETED
            run.completed_at = int(time.time() * 1000)
            
            return report
            
        except Exception as e:
            run.status = RunStatus.FAILED
            run.error_message = str(e)
            raise
    
    async def _load_candles(
        self,
        asset: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """Load candle data from database"""
        from motor.motor_asyncio import AsyncIOMotorClient
        import os
        
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "ta_engine")
        
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Parse dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Query candles - use 'symbol' field as that's what exists in DB
        cursor = db.candles.find({
            "symbol": asset.upper(),
            "timeframe": "1d",
            "timestamp": {
                "$gte": int(start_dt.timestamp() * 1000),
                "$lte": int(end_dt.timestamp() * 1000)
            }
        }, {"_id": 0}).sort("timestamp", 1)
        
        candles = await cursor.to_list(length=None)
        
        # Convert to simple dicts
        result = []
        for c in candles:
            ts = c.get("timestamp", 0)
            if ts > 0:
                dt = datetime.utcfromtimestamp(ts / 1000)
                date_str = dt.strftime("%Y-%m-%d")
            else:
                date_str = ""
            
            result.append({
                "timestamp": ts,
                "date": date_str,
                "open": c.get("open", 0),
                "high": c.get("high", 0),
                "low": c.get("low", 0),
                "close": c.get("close", 0),
                "volume": c.get("volume", 0)
            })
        
        return result
    
    async def _get_strategies(self, mode: SimMode) -> List[Dict]:
        """Get strategies for simulation"""
        # Default strategies based on mode
        strategies = [
            {"id": "MTF_BREAKOUT", "family": "breakout", "status": "APPROVED"},
            {"id": "MOMENTUM_ADX", "family": "momentum", "status": "APPROVED"},
            {"id": "REVERSAL_RSI", "family": "reversal", "status": "APPROVED"},
            {"id": "DOUBLE_BOTTOM", "family": "reversal", "status": "APPROVED"},
            {"id": "HEAD_SHOULDERS", "family": "pattern", "status": "APPROVED"},
            {"id": "CONTINUATION_FLAG", "family": "continuation", "status": "LIMITED"},
            {"id": "HARMONIC_GARTLEY", "family": "harmonic", "status": "LIMITED"},
            {"id": "CHANNEL_BREAKOUT", "family": "breakout", "status": "LIMITED"},
            {"id": "TREND_PULLBACK", "family": "momentum", "status": "LIMITED"},
            {"id": "MEAN_REVERT_BB", "family": "reversal", "status": "LIMITED"},
        ]
        
        if mode == SimMode.CORE_ONLY:
            return [s for s in strategies if s["status"] == "APPROVED"]
        
        return strategies
    
    def _detect_regime(self, candles: List[Dict]) -> str:
        """Simple regime detection"""
        if len(candles) < 50:
            return "UNKNOWN"
        
        # Calculate 20 and 50 period SMAs
        closes = [c["close"] for c in candles[-50:]]
        sma_20 = sum(closes[-20:]) / 20
        sma_50 = sum(closes) / 50
        
        current_close = closes[-1]
        
        # Calculate ATR for volatility
        atrs = []
        for i in range(1, min(14, len(candles))):
            c = candles[-i]
            prev_c = candles[-i-1]
            tr = max(
                c["high"] - c["low"],
                abs(c["high"] - prev_c["close"]),
                abs(c["low"] - prev_c["close"])
            )
            atrs.append(tr)
        avg_atr = sum(atrs) / len(atrs) if atrs else 0
        
        # Volatility threshold
        volatility = avg_atr / current_close if current_close > 0 else 0
        
        # Determine regime
        if volatility > 0.03:  # High volatility
            if current_close > sma_20 > sma_50:
                return "EXPANSION"
            else:
                return "VOLATILITY"
        elif sma_20 > sma_50 and current_close > sma_20:
            return "BULL_TREND"
        elif sma_20 < sma_50 and current_close < sma_20:
            return "BEAR_TREND"
        else:
            return "RANGING"
    
    def _generate_signal(
        self,
        strategy: Dict,
        candles: List[Dict],
        regime: str
    ) -> Optional[Dict]:
        """Generate trading signal for strategy"""
        if len(candles) < 50:
            return None
        
        # Simple signal generation based on strategy type
        sid = strategy["id"]
        closes = [c["close"] for c in candles[-50:]]
        current_close = closes[-1]
        
        # Random-ish but deterministic signal generation
        # In real system this would use actual indicators
        import hashlib
        
        hash_input = f"{sid}_{len(candles)}_{current_close:.2f}"
        hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        signal_prob = (hash_val % 1000) / 1000
        
        if signal_prob < 0.02:  # ~2% chance per bar
            direction = "LONG" if (hash_val % 2) == 0 else "SHORT"
            confidence = 0.4 + (hash_val % 100) / 200  # 0.4 - 0.9
            
            # Calculate TP/SL
            atr = abs(closes[-1] - closes[-2]) if len(closes) > 1 else current_close * 0.02
            
            if direction == "LONG":
                stop_loss = current_close - (atr * 2)
                take_profit = current_close + (atr * 3)
            else:
                stop_loss = current_close + (atr * 2)
                take_profit = current_close - (atr * 3)
            
            return {
                "strategy_id": sid,
                "direction": direction,
                "confidence": confidence,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "regime": regime
            }
        
        return None
    
    def _apply_self_healing(
        self,
        bar_index: int,
        asset: str,
        adapter,
        recent_trades: List[SimulatedTrade],
        weights: Dict[str, float],
        health: Dict[str, float],
        logger: GovernanceEventLogger
    ) -> List[GovernanceEvent]:
        """Apply self-healing adjustments"""
        events = []
        
        # Group trades by strategy
        by_strategy = defaultdict(list)
        for trade in recent_trades:
            by_strategy[trade.strategy_id].append(trade)
        
        for sid, trades in by_strategy.items():
            if len(trades) < 5:
                continue
            
            wins = sum(1 for t in trades if t.outcome == "WIN")
            win_rate = wins / len(trades)
            
            current_health = health.get(sid, 1.0)
            
            if win_rate < adapter.demote_winrate_threshold:
                # Demote
                new_health = max(0.2, current_health * adapter.weight_decay_factor)
                if new_health < current_health * 0.98:
                    logger.log_healing_demotion(
                        bar_index, asset, sid, current_health, new_health, win_rate
                    )
                health[sid] = new_health
                weights[sid] = max(0.1, weights.get(sid, 0.5) * adapter.weight_decay_factor)
            
            elif win_rate > adapter.promote_winrate_threshold:
                # Promote
                new_health = min(1.0, current_health * adapter.weight_boost_factor)
                if new_health > current_health * 1.01:
                    logger.log_healing_recovery(
                        bar_index, asset, sid, current_health, new_health, win_rate
                    )
                health[sid] = new_health
                weights[sid] = min(1.0, weights.get(sid, 0.5) * adapter.weight_boost_factor)
        
        return events
    
    def _apply_meta_strategy(
        self,
        bar_index: int,
        asset: str,
        regime: str,
        budgets: Dict[str, float],
        logger: GovernanceEventLogger
    ) -> List[GovernanceEvent]:
        """Apply meta-strategy budget reallocations"""
        events = []
        
        # Regime-based budget adjustments
        regime_budgets = {
            "BULL_TREND": {"breakout": 0.30, "momentum": 0.30, "reversal": 0.10},
            "BEAR_TREND": {"reversal": 0.30, "breakout": 0.15, "momentum": 0.15},
            "RANGING": {"reversal": 0.25, "pattern": 0.20, "mean_reversion": 0.20},
            "EXPANSION": {"breakout": 0.35, "momentum": 0.30, "continuation": 0.15},
            "VOLATILITY": {"reversal": 0.20, "harmonic": 0.15, "pattern": 0.15},
        }
        
        target_budgets = regime_budgets.get(regime, {})
        
        for family, target in target_budgets.items():
            current = budgets.get(family, 0.15)
            if abs(target - current) > 0.05:
                # Smooth transition
                new_budget = current + (target - current) * 0.1
                
                logger.log_meta_reallocation(
                    bar_index, asset, family, current, new_budget, regime
                )
                
                budgets[family] = new_budget
        
        return events
    
    def _calculate_overlay(
        self,
        drawdown_pct: float,
        regime: str,
        bar_index: int,
        asset: str,
        logger: GovernanceEventLogger
    ) -> float:
        """Calculate portfolio overlay multiplier"""
        
        # Drawdown-based reduction
        if drawdown_pct > 0.30:
            multiplier = 0.3
            logger.log_overlay_trigger(
                bar_index, asset, "SEVERE_DRAWDOWN",
                multiplier, f"DD: {drawdown_pct:.2%}"
            )
        elif drawdown_pct > 0.20:
            multiplier = 0.5
            logger.log_overlay_trigger(
                bar_index, asset, "HIGH_DRAWDOWN",
                multiplier, f"DD: {drawdown_pct:.2%}"
            )
        elif drawdown_pct > 0.10:
            multiplier = 0.75
        else:
            multiplier = 1.0
        
        # Regime-based adjustment
        if regime == "VOLATILITY":
            multiplier *= 0.8
        elif regime == "EXPANSION":
            multiplier *= 1.1  # Can go slightly above 1.0
        
        return min(1.2, max(0.2, multiplier))
    
    def _check_bias_alignment(self, direction: str, regime: str) -> bool:
        """Check if signal aligns with structural bias"""
        # Long bias allowed in trending up regimes
        if direction == "LONG" and regime in ["BULL_TREND", "EXPANSION"]:
            return True
        # Short bias allowed in down regimes
        if direction == "SHORT" and regime == "BEAR_TREND":
            return True
        # Both allowed in neutral
        if regime in ["RANGING", "UNKNOWN"]:
            return True
        # High volatility - reduce both
        if regime == "VOLATILITY":
            return False
        
        return True
    
    def get_run(self, run_id: str) -> Optional[WalkForwardRun]:
        """Get run by ID"""
        return self.runs.get(run_id)
    
    def get_report(self, run_id: str) -> Optional[WalkForwardReport]:
        """Get report by run ID"""
        return self.reports.get(run_id)
    
    def list_runs(self) -> List[Dict]:
        """List all runs"""
        return [
            {
                "run_id": r.run_id,
                "asset": r.asset,
                "mode": r.mode.value,
                "status": r.status.value,
                "progress_pct": round(r.progress_pct, 2)
            }
            for r in self.runs.values()
        ]


# Singleton instance
cross_asset_engine = CrossAssetWalkForwardEngine()
