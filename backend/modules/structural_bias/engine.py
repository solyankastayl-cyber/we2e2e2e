"""
Structural Bias Engine
======================

Determines structural market bias based on:
1. Long-term trend (EMA 200)
2. Volatility regime
3. Drawdown state
4. Crisis override

Does NOT change strategies - only changes PERMISSION to trade direction.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import math

from .types import (
    StructuralBiasState, BiasDirection, TrendState,
    VolatilityRegime, DrawdownState, BiasAdjustedSignal,
    ASSET_CLASS_CONFIG, BIAS_MULTIPLIERS
)


class StructuralBiasEngine:
    """
    Engine for calculating structural market bias.
    
    Key principle: Equities have structural long bias.
    Don't fight the secular trend - adjust trade permissions.
    """
    
    def __init__(self, asset: str = "SPX"):
        self.asset = asset
        self.config = ASSET_CLASS_CONFIG.get(asset, ASSET_CLASS_CONFIG["SPX"])
        
        # Historical state for calculations
        self.price_history: List[float] = []
        self.ema_50 = 0.0
        self.ema_200 = 0.0
        self.ema_200_prev = 0.0
        self.peak_price = 0.0
        self.vol_history: List[float] = []
        
        # Current state
        self.current_state: Optional[StructuralBiasState] = None
    
    def update(self, price: float, timestamp: int, timeframe: str = "1d") -> StructuralBiasState:
        """
        Update bias state with new price data.
        Returns current structural bias.
        """
        # Update price history
        self.price_history.append(price)
        
        # Track peak for drawdown
        if price > self.peak_price:
            self.peak_price = price
        
        # Need enough history for EMA 200
        if len(self.price_history) < 200:
            return self._create_default_state(price, timestamp, timeframe)
        
        # Calculate EMAs
        self.ema_200_prev = self.ema_200
        self.ema_50 = self._calculate_ema(50)
        self.ema_200 = self._calculate_ema(200)
        
        # Calculate EMA 200 slope (rate of change)
        ema_200_slope = 0.0
        if self.ema_200_prev > 0:
            ema_200_slope = (self.ema_200 - self.ema_200_prev) / self.ema_200_prev
        
        # Calculate volatility
        current_vol = self._calculate_volatility(20)
        avg_vol = self._calculate_volatility(100)
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
        self.vol_history.append(current_vol)
        
        # Calculate drawdown
        current_drawdown = (self.peak_price - price) / self.peak_price if self.peak_price > 0 else 0
        
        # Determine trend state
        trend_state = self._determine_trend(price, ema_200_slope)
        
        # Determine volatility regime
        vol_regime = self._determine_volatility_regime(vol_ratio)
        
        # Determine drawdown state
        dd_state = self._determine_drawdown_state(current_drawdown)
        
        # Calculate final bias
        bias, reasons = self._calculate_bias(trend_state, vol_regime, dd_state, price)
        
        # Get multipliers
        multipliers = BIAS_MULTIPLIERS[bias]
        
        # Check for crisis override
        crisis_override = False
        if self.config["enable_crisis_override"] and dd_state == DrawdownState.CRISIS:
            crisis_override = True
            if bias == BiasDirection.LONG_ONLY:
                bias = BiasDirection.NEUTRAL
                reasons.append("Crisis override: relaxed from LONG_ONLY to NEUTRAL")
        
        # Create state
        state = StructuralBiasState(
            asset=self.asset,
            timeframe=timeframe,
            timestamp=timestamp,
            long_term_trend=trend_state,
            volatility_regime=vol_regime,
            drawdown_state=dd_state,
            price=price,
            ema_50=self.ema_50,
            ema_200=self.ema_200,
            ema_200_slope=ema_200_slope,
            current_vol=current_vol,
            avg_vol=avg_vol,
            vol_ratio=vol_ratio,
            current_drawdown=current_drawdown,
            peak_price=self.peak_price,
            bias=bias,
            long_multiplier=multipliers["long"],
            short_multiplier=multipliers["short"],
            crisis_override_active=crisis_override,
            reasons=reasons
        )
        
        self.current_state = state
        return state
    
    def _calculate_ema(self, period: int) -> float:
        """Calculate EMA for given period"""
        if len(self.price_history) < period:
            return self.price_history[-1] if self.price_history else 0
        
        prices = self.price_history[-period:]
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _calculate_volatility(self, period: int) -> float:
        """Calculate volatility (std of returns) for period"""
        if len(self.price_history) < period + 1:
            return 0.02  # Default 2%
        
        prices = self.price_history[-(period + 1):]
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        if not returns:
            return 0.02
        
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret)**2 for r in returns) / len(returns)
        return math.sqrt(variance)
    
    def _determine_trend(self, price: float, ema_slope: float) -> TrendState:
        """Determine long-term trend state"""
        price_vs_ema = (price - self.ema_200) / self.ema_200 if self.ema_200 > 0 else 0
        
        # Strong trends
        if price_vs_ema > 0.10 and ema_slope > 0.001:
            return TrendState.STRONG_UP
        if price_vs_ema < -0.10 and ema_slope < -0.001:
            return TrendState.STRONG_DOWN
        
        # Normal trends
        if price > self.ema_200 and ema_slope > 0:
            return TrendState.UP
        if price < self.ema_200 and ema_slope < 0:
            return TrendState.DOWN
        
        return TrendState.FLAT
    
    def _determine_volatility_regime(self, vol_ratio: float) -> VolatilityRegime:
        """Determine volatility regime from ratio to average"""
        if vol_ratio > 2.0:
            return VolatilityRegime.EXTREME
        if vol_ratio > 1.5:
            return VolatilityRegime.HIGH
        if vol_ratio < 0.7:
            return VolatilityRegime.LOW
        return VolatilityRegime.NORMAL
    
    def _determine_drawdown_state(self, drawdown: float) -> DrawdownState:
        """Determine drawdown severity"""
        if drawdown > 0.20:
            return DrawdownState.CRISIS
        if drawdown > 0.10:
            return DrawdownState.STRESSED
        if drawdown > 0.05:
            return DrawdownState.ELEVATED
        return DrawdownState.NORMAL
    
    def _calculate_bias(
        self,
        trend: TrendState,
        vol: VolatilityRegime,
        dd: DrawdownState,
        price: float
    ) -> tuple[BiasDirection, List[str]]:
        """
        Calculate structural bias based on market conditions.
        
        For equities (SPX):
        - Default is LONG_PREFERRED
        - Strong uptrend → LONG_ONLY
        - Crisis/downtrend → NEUTRAL or SHORT_PREFERRED
        """
        reasons = []
        asset_class = self.config["class"]
        
        # Equity index logic
        if asset_class == "equity_index":
            return self._calculate_equity_bias(trend, vol, dd, reasons)
        
        # Crypto logic - more symmetric
        if asset_class == "crypto":
            return self._calculate_crypto_bias(trend, vol, dd, reasons)
        
        # FX logic - mostly neutral
        if asset_class == "fx":
            reasons.append("FX: symmetric market structure")
            return BiasDirection.NEUTRAL, reasons
        
        # Default
        return BiasDirection.NEUTRAL, reasons
    
    def _calculate_equity_bias(
        self,
        trend: TrendState,
        vol: VolatilityRegime,
        dd: DrawdownState,
        reasons: List[str]
    ) -> tuple[BiasDirection, List[str]]:
        """Equity-specific bias calculation"""
        
        # Strong bull market → LONG_ONLY
        if trend == TrendState.STRONG_UP and vol in [VolatilityRegime.LOW, VolatilityRegime.NORMAL]:
            reasons.append(f"Strong uptrend + normal vol → LONG_ONLY")
            return BiasDirection.LONG_ONLY, reasons
        
        # Normal bull market → LONG_PREFERRED
        if trend in [TrendState.STRONG_UP, TrendState.UP]:
            if dd == DrawdownState.NORMAL:
                reasons.append(f"Uptrend + healthy drawdown → LONG_PREFERRED")
                return BiasDirection.LONG_PREFERRED, reasons
        
        # High volatility in uptrend → LONG_PREFERRED (not ONLY)
        if trend == TrendState.UP and vol == VolatilityRegime.HIGH:
            reasons.append(f"Uptrend but high vol → LONG_PREFERRED")
            return BiasDirection.LONG_PREFERRED, reasons
        
        # Flat market → LONG_PREFERRED (equity drift)
        if trend == TrendState.FLAT:
            reasons.append(f"Flat trend, maintain equity drift bias → LONG_PREFERRED")
            return BiasDirection.LONG_PREFERRED, reasons
        
        # Beginning of downtrend → NEUTRAL
        if trend == TrendState.DOWN and dd in [DrawdownState.NORMAL, DrawdownState.ELEVATED]:
            reasons.append(f"Downtrend developing → NEUTRAL")
            return BiasDirection.NEUTRAL, reasons
        
        # Strong downtrend + crisis → SHORT_PREFERRED
        if trend == TrendState.STRONG_DOWN and dd == DrawdownState.CRISIS:
            reasons.append(f"Strong downtrend + crisis → SHORT_PREFERRED")
            return BiasDirection.SHORT_PREFERRED, reasons
        
        # Stressed market → NEUTRAL
        if dd in [DrawdownState.STRESSED, DrawdownState.CRISIS]:
            reasons.append(f"Stressed drawdown → NEUTRAL")
            return BiasDirection.NEUTRAL, reasons
        
        # Default for equities
        reasons.append(f"Default equity bias → LONG_PREFERRED")
        return BiasDirection.LONG_PREFERRED, reasons
    
    def _calculate_crypto_bias(
        self,
        trend: TrendState,
        vol: VolatilityRegime,
        dd: DrawdownState,
        reasons: List[str]
    ) -> tuple[BiasDirection, List[str]]:
        """Crypto-specific bias calculation - more symmetric"""
        
        # Strong trends get directional bias
        if trend == TrendState.STRONG_UP:
            reasons.append(f"Strong crypto uptrend → LONG_PREFERRED")
            return BiasDirection.LONG_PREFERRED, reasons
        
        if trend == TrendState.STRONG_DOWN:
            reasons.append(f"Strong crypto downtrend → SHORT_PREFERRED")
            return BiasDirection.SHORT_PREFERRED, reasons
        
        # Default neutral for crypto
        reasons.append(f"Crypto default → NEUTRAL")
        return BiasDirection.NEUTRAL, reasons
    
    def apply_bias(self, signal_direction: str, signal_weight: float) -> BiasAdjustedSignal:
        """
        Apply structural bias to a trading signal.
        
        Args:
            signal_direction: "LONG" or "SHORT"
            signal_weight: Original signal weight (0-1)
            
        Returns:
            BiasAdjustedSignal with adjusted weight
        """
        if self.current_state is None:
            return BiasAdjustedSignal(
                original_weight=signal_weight,
                bias_multiplier=1.0,
                adjusted_weight=signal_weight,
                direction=signal_direction,
                bias_state=BiasDirection.NEUTRAL,
                allowed=True
            )
        
        state = self.current_state
        
        # Get appropriate multiplier
        if signal_direction.upper() == "LONG":
            multiplier = state.long_multiplier
        else:
            multiplier = state.short_multiplier
        
        # Calculate adjusted weight
        adjusted_weight = signal_weight * multiplier
        
        # Check if trade is allowed
        allowed = True
        rejection_reason = None
        
        if multiplier == 0:
            allowed = False
            rejection_reason = f"{signal_direction} blocked by {state.bias.value} bias"
        elif adjusted_weight < 0.05:
            allowed = False
            rejection_reason = f"Adjusted weight too low ({adjusted_weight:.2f})"
        
        return BiasAdjustedSignal(
            original_weight=signal_weight,
            bias_multiplier=multiplier,
            adjusted_weight=adjusted_weight,
            direction=signal_direction,
            bias_state=state.bias,
            allowed=allowed,
            rejection_reason=rejection_reason
        )
    
    def _create_default_state(self, price: float, timestamp: int, timeframe: str) -> StructuralBiasState:
        """Create default state during warmup"""
        default_bias = self.config["default_bias"]
        multipliers = BIAS_MULTIPLIERS[default_bias]
        
        return StructuralBiasState(
            asset=self.asset,
            timeframe=timeframe,
            timestamp=timestamp,
            price=price,
            bias=default_bias,
            long_multiplier=multipliers["long"],
            short_multiplier=multipliers["short"],
            reasons=["Warmup period - using default bias"]
        )
    
    def get_state(self) -> Optional[StructuralBiasState]:
        """Get current bias state"""
        return self.current_state
    
    def reset(self):
        """Reset engine state"""
        self.price_history = []
        self.ema_50 = 0.0
        self.ema_200 = 0.0
        self.ema_200_prev = 0.0
        self.peak_price = 0.0
        self.vol_history = []
        self.current_state = None
