"""
Portfolio Overlay Engine
========================

Main engine for position sizing adjustments.

Three main components:
1. Volatility Targeting - stable risk
2. Conviction Weighting - size by quality
3. Drawdown Control - reduce risk in DD
"""

import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .types import (
    OverlayConfig, OverlayState, SizedPosition,
    DrawdownState, ConvictionLevel,
    DRAWDOWN_MULTIPLIERS, CONVICTION_MULTIPLIERS
)


class VolatilityTargeting:
    """
    Volatility Targeting Component
    
    Keeps portfolio risk stable by adjusting position sizes
    based on realized vs target volatility.
    
    multiplier = target_vol / realized_vol
    """
    
    def __init__(self, config: OverlayConfig):
        self.config = config
        self.returns: List[float] = []
    
    def update(self, current_return: float) -> None:
        """Add new return to history"""
        self.returns.append(current_return)
        # Keep only lookback period
        if len(self.returns) > self.config.vol_lookback_days:
            self.returns = self.returns[-self.config.vol_lookback_days:]
    
    def calculate_realized_vol(self) -> float:
        """Calculate realized volatility from returns"""
        if len(self.returns) < 5:
            return self.config.target_volatility
        
        mean_ret = sum(self.returns) / len(self.returns)
        variance = sum((r - mean_ret)**2 for r in self.returns) / len(self.returns)
        daily_vol = math.sqrt(variance)
        
        # Annualize (assuming daily returns)
        annual_vol = daily_vol * math.sqrt(252)
        
        return max(annual_vol, 0.01)  # Floor at 1%
    
    def get_multiplier(self) -> tuple[float, float]:
        """Get volatility multiplier and realized vol"""
        realized_vol = self.calculate_realized_vol()
        
        if realized_vol <= 0:
            return 1.0, self.config.target_volatility
        
        multiplier = self.config.target_volatility / realized_vol
        
        # Clip to bounds
        multiplier = max(self.config.min_vol_multiplier, 
                        min(self.config.max_vol_multiplier, multiplier))
        
        return multiplier, realized_vol


class ConvictionWeighting:
    """
    Conviction Weighting Component
    
    Adjusts position size based on signal quality:
    - Strategy score (from validation)
    - Regime confidence (from regime detector)
    - Health score (from self-healing)
    """
    
    def __init__(self, config: OverlayConfig):
        self.config = config
    
    def calculate_conviction(
        self,
        strategy_score: float = 0.5,
        regime_confidence: float = 0.5,
        health_score: float = 1.0,
        signal_confidence: float = 0.5
    ) -> tuple[ConvictionLevel, float]:
        """
        Calculate conviction level and multiplier.
        
        Returns (level, multiplier)
        """
        factors = []
        weights = []
        
        # Strategy score (validation robustness)
        if self.config.use_strategy_score:
            factors.append(strategy_score)
            weights.append(0.3)
        
        # Regime confidence
        if self.config.use_regime_confidence:
            factors.append(regime_confidence)
            weights.append(0.3)
        
        # Health score
        if self.config.use_health_score:
            factors.append(health_score)
            weights.append(0.2)
        
        # Signal confidence
        factors.append(signal_confidence)
        weights.append(0.2)
        
        # Weighted average
        if weights:
            total_weight = sum(weights)
            conviction = sum(f * w for f, w in zip(factors, weights)) / total_weight
        else:
            conviction = signal_confidence
        
        # Determine level
        if conviction >= self.config.high_conviction_threshold:
            level = ConvictionLevel.HIGH
        elif conviction <= self.config.low_conviction_threshold:
            level = ConvictionLevel.LOW
        else:
            level = ConvictionLevel.MEDIUM
        
        multiplier = CONVICTION_MULTIPLIERS[level]
        
        return level, multiplier


class DrawdownControl:
    """
    Drawdown Risk Control Component
    
    Reduces position sizes when portfolio is in drawdown.
    The deeper the drawdown, the more aggressive the reduction.
    """
    
    def __init__(self, config: OverlayConfig):
        self.config = config
        self.peak_equity = 0.0
    
    def update_peak(self, equity: float) -> None:
        """Update peak equity if new high"""
        if equity > self.peak_equity:
            self.peak_equity = equity
    
    def calculate_drawdown(self, equity: float) -> float:
        """Calculate current drawdown percentage"""
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - equity) / self.peak_equity
    
    def get_state_and_multiplier(self, equity: float) -> tuple[DrawdownState, float, float]:
        """
        Get drawdown state, multiplier and current DD.
        
        Returns (state, multiplier, drawdown_pct)
        """
        self.update_peak(equity)
        dd = self.calculate_drawdown(equity)
        
        # Determine state
        if dd >= self.config.dd_threshold_critical:
            state = DrawdownState.CRITICAL
        elif dd >= self.config.dd_threshold_danger:
            state = DrawdownState.DANGER
        elif dd >= self.config.dd_threshold_warning:
            state = DrawdownState.WARNING
        elif dd >= self.config.dd_threshold_elevated:
            state = DrawdownState.ELEVATED
        else:
            state = DrawdownState.NORMAL
        
        multiplier = DRAWDOWN_MULTIPLIERS[state]
        
        return state, multiplier, dd


class PortfolioOverlayEngine:
    """
    Main Portfolio Overlay Engine
    
    Combines all three components to produce final position multiplier.
    
    final_size = base_size × vol_mult × conviction_mult × dd_mult
    """
    
    def __init__(self, config: OverlayConfig = None):
        self.config = config or OverlayConfig()
        
        # Initialize components
        self.vol_targeting = VolatilityTargeting(self.config)
        self.conviction = ConvictionWeighting(self.config)
        self.dd_control = DrawdownControl(self.config)
        
        # Current state
        self.current_state: Optional[OverlayState] = None
    
    def update(
        self,
        timestamp: int,
        equity: float,
        daily_return: float = 0.0,
        strategy_score: float = 0.5,
        regime_confidence: float = 0.5,
        health_score: float = 1.0,
        signal_confidence: float = 0.5
    ) -> OverlayState:
        """
        Update overlay state with new data.
        
        Should be called on each bar.
        """
        reasons = []
        
        # 1. Volatility Targeting
        self.vol_targeting.update(daily_return)
        vol_mult, realized_vol = self.vol_targeting.get_multiplier()
        reasons.append(f"Vol: target={self.config.target_volatility:.1%}, realized={realized_vol:.1%}, mult={vol_mult:.2f}")
        
        # 2. Conviction Weighting
        conv_level, conv_mult = self.conviction.calculate_conviction(
            strategy_score, regime_confidence, health_score, signal_confidence
        )
        reasons.append(f"Conviction: {conv_level.value}, mult={conv_mult:.2f}")
        
        # 3. Drawdown Control
        dd_state, dd_mult, dd_pct = self.dd_control.get_state_and_multiplier(equity)
        reasons.append(f"DD: {dd_pct:.1%} ({dd_state.value}), mult={dd_mult:.2f}")
        
        # Final multiplier
        final_mult = vol_mult * conv_mult * dd_mult
        
        # Clip final multiplier
        final_mult = max(self.config.min_position_multiplier,
                        min(self.config.max_position_multiplier, final_mult))
        
        reasons.append(f"Final multiplier: {final_mult:.2f}")
        
        # Create state
        state = OverlayState(
            timestamp=timestamp,
            target_volatility=self.config.target_volatility,
            realized_volatility=realized_vol,
            volatility_multiplier=vol_mult,
            strategy_score=strategy_score,
            regime_confidence=regime_confidence,
            health_score=health_score,
            conviction_level=conv_level,
            conviction_multiplier=conv_mult,
            current_drawdown=dd_pct,
            peak_equity=self.dd_control.peak_equity,
            drawdown_state=dd_state,
            drawdown_multiplier=dd_mult,
            final_multiplier=final_mult,
            reasons=reasons
        )
        
        self.current_state = state
        return state
    
    def size_position(self, base_size: float) -> SizedPosition:
        """
        Apply overlay to position size.
        
        Returns fully adjusted position.
        """
        if self.current_state is None:
            return SizedPosition(
                original_size=base_size,
                volatility_adjusted=base_size,
                conviction_adjusted=base_size,
                drawdown_adjusted=base_size,
                final_size=base_size,
                multipliers={"vol": 1.0, "conviction": 1.0, "dd": 1.0}
            )
        
        state = self.current_state
        
        # Apply multipliers sequentially
        vol_adjusted = base_size * state.volatility_multiplier
        conv_adjusted = vol_adjusted * state.conviction_multiplier
        dd_adjusted = conv_adjusted * state.drawdown_multiplier
        
        return SizedPosition(
            original_size=base_size,
            volatility_adjusted=vol_adjusted,
            conviction_adjusted=conv_adjusted,
            drawdown_adjusted=dd_adjusted,
            final_size=dd_adjusted,
            multipliers={
                "volatility": state.volatility_multiplier,
                "conviction": state.conviction_multiplier,
                "drawdown": state.drawdown_multiplier,
                "final": state.final_multiplier
            }
        )
    
    def get_state(self) -> Optional[OverlayState]:
        """Get current overlay state"""
        return self.current_state
    
    def reset(self) -> None:
        """Reset all components"""
        self.vol_targeting = VolatilityTargeting(self.config)
        self.conviction = ConvictionWeighting(self.config)
        self.dd_control = DrawdownControl(self.config)
        self.current_state = None
