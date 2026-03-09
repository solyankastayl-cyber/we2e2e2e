/**
 * MetaBrain v2.1 — Module Weights Engine
 * 
 * Computes and manages adaptive weights for analysis modules
 */

import {
  AnalysisModule,
  ALL_MODULES,
  ModuleWeight,
  ModuleContribution,
  ModuleWeightHistory,
  LearningConfig,
  DEFAULT_LEARNING_CONFIG
} from './module_attribution.types.js';

// ═══════════════════════════════════════════════════════════════
// WEIGHT CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate raw weight from edge score
 * edgeScore 1.5 -> weight 1.0 (neutral)
 * edgeScore 3.0 -> weight 1.6 (max)
 * edgeScore 0.0 -> weight 0.4 (min)
 */
export function calculateRawWeight(edgeScore: number): number {
  // Map 0-3 edge score to weight
  // 1.5 is neutral (weight 1.0)
  const deviation = edgeScore - 1.5;
  
  // Scale factor: 1.5 deviation -> 0.6 weight change
  const weightChange = deviation * 0.4;
  
  return 1.0 + weightChange;
}

/**
 * Apply shrinkage toward 1.0 based on confidence
 */
export function applyShrinkage(
  rawWeight: number,
  confidence: number,
  shrinkageStrength: number = 0.5
): number {
  // Shrink toward 1.0 based on confidence and shrinkage strength
  const effectiveShrinkage = shrinkageStrength * (1 - confidence);
  return 1.0 + (rawWeight - 1.0) * (1 - effectiveShrinkage);
}

/**
 * Clamp weight to allowed bounds
 */
export function clampWeight(
  weight: number,
  config: LearningConfig = DEFAULT_LEARNING_CONFIG
): number {
  return Math.max(config.minWeight, Math.min(config.maxWeight, weight));
}

/**
 * Apply rate limiting to weight change
 */
export function applyRateLimit(
  newWeight: number,
  previousWeight: number | undefined,
  maxDailyChange: number = 0.05
): { weight: number; rateLimited: boolean } {
  if (previousWeight === undefined) {
    return { weight: newWeight, rateLimited: false };
  }
  
  const change = newWeight - previousWeight;
  
  if (Math.abs(change) > maxDailyChange) {
    const limitedWeight = previousWeight + Math.sign(change) * maxDailyChange;
    return { weight: limitedWeight, rateLimited: true };
  }
  
  return { weight: newWeight, rateLimited: false };
}

// ═══════════════════════════════════════════════════════════════
// MAIN WEIGHT COMPUTATION
// ═══════════════════════════════════════════════════════════════

/**
 * Compute weights for all modules from contributions
 */
export function computeModuleWeights(
  contributions: ModuleContribution[],
  previousWeights: Map<AnalysisModule, number>,
  config: LearningConfig = DEFAULT_LEARNING_CONFIG,
  regime?: string
): ModuleWeight[] {
  const weights: ModuleWeight[] = [];
  
  for (const contribution of contributions) {
    // Calculate raw weight
    const rawWeight = calculateRawWeight(contribution.edgeScore);
    
    // Apply shrinkage
    const shrunkWeight = applyShrinkage(rawWeight, contribution.confidence, config.shrinkageStrength);
    
    // Clamp to bounds
    const clampedWeight = clampWeight(shrunkWeight, config);
    
    // Apply rate limiting
    const previousWeight = previousWeights.get(contribution.module);
    const { weight: finalWeight, rateLimited } = applyRateLimit(
      clampedWeight,
      previousWeight,
      config.maxDailyChange
    );
    
    weights.push({
      module: contribution.module,
      weight: Math.round(finalWeight * 100) / 100,
      rawWeight: Math.round(rawWeight * 100) / 100,
      confidence: contribution.confidence,
      basedOnSample: contribution.sampleSize,
      basedOnEdgeScore: contribution.edgeScore,
      regime,
      updatedAt: new Date()
    });
  }
  
  return weights;
}

/**
 * Get default weights (all neutral)
 */
export function getDefaultWeights(): ModuleWeight[] {
  return ALL_MODULES.map(module => ({
    module,
    weight: 1.0,
    rawWeight: 1.0,
    confidence: 0,
    basedOnSample: 0,
    basedOnEdgeScore: 1.5,
    updatedAt: new Date()
  }));
}

// ═══════════════════════════════════════════════════════════════
// WEIGHT APPLICATION
// ═══════════════════════════════════════════════════════════════

/**
 * Apply weights to a score calculation
 */
export function applyModuleWeights(
  scores: Map<AnalysisModule, number>,
  weights: Map<AnalysisModule, number>
): number {
  let weightedSum = 0;
  let totalWeight = 0;
  
  for (const [module, score] of scores) {
    const weight = weights.get(module) ?? 1.0;
    weightedSum += score * weight;
    totalWeight += weight;
  }
  
  return totalWeight > 0 ? weightedSum / totalWeight : 0;
}

/**
 * Get weight multiplier for a specific module
 */
export function getModuleMultiplier(
  module: AnalysisModule,
  weights: ModuleWeight[]
): number {
  const found = weights.find(w => w.module === module);
  return found?.weight ?? 1.0;
}

// ═══════════════════════════════════════════════════════════════
// WEIGHT HISTORY
// ═══════════════════════════════════════════════════════════════

/**
 * Create weight history entry
 */
export function createWeightHistoryEntry(
  module: AnalysisModule,
  oldWeight: number | undefined,
  newWeight: number,
  regime?: string
): ModuleWeightHistory {
  let reason = 'Initial weight';
  
  if (oldWeight !== undefined) {
    const change = newWeight - oldWeight;
    if (change > 0) {
      reason = `Increased by ${(change * 100).toFixed(1)}% due to positive edge`;
    } else if (change < 0) {
      reason = `Decreased by ${(Math.abs(change) * 100).toFixed(1)}% due to negative edge`;
    } else {
      reason = 'No change';
    }
  }
  
  return {
    module,
    weight: newWeight,
    regime,
    reason,
    changedAt: new Date()
  };
}

// ═══════════════════════════════════════════════════════════════
// WEIGHT NORMALIZATION
// ═══════════════════════════════════════════════════════════════

/**
 * Normalize weights so they average to 1.0
 */
export function normalizeWeights(weights: ModuleWeight[]): ModuleWeight[] {
  const avgWeight = weights.reduce((sum, w) => sum + w.weight, 0) / weights.length;
  
  if (avgWeight === 0) return weights;
  
  return weights.map(w => ({
    ...w,
    weight: Math.round((w.weight / avgWeight) * 100) / 100
  }));
}

/**
 * Get weight summary statistics
 */
export function getWeightSummary(weights: ModuleWeight[]): {
  min: number;
  max: number;
  avg: number;
  spread: number;
  topModule: AnalysisModule | null;
  weakestModule: AnalysisModule | null;
} {
  if (weights.length === 0) {
    return { min: 1, max: 1, avg: 1, spread: 0, topModule: null, weakestModule: null };
  }
  
  const sorted = [...weights].sort((a, b) => b.weight - a.weight);
  const min = Math.min(...weights.map(w => w.weight));
  const max = Math.max(...weights.map(w => w.weight));
  const avg = weights.reduce((sum, w) => sum + w.weight, 0) / weights.length;
  
  return {
    min,
    max,
    avg: Math.round(avg * 100) / 100,
    spread: Math.round((max - min) * 100) / 100,
    topModule: sorted[0]?.module ?? null,
    weakestModule: sorted[sorted.length - 1]?.module ?? null
  };
}
