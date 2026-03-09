/**
 * Phase 9.5 — Edge Validation: Confidence Calculator
 */

import {
  RobustnessScore,
  SimilarityAnalysis,
  ConfidenceScore,
  EdgeValidationConfig,
  DEFAULT_EDGE_CONFIG,
  RISK_FLAGS
} from './edge.types.js';

/**
 * Calculate sample score based on trade count
 */
export function calculateSampleScore(
  trades: number,
  config: EdgeValidationConfig = DEFAULT_EDGE_CONFIG
): number {
  if (trades < config.minTrades) {
    return trades / config.minTrades * 0.5;  // Below min = capped at 0.5
  }
  
  if (trades >= config.optimalTrades) {
    return 1.0;
  }
  
  // Linear scale from minTrades to optimalTrades
  const range = config.optimalTrades - config.minTrades;
  const progress = (trades - config.minTrades) / range;
  
  return 0.5 + progress * 0.5;
}

/**
 * Calculate sample size penalty
 */
export function calculateSamplePenalty(
  trades: number,
  config: EdgeValidationConfig = DEFAULT_EDGE_CONFIG
): number {
  if (trades >= config.minTrades) return 0;
  
  // Penalty increases as trades decrease below minimum
  const deficit = (config.minTrades - trades) / config.minTrades;
  return Math.min(0.4, deficit * 0.5);
}

/**
 * Calculate full confidence score
 */
export function calculateConfidenceScore(
  trades: number,
  winRate: number,
  profitFactor: number,
  maxDrawdown: number,
  robustness: RobustnessScore,
  similarity: SimilarityAnalysis,
  config: EdgeValidationConfig = DEFAULT_EDGE_CONFIG
): ConfidenceScore {
  const riskFlags: string[] = [];
  
  // Component scores
  const sampleScore = calculateSampleScore(trades, config);
  const regimeRobustness = robustness.regimeScore;
  const crossMarketRobustness = robustness.crossMarketScore;
  const stabilityScore = robustness.stabilityScore;
  
  // Penalties
  const sampleSizePenalty = calculateSamplePenalty(trades, config);
  const similarityPenalty = similarity.similarityPenalty;
  
  // Check risk flags
  if (trades < config.minTrades) {
    riskFlags.push(RISK_FLAGS.SMALL_SAMPLE);
  }
  
  if (robustness.strongRegimes.length <= 1) {
    riskFlags.push(RISK_FLAGS.SINGLE_REGIME);
  }
  
  if (robustness.validMarkets.length <= 1) {
    riskFlags.push(RISK_FLAGS.SINGLE_MARKET);
  }
  
  if (maxDrawdown > config.maxDrawdown) {
    riskFlags.push(RISK_FLAGS.HIGH_DRAWDOWN);
  }
  
  if (profitFactor < config.minProfitFactor) {
    riskFlags.push(RISK_FLAGS.LOW_PROFIT_FACTOR);
  }
  
  if (similarityPenalty > 0.3) {
    riskFlags.push(RISK_FLAGS.HIGH_SIMILARITY);
  }
  
  if (stabilityScore < config.minStabilityScore) {
    riskFlags.push(RISK_FLAGS.UNSTABLE);
  }
  
  // Calculate raw confidence (weighted average)
  const weights = config.confidenceWeights;
  const rawConfidence = 
    sampleScore * weights.sample +
    regimeRobustness * weights.regime +
    crossMarketRobustness * weights.crossMarket +
    stabilityScore * weights.stability;
  
  // Apply penalties
  const totalPenalty = sampleSizePenalty + similarityPenalty;
  const adjustedConfidence = Math.max(0, rawConfidence - totalPenalty);
  
  return {
    sampleScore,
    regimeRobustness,
    crossMarketRobustness,
    stabilityScore,
    similarityPenalty,
    sampleSizePenalty,
    rawConfidence,
    adjustedConfidence: Math.min(1, adjustedConfidence),
    riskFlags
  };
}

/**
 * Determine recommended lifecycle status
 */
export function determineLifecycleStatus(
  confidence: ConfidenceScore,
  robustness: RobustnessScore,
  config: EdgeValidationConfig = DEFAULT_EDGE_CONFIG
): {
  status: 'CANDIDATE' | 'TESTING' | 'LIMITED' | 'APPROVED' | 'REJECTED';
  reason: string;
} {
  const { adjustedConfidence, riskFlags } = confidence;
  
  // Rejection criteria
  if (riskFlags.length >= 4) {
    return { status: 'REJECTED', reason: 'Too many risk flags' };
  }
  
  if (riskFlags.includes(RISK_FLAGS.HIGH_DRAWDOWN) && 
      riskFlags.includes(RISK_FLAGS.LOW_PROFIT_FACTOR)) {
    return { status: 'REJECTED', reason: 'Poor risk-adjusted performance' };
  }
  
  // Approval criteria
  if (adjustedConfidence >= config.approvalConfidence && 
      riskFlags.length <= 1 &&
      robustness.strongRegimes.length >= 2 &&
      robustness.validMarkets.length >= 2) {
    return { status: 'APPROVED', reason: 'High confidence with cross-validation' };
  }
  
  // Limited criteria
  if (adjustedConfidence >= config.limitedConfidence) {
    const limitations: string[] = [];
    
    if (robustness.strongRegimes.length === 1) {
      limitations.push(`Only in ${robustness.strongRegimes[0]}`);
    }
    if (robustness.validMarkets.length === 1) {
      limitations.push(`Only on ${robustness.validMarkets[0]}`);
    }
    
    if (limitations.length > 0) {
      return { 
        status: 'LIMITED', 
        reason: `Works with limitations: ${limitations.join(', ')}` 
      };
    }
    
    // If no specific limitations but not enough for approval
    return { status: 'LIMITED', reason: 'Moderate confidence, needs more validation' };
  }
  
  // Testing criteria
  if (adjustedConfidence >= config.testingConfidence) {
    return { status: 'TESTING', reason: 'Promising but needs more data' };
  }
  
  // Default: Candidate
  return { status: 'CANDIDATE', reason: 'Early stage, insufficient evidence' };
}
