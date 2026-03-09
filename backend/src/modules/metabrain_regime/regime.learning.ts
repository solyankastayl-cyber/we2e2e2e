/**
 * P1.4 — MetaBrain v2.3 Regime-conditioned Learning Engine
 * 
 * Computes module weights per market regime
 */

import { AnalysisModule, ALL_MODULES } from '../metabrain_learning/module_attribution.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import {
  RegimeModuleWeight,
  RegimeWeightMap,
  RegimeLearningRules,
  DEFAULT_REGIME_LEARNING_RULES,
  ALL_REGIMES
} from './regime.learning.types.js';

// ═══════════════════════════════════════════════════════════════
// WEIGHT CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate confidence based on sample size
 */
export function calculateRegimeConfidence(
  sampleSize: number,
  rules: RegimeLearningRules = DEFAULT_REGIME_LEARNING_RULES
): number {
  if (sampleSize < rules.minSampleForWeight) return 0;
  
  const confidence = Math.min(sampleSize / rules.fullConfidenceSample, 1);
  return Math.round(confidence * 1000) / 1000;
}

/**
 * Calculate regime-specific weight for a module
 * 
 * Formula: weight = 1 + (avgOutcomeImpact × confidence)
 * Clamped to [minWeight, maxWeight]
 */
export function calculateRegimeWeight(
  avgOutcomeImpact: number,
  sampleSize: number,
  rules: RegimeLearningRules = DEFAULT_REGIME_LEARNING_RULES
): { weight: number; confidence: number } {
  const confidence = calculateRegimeConfidence(sampleSize, rules);
  
  if (confidence === 0) {
    return { weight: 1.0, confidence: 0 };
  }
  
  // Weight = 1 + (impact × confidence)
  const rawWeight = 1 + (avgOutcomeImpact * confidence);
  
  // Clamp
  const weight = Math.max(
    rules.minWeight,
    Math.min(rules.maxWeight, rawWeight)
  );
  
  return {
    weight: Math.round(weight * 1000) / 1000,
    confidence
  };
}

/**
 * Compute regime weight from attribution data
 */
export function computeRegimeModuleWeight(
  module: AnalysisModule,
  regime: MarketRegime,
  avgOutcomeImpact: number,
  sampleSize: number,
  rules: RegimeLearningRules = DEFAULT_REGIME_LEARNING_RULES
): RegimeModuleWeight {
  const { weight, confidence } = calculateRegimeWeight(avgOutcomeImpact, sampleSize, rules);
  const now = Date.now();
  
  return {
    module,
    regime,
    weight,
    sampleSize,
    avgOutcomeImpact,
    confidence,
    updatedAt: now,
    createdAt: now
  };
}

// ═══════════════════════════════════════════════════════════════
// WEIGHT MAP CONSTRUCTION
// ═══════════════════════════════════════════════════════════════

/**
 * Build regime weight map from individual weights
 */
export function buildRegimeWeightMap(
  regime: MarketRegime,
  weights: RegimeModuleWeight[]
): RegimeWeightMap {
  const weightRecord: Record<AnalysisModule, number> = {} as Record<AnalysisModule, number>;
  
  // Initialize with defaults
  for (const module of ALL_MODULES) {
    weightRecord[module] = 1.0;
  }
  
  // Apply regime-specific weights
  let totalConfidence = 0;
  let totalSamples = 0;
  let count = 0;
  
  for (const w of weights) {
    if (w.regime === regime) {
      weightRecord[w.module] = w.weight;
      totalConfidence += w.confidence;
      totalSamples += w.sampleSize;
      count++;
    }
  }
  
  return {
    regime,
    weights: weightRecord,
    avgConfidence: count > 0 ? Math.round((totalConfidence / count) * 1000) / 1000 : 0,
    totalSamples
  };
}

/**
 * Build all regime weight maps
 */
export function buildAllRegimeWeightMaps(
  weights: RegimeModuleWeight[]
): RegimeWeightMap[] {
  return ALL_REGIMES.map(regime => buildRegimeWeightMap(regime, weights));
}

// ═══════════════════════════════════════════════════════════════
// WEIGHT APPLICATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get regime weight for a module
 */
export function getRegimeWeight(
  module: AnalysisModule,
  regime: MarketRegime,
  weights: RegimeModuleWeight[]
): number {
  const found = weights.find(w => w.module === module && w.regime === regime);
  return found?.weight ?? 1.0;
}

/**
 * Get regime weight map for current regime
 */
export function getRegimeWeightRecord(
  regime: MarketRegime,
  weights: RegimeModuleWeight[]
): Record<AnalysisModule, number> {
  const map = buildRegimeWeightMap(regime, weights);
  return map.weights;
}

/**
 * Apply regime weight to boost
 * 
 * finalBoost = boost × moduleWeight × regimeWeight
 */
export function applyRegimeWeight(
  boost: number,
  moduleWeight: number,
  regimeWeight: number
): number {
  const result = boost * moduleWeight * regimeWeight;
  return Math.round(result * 1000) / 1000;
}

// ═══════════════════════════════════════════════════════════════
// DECAY & MAINTENANCE
// ═══════════════════════════════════════════════════════════════

/**
 * Apply time decay to weight
 * Weights decay toward 1.0 over time
 */
export function applyWeightDecay(
  weight: number,
  daysSinceUpdate: number,
  rules: RegimeLearningRules = DEFAULT_REGIME_LEARNING_RULES
): number {
  if (daysSinceUpdate < rules.decayPeriodDays) return weight;
  
  const decayPeriods = Math.floor(daysSinceUpdate / rules.decayPeriodDays);
  const decayMultiplier = Math.pow(rules.decayFactor, decayPeriods);
  
  // Decay toward 1.0
  const deviation = weight - 1.0;
  const decayedDeviation = deviation * decayMultiplier;
  
  return Math.round((1.0 + decayedDeviation) * 1000) / 1000;
}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════

/**
 * Get default regime weights (all 1.0)
 */
export function getDefaultRegimeWeights(regime: MarketRegime): RegimeModuleWeight[] {
  const now = Date.now();
  
  return ALL_MODULES.map(module => ({
    module,
    regime,
    weight: 1.0,
    sampleSize: 0,
    avgOutcomeImpact: 0,
    confidence: 0,
    updatedAt: now,
    createdAt: now
  }));
}

/**
 * Get default regime weight map
 */
export function getDefaultRegimeWeightMap(regime: MarketRegime): RegimeWeightMap {
  const weights: Record<AnalysisModule, number> = {} as Record<AnalysisModule, number>;
  
  for (const module of ALL_MODULES) {
    weights[module] = 1.0;
  }
  
  return {
    regime,
    weights,
    avgConfidence: 0,
    totalSamples: 0
  };
}

/**
 * Compare regime weights across regimes
 */
export function compareRegimeWeights(
  module: AnalysisModule,
  weights: RegimeModuleWeight[]
): Record<MarketRegime, number> {
  const result: Record<MarketRegime, number> = {} as Record<MarketRegime, number>;
  
  for (const regime of ALL_REGIMES) {
    result[regime] = getRegimeWeight(module, regime, weights);
  }
  
  return result;
}
