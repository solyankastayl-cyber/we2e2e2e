/**
 * Liquidity Engine - Core Detection Logic
 * 
 * Detects:
 * 1. Equal Highs/Lows (EQH/EQL)
 * 2. Swing Points
 * 3. Liquidity Sweeps
 * 4. Range Boundaries
 * 5. Order Blocks
 */

import {
  Candle,
  LiquidityZone,
  LiquidityZoneType,
  SweepEvent,
  LiquidityAnalysis,
  LiquidityConfig,
  DEFAULT_LIQUIDITY_CONFIG,
} from './liquidity.types.js';

// ═══════════════════════════════════════════════════════════════
// ATR Calculation
// ═══════════════════════════════════════════════════════════════

function calculateATR(candles: Candle[], period: number = 14): number {
  if (candles.length < period + 1) return 0;
  
  let trSum = 0;
  for (let i = 1; i <= period; i++) {
    const curr = candles[candles.length - i];
    const prev = candles[candles.length - i - 1];
    
    const tr = Math.max(
      curr.high - curr.low,
      Math.abs(curr.high - prev.close),
      Math.abs(curr.low - prev.close)
    );
    trSum += tr;
  }
  
  return trSum / period;
}

// ═══════════════════════════════════════════════════════════════
// Equal Highs Detection
// ═══════════════════════════════════════════════════════════════

function detectEqualHighs(
  candles: Candle[],
  config: LiquidityConfig
): LiquidityZone[] {
  const zones: LiquidityZone[] = [];
  const tolerance = config.equalLevelTolerance;
  const minTouches = config.minEqualTouches;
  
  // Get all local highs
  const highs: { price: number; index: number; timestamp: number }[] = [];
  
  for (let i = 2; i < candles.length - 2; i++) {
    const c = candles[i];
    const isLocalHigh = 
      c.high > candles[i-1].high && 
      c.high > candles[i-2].high &&
      c.high > candles[i+1].high &&
      c.high > candles[i+2].high;
    
    if (isLocalHigh) {
      highs.push({
        price: c.high,
        index: i,
        timestamp: c.openTime,
      });
    }
  }
  
  // Group highs at same level
  const grouped: Map<number, typeof highs> = new Map();
  
  for (const h of highs) {
    let foundGroup = false;
    
    for (const [level, group] of grouped) {
      if (Math.abs(h.price - level) / level <= tolerance) {
        group.push(h);
        foundGroup = true;
        break;
      }
    }
    
    if (!foundGroup) {
      grouped.set(h.price, [h]);
    }
  }
  
  // Create zones from groups with enough touches
  for (const [level, group] of grouped) {
    if (group.length >= minTouches) {
      const prices = group.map(g => g.price);
      const avgPrice = prices.reduce((a, b) => a + b, 0) / prices.length;
      
      zones.push({
        type: 'EQUAL_HIGHS',
        price: avgPrice,
        priceRange: {
          low: Math.min(...prices) * (1 - tolerance),
          high: Math.max(...prices) * (1 + tolerance),
        },
        strength: Math.min(1, group.length / 4),
        touches: group.length,
        swept: false,
        candleIndex: group[group.length - 1].index,
        timestamp: group[group.length - 1].timestamp,
      });
    }
  }
  
  return zones;
}

// ═══════════════════════════════════════════════════════════════
// Equal Lows Detection
// ═══════════════════════════════════════════════════════════════

function detectEqualLows(
  candles: Candle[],
  config: LiquidityConfig
): LiquidityZone[] {
  const zones: LiquidityZone[] = [];
  const tolerance = config.equalLevelTolerance;
  const minTouches = config.minEqualTouches;
  
  // Get all local lows
  const lows: { price: number; index: number; timestamp: number }[] = [];
  
  for (let i = 2; i < candles.length - 2; i++) {
    const c = candles[i];
    const isLocalLow = 
      c.low < candles[i-1].low && 
      c.low < candles[i-2].low &&
      c.low < candles[i+1].low &&
      c.low < candles[i+2].low;
    
    if (isLocalLow) {
      lows.push({
        price: c.low,
        index: i,
        timestamp: c.openTime,
      });
    }
  }
  
  // Group lows at same level
  const grouped: Map<number, typeof lows> = new Map();
  
  for (const l of lows) {
    let foundGroup = false;
    
    for (const [level, group] of grouped) {
      if (Math.abs(l.price - level) / level <= tolerance) {
        group.push(l);
        foundGroup = true;
        break;
      }
    }
    
    if (!foundGroup) {
      grouped.set(l.price, [l]);
    }
  }
  
  // Create zones from groups with enough touches
  for (const [level, group] of grouped) {
    if (group.length >= minTouches) {
      const prices = group.map(g => g.price);
      const avgPrice = prices.reduce((a, b) => a + b, 0) / prices.length;
      
      zones.push({
        type: 'EQUAL_LOWS',
        price: avgPrice,
        priceRange: {
          low: Math.min(...prices) * (1 - tolerance),
          high: Math.max(...prices) * (1 + tolerance),
        },
        strength: Math.min(1, group.length / 4),
        touches: group.length,
        swept: false,
        candleIndex: group[group.length - 1].index,
        timestamp: group[group.length - 1].timestamp,
      });
    }
  }
  
  return zones;
}

// ═══════════════════════════════════════════════════════════════
// Swing Points Detection
// ═══════════════════════════════════════════════════════════════

function detectSwingPoints(
  candles: Candle[],
  config: LiquidityConfig
): LiquidityZone[] {
  const zones: LiquidityZone[] = [];
  const lookback = config.swingLookback;
  const strength = config.swingStrengthBars;
  
  const recentCandles = candles.slice(-lookback);
  
  for (let i = strength; i < recentCandles.length - strength; i++) {
    const c = recentCandles[i];
    
    // Check swing high
    let isSwingHigh = true;
    for (let j = 1; j <= strength; j++) {
      if (recentCandles[i - j].high >= c.high || recentCandles[i + j].high >= c.high) {
        isSwingHigh = false;
        break;
      }
    }
    
    if (isSwingHigh) {
      zones.push({
        type: 'SWING_HIGH',
        price: c.high,
        priceRange: {
          low: c.high * 0.998,
          high: c.high * 1.002,
        },
        strength: 0.7,
        touches: 1,
        swept: false,
        candleIndex: candles.length - lookback + i,
        timestamp: c.openTime,
      });
    }
    
    // Check swing low
    let isSwingLow = true;
    for (let j = 1; j <= strength; j++) {
      if (recentCandles[i - j].low <= c.low || recentCandles[i + j].low <= c.low) {
        isSwingLow = false;
        break;
      }
    }
    
    if (isSwingLow) {
      zones.push({
        type: 'SWING_LOW',
        price: c.low,
        priceRange: {
          low: c.low * 0.998,
          high: c.low * 1.002,
        },
        strength: 0.7,
        touches: 1,
        swept: false,
        candleIndex: candles.length - lookback + i,
        timestamp: c.openTime,
      });
    }
  }
  
  return zones;
}

// ═══════════════════════════════════════════════════════════════
// Sweep Detection
// ═══════════════════════════════════════════════════════════════

function detectSweeps(
  candles: Candle[],
  zones: LiquidityZone[],
  config: LiquidityConfig
): SweepEvent[] {
  const sweeps: SweepEvent[] = [];
  const recentBars = config.recentBarsForSweep;
  const recoveryBars = config.sweepRecoveryBars;
  
  const recentCandles = candles.slice(-recentBars);
  
  for (let i = 0; i < recentCandles.length - recoveryBars; i++) {
    const c = recentCandles[i];
    
    // Check for sweep up (wick above resistance, close back below)
    for (const zone of zones) {
      if (zone.type === 'EQUAL_HIGHS' || zone.type === 'SWING_HIGH' || zone.type === 'RANGE_HIGH') {
        // Wick went above zone
        if (c.high > zone.priceRange.high) {
          // But close was below zone
          const closeBelow = c.close < zone.price;
          
          // Check if recovered in next bars
          let recovered = closeBelow;
          if (!recovered) {
            for (let j = 1; j <= recoveryBars && i + j < recentCandles.length; j++) {
              if (recentCandles[i + j].close < zone.price) {
                recovered = true;
                break;
              }
            }
          }
          
          if (recovered) {
            sweeps.push({
              type: 'SWEEP_UP',
              zonePrice: zone.price,
              wickHigh: c.high,
              wickLow: c.low,
              closePrice: c.close,
              candleIndex: candles.length - recentBars + i,
              timestamp: c.openTime,
              magnitude: (c.high - zone.price) / zone.price,
              recovered: true,
            });
            
            // Mark zone as swept
            zone.swept = true;
            zone.sweptAt = c.openTime;
          }
        }
      }
      
      // Check for sweep down (wick below support, close back above)
      if (zone.type === 'EQUAL_LOWS' || zone.type === 'SWING_LOW' || zone.type === 'RANGE_LOW') {
        // Wick went below zone
        if (c.low < zone.priceRange.low) {
          // But close was above zone
          const closeAbove = c.close > zone.price;
          
          // Check if recovered in next bars
          let recovered = closeAbove;
          if (!recovered) {
            for (let j = 1; j <= recoveryBars && i + j < recentCandles.length; j++) {
              if (recentCandles[i + j].close > zone.price) {
                recovered = true;
                break;
              }
            }
          }
          
          if (recovered) {
            sweeps.push({
              type: 'SWEEP_DOWN',
              zonePrice: zone.price,
              wickHigh: c.high,
              wickLow: c.low,
              closePrice: c.close,
              candleIndex: candles.length - recentBars + i,
              timestamp: c.openTime,
              magnitude: (zone.price - c.low) / zone.price,
              recovered: true,
            });
            
            // Mark zone as swept
            zone.swept = true;
            zone.sweptAt = c.openTime;
          }
        }
      }
    }
  }
  
  return sweeps;
}

// ═══════════════════════════════════════════════════════════════
// Range Detection
// ═══════════════════════════════════════════════════════════════

function detectRange(
  candles: Candle[],
  config: LiquidityConfig,
  atr: number
): LiquidityZone[] {
  const zones: LiquidityZone[] = [];
  const lookback = config.rangeLookback;
  const maxWidth = atr * config.rangeAtrMultiplier;
  
  if (candles.length < lookback) return zones;
  
  const recentCandles = candles.slice(-lookback);
  
  const high = Math.max(...recentCandles.map(c => c.high));
  const low = Math.min(...recentCandles.map(c => c.low));
  const width = high - low;
  
  // If range is tight enough, add range boundaries as liquidity zones
  if (width <= maxWidth) {
    zones.push({
      type: 'RANGE_HIGH',
      price: high,
      priceRange: { low: high * 0.998, high: high * 1.002 },
      strength: 0.8,
      touches: recentCandles.filter(c => Math.abs(c.high - high) / high < 0.003).length,
      swept: false,
      candleIndex: candles.length - 1,
      timestamp: recentCandles[recentCandles.length - 1].openTime,
    });
    
    zones.push({
      type: 'RANGE_LOW',
      price: low,
      priceRange: { low: low * 0.998, high: low * 1.002 },
      strength: 0.8,
      touches: recentCandles.filter(c => Math.abs(c.low - low) / low < 0.003).length,
      swept: false,
      candleIndex: candles.length - 1,
      timestamp: recentCandles[recentCandles.length - 1].openTime,
    });
  }
  
  return zones;
}

// ═══════════════════════════════════════════════════════════════
// Main Analysis Function
// ═══════════════════════════════════════════════════════════════

export function analyzeLiquidity(
  candles: Candle[],
  asset: string,
  timeframe: string,
  config: LiquidityConfig = DEFAULT_LIQUIDITY_CONFIG
): LiquidityAnalysis {
  if (candles.length < 50) {
    return {
      asset,
      timeframe,
      timestamp: new Date(),
      zones: [],
      sweeps: [],
      nearestResistance: null,
      nearestSupport: null,
      metrics: {
        zonesAbove: 0,
        zonesBelow: 0,
        recentSweepUp: false,
        recentSweepDown: false,
        liquidityBias: 'NEUTRAL',
        distanceToNearestZoneATR: 0,
      },
    };
  }
  
  const currentPrice = candles[candles.length - 1].close;
  const atr = calculateATR(candles, 14);
  
  // Detect all zone types
  let zones: LiquidityZone[] = [
    ...detectEqualHighs(candles, config),
    ...detectEqualLows(candles, config),
    ...detectSwingPoints(candles, config),
    ...detectRange(candles, config, atr),
  ];
  
  // Detect sweeps
  const sweeps = detectSweeps(candles, zones, config);
  
  // Sort zones by strength and limit
  zones = zones
    .sort((a, b) => b.strength - a.strength)
    .slice(0, config.maxZones);
  
  // Find nearest zones
  const zonesAbove = zones.filter(z => z.price > currentPrice);
  const zonesBelow = zones.filter(z => z.price < currentPrice);
  
  const nearestResistance = zonesAbove.length > 0
    ? zonesAbove.reduce((min, z) => z.price < min.price ? z : min)
    : null;
  
  const nearestSupport = zonesBelow.length > 0
    ? zonesBelow.reduce((max, z) => z.price > max.price ? z : max)
    : null;
  
  // Calculate metrics
  const recentSweeps = sweeps.filter(s => 
    candles.length - s.candleIndex <= config.recentBarsForSweep
  );
  const recentSweepUp = recentSweeps.some(s => s.type === 'SWEEP_UP');
  const recentSweepDown = recentSweeps.some(s => s.type === 'SWEEP_DOWN');
  
  // Liquidity bias
  let liquidityBias: 'BULLISH' | 'BEARISH' | 'NEUTRAL' = 'NEUTRAL';
  if (recentSweepDown && !recentSweepUp) {
    liquidityBias = 'BULLISH';  // Swept lows, likely to go up
  } else if (recentSweepUp && !recentSweepDown) {
    liquidityBias = 'BEARISH';  // Swept highs, likely to go down
  }
  
  // Distance to nearest zone
  const nearestZone = nearestResistance || nearestSupport;
  const distanceToNearestZoneATR = nearestZone && atr > 0
    ? Math.abs(nearestZone.price - currentPrice) / atr
    : 0;
  
  return {
    asset,
    timeframe,
    timestamp: new Date(),
    zones,
    sweeps,
    nearestResistance,
    nearestSupport,
    metrics: {
      zonesAbove: zonesAbove.length,
      zonesBelow: zonesBelow.length,
      recentSweepUp,
      recentSweepDown,
      liquidityBias,
      distanceToNearestZoneATR,
    },
  };
}
