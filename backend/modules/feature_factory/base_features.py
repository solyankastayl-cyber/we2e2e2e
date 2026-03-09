"""
Feature Base Generator
======================

Phase 9.31 - Generates base features from OHLCV data.

Base features are the raw building blocks:
- Returns
- Volatility
- Moving averages
- ATR
- Momentum
- Volume metrics
"""

import math
from typing import List, Dict, Optional
from collections import deque

from .types import (
    FeatureDescriptor, FeatureFamily, FeatureType,
    NormalizationMethod, FeatureStatus
)


class BaseFeatureGenerator:
    """
    Generates base features from OHLCV data.
    
    These are primary features computed directly from market data.
    """
    
    # ============================================
    # Return Features
    # ============================================
    
    @staticmethod
    def returns(closes: List[float]) -> List[float]:
        """Simple returns: (close[t] - close[t-1]) / close[t-1]"""
        if len(closes) < 2:
            return []
        return [(closes[i] - closes[i-1]) / closes[i-1] if closes[i-1] != 0 else 0 
                for i in range(1, len(closes))]
    
    @staticmethod
    def log_returns(closes: List[float]) -> List[float]:
        """Log returns: ln(close[t] / close[t-1])"""
        if len(closes) < 2:
            return []
        result = []
        for i in range(1, len(closes)):
            if closes[i-1] > 0 and closes[i] > 0:
                result.append(math.log(closes[i] / closes[i-1]))
            else:
                result.append(0)
        return result
    
    # ============================================
    # Volatility Features
    # ============================================
    
    @staticmethod
    def rolling_volatility(returns: List[float], window: int = 20) -> List[float]:
        """Rolling standard deviation of returns"""
        if len(returns) < window:
            return [0.0] * len(returns)
        
        result = [0.0] * (window - 1)
        
        for i in range(window - 1, len(returns)):
            window_returns = returns[i - window + 1:i + 1]
            mean = sum(window_returns) / window
            variance = sum((r - mean) ** 2 for r in window_returns) / window
            result.append(math.sqrt(variance) if variance > 0 else 0)
        
        return result
    
    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], window: int = 14) -> List[float]:
        """Average True Range"""
        if len(highs) < 2:
            return []
        
        # Calculate true ranges
        true_ranges = [highs[0] - lows[0]]  # First TR is just high-low
        
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            true_ranges.append(tr)
        
        # Calculate ATR (SMA of TR)
        if len(true_ranges) < window:
            return [sum(true_ranges[:i+1]) / (i+1) for i in range(len(true_ranges))]
        
        result = []
        for i in range(len(true_ranges)):
            if i < window - 1:
                result.append(sum(true_ranges[:i+1]) / (i+1))
            else:
                result.append(sum(true_ranges[i-window+1:i+1]) / window)
        
        return result
    
    # ============================================
    # Moving Average Features
    # ============================================
    
    @staticmethod
    def sma(values: List[float], window: int) -> List[float]:
        """Simple Moving Average"""
        if len(values) < window:
            return [sum(values[:i+1]) / (i+1) for i in range(len(values))]
        
        result = []
        for i in range(len(values)):
            if i < window - 1:
                result.append(sum(values[:i+1]) / (i+1))
            else:
                result.append(sum(values[i-window+1:i+1]) / window)
        
        return result
    
    @staticmethod
    def ema(values: List[float], window: int) -> List[float]:
        """Exponential Moving Average"""
        if not values:
            return []
        
        alpha = 2 / (window + 1)
        result = [values[0]]
        
        for i in range(1, len(values)):
            ema_val = alpha * values[i] + (1 - alpha) * result[-1]
            result.append(ema_val)
        
        return result
    
    @staticmethod
    def ma_distance(closes: List[float], window: int) -> List[float]:
        """Distance from moving average: (close - MA) / MA"""
        ma = BaseFeatureGenerator.sma(closes, window)
        
        return [(closes[i] - ma[i]) / ma[i] if ma[i] != 0 else 0 
                for i in range(len(closes))]
    
    @staticmethod
    def ma_spread(closes: List[float], fast: int = 10, slow: int = 50) -> List[float]:
        """MA spread: (fast_MA - slow_MA) / slow_MA"""
        fast_ma = BaseFeatureGenerator.sma(closes, fast)
        slow_ma = BaseFeatureGenerator.sma(closes, slow)
        
        return [(fast_ma[i] - slow_ma[i]) / slow_ma[i] if slow_ma[i] != 0 else 0
                for i in range(len(closes))]
    
    # ============================================
    # Momentum Features
    # ============================================
    
    @staticmethod
    def momentum(closes: List[float], period: int = 10) -> List[float]:
        """Momentum: close[t] / close[t-n] - 1"""
        if len(closes) <= period:
            return [0.0] * len(closes)
        
        result = [0.0] * period
        
        for i in range(period, len(closes)):
            if closes[i - period] != 0:
                result.append(closes[i] / closes[i - period] - 1)
            else:
                result.append(0)
        
        return result
    
    @staticmethod
    def roc(closes: List[float], period: int = 10) -> List[float]:
        """Rate of Change: ((close - close[n]) / close[n]) * 100"""
        if len(closes) <= period:
            return [0.0] * len(closes)
        
        result = [0.0] * period
        
        for i in range(period, len(closes)):
            if closes[i - period] != 0:
                result.append((closes[i] - closes[i - period]) / closes[i - period] * 100)
            else:
                result.append(0)
        
        return result
    
    @staticmethod
    def rsi(closes: List[float], period: int = 14) -> List[float]:
        """Relative Strength Index"""
        if len(closes) < period + 1:
            return [50.0] * len(closes)
        
        # Calculate gains and losses
        changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [max(0, c) for c in changes]
        losses = [abs(min(0, c)) for c in changes]
        
        # Initial averages
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        result = [50.0] * period
        
        # Calculate RSI
        for i in range(period, len(changes)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                result.append(100.0)
            else:
                rs = avg_gain / avg_loss
                result.append(100 - (100 / (1 + rs)))
        
        return result
    
    # ============================================
    # Trend Features
    # ============================================
    
    @staticmethod
    def trend_strength(closes: List[float], window: int = 20) -> List[float]:
        """Trend strength: abs(slope) / volatility"""
        if len(closes) < window:
            return [0.0] * len(closes)
        
        result = [0.0] * (window - 1)
        
        for i in range(window - 1, len(closes)):
            window_prices = closes[i - window + 1:i + 1]
            
            # Calculate slope (linear regression)
            x_mean = (window - 1) / 2
            y_mean = sum(window_prices) / window
            
            numerator = sum((j - x_mean) * (window_prices[j] - y_mean) for j in range(window))
            denominator = sum((j - x_mean) ** 2 for j in range(window))
            
            slope = numerator / denominator if denominator != 0 else 0
            
            # Calculate volatility
            variance = sum((p - y_mean) ** 2 for p in window_prices) / window
            vol = math.sqrt(variance) if variance > 0 else 0.001
            
            result.append(abs(slope) / vol if vol > 0 else 0)
        
        return result
    
    @staticmethod
    def trend_persistence(returns: List[float], window: int = 20) -> List[float]:
        """Trend persistence: % of same-sign returns"""
        if len(returns) < window:
            return [0.5] * len(returns)
        
        result = [0.5] * (window - 1)
        
        for i in range(window - 1, len(returns)):
            window_returns = returns[i - window + 1:i + 1]
            positive = sum(1 for r in window_returns if r > 0)
            result.append(max(positive, window - positive) / window)
        
        return result
    
    # ============================================
    # Structure Features
    # ============================================
    
    @staticmethod
    def range_width(highs: List[float], lows: List[float], window: int = 20) -> List[float]:
        """Range width: (max - min) / mid"""
        if len(highs) < window:
            return [0.0] * len(highs)
        
        result = [0.0] * (window - 1)
        
        for i in range(window - 1, len(highs)):
            high_max = max(highs[i - window + 1:i + 1])
            low_min = min(lows[i - window + 1:i + 1])
            mid = (high_max + low_min) / 2
            result.append((high_max - low_min) / mid if mid != 0 else 0)
        
        return result
    
    @staticmethod
    def candle_body_ratio(opens: List[float], highs: List[float], 
                         lows: List[float], closes: List[float]) -> List[float]:
        """Candle body ratio: body / range"""
        result = []
        
        for i in range(len(opens)):
            body = abs(closes[i] - opens[i])
            range_val = highs[i] - lows[i]
            result.append(body / range_val if range_val != 0 else 0)
        
        return result
    
    @staticmethod
    def drawdown_depth(closes: List[float]) -> List[float]:
        """Current drawdown from peak"""
        if not closes:
            return []
        
        result = []
        peak = closes[0]
        
        for close in closes:
            if close > peak:
                peak = close
            dd = (peak - close) / peak if peak != 0 else 0
            result.append(dd)
        
        return result
    
    # ============================================
    # Volume Features
    # ============================================
    
    @staticmethod
    def volume_ratio(volumes: List[float], window: int = 20) -> List[float]:
        """Volume ratio: current / MA(volume)"""
        if not volumes:
            return []
        
        ma = BaseFeatureGenerator.sma(volumes, window)
        
        return [volumes[i] / ma[i] if ma[i] != 0 else 1 for i in range(len(volumes))]
    
    @staticmethod
    def volume_change(volumes: List[float]) -> List[float]:
        """Volume change: (vol[t] - vol[t-1]) / vol[t-1]"""
        if len(volumes) < 2:
            return []
        
        return [(volumes[i] - volumes[i-1]) / volumes[i-1] if volumes[i-1] != 0 else 0
                for i in range(1, len(volumes))]
    
    # ============================================
    # Breakout Features
    # ============================================
    
    @staticmethod
    def breakout_distance(closes: List[float], highs: List[float], 
                         lows: List[float], window: int = 20) -> List[float]:
        """Distance from N-period high/low"""
        if len(closes) < window:
            return [0.0] * len(closes)
        
        result = [0.0] * (window - 1)
        
        for i in range(window - 1, len(closes)):
            high_max = max(highs[i - window + 1:i + 1])
            low_min = min(lows[i - window + 1:i + 1])
            range_val = high_max - low_min
            
            if range_val != 0:
                # Position in range (0 = at low, 1 = at high)
                position = (closes[i] - low_min) / range_val
                # Convert to breakout distance (-0.5 to 0.5)
                result.append(position - 0.5)
            else:
                result.append(0)
        
        return result


# Feature definitions for registry
BASE_FEATURE_DEFINITIONS = [
    FeatureDescriptor(
        feature_id="F_RETURNS",
        name="Simple Returns",
        family=FeatureFamily.MOMENTUM,
        feature_type=FeatureType.BASE,
        source_fields=["close"],
        formula="(close[t] - close[t-1]) / close[t-1]",
        description="Daily simple returns"
    ),
    FeatureDescriptor(
        feature_id="F_LOG_RETURNS",
        name="Log Returns",
        family=FeatureFamily.MOMENTUM,
        feature_type=FeatureType.BASE,
        source_fields=["close"],
        formula="ln(close[t] / close[t-1])",
        description="Daily log returns"
    ),
    FeatureDescriptor(
        feature_id="F_VOLATILITY_20",
        name="Rolling Volatility 20",
        family=FeatureFamily.VOLATILITY,
        feature_type=FeatureType.BASE,
        source_fields=["returns"],
        formula="std(returns, 20)",
        description="20-day rolling volatility"
    ),
    FeatureDescriptor(
        feature_id="F_ATR_14",
        name="ATR 14",
        family=FeatureFamily.VOLATILITY,
        feature_type=FeatureType.BASE,
        source_fields=["high", "low", "close"],
        formula="SMA(TR, 14)",
        description="14-day Average True Range"
    ),
    FeatureDescriptor(
        feature_id="F_MA_DISTANCE_20",
        name="MA Distance 20",
        family=FeatureFamily.TREND,
        feature_type=FeatureType.BASE,
        source_fields=["close"],
        formula="(close - SMA(close, 20)) / SMA(close, 20)",
        description="Distance from 20-day MA"
    ),
    FeatureDescriptor(
        feature_id="F_MA_SPREAD_10_50",
        name="MA Spread 10/50",
        family=FeatureFamily.TREND,
        feature_type=FeatureType.BASE,
        source_fields=["close"],
        formula="(SMA(10) - SMA(50)) / SMA(50)",
        description="Spread between fast and slow MA"
    ),
    FeatureDescriptor(
        feature_id="F_MOMENTUM_10",
        name="Momentum 10",
        family=FeatureFamily.MOMENTUM,
        feature_type=FeatureType.BASE,
        source_fields=["close"],
        formula="close[t] / close[t-10] - 1",
        description="10-day momentum"
    ),
    FeatureDescriptor(
        feature_id="F_RSI_14",
        name="RSI 14",
        family=FeatureFamily.MOMENTUM,
        feature_type=FeatureType.BASE,
        source_fields=["close"],
        formula="RSI(close, 14)",
        description="14-day Relative Strength Index"
    ),
    FeatureDescriptor(
        feature_id="F_TREND_STRENGTH_20",
        name="Trend Strength 20",
        family=FeatureFamily.TREND,
        feature_type=FeatureType.BASE,
        source_fields=["close"],
        formula="abs(slope(close, 20)) / std(close, 20)",
        description="Trend strength measure"
    ),
    FeatureDescriptor(
        feature_id="F_TREND_PERSISTENCE_20",
        name="Trend Persistence 20",
        family=FeatureFamily.TREND,
        feature_type=FeatureType.BASE,
        source_fields=["returns"],
        formula="max(pos_pct, neg_pct)",
        description="Percentage of consistent direction"
    ),
    FeatureDescriptor(
        feature_id="F_RANGE_WIDTH_20",
        name="Range Width 20",
        family=FeatureFamily.STRUCTURE,
        feature_type=FeatureType.BASE,
        source_fields=["high", "low"],
        formula="(max(high, 20) - min(low, 20)) / mid",
        description="20-day range width"
    ),
    FeatureDescriptor(
        feature_id="F_CANDLE_BODY_RATIO",
        name="Candle Body Ratio",
        family=FeatureFamily.STRUCTURE,
        feature_type=FeatureType.BASE,
        source_fields=["open", "high", "low", "close"],
        formula="abs(close - open) / (high - low)",
        description="Candle body to range ratio"
    ),
    FeatureDescriptor(
        feature_id="F_DRAWDOWN_DEPTH",
        name="Drawdown Depth",
        family=FeatureFamily.STRUCTURE,
        feature_type=FeatureType.BASE,
        source_fields=["close"],
        formula="(peak - close) / peak",
        description="Current drawdown from peak"
    ),
    FeatureDescriptor(
        feature_id="F_VOLUME_RATIO_20",
        name="Volume Ratio 20",
        family=FeatureFamily.LIQUIDITY,
        feature_type=FeatureType.BASE,
        source_fields=["volume"],
        formula="volume / SMA(volume, 20)",
        description="Volume relative to 20-day average"
    ),
    FeatureDescriptor(
        feature_id="F_BREAKOUT_DISTANCE_20",
        name="Breakout Distance 20",
        family=FeatureFamily.BREAKOUT,
        feature_type=FeatureType.BASE,
        source_fields=["close", "high", "low"],
        formula="(close - low_20) / range_20 - 0.5",
        description="Position in 20-day range"
    ),
]
