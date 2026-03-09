/**
 * Forecast Blend (P4.4)
 * 
 * Blending projector path with scenario bands
 */

import type { ForecastPoint, ForecastSources, ForecastComputeInput } from './forecast.types.js';

/**
 * Calculate source weights based on input quality
 */
export function calculateSourceWeights(input: ForecastComputeInput): ForecastSources {
  let projectorWeight = 0.4;
  let scenarioWeight = 0.35;
  let stabilityWeight = 0.15;
  let mlWeight = 0.1;
  
  // Adjust based on available data
  if (!input.patternType) {
    projectorWeight = 0.2;
    scenarioWeight += 0.2;
  }
  
  if (!input.scenarioBands) {
    scenarioWeight = 0.2;
    projectorWeight += 0.15;
  }
  
  if (input.stabilityMultiplier && input.stabilityMultiplier < 0.8) {
    // Stability degrading - reduce its weight
    stabilityWeight = 0.05;
    mlWeight += 0.1;
  }
  
  // Normalize
  const total = projectorWeight + scenarioWeight + stabilityWeight + mlWeight;
  
  return {
    projectorWeight: projectorWeight / total,
    scenarioWeight: scenarioWeight / total,
    stabilityWeight: stabilityWeight / total,
    mlWeight: mlWeight / total
  };
}

/**
 * Blend projector path with scenario path
 */
export function blendPaths(
  projectorPath: ForecastPoint[],
  scenarioPath: ForecastPoint[] | null,
  weights: ForecastSources
): ForecastPoint[] {
  if (!scenarioPath || scenarioPath.length === 0) {
    return projectorPath;
  }
  
  const blended: ForecastPoint[] = [];
  const len = Math.min(projectorPath.length, scenarioPath.length);
  
  for (let i = 0; i < len; i++) {
    const projPrice = projectorPath[i].price;
    const scenPrice = scenarioPath[i].price;
    
    // Weighted blend
    const blendedPrice = 
      projPrice * weights.projectorWeight + 
      scenPrice * weights.scenarioWeight + 
      ((projPrice + scenPrice) / 2) * (weights.mlWeight + weights.stabilityWeight);
    
    blended.push({
      t: projectorPath[i].t,
      price: Math.round(blendedPrice * 100) / 100
    });
  }
  
  // Add remaining points from longer path
  if (projectorPath.length > len) {
    blended.push(...projectorPath.slice(len));
  }
  
  return blended;
}

/**
 * Apply stability damping to path
 */
export function applyStabilityToPath(
  path: ForecastPoint[],
  stabilityMultiplier: number,
  priceNow: number
): ForecastPoint[] {
  if (stabilityMultiplier >= 1.0) {
    return path;
  }
  
  // Dampen price movements when stability is low
  return path.map(p => ({
    t: p.t,
    price: Math.round((priceNow + (p.price - priceNow) * stabilityMultiplier) * 100) / 100
  }));
}
