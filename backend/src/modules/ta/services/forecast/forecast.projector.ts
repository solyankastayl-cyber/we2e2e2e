/**
 * Forecast Projector (P4.4.2)
 * 
 * Pattern-aware path projection using measured moves and geometry
 */

import type { ForecastPoint, ForecastComputeInput } from './forecast.types.js';
import { getHorizonBars } from './forecast.types.js';

/**
 * Ease functions
 */
function easeOut(x: number): number {
  return 1 - Math.pow(1 - x, 2);
}

function easeInOut(x: number): number {
  return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
}

/**
 * Pattern projector registry
 */
interface PatternProjector {
  buildPath: (input: ForecastComputeInput) => ForecastPoint[];
}

/**
 * Triangle projector (ASC, DESC, SYM)
 * Pattern: compression → breakout → impulse → retest → continuation
 */
function triangleProjector(input: ForecastComputeInput): ForecastPoint[] {
  const horizonBars = getHorizonBars(input.timeframe);
  const path: ForecastPoint[] = [];
  
  const start = input.priceNow;
  const breakout = input.breakoutLevel || start * 1.02;
  const measuredMove = input.measuredMove || (breakout - start) * 2;
  const target = breakout + measuredMove;
  
  // Segment timings
  const compressionEnd = Math.floor(horizonBars * 0.15);
  const breakoutBar = Math.floor(horizonBars * 0.25);
  const impulseEnd = Math.floor(horizonBars * 0.45);
  const retestEnd = Math.floor(horizonBars * 0.6);
  
  for (let i = 0; i <= horizonBars; i++) {
    let price: number;
    
    if (i <= compressionEnd) {
      // Compression phase (slight consolidation)
      const progress = i / compressionEnd;
      const midpoint = (start + breakout) / 2;
      price = start + (midpoint - start) * easeInOut(progress) * 0.5;
    } else if (i <= breakoutBar) {
      // Move to breakout
      const progress = (i - compressionEnd) / (breakoutBar - compressionEnd);
      const midpoint = (start + breakout) / 2;
      price = midpoint + (breakout - midpoint) * easeOut(progress);
    } else if (i <= impulseEnd) {
      // Impulse move
      const progress = (i - breakoutBar) / (impulseEnd - breakoutBar);
      const impulseTarget = breakout + measuredMove * 0.7;
      price = breakout + (impulseTarget - breakout) * easeOut(progress);
    } else if (i <= retestEnd) {
      // Retest (pull back to breakout zone)
      const progress = (i - impulseEnd) / (retestEnd - impulseEnd);
      const impulseHigh = breakout + measuredMove * 0.7;
      const retestLevel = breakout * 1.01;
      price = impulseHigh + (retestLevel - impulseHigh) * easeInOut(progress);
    } else {
      // Continuation to target
      const progress = (i - retestEnd) / (horizonBars - retestEnd);
      const retestLevel = breakout * 1.01;
      price = retestLevel + (target - retestLevel) * easeOut(progress);
    }
    
    path.push({
      t: i,
      price: Math.round(price * 100) / 100
    });
  }
  
  return path;
}

/**
 * Flag projector
 * Pattern: impulse → consolidation → continuation
 */
function flagProjector(input: ForecastComputeInput): ForecastPoint[] {
  const horizonBars = getHorizonBars(input.timeframe);
  const path: ForecastPoint[] = [];
  
  const start = input.priceNow;
  const flagpole = input.measuredMove || start * 0.05;
  const target = start + flagpole;
  
  // Segment timings
  const impulseEnd = Math.floor(horizonBars * 0.3);
  const consolidationEnd = Math.floor(horizonBars * 0.6);
  
  for (let i = 0; i <= horizonBars; i++) {
    let price: number;
    
    if (i <= impulseEnd) {
      // Impulse (flagpole replication)
      const progress = i / impulseEnd;
      price = start + flagpole * 0.6 * easeOut(progress);
    } else if (i <= consolidationEnd) {
      // Consolidation (flag pattern - slight pullback)
      const progress = (i - impulseEnd) / (consolidationEnd - impulseEnd);
      const impulseHigh = start + flagpole * 0.6;
      const pullback = impulseHigh * 0.97;
      price = impulseHigh + (pullback - impulseHigh) * Math.sin(progress * Math.PI);
    } else {
      // Continuation
      const progress = (i - consolidationEnd) / (horizonBars - consolidationEnd);
      const pullback = (start + flagpole * 0.6) * 0.97;
      price = pullback + (target - pullback) * easeOut(progress);
    }
    
    path.push({
      t: i,
      price: Math.round(price * 100) / 100
    });
  }
  
  return path;
}

/**
 * Channel projector
 * Pattern: oscillation within bounds
 */
function channelProjector(input: ForecastComputeInput): ForecastPoint[] {
  const horizonBars = getHorizonBars(input.timeframe);
  const path: ForecastPoint[] = [];
  
  const start = input.priceNow;
  const channelWidth = input.measuredMove || start * 0.04;
  const upper = start + channelWidth / 2;
  const lower = start - channelWidth / 2;
  const trend = input.bias === 'LONG' ? 0.001 : input.bias === 'SHORT' ? -0.001 : 0;
  
  for (let i = 0; i <= horizonBars; i++) {
    // Oscillation within channel
    const oscillation = Math.sin(i * Math.PI / 8) * channelWidth / 2;
    // Trend drift
    const drift = trend * start * i;
    
    const price = start + oscillation + drift;
    
    path.push({
      t: i,
      price: Math.round(Math.max(lower, Math.min(upper + drift, price)) * 100) / 100
    });
  }
  
  return path;
}

/**
 * Head & Shoulders projector
 * Pattern: peak → neckline → target (measured move)
 */
function headShouldersProjector(input: ForecastComputeInput): ForecastPoint[] {
  const horizonBars = getHorizonBars(input.timeframe);
  const path: ForecastPoint[] = [];
  
  const start = input.priceNow;
  const neckline = input.breakoutLevel || start * 0.98;
  const headHeight = start - neckline;
  const target = neckline - headHeight; // Measured move
  
  // Segment timings
  const rightShoulderEnd = Math.floor(horizonBars * 0.2);
  const breakdownBar = Math.floor(horizonBars * 0.35);
  const retestEnd = Math.floor(horizonBars * 0.5);
  
  for (let i = 0; i <= horizonBars; i++) {
    let price: number;
    
    if (i <= rightShoulderEnd) {
      // Right shoulder formation
      const progress = i / rightShoulderEnd;
      price = start + (neckline - start) * 0.3 * easeInOut(progress);
    } else if (i <= breakdownBar) {
      // Break neckline
      const progress = (i - rightShoulderEnd) / (breakdownBar - rightShoulderEnd);
      const shoulder = start + (neckline - start) * 0.3;
      price = shoulder + (neckline - shoulder) * easeOut(progress);
    } else if (i <= retestEnd) {
      // Retest neckline
      const progress = (i - breakdownBar) / (retestEnd - breakdownBar);
      price = neckline + (neckline * 1.01 - neckline) * Math.sin(progress * Math.PI);
    } else {
      // Move to target
      const progress = (i - retestEnd) / (horizonBars - retestEnd);
      price = neckline + (target - neckline) * easeOut(progress);
    }
    
    path.push({
      t: i,
      price: Math.round(price * 100) / 100
    });
  }
  
  return path;
}

/**
 * Get projector for pattern type
 */
const PROJECTORS: Record<string, PatternProjector['buildPath']> = {
  'TRIANGLE_ASC': triangleProjector,
  'TRIANGLE_DESC': triangleProjector,
  'TRIANGLE_SYM': triangleProjector,
  'ASC_TRIANGLE': triangleProjector,
  'DESC_TRIANGLE': triangleProjector,
  
  'FLAG_BULL': flagProjector,
  'FLAG_BEAR': flagProjector,
  'FLAG': flagProjector,
  'PENNANT': flagProjector,
  
  'CHANNEL_UP': channelProjector,
  'CHANNEL_DOWN': channelProjector,
  'CHANNEL_HORIZ': channelProjector,
  'CHANNEL': channelProjector,
  
  'HS_TOP': headShouldersProjector,
  'HS_BOTTOM': headShouldersProjector,
  'IHS': headShouldersProjector,
  'HEAD_SHOULDERS': headShouldersProjector,
};

/**
 * Build projection-aware path
 */
export function buildProjectionPath(input: ForecastComputeInput): {
  path: ForecastPoint[];
  method: 'PATTERN_PROJECTOR' | 'FALLBACK';
  patternType?: string;
} {
  // Try to find matching projector
  if (input.patternType) {
    const upperType = input.patternType.toUpperCase();
    
    for (const [key, projector] of Object.entries(PROJECTORS)) {
      if (upperType.includes(key) || key.includes(upperType)) {
        return {
          path: projector(input),
          method: 'PATTERN_PROJECTOR',
          patternType: input.patternType
        };
      }
    }
  }
  
  // Fallback to simple path (inline implementation)
  const path = buildFallbackPath(input);
  return {
    path,
    method: 'FALLBACK'
  };
}

/**
 * Fallback path builder (simple ease-out to target)
 */
function buildFallbackPath(input: ForecastComputeInput): ForecastPoint[] {
  const horizonBars = HORIZON_BARS[input.timeframe.toLowerCase()] || 30;
  const path: ForecastPoint[] = [];
  
  const start = input.priceNow;
  let end = start;
  
  if (input.bias === 'LONG' && input.target) {
    end = input.target;
  } else if (input.bias === 'SHORT' && input.target) {
    end = input.target;
  } else if (input.scenarioBands) {
    end = start * (1 + input.scenarioBands.p50 * 0.02);
  }
  
  for (let i = 0; i <= horizonBars; i++) {
    const progress = i / horizonBars;
    const eased = 1 - Math.pow(1 - progress, 2);
    const price = start + (end - start) * eased;
    
    path.push({
      t: i,
      price: Math.round(price * 100) / 100
    });
  }
  
  return path;
}

// Horizon bars constant
const HORIZON_BARS: Record<string, number> = {
  '1m': 60, '5m': 60, '15m': 56, '30m': 48,
  '1h': 48, '4h': 42, '1d': 30, '1w': 26, '1M': 18
};
