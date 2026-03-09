/**
 * P1.4 — MetaBrain v2.3 Regime-conditioned Learning Types
 * 
 * Stores and applies module weights per market regime
 */

import { AnalysisModule } from '../metabrain_learning/module_attribution.types.js';
import { MarketRegime } from '../regime/regime.types.js';

// ═══════════════════════════════════════════════════════════════
// REGIME WEIGHT TYPES
// ═══════════════════════════════════════════════════════════════

export interface RegimeModuleWeight {
  module: AnalysisModule;
  regime: MarketRegime;
  
  weight: number;
  sampleSize: number;
  avgOutcomeImpact: number;
  confidence: number;
  
  updatedAt: number;
  createdAt: number;
}

export interface RegimeWeightMap {
  regime: MarketRegime;
  weights: Record<AnalysisModule, number>;
  avgConfidence: number;
  totalSamples: number;
}

// ═══════════════════════════════════════════════════════════════
// REGIME LEARNING RULES
// ═══════════════════════════════════════════════════════════════

export interface RegimeLearningRules {
  // Sample requirements
  minSampleForWeight: number;
  fullConfidenceSample: number;
  
  // Weight bounds
  minWeight: number;
  maxWeight: number;
  
  // Decay settings
  decayFactor: number;
  decayPeriodDays: number;
}

export const DEFAULT_REGIME_LEARNING_RULES: RegimeLearningRules = {
  // Minimum 50 samples to start learning
  minSampleForWeight: 50,
  // Full confidence at 300 samples
  fullConfidenceSample: 300,
  
  // Weight clamp
  minWeight: 0.75,
  maxWeight: 1.25,
  
  // Decay over time
  decayFactor: 0.95,
  decayPeriodDays: 30
};

// ═══════════════════════════════════════════════════════════════
// ALL REGIMES
// ═══════════════════════════════════════════════════════════════

export const ALL_REGIMES: MarketRegime[] = [
  'COMPRESSION',
  'BREAKOUT_PREP',
  'TREND_EXPANSION',
  'RANGE_ROTATION',
  'TREND_CONTINUATION',
  'VOLATILITY_EXPANSION',
  'LIQUIDITY_HUNT',
  'ACCUMULATION',
  'DISTRIBUTION'
];

// ═══════════════════════════════════════════════════════════════
// API TYPES
// ═══════════════════════════════════════════════════════════════

export interface RegimeWeightsResponse {
  success: boolean;
  data?: {
    regime: MarketRegime;
    weights: RegimeModuleWeight[];
    summary: {
      avgConfidence: number;
      totalSamples: number;
      modulesWithData: number;
    };
  };
  error?: string;
}

export interface RegimeWeightsRebuildResponse {
  success: boolean;
  data?: {
    regimesProcessed: number;
    weightsUpdated: number;
    rebuiltAt: Date;
  };
  error?: string;
}

export interface AllRegimeWeightsResponse {
  success: boolean;
  data?: {
    regimes: RegimeWeightMap[];
    totalRegimes: number;
  };
  error?: string;
}
