/**
 * Forecast Path Builder (P4.4)
 * 
 * Builds expected price path
 */

import type { ForecastPoint, ForecastComputeInput } from './forecast.types.js';
import { getHorizonBars } from './forecast.types.js';

/**
 * Ease-out function: s = 1 - (1-x)^2
 */
function easeOut(x: number): number {
  return 1 - Math.pow(1 - x, 2);
}

/**
 * Ease-in-out function
 */
function easeInOut(x: number): number {
  return x < 0.5 
    ? 2 * x * x 
    : 1 - Math.pow(-2 * x + 2, 2) / 2;
}

/**
 * Build simple path from start to target
 */
export function buildSimplePath(input: ForecastComputeInput): ForecastPoint[] {
  const horizonBars = getHorizonBars(input.timeframe);
  const path: ForecastPoint[] = [];
  
  const start = input.priceNow;
  let end = start;
  
  // Determine end price based on bias
  if (input.bias === 'LONG' && input.target) {
    end = input.target;
  } else if (input.bias === 'SHORT' && input.target) {
    end = input.target;
  } else if (input.scenarioBands) {
    end = start * (1 + input.scenarioBands.p50 * 0.02); // Convert R to price
  }
  
  // Generate path with easing
  for (let i = 0; i <= horizonBars; i++) {
    const progress = i / horizonBars;
    const eased = easeOut(progress);
    const price = start + (end - start) * eased;
    
    path.push({
      t: i, // Bar offset
      price: Math.round(price * 100) / 100
    });
  }
  
  return path;
}

/**
 * Build path with retest pattern
 */
export function buildRetestPath(input: ForecastComputeInput): ForecastPoint[] {
  const horizonBars = getHorizonBars(input.timeframe);
  const path: ForecastPoint[] = [];
  
  const start = input.priceNow;
  const breakout = input.breakoutLevel || start * 1.02;
  const target = input.target || breakout * 1.05;
  
  // Segment timings
  const breakoutBar = Math.floor(horizonBars * 0.2);
  const retestBar = Math.floor(horizonBars * 0.4);
  const continuationBar = horizonBars;
  
  for (let i = 0; i <= horizonBars; i++) {
    let price: number;
    
    if (i <= breakoutBar) {
      // Move to breakout
      const progress = i / breakoutBar;
      price = start + (breakout - start) * easeOut(progress);
    } else if (i <= retestBar) {
      // Retest (pull back)
      const progress = (i - breakoutBar) / (retestBar - breakoutBar);
      const retestLevel = start + (breakout - start) * 0.5; // 50% retest
      price = breakout + (retestLevel - breakout) * easeInOut(progress);
    } else {
      // Continuation to target
      const progress = (i - retestBar) / (continuationBar - retestBar);
      const retestLevel = start + (breakout - start) * 0.5;
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
 * Build flat/range path for WAIT bias
 */
export function buildFlatPath(input: ForecastComputeInput): ForecastPoint[] {
  const horizonBars = getHorizonBars(input.timeframe);
  const path: ForecastPoint[] = [];
  
  const start = input.priceNow;
  const volatility = input.atrPct || 0.02;
  
  // Small random walk with mean reversion
  let price = start;
  const seed = Math.sin(start) * 10000;
  
  for (let i = 0; i <= horizonBars; i++) {
    // Deterministic "random" using seed
    const noise = Math.sin(seed + i * 0.5) * volatility * start * 0.5;
    price = start + noise;
    
    path.push({
      t: i,
      price: Math.round(price * 100) / 100
    });
  }
  
  return path;
}

/**
 * Build path based on input
 */
export function buildPath(input: ForecastComputeInput): ForecastPoint[] {
  // If WAIT bias, use flat path
  if (input.bias === 'WAIT' || (!input.target && !input.scenarioBands)) {
    return buildFlatPath(input);
  }
  
  // If we have breakout level, use retest pattern
  if (input.breakoutLevel) {
    return buildRetestPath(input);
  }
  
  // Default: simple eased path
  return buildSimplePath(input);
}
