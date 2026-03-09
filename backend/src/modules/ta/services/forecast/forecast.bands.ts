/**
 * Forecast Bands Builder (P4.4)
 * 
 * Builds probability bands around expected path
 */

import type { ForecastBandsPoint, ForecastPoint, ForecastComputeInput } from './forecast.types.js';

/**
 * Build bands from scenario percentiles
 */
export function buildBandsFromScenario(
  path: ForecastPoint[],
  scenarioBands: { p10: number; p50: number; p90: number },
  priceNow: number
): ForecastBandsPoint[] {
  const bands: ForecastBandsPoint[] = [];
  const horizonBars = path.length - 1;
  
  // Convert R to price delta
  const rToPrice = (r: number, step: number) => {
    const progress = step / horizonBars;
    return priceNow * (1 + r * 0.02 * progress);
  };
  
  for (let i = 0; i <= horizonBars; i++) {
    const p50 = path[i].price;
    
    // Scale bands with time
    const progress = i / horizonBars;
    const p10Delta = (scenarioBands.p10 - scenarioBands.p50) * 0.02 * priceNow * progress;
    const p90Delta = (scenarioBands.p90 - scenarioBands.p50) * 0.02 * priceNow * progress;
    
    bands.push({
      t: i,
      p10: Math.round((p50 + p10Delta) * 100) / 100,
      p50: Math.round(p50 * 100) / 100,
      p90: Math.round((p50 + p90Delta) * 100) / 100
    });
  }
  
  return bands;
}

/**
 * Build bands using ATR (fallback)
 */
export function buildBandsFromATR(
  path: ForecastPoint[],
  atrPct: number,
  priceNow: number
): ForecastBandsPoint[] {
  const bands: ForecastBandsPoint[] = [];
  const horizonBars = path.length - 1;
  
  // k = 1.28 for ~80% interval (1 std dev approximation)
  const k = 1.28;
  
  for (let i = 0; i <= horizonBars; i++) {
    const p50 = path[i].price;
    
    // Volatility scales with sqrt(time)
    const timeFactor = Math.sqrt((i + 1) / horizonBars);
    const sigma = atrPct * priceNow * timeFactor;
    
    bands.push({
      t: i,
      p10: Math.max(p50 * 0.5, p50 - k * sigma), // Floor at 50% of price
      p50: p50,
      p90: p50 + k * sigma
    });
  }
  
  return bands;
}

/**
 * Build bands based on available data
 */
export function buildBands(
  path: ForecastPoint[],
  input: ForecastComputeInput
): ForecastBandsPoint[] {
  // Use scenario bands if available
  if (input.scenarioBands) {
    return buildBandsFromScenario(path, input.scenarioBands, input.priceNow);
  }
  
  // Fallback to ATR-based bands
  const atrPct = input.atrPct || 0.02; // Default 2%
  return buildBandsFromATR(path, atrPct, input.priceNow);
}

/**
 * Apply stability damping to bands
 */
export function applyStabilityDamping(
  bands: ForecastBandsPoint[],
  stabilityMultiplier: number
): ForecastBandsPoint[] {
  if (stabilityMultiplier >= 1.0) {
    return bands; // No damping needed
  }
  
  // Reduce band width when stability is degrading
  const dampingFactor = stabilityMultiplier;
  
  return bands.map(b => ({
    t: b.t,
    p10: b.p50 - (b.p50 - b.p10) * dampingFactor,
    p50: b.p50,
    p90: b.p50 + (b.p90 - b.p50) * dampingFactor
  }));
}
