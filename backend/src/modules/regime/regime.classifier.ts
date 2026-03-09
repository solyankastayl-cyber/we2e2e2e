/**
 * Phase 9 — Regime Classifier
 * 
 * Classifies market regime from features
 */

import {
  MarketRegime,
  RegimeFeatures,
  RegimeDetectionResult,
  RegimeConfig,
  DEFAULT_REGIME_CONFIG,
  REGIME_PATTERN_BOOSTS
} from './regime.types.js';

// ═══════════════════════════════════════════════════════════════
// CLASSIFICATION RULES
// ═══════════════════════════════════════════════════════════════

interface RegimeRule {
  regime: MarketRegime;
  conditions: (features: RegimeFeatures) => number;  // Returns score 0-1
}

const REGIME_RULES: RegimeRule[] = [
  {
    regime: 'TREND_EXPANSION',
    conditions: (f) => {
      let score = 0;
      if (f.trendStrength > 0.6) score += 0.3;
      if (Math.abs(f.trendDirection) > 0.5) score += 0.25;
      if (f.volatility > 1.2) score += 0.2;
      if (f.volatilityTrend > 0.1) score += 0.15;
      if (f.rangeScore < 0.4) score += 0.1;
      return score;
    }
  },
  {
    regime: 'TREND_CONTINUATION',
    conditions: (f) => {
      let score = 0;
      if (f.trendStrength > 0.4 && f.trendStrength < 0.7) score += 0.3;
      if (Math.abs(f.trendDirection) > 0.3) score += 0.25;
      if (f.volatility > 0.8 && f.volatility < 1.3) score += 0.2;
      if (f.rangeScore < 0.5) score += 0.15;
      if (f.volumeProfile > 0.8) score += 0.1;
      return score;
    }
  },
  {
    regime: 'RANGE_ROTATION',
    conditions: (f) => {
      let score = 0;
      if (f.rangeScore > 0.6) score += 0.3;
      if (f.trendStrength < 0.4) score += 0.25;
      if (Math.abs(f.trendDirection) < 0.3) score += 0.2;
      if (f.volatility < 1.2) score += 0.15;
      if (f.rangeWidth > 0.03) score += 0.1;
      return score;
    }
  },
  {
    regime: 'COMPRESSION',
    conditions: (f) => {
      let score = 0;
      if (f.compression > 0.6) score += 0.35;
      if (f.compressionTrend > 0.1) score += 0.2;
      if (f.volatility < 0.8) score += 0.2;
      if (f.trendStrength < 0.5) score += 0.15;
      if (f.volumeTrend < 0) score += 0.1;
      return score;
    }
  },
  {
    regime: 'BREAKOUT_PREP',
    conditions: (f) => {
      let score = 0;
      if (f.compression > 0.5) score += 0.25;
      if (f.volatilityTrend > 0) score += 0.2;
      if (f.volumeTrend > 0.1) score += 0.2;
      if (f.trendStrength < 0.6 && f.trendStrength > 0.3) score += 0.2;
      if (f.momentum > 0.2 || f.momentum < -0.2) score += 0.15;
      return score;
    }
  },
  {
    regime: 'VOLATILITY_EXPANSION',
    conditions: (f) => {
      let score = 0;
      if (f.volatility > 1.5) score += 0.35;
      if (f.volatilityTrend > 0.2) score += 0.25;
      if (f.trendStrength < 0.5) score += 0.15;
      if (f.rangeWidth > 0.05) score += 0.15;
      if (f.volumeProfile > 1.5) score += 0.1;
      return score;
    }
  },
  {
    regime: 'LIQUIDITY_HUNT',
    conditions: (f) => {
      let score = 0;
      if (f.liquidityActivity > 0.4) score += 0.35;
      if (Math.abs(f.liquidityBias) > 0.3) score += 0.25;
      if (f.volatility > 1.0) score += 0.2;
      if (f.momentumDivergence > 0.5) score += 0.1;
      if (f.volumeProfile > 1.2) score += 0.1;
      return score;
    }
  },
  {
    regime: 'ACCUMULATION',
    conditions: (f) => {
      let score = 0;
      if (f.rangeScore > 0.5) score += 0.25;
      if (f.volumeTrend > 0.1) score += 0.2;
      if (f.liquidityBias > 0.2) score += 0.2;  // More downside sweeps = bullish accumulation
      if (f.trendDirection < 0 && f.trendDirection > -0.5) score += 0.2;
      if (f.compression > 0.3) score += 0.15;
      return score;
    }
  },
  {
    regime: 'DISTRIBUTION',
    conditions: (f) => {
      let score = 0;
      if (f.rangeScore > 0.5) score += 0.25;
      if (f.volumeTrend > 0.1) score += 0.2;
      if (f.liquidityBias < -0.2) score += 0.2;  // More upside sweeps = bearish distribution
      if (f.trendDirection > 0 && f.trendDirection < 0.5) score += 0.2;
      if (f.momentumDivergence > 0.5) score += 0.15;
      return score;
    }
  }
];

// ═══════════════════════════════════════════════════════════════
// MAIN CLASSIFIER
// ═══════════════════════════════════════════════════════════════

/**
 * Detect market regime from features
 */
export function detectRegime(
  features: RegimeFeatures,
  config: RegimeConfig = DEFAULT_REGIME_CONFIG
): RegimeDetectionResult {
  // Calculate scores for each regime
  const scores: Record<MarketRegime, number> = {} as Record<MarketRegime, number>;
  
  for (const rule of REGIME_RULES) {
    scores[rule.regime] = rule.conditions(features);
  }
  
  // Calculate sub-scores for debugging
  const trendScore = (features.trendStrength + Math.abs(features.trendDirection)) / 2;
  const rangeScore = features.rangeScore;
  const compressionScore = features.compression;
  const volatilityScore = features.volatility / 2;  // Normalize to ~0-1
  const liquidityScore = features.liquidityActivity;
  
  // Find regime with highest score
  let maxScore = 0;
  let detectedRegime: MarketRegime = 'COMPRESSION';  // Default
  
  for (const [regime, score] of Object.entries(scores)) {
    if (score > maxScore) {
      maxScore = score;
      detectedRegime = regime as MarketRegime;
    }
  }
  
  // Normalize scores to probabilities
  const totalScore = Object.values(scores).reduce((a, b) => a + b, 0);
  const probabilities: Record<MarketRegime, number> = {} as Record<MarketRegime, number>;
  
  for (const [regime, score] of Object.entries(scores)) {
    probabilities[regime as MarketRegime] = totalScore > 0 ? score / totalScore : 0;
  }
  
  // Calculate confidence
  const confidence = maxScore > config.minConfidence ? maxScore : config.minConfidence;
  
  return {
    regime: detectedRegime,
    confidence,
    scores: {
      trendScore,
      rangeScore,
      compressionScore,
      volatilityScore,
      liquidityScore
    },
    features,
    probabilities,
    detectedAt: new Date()
  };
}

/**
 * Get regime with smoothing (prevents rapid switching)
 */
export function detectRegimeSmoothed(
  features: RegimeFeatures,
  previousRegime: MarketRegime | null,
  previousConfidence: number,
  config: RegimeConfig = DEFAULT_REGIME_CONFIG
): RegimeDetectionResult {
  const result = detectRegime(features, config);
  
  // If no previous regime, return as-is
  if (!previousRegime) {
    return result;
  }
  
  // Check if we should switch regimes
  const currentScore = result.probabilities[result.regime];
  const previousScore = result.probabilities[previousRegime];
  
  const shouldSwitch = currentScore - previousScore > config.transitionThreshold;
  
  if (!shouldSwitch && previousConfidence > config.minConfidence) {
    // Keep previous regime with smoothed confidence
    return {
      ...result,
      regime: previousRegime,
      confidence: previousConfidence * (1 - config.smoothingFactor) + result.confidence * config.smoothingFactor
    };
  }
  
  return result;
}

/**
 * Get regime boost for pattern
 */
export function getRegimeBoost(
  regime: MarketRegime,
  patternType: string
): number {
  const boosts = REGIME_PATTERN_BOOSTS[regime] || {};
  
  // Check pattern family
  for (const [family, boost] of Object.entries(boosts)) {
    if (patternType.toUpperCase().includes(family.toUpperCase())) {
      return boost as number;
    }
  }
  
  return 1.0;  // No boost
}
