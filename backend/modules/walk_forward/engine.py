"""
Walk-Forward Engine
===================

Main simulation engine with strict forward-only logic.
No future leakage - each day only sees data up to that point.

Modes:
- full_system: All layers (governance, self-healing, meta-strategy)
- full_system_bias: Full system + Structural Bias Layer (Phase 9.3A)
- no_meta: Without Meta-Strategy (Phase 9.27)
- no_healing: Without Self-Healing (Phase 9.26)  
- core_only: Only APPROVED core strategies
- core_bias: Core strategies + Structural Bias Layer
"""

import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict

from .types import (
    Candle, Signal, Trade, DayResult,
    WalkForwardConfig, WalkForwardResult,
    SimulationMode, RegimeType, FailureEvent,
    HISTORICAL_REGIMES
)
from .portfolio import WalkForwardPortfolio
from .metrics import WalkForwardMetrics

# Import Structural Bias Engine
try:
    from modules.structural_bias.engine import StructuralBiasEngine
    BIAS_AVAILABLE = True
except ImportError:
    BIAS_AVAILABLE = False
    print("[WalkForward] Structural Bias not available")

# Import Portfolio Overlay Engine
try:
    from modules.portfolio_overlay.engine import PortfolioOverlayEngine
    OVERLAY_AVAILABLE = True
except ImportError:
    OVERLAY_AVAILABLE = False
    print("[WalkForward] Portfolio Overlay not available")

# Import Hierarchical Allocator Engine (Phase 9.3F)
try:
    from modules.hierarchical_allocator.engine import HierarchicalAllocatorEngine
    from modules.hierarchical_allocator.types import FamilyType, AlphaInput
    HIERARCHICAL_AVAILABLE = True
except ImportError:
    HIERARCHICAL_AVAILABLE = False
    print("[WalkForward] Hierarchical Allocator not available")


class WalkForwardEngine:
    """
    Walk-Forward Simulation Engine
    
    Strict forward-only simulation:
    - Each day only uses data available at that time
    - No future information in indicators, regime detection, or weights
    - Full system stack with configurable layer disabling
    - Optional Structural Bias Layer for equities
    """
    
    def __init__(self, config: WalkForwardConfig):
        self.config = config
        self.portfolio = WalkForwardPortfolio(config)
        
        # Governance state
        self.strategy_health: Dict[str, float] = {}
        self.strategy_weights: Dict[str, float] = {}
        self.family_budgets: Dict[str, float] = {}
        
        # Strategy registry (from bootstrap) - must be after governance state init
        self.strategies = self._load_strategies()
        
        # Structural Bias Engine (Phase 9.3A)
        self.use_bias = config.mode.value in ["full_system_bias", "core_bias"]
        self.bias_engine = None
        if BIAS_AVAILABLE and self.use_bias:
            self.bias_engine = StructuralBiasEngine(config.asset)
            print(f"[WalkForward] Structural Bias enabled for {config.asset}")
        
        # Portfolio Overlay Engine (Phase 9.3D)
        self.use_overlay = config.mode.value in ["full_overlay", "core_overlay"]
        self.overlay_engine = None
        if OVERLAY_AVAILABLE and self.use_overlay:
            self.overlay_engine = PortfolioOverlayEngine()
            print(f"[WalkForward] Portfolio Overlay enabled")
        
        # Hierarchical Allocator Engine (Phase 9.3F)
        self.use_hierarchical = config.mode.value in ["full_hierarchical", "hierarchical_only"]
        self.hierarchical_engine = None
        if HIERARCHICAL_AVAILABLE and self.use_hierarchical:
            self.hierarchical_engine = HierarchicalAllocatorEngine()
            print(f"[WalkForward] Hierarchical Allocator enabled")
        
        # Strategy performance tracking for hierarchical allocation
        self.strategy_returns: Dict[str, List[float]] = {}
        self.last_hierarchical_rebalance = 0
        self.hierarchical_rebalance_period = 20  # Bars between rebalances
        
        # Asset-class specific thresholds for self-healing
        self.asset_class = self._detect_asset_class(config.asset)
        self.healing_thresholds = self._get_healing_thresholds(self.asset_class)
        
        # State tracking
        self.current_regime = "RANGE"
        self.current_bar_index = 0
        self.warmup_complete = False
        
        # Rolling windows for indicators (forward-only)
        self.price_history: List[float] = []
        self.atr_history: List[float] = []
        self.returns_history: List[float] = []
        
        # Event tracking
        self.governance_events: List[Dict[str, Any]] = []
        self.healing_events: List[Dict[str, Any]] = []
        self.bias_events: List[Dict[str, Any]] = []  # Track bias adjustments
        self.day_results: List[DayResult] = []
        
        # Rebalance tracking
        self.last_rebalance_bar = 0
        self.bars_per_week = 5  # Trading days
        
    def _load_strategies(self) -> List[Dict[str, Any]]:
        """Load strategies from config/registry"""
        # Core approved strategies
        strategies = [
            {"id": "MTF_BREAKOUT", "status": "APPROVED", "family": "breakout", "tier": "CORE"},
            {"id": "DOUBLE_BOTTOM", "status": "APPROVED", "family": "reversal", "tier": "CORE"},
            {"id": "DOUBLE_TOP", "status": "APPROVED", "family": "reversal", "tier": "CORE"},
            {"id": "CHANNEL_BREAKOUT", "status": "APPROVED", "family": "breakout", "tier": "CORE"},
            {"id": "MOMENTUM_CONTINUATION", "status": "APPROVED", "family": "continuation", "tier": "CORE"},
            {"id": "HEAD_SHOULDERS", "status": "LIMITED", "family": "reversal", "tier": "TACTICAL"},
            {"id": "HARMONIC_ABCD", "status": "LIMITED", "family": "harmonic", "tier": "TACTICAL"},
            {"id": "WEDGE_RISING", "status": "LIMITED", "family": "pattern", "tier": "TACTICAL"},
            {"id": "WEDGE_FALLING", "status": "LIMITED", "family": "pattern", "tier": "TACTICAL"},
        ]
        
        # Initialize weights
        for s in strategies:
            self.strategy_weights[s["id"]] = 0.5 if s["status"] == "APPROVED" else 0.3
            self.strategy_health[s["id"]] = 1.0
        
        # Initialize family budgets
        self.family_budgets = {
            "breakout": 0.35,
            "reversal": 0.25,
            "continuation": 0.15,
            "pattern": 0.15,
            "harmonic": 0.10
        }
        
        return strategies
    
    def _detect_asset_class(self, asset: str) -> str:
        """Detect asset class from symbol"""
        asset_upper = asset.upper()
        
        # Crypto assets
        if any(c in asset_upper for c in ["BTC", "ETH", "SOL", "XRP", "ADA"]):
            return "CRYPTO"
        
        # Equities / Indices
        if any(e in asset_upper for e in ["SPX", "SPY", "NDX", "QQQ", "DJI", "AAPL", "MSFT", "GOOGL"]):
            return "EQUITY"
        
        # FX
        if any(f in asset_upper for f in ["DXY", "EUR", "GBP", "JPY", "CHF"]):
            return "FX"
        
        # Commodities
        if any(c in asset_upper for c in ["GOLD", "XAU", "SILVER", "XAG", "OIL", "CL"]):
            return "COMMODITY"
        
        return "UNKNOWN"
    
    def _get_healing_thresholds(self, asset_class: str) -> Dict[str, float]:
        """
        Get asset-class specific thresholds for self-healing.
        
        Crypto is more volatile → aggressive thresholds
        Equities have lower volatility → relaxed thresholds (fix for issue P1)
        """
        thresholds = {
            "CRYPTO": {
                "demote_winrate": 0.35,      # Original - aggressive for crypto
                "promote_winrate": 0.60,
                "health_warning": 0.60,
                "health_degraded": 0.40,
                "weight_decay": 0.90,
                "weight_boost": 1.05,
            },
            "EQUITY": {
                "demote_winrate": 0.30,      # More lenient for equities (user fix)
                "promote_winrate": 0.55,     # Lower bar for promotion
                "health_warning": 0.50,      # User suggested: 0.50
                "health_degraded": 0.30,     # User suggested: 0.30
                "weight_decay": 0.95,        # Slower decay
                "weight_boost": 1.03,        # Slower boost
            },
            "FX": {
                "demote_winrate": 0.32,
                "promote_winrate": 0.58,
                "health_warning": 0.55,
                "health_degraded": 0.35,
                "weight_decay": 0.92,
                "weight_boost": 1.04,
            },
            "COMMODITY": {
                "demote_winrate": 0.33,
                "promote_winrate": 0.57,
                "health_warning": 0.55,
                "health_degraded": 0.35,
                "weight_decay": 0.93,
                "weight_boost": 1.04,
            },
        }
        return thresholds.get(asset_class, thresholds["CRYPTO"])
    
    def _get_active_strategies(self) -> List[Dict[str, Any]]:
        """Get strategies based on mode"""
        if self.config.mode == SimulationMode.CORE_ONLY:
            return [s for s in self.strategies if s["status"] == "APPROVED"]
        return self.strategies
    
    # ========================================
    # Indicator Calculation (Forward-Only)
    # ========================================
    
    def _calculate_indicators(self, candles: List[Candle], current_idx: int) -> Dict[str, Any]:
        """Calculate indicators using only data up to current_idx"""
        if current_idx < 20:
            return {"valid": False}
        
        # Get lookback data (only past data)
        lookback = min(200, current_idx)
        recent_candles = candles[current_idx - lookback:current_idx + 1]
        
        if len(recent_candles) < 20:
            return {"valid": False}
        
        closes = [c.close for c in recent_candles]
        highs = [c.high for c in recent_candles]
        lows = [c.low for c in recent_candles]
        
        # SMA
        sma20 = sum(closes[-20:]) / 20
        sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else sma20
        sma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else sma50
        
        # ATR (14-period)
        atr_period = 14
        tr_values = []
        for i in range(1, min(atr_period + 1, len(recent_candles))):
            high = recent_candles[-i].high
            low = recent_candles[-i].low
            prev_close = recent_candles[-i-1].close if i < len(recent_candles) - 1 else low
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)
        atr = sum(tr_values) / len(tr_values) if tr_values else 0
        
        # RSI (14-period)
        rsi = self._calculate_rsi(closes, 14)
        
        # MACD
        ema12 = self._calculate_ema(closes, 12)
        ema26 = self._calculate_ema(closes, 26)
        macd = ema12 - ema26
        signal_line = self._calculate_ema([macd], 9)  # Simplified
        
        # Volatility (20-day std of returns)
        if len(closes) > 20:
            returns = [(closes[i] - closes[i-1]) / closes[i-1] 
                      for i in range(1, len(closes)) if closes[i-1] > 0]
            if len(returns) >= 20:
                recent_returns = returns[-20:]
                mean_ret = sum(recent_returns) / len(recent_returns)
                volatility = (sum((r - mean_ret)**2 for r in recent_returns) / len(recent_returns)) ** 0.5
            else:
                volatility = 0.02
        else:
            volatility = 0.02
        
        return {
            "valid": True,
            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,
            "atr": atr,
            "rsi": rsi,
            "macd": macd,
            "volatility": volatility,
            "close": closes[-1],
            "trend_up": closes[-1] > sma50 > sma200,
            "trend_down": closes[-1] < sma50 < sma200
        }
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        recent_gains = gains[-period:]
        recent_losses = losses[-period:]
        
        avg_gain = sum(recent_gains) / period
        avg_loss = sum(recent_losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    # ========================================
    # Regime Detection (Forward-Only)
    # ========================================
    
    def _detect_regime(self, candles: List[Candle], current_idx: int, indicators: Dict[str, Any]) -> str:
        """Detect market regime using only data up to current_idx"""
        if not indicators.get("valid"):
            return "RANGE"
        
        close = indicators["close"]
        sma50 = indicators["sma50"]
        sma200 = indicators["sma200"]
        atr = indicators["atr"]
        volatility = indicators["volatility"]
        
        # Trend detection
        if indicators["trend_up"]:
            # Check for expansion
            if volatility > 0.025:  # High volatility
                return "EXPANSION"
            return "TREND_UP"
        
        if indicators["trend_down"]:
            if volatility > 0.03:  # Very high volatility = crisis
                return "CRISIS"
            return "TREND_DOWN"
        
        # Range or compression
        if volatility < 0.01:
            return "COMPRESSION"
        
        return "RANGE"
    
    # ========================================
    # Signal Generation
    # ========================================
    
    def _generate_signals(
        self, 
        candle: Candle, 
        candles: List[Candle],
        current_idx: int,
        indicators: Dict[str, Any],
        regime: str
    ) -> List[Signal]:
        """Generate trading signals from active strategies"""
        if not indicators.get("valid"):
            return []
        
        signals = []
        active_strategies = self._get_active_strategies()
        
        for strategy in active_strategies:
            # Check if strategy is active in current regime
            if not self._is_strategy_active(strategy, regime):
                continue
            
            # Check strategy weight (meta-strategy effect)
            weight = self.strategy_weights.get(strategy["id"], 0.5)
            if weight < 0.1:
                continue
            
            # Generate signal based on strategy type
            signal = self._generate_strategy_signal(
                strategy, candle, candles, current_idx, indicators, regime
            )
            
            if signal:
                signals.append(signal)
        
        return signals
    
    def _is_strategy_active(self, strategy: Dict[str, Any], regime: str) -> bool:
        """Check if strategy should be active in current regime"""
        # Regime activation map (simplified)
        activation_map = {
            "MTF_BREAKOUT": {"TREND_UP": True, "TREND_DOWN": True, "EXPANSION": True},
            "DOUBLE_BOTTOM": {"TREND_UP": True, "RANGE": True, "EXPANSION": True},
            "DOUBLE_TOP": {"TREND_DOWN": True, "RANGE": True, "EXPANSION": True},
            "CHANNEL_BREAKOUT": {"TREND_UP": True, "TREND_DOWN": True, "EXPANSION": True},
            "MOMENTUM_CONTINUATION": {"TREND_UP": True, "TREND_DOWN": True, "EXPANSION": True},
            "HEAD_SHOULDERS": {"TREND_DOWN": True, "EXPANSION": True},
            "HARMONIC_ABCD": {"TREND_UP": True, "RANGE": True},
            "WEDGE_RISING": {"TREND_DOWN": True, "EXPANSION": True},
            "WEDGE_FALLING": {"TREND_UP": True, "EXPANSION": True},
        }
        
        strategy_id = strategy["id"]
        if strategy_id in activation_map:
            return activation_map[strategy_id].get(regime, False)
        
        return True  # Default active
    
    def _generate_strategy_signal(
        self,
        strategy: Dict[str, Any],
        candle: Candle,
        candles: List[Candle],
        current_idx: int,
        indicators: Dict[str, Any],
        regime: str
    ) -> Optional[Signal]:
        """Generate signal for specific strategy"""
        strategy_id = strategy["id"]
        close = indicators["close"]
        atr = indicators["atr"]
        rsi = indicators["rsi"]
        sma20 = indicators["sma20"]
        sma50 = indicators["sma50"]
        
        signal = None
        
        # Breakout strategies - relaxed conditions
        if "BREAKOUT" in strategy_id:
            if current_idx > 20:
                recent_high = max(c.high for c in candles[current_idx-20:current_idx])
                recent_low = min(c.low for c in candles[current_idx-20:current_idx])
                
                # Long breakout
                if candle.close > recent_high * 1.001:  # Small buffer
                    signal = Signal(
                        id=f"sig_{candle.timestamp}_{strategy_id}",
                        strategy_id=strategy_id,
                        direction="LONG",
                        entry_price=candle.close,
                        stop_loss=candle.close - 2 * atr,
                        take_profit=candle.close + 3 * atr,
                        confidence=0.6,
                        timestamp=candle.timestamp,
                        pattern_type="BREAKOUT",
                        regime=regime
                    )
                # Short breakdown
                elif candle.close < recent_low * 0.999:
                    signal = Signal(
                        id=f"sig_{candle.timestamp}_{strategy_id}",
                        strategy_id=strategy_id,
                        direction="SHORT",
                        entry_price=candle.close,
                        stop_loss=candle.close + 2 * atr,
                        take_profit=candle.close - 3 * atr,
                        confidence=0.55,
                        timestamp=candle.timestamp,
                        pattern_type="BREAKDOWN",
                        regime=regime
                    )
        
        # Double bottom - oversold reversal
        elif strategy_id == "DOUBLE_BOTTOM":
            if rsi < 35:
                signal = Signal(
                    id=f"sig_{candle.timestamp}_{strategy_id}",
                    strategy_id=strategy_id,
                    direction="LONG",
                    entry_price=candle.close,
                    stop_loss=candle.close - 2.5 * atr,
                    take_profit=candle.close + 3.5 * atr,
                    confidence=0.55,
                    timestamp=candle.timestamp,
                    pattern_type="DOUBLE_BOTTOM",
                    regime=regime
                )
        
        # Double top - overbought reversal
        elif strategy_id == "DOUBLE_TOP":
            if rsi > 65:
                signal = Signal(
                    id=f"sig_{candle.timestamp}_{strategy_id}",
                    strategy_id=strategy_id,
                    direction="SHORT",
                    entry_price=candle.close,
                    stop_loss=candle.close + 2.5 * atr,
                    take_profit=candle.close - 3.5 * atr,
                    confidence=0.55,
                    timestamp=candle.timestamp,
                    pattern_type="DOUBLE_TOP",
                    regime=regime
                )
        
        # Momentum continuation - trend following
        elif strategy_id == "MOMENTUM_CONTINUATION":
            # Long in uptrend
            if close > sma50 and close > sma20 and 35 < rsi < 65:
                signal = Signal(
                    id=f"sig_{candle.timestamp}_{strategy_id}",
                    strategy_id=strategy_id,
                    direction="LONG",
                    entry_price=candle.close,
                    stop_loss=candle.close - 1.5 * atr,
                    take_profit=candle.close + 2.5 * atr,
                    confidence=0.6,
                    timestamp=candle.timestamp,
                    pattern_type="CONTINUATION",
                    regime=regime
                )
            # Short in downtrend
            elif close < sma50 and close < sma20 and 35 < rsi < 65:
                signal = Signal(
                    id=f"sig_{candle.timestamp}_{strategy_id}",
                    strategy_id=strategy_id,
                    direction="SHORT",
                    entry_price=candle.close,
                    stop_loss=candle.close + 1.5 * atr,
                    take_profit=candle.close - 2.5 * atr,
                    confidence=0.6,
                    timestamp=candle.timestamp,
                    pattern_type="CONTINUATION",
                    regime=regime
                )
        
        # Channel breakout
        elif strategy_id == "CHANNEL_BREAKOUT":
            if current_idx > 50:
                high_50 = max(c.high for c in candles[current_idx-50:current_idx])
                low_50 = min(c.low for c in candles[current_idx-50:current_idx])
                channel_mid = (high_50 + low_50) / 2
                
                if candle.close > high_50 * 1.002:
                    signal = Signal(
                        id=f"sig_{candle.timestamp}_{strategy_id}",
                        strategy_id=strategy_id,
                        direction="LONG",
                        entry_price=candle.close,
                        stop_loss=channel_mid,
                        take_profit=candle.close + 4 * atr,
                        confidence=0.65,
                        timestamp=candle.timestamp,
                        pattern_type="CHANNEL_BREAKOUT",
                        regime=regime
                    )
                elif candle.close < low_50 * 0.998:
                    signal = Signal(
                        id=f"sig_{candle.timestamp}_{strategy_id}",
                        strategy_id=strategy_id,
                        direction="SHORT",
                        entry_price=candle.close,
                        stop_loss=channel_mid,
                        take_profit=candle.close - 4 * atr,
                        confidence=0.65,
                        timestamp=candle.timestamp,
                        pattern_type="CHANNEL_BREAKDOWN",
                        regime=regime
                    )
        
        # Harmonic (mean reversion)
        elif strategy_id == "HARMONIC_ABCD":
            if rsi < 25:  # Extreme oversold
                signal = Signal(
                    id=f"sig_{candle.timestamp}_{strategy_id}",
                    strategy_id=strategy_id,
                    direction="LONG",
                    entry_price=candle.close,
                    stop_loss=candle.close - 3 * atr,
                    take_profit=candle.close + 4 * atr,
                    confidence=0.5,
                    timestamp=candle.timestamp,
                    pattern_type="HARMONIC",
                    regime=regime
                )
            elif rsi > 75:  # Extreme overbought
                signal = Signal(
                    id=f"sig_{candle.timestamp}_{strategy_id}",
                    strategy_id=strategy_id,
                    direction="SHORT",
                    entry_price=candle.close,
                    stop_loss=candle.close + 3 * atr,
                    take_profit=candle.close - 4 * atr,
                    confidence=0.5,
                    timestamp=candle.timestamp,
                    pattern_type="HARMONIC",
                    regime=regime
                )
        
        # Random suppression with fixed seed for reproducibility
        if signal:
            import random
            # Use timestamp as seed for reproducible results
            random.seed(candle.timestamp % 1000000)
            if random.random() > 0.50:
                return None
        
        return signal
    
    # ========================================
    # Governance Layers
    # ========================================
    
    def _apply_self_healing(self, bar_index: int) -> List[Dict[str, Any]]:
        """Apply self-healing adjustments (Phase 9.26) with asset-class calibration"""
        if self.config.mode == SimulationMode.NO_HEALING:
            return []
        
        events = []
        
        # Get asset-class specific thresholds
        demote_threshold = self.healing_thresholds["demote_winrate"]
        promote_threshold = self.healing_thresholds["promote_winrate"]
        weight_decay = self.healing_thresholds["weight_decay"]
        weight_boost = self.healing_thresholds["weight_boost"]
        
        # Calculate rolling performance for each strategy
        recent_trades = self.portfolio.trade_history[-50:] if len(self.portfolio.trade_history) > 50 else self.portfolio.trade_history
        
        strategy_performance: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0})
        
        for trade in recent_trades:
            sid = trade.strategy_id
            strategy_performance[sid]["pnl"] += trade.pnl
            if trade.outcome == "WIN":
                strategy_performance[sid]["wins"] += 1
            else:
                strategy_performance[sid]["losses"] += 1
        
        # Track returns for hierarchical allocator
        for trade in recent_trades:
            sid = trade.strategy_id
            if sid not in self.strategy_returns:
                self.strategy_returns[sid] = []
            # Simple return approximation
            ret = trade.pnl / max(abs(trade.entry_price), 1)
            self.strategy_returns[sid].append(ret)
            # Keep last 200 returns
            self.strategy_returns[sid] = self.strategy_returns[sid][-200:]
        
        # Adjust weights based on performance with calibrated thresholds
        for sid, perf in strategy_performance.items():
            total = perf["wins"] + perf["losses"]
            if total < 5:
                continue
            
            win_rate = perf["wins"] / total
            
            # Update health score
            current_health = self.strategy_health.get(sid, 1.0)
            
            if win_rate < demote_threshold:
                # Demote - reduce health (calibrated decay)
                new_health = max(0.2, current_health * weight_decay)
                if new_health < current_health * 0.98:
                    events.append({
                        "type": "DEMOTION",
                        "strategy_id": sid,
                        "old_health": current_health,
                        "new_health": new_health,
                        "reason": f"Low win rate: {win_rate:.2%} (threshold: {demote_threshold:.0%})",
                        "asset_class": self.asset_class,
                        "bar_index": bar_index
                    })
                self.strategy_health[sid] = new_health
                self.strategy_weights[sid] = max(0.1, self.strategy_weights.get(sid, 0.5) * weight_decay)
            
            elif win_rate > promote_threshold:
                # Promote - increase health (calibrated boost)
                new_health = min(1.0, current_health * weight_boost)
                if new_health > current_health * 1.01:
                    events.append({
                        "type": "RECOVERY",
                        "strategy_id": sid,
                        "old_health": current_health,
                        "new_health": new_health,
                        "reason": f"High win rate: {win_rate:.2%} (threshold: {promote_threshold:.0%})",
                        "asset_class": self.asset_class,
                        "bar_index": bar_index
                    })
                self.strategy_health[sid] = new_health
                self.strategy_weights[sid] = min(1.0, self.strategy_weights.get(sid, 0.5) * weight_boost)
        
        return events
    
    def _apply_meta_strategy(self, regime: str, bar_index: int) -> List[Dict[str, Any]]:
        """Apply meta-strategy weight adjustments (Phase 9.27)"""
        if self.config.mode == SimulationMode.NO_META:
            return []
        
        events = []
        
        # Check rebalance timing
        bars_since_rebalance = bar_index - self.last_rebalance_bar
        should_rebalance = False
        
        if self.config.rebalance_frequency == "weekly":
            should_rebalance = bars_since_rebalance >= self.bars_per_week
        elif self.config.rebalance_frequency == "daily":
            should_rebalance = True
        elif self.config.rebalance_frequency == "monthly":
            should_rebalance = bars_since_rebalance >= 20
        
        if not should_rebalance:
            return []
        
        self.last_rebalance_bar = bar_index
        
        # Regime-based family budget adjustment
        regime_budgets = {
            "TREND_UP": {"breakout": 0.40, "continuation": 0.25, "reversal": 0.15, "harmonic": 0.10, "pattern": 0.10},
            "TREND_DOWN": {"reversal": 0.35, "breakout": 0.25, "continuation": 0.20, "harmonic": 0.10, "pattern": 0.10},
            "RANGE": {"reversal": 0.35, "harmonic": 0.20, "pattern": 0.20, "breakout": 0.15, "continuation": 0.10},
            "COMPRESSION": {"breakout": 0.30, "reversal": 0.25, "pattern": 0.20, "harmonic": 0.15, "continuation": 0.10},
            "EXPANSION": {"breakout": 0.35, "continuation": 0.25, "reversal": 0.20, "pattern": 0.10, "harmonic": 0.10},
            "CRISIS": {"reversal": 0.40, "breakout": 0.25, "continuation": 0.15, "pattern": 0.10, "harmonic": 0.10},
        }
        
        target_budgets = regime_budgets.get(regime, self.family_budgets)
        
        # Smooth adjustment (max change limit)
        for family, target in target_budgets.items():
            current = self.family_budgets.get(family, 0.2)
            max_change = self.config.max_weekly_weight_change
            
            if target > current:
                new_budget = min(target, current + max_change)
            else:
                new_budget = max(target, current - max_change)
            
            if abs(new_budget - current) > 0.01:
                events.append({
                    "type": "META_REALLOCATION",
                    "family": family,
                    "old_budget": current,
                    "new_budget": new_budget,
                    "regime": regime,
                    "bar_index": bar_index
                })
            
            self.family_budgets[family] = new_budget
        
        # Update portfolio with new weights
        self.portfolio.update_weights(self.strategy_weights, self.family_budgets)
        
        return events
    
    def _apply_hierarchical_allocation(self, regime: str, bar_index: int) -> List[Dict[str, Any]]:
        """
        Apply Hierarchical Alpha Allocation (Phase 9.3F)
        
        Two-level optimization:
        1. Intra-family: optimize within each family
        2. Cross-family: allocate between families based on regime
        
        This prevents optimizer from concentrating on noise when scaling to 50+ strategies.
        """
        if not self.use_hierarchical or not self.hierarchical_engine:
            return []
        
        events = []
        
        # Check if it's time to rebalance
        bars_since_rebalance = bar_index - self.last_hierarchical_rebalance
        if bars_since_rebalance < self.hierarchical_rebalance_period:
            return []
        
        self.last_hierarchical_rebalance = bar_index
        
        # Set regime for budget adjustments
        self.hierarchical_engine.set_regime(regime)
        
        # Build alpha inputs from strategy performance
        alpha_inputs = []
        
        family_map = {
            "breakout": FamilyType.BREAKOUT,
            "reversal": FamilyType.REVERSAL,
            "continuation": FamilyType.MOMENTUM,
            "pattern": FamilyType.STRUCTURE,
            "harmonic": FamilyType.HARMONIC,
        }
        
        for strategy in self.strategies:
            sid = strategy["id"]
            family_str = strategy.get("family", "experimental")
            family_type = family_map.get(family_str, FamilyType.EXPERIMENTAL)
            
            # Get returns (need at least 20 for meaningful optimization)
            returns = self.strategy_returns.get(sid, [])
            if len(returns) < 20:
                continue
            
            # Calculate stats
            import numpy as np
            returns_arr = np.array(returns)
            expected_return = float(np.mean(returns_arr) * 252)
            volatility = float(np.std(returns_arr) * np.sqrt(252))
            if volatility < 0.001:
                volatility = 0.01
            sharpe = expected_return / volatility if volatility > 0 else 0
            
            alpha = AlphaInput(
                strategy_id=sid,
                family=family_type,
                returns=returns,
                expected_return=expected_return,
                volatility=volatility,
                sharpe=sharpe,
                health_score=self.strategy_health.get(sid, 1.0),
                regime_fit=1.0 if self._is_strategy_active(strategy, regime) else 0.5
            )
            alpha_inputs.append(alpha)
        
        if len(alpha_inputs) < 3:
            return []
        
        # Add alphas to hierarchical engine
        self.hierarchical_engine.alphas = []  # Reset
        self.hierarchical_engine.add_alphas(alpha_inputs)
        
        # Run hierarchical allocation
        try:
            portfolio = self.hierarchical_engine.allocate(method="max_sharpe")
            
            # Update strategy weights from hierarchical optimization
            new_weights = portfolio.final_weights
            
            for sid, new_weight in new_weights.items():
                old_weight = self.strategy_weights.get(sid, 0.5)
                
                # Smooth transition (max 20% change per rebalance)
                max_change = 0.2
                if abs(new_weight - old_weight) > max_change:
                    if new_weight > old_weight:
                        new_weight = old_weight + max_change
                    else:
                        new_weight = old_weight - max_change
                
                if abs(new_weight - old_weight) > 0.02:
                    events.append({
                        "type": "HIERARCHICAL_REWEIGHT",
                        "strategy_id": sid,
                        "old_weight": round(old_weight, 4),
                        "new_weight": round(new_weight, 4),
                        "regime": regime,
                        "bar_index": bar_index
                    })
                
                self.strategy_weights[sid] = new_weight
            
            # Log portfolio metrics
            if events:
                events.append({
                    "type": "HIERARCHICAL_PORTFOLIO_METRICS",
                    "expected_sharpe": round(portfolio.expected_sharpe, 2),
                    "effective_strategies": round(portfolio.effective_strategies, 1),
                    "effective_families": round(portfolio.effective_families, 1),
                    "diversification_ratio": round(portfolio.diversification_ratio, 2),
                    "bar_index": bar_index
                })
        
        except Exception as e:
            events.append({
                "type": "HIERARCHICAL_ERROR",
                "error": str(e),
                "bar_index": bar_index
            })
        
        return events
    
    def _check_kill_switch(self) -> bool:
        """Check if kill switch should activate (relaxed for long-term sim)"""
        # Max drawdown trigger - 40% for 70-year simulation
        if self.portfolio.drawdown_pct > 0.40:
            if not self.portfolio.kill_switch_active:
                self.portfolio.activate_kill_switch()
                self.governance_events.append({
                    "type": "KILL_SWITCH_ACTIVATED",
                    "reason": f"Max drawdown exceeded: {self.portfolio.drawdown_pct:.2%}",
                    "timestamp": time.time()
                })
            return True
        
        # Consecutive losses trigger
        if self.portfolio.consecutive_losses >= 20:
            if not self.portfolio.kill_switch_active:
                self.portfolio.activate_kill_switch()
                self.governance_events.append({
                    "type": "KILL_SWITCH_ACTIVATED",
                    "reason": f"Consecutive losses: {self.portfolio.consecutive_losses}",
                    "timestamp": time.time()
                })
            return True
        
        # Deactivate if conditions improve significantly
        if self.portfolio.kill_switch_active:
            # Reset if drawdown improves below 25%
            if self.portfolio.drawdown_pct < 0.25 or self.portfolio.consecutive_losses < 3:
                self.portfolio.deactivate_kill_switch()
                self.governance_events.append({
                    "type": "KILL_SWITCH_DEACTIVATED",
                    "reason": "Conditions improved",
                    "timestamp": time.time()
                })
        
        return self.portfolio.kill_switch_active
    
    # ========================================
    # Main Simulation Loop
    # ========================================
    
    def run(self, candles: List[Candle]) -> WalkForwardResult:
        """Run walk-forward simulation"""
        run_id = f"wf_{self.config.asset}_{int(time.time())}"
        started_at = int(time.time() * 1000)
        
        print(f"[WalkForward] Starting {self.config.mode.value} run on {self.config.asset}")
        print(f"[WalkForward] Period: {len(candles)} bars, warmup: {self.config.warmup_bars}")
        
        # Main simulation loop
        for i, candle in enumerate(candles):
            self.current_bar_index = i
            
            # Warmup period - only build indicators and bias engine
            if i < self.config.warmup_bars:
                self.price_history.append(candle.close)
                # Update bias engine during warmup too
                if self.bias_engine:
                    self.bias_engine.update(candle.close, candle.timestamp, self.config.timeframe)
                continue
            
            if not self.warmup_complete:
                self.warmup_complete = True
                print(f"[WalkForward] Warmup complete at bar {i}")
            
            # Update prices first
            self.portfolio.update_prices(candle)
            
            # Update Structural Bias Engine (Phase 9.3A)
            if self.bias_engine:
                bias_state = self.bias_engine.update(candle.close, candle.timestamp, self.config.timeframe)
            
            # Check exits on existing positions
            closed_trades = self.portfolio.check_exits(candle)
            
            # Calculate indicators (forward-only)
            indicators = self._calculate_indicators(candles, i)
            
            # Detect regime (forward-only)
            regime = self._detect_regime(candles, i, indicators)
            self.current_regime = regime
            
            # Apply governance layers
            healing_events = self._apply_self_healing(i)
            self.healing_events.extend(healing_events)
            
            meta_events = self._apply_meta_strategy(regime, i)
            self.governance_events.extend(meta_events)
            
            # Apply Hierarchical Allocation (Phase 9.3F)
            hierarchical_events = self._apply_hierarchical_allocation(regime, i)
            self.governance_events.extend(hierarchical_events)
            
            # Check kill switch
            kill_switch = self._check_kill_switch()
            
            # Generate signals
            signals = []
            trades_opened = []
            if not kill_switch:
                raw_signals = self._generate_signals(candle, candles, i, indicators, regime)
                
                # Apply Structural Bias filter (Phase 9.3A)
                if self.bias_engine and raw_signals:
                    for signal in raw_signals:
                        bias_result = self.bias_engine.apply_bias(signal.direction, signal.confidence)
                        
                        if bias_result.allowed:
                            # Adjust signal confidence by bias multiplier
                            signal.confidence *= bias_result.bias_multiplier
                            signals.append(signal)
                        else:
                            # Track rejected signals
                            self.bias_events.append({
                                "type": "SIGNAL_REJECTED",
                                "bar_index": i,
                                "direction": signal.direction,
                                "reason": bias_result.rejection_reason,
                                "bias_state": bias_result.bias_state.value
                            })
                else:
                    signals = raw_signals
                
                # Calculate daily return for overlay
                daily_return = 0.0
                if i > 0 and candles[i-1].close > 0:
                    daily_return = (candle.close - candles[i-1].close) / candles[i-1].close
                
                # Update Portfolio Overlay (Phase 9.3D)
                overlay_multiplier = 1.0
                if self.overlay_engine:
                    # Get average strategy health and regime confidence
                    avg_health = sum(self.strategy_health.values()) / len(self.strategy_health) if self.strategy_health else 1.0
                    regime_conf = 0.7 if regime in ["TREND_UP", "TREND_DOWN"] else 0.5
                    
                    overlay_state = self.overlay_engine.update(
                        timestamp=candle.timestamp,
                        equity=self.portfolio.equity,
                        daily_return=daily_return,
                        strategy_score=0.6,  # From validation
                        regime_confidence=regime_conf,
                        health_score=avg_health
                    )
                    overlay_multiplier = overlay_state.final_multiplier
                
                # Try to open positions (with overlay-adjusted sizing)
                for signal in signals:
                    # Apply overlay multiplier to position sizing
                    if self.overlay_engine and overlay_multiplier != 1.0:
                        signal.confidence *= overlay_multiplier
                    
                    trade = self.portfolio.open_position(signal, candle)
                    if trade:
                        trades_opened.append(trade)
            
            # Update trade regimes for closed trades
            for trade in closed_trades:
                trade.regime = regime
            
            # Record equity point
            self.portfolio.record_equity(candle.timestamp, regime)
            
            # Record daily result
            dt = candle.date
            day_result = DayResult(
                timestamp=candle.timestamp,
                date_str=dt.strftime("%Y-%m-%d"),
                candle=candle,
                regime=regime,
                signals_generated=len(signals),
                trades_opened=len(trades_opened),
                trades_closed=len(closed_trades),
                pnl=sum(t.pnl for t in closed_trades),
                equity=self.portfolio.equity,
                drawdown_pct=self.portfolio.drawdown_pct,
                events=healing_events + meta_events
            )
            self.day_results.append(day_result)
            
            # Reset daily counters
            self.portfolio.reset_daily()
            
            # Progress logging
            if i % 1000 == 0:
                print(f"[WalkForward] Bar {i}/{len(candles)}, Equity: {self.portfolio.equity:.2f}, DD: {self.portfolio.drawdown_pct:.2%}")
        
        # Close remaining positions at end
        for pos_id in list(self.portfolio.positions.keys()):
            self.portfolio.close_position(pos_id, candles[-1], candles[-1].close, "END")
        
        # Calculate final metrics
        completed_at = int(time.time() * 1000)
        trades = self.portfolio.trade_history
        equity_curve = self.portfolio.equity_history
        
        # Calculate years
        if candles:
            start_date = datetime.utcfromtimestamp(candles[self.config.warmup_bars].timestamp / 1000)
            end_date = datetime.utcfromtimestamp(candles[-1].timestamp / 1000)
            years = (end_date - start_date).days / 365.25
        else:
            years = 1
        
        # Global metrics
        global_metrics = WalkForwardMetrics.calculate_global_metrics(
            trades, equity_curve, self.config.initial_capital, years
        )
        
        # Breakdowns
        decade_metrics = WalkForwardMetrics.calculate_decade_metrics(trades)
        regime_metrics = WalkForwardMetrics.calculate_regime_metrics(trades)
        strategy_metrics = WalkForwardMetrics.calculate_strategy_metrics(trades, self.healing_events)
        
        # Failures
        failure_events = WalkForwardMetrics.detect_failures(trades)
        
        # Build result
        result = WalkForwardResult(
            run_id=run_id,
            config=self.config,
            mode=self.config.mode.value,
            started_at=started_at,
            completed_at=completed_at,
            
            total_trades=global_metrics["total_trades"],
            win_rate=global_metrics["win_rate"],
            profit_factor=global_metrics["profit_factor"],
            sharpe=global_metrics["sharpe"],
            sortino=global_metrics["sortino"],
            calmar=global_metrics["calmar"],
            max_drawdown=global_metrics["max_drawdown"],
            max_drawdown_pct=global_metrics["max_drawdown_pct"],
            total_return=global_metrics["total_return"],
            cagr=global_metrics["cagr"],
            expectancy=global_metrics["expectancy"],
            max_losing_streak=global_metrics["max_losing_streak"],
            avg_recovery_bars=global_metrics["avg_recovery_bars"],
            
            final_equity=self.portfolio.equity,
            peak_equity=self.portfolio.peak_equity,
            
            decade_metrics=decade_metrics,
            regime_metrics=regime_metrics,
            strategy_metrics=strategy_metrics,
            
            governance_events=len(self.governance_events),
            healing_events=len(self.healing_events),
            kill_switch_events=len([e for e in self.governance_events if "KILL_SWITCH" in e.get("type", "")]),
            meta_reallocations=len([e for e in self.governance_events if e.get("type") == "META_REALLOCATION"]),
            
            failure_events=failure_events,
            equity_curve=equity_curve,
            daily_results=self.day_results
        )
        
        # Log bias stats if enabled
        if self.bias_engine and self.bias_events:
            rejected_shorts = len([e for e in self.bias_events if e.get("direction") == "SHORT"])
            rejected_longs = len([e for e in self.bias_events if e.get("direction") == "LONG"])
            print(f"[WalkForward] Bias rejected: {rejected_shorts} shorts, {rejected_longs} longs")
        
        print(f"[WalkForward] Completed: {global_metrics['total_trades']} trades, PF: {global_metrics['profit_factor']}, WR: {global_metrics['win_rate']:.2%}")
        
        return result
