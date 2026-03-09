/**
 * MetaBrain v1 — Policy Engine
 * 
 * Builds decisions from context and risk mode
 */

import {
  MetaBrainContext,
  MetaBrainDecision,
  MetaRiskMode,
  RISK_MODE_CONFIG
} from './metabrain.types.js';

// ═══════════════════════════════════════════════════════════════
// DECISION BUILDING
// ═══════════════════════════════════════════════════════════════

/**
 * Build MetaBrain decision from context and risk mode
 */
export function buildMetaDecision(
  context: MetaBrainContext,
  riskMode: MetaRiskMode,
  reasons: string[]
): MetaBrainDecision {
  const config = RISK_MODE_CONFIG[riskMode];
  
  // Apply context-based adjustments
  let confidenceThreshold = config.confidenceThreshold;
  let scenarioProbabilityThreshold = config.confidenceThreshold - 0.05;
  let strategyMultiplier = config.strategyMultiplier;
  let riskMultiplier = config.riskMultiplier;
  
  // Further adjustments based on specific conditions
  const adjustments: string[] = [];
  
  // If high volatility but not CONSERVATIVE, still increase threshold
  if (context.volatility === 'HIGH' && riskMode !== 'CONSERVATIVE') {
    confidenceThreshold += 0.05;
    adjustments.push('Increased confidence threshold due to high volatility');
  }
  
  // If edge is very strong, allow slightly lower confidence
  if (context.edgeHealth > 0.75 && riskMode !== 'CONSERVATIVE') {
    confidenceThreshold -= 0.03;
    adjustments.push('Reduced confidence threshold due to strong edge');
  }
  
  // If many open positions, reduce further risk taking
  if (context.openPositions >= 5) {
    riskMultiplier *= 0.9;
    adjustments.push('Reduced risk multiplier due to open position count');
  }
  
  // Regime-specific adjustments
  if (context.regime === 'COMPRESSION' && riskMode === 'AGGRESSIVE') {
    // Don't be too aggressive in compression - wait for breakout
    riskMultiplier *= 0.85;
    adjustments.push('Moderated aggression in compression regime');
  }
  
  // Calculate effective base risk
  const effectiveBaseRisk = config.baseRiskPct * riskMultiplier;
  
  return {
    riskMode,
    confidenceThreshold: Math.round(confidenceThreshold * 100) / 100,
    scenarioProbabilityThreshold: Math.round(scenarioProbabilityThreshold * 100) / 100,
    strategyMultiplier: Math.round(strategyMultiplier * 100) / 100,
    riskMultiplier: Math.round(riskMultiplier * 100) / 100,
    reason: [...reasons, ...adjustments],
    effectiveBaseRisk: Math.round(effectiveBaseRisk * 100) / 100,
    isOverride: false,
    decidedAt: new Date()
  };
}

// ═══════════════════════════════════════════════════════════════
// STRATEGY POLICY
// ═══════════════════════════════════════════════════════════════

export interface StrategyPolicyResult {
  strategyId: string;
  action: 'ENABLE' | 'DISABLE' | 'DOWNWEIGHT' | 'UPWEIGHT' | 'MAINTAIN';
  weight: number;
  reason: string;
}

/**
 * Generate strategy policies based on context
 */
export function generateStrategyPolicies(
  strategies: Array<{
    strategyId: string;
    profitFactor: number;
    regime?: string;
    recentPerformance: number;  // -1 to 1
  }>,
  context: MetaBrainContext,
  riskMode: MetaRiskMode
): StrategyPolicyResult[] {
  const results: StrategyPolicyResult[] = [];
  
  for (const strategy of strategies) {
    let action: StrategyPolicyResult['action'] = 'MAINTAIN';
    let weight = 1.0;
    let reason = 'Default weight';
    
    // Check profit factor
    if (strategy.profitFactor < 1.0) {
      action = 'DISABLE';
      weight = 0;
      reason = `Negative edge: PF ${strategy.profitFactor.toFixed(2)}`;
    } else if (strategy.profitFactor < 1.1) {
      action = 'DOWNWEIGHT';
      weight = 0.7;
      reason = `Weak edge: PF ${strategy.profitFactor.toFixed(2)}`;
    }
    
    // Check regime alignment
    if (strategy.regime && strategy.regime !== context.regime) {
      action = action === 'MAINTAIN' ? 'DOWNWEIGHT' : action;
      weight *= 0.8;
      reason = `Regime mismatch: ${strategy.regime} vs ${context.regime}`;
    } else if (strategy.regime === context.regime) {
      if (action === 'MAINTAIN') {
        action = 'UPWEIGHT';
        weight = 1.15;
        reason = `Regime match: ${context.regime}`;
      }
    }
    
    // Check recent performance
    if (strategy.recentPerformance < -0.3) {
      action = action === 'DISABLE' ? 'DISABLE' : 'DOWNWEIGHT';
      weight *= 0.8;
      reason = `Poor recent performance: ${(strategy.recentPerformance * 100).toFixed(0)}%`;
    } else if (strategy.recentPerformance > 0.3) {
      weight *= 1.1;
    }
    
    // Apply risk mode adjustments
    if (riskMode === 'CONSERVATIVE') {
      weight *= 0.9;
    } else if (riskMode === 'AGGRESSIVE') {
      weight *= 1.1;
    }
    
    results.push({
      strategyId: strategy.strategyId,
      action,
      weight: Math.round(weight * 100) / 100,
      reason
    });
  }
  
  return results;
}

// ═══════════════════════════════════════════════════════════════
// SIGNAL THRESHOLD POLICY
// ═══════════════════════════════════════════════════════════════

export interface SignalThresholds {
  minConfidence: number;
  minScenarioProbability: number;
  minEdgeScore: number;
  minStrategyScore: number;
}

/**
 * Determine signal thresholds based on context
 */
export function determineSignalThresholds(
  context: MetaBrainContext,
  decision: MetaBrainDecision
): SignalThresholds {
  let minConfidence = decision.confidenceThreshold;
  let minScenarioProbability = decision.scenarioProbabilityThreshold;
  let minEdgeScore = 0.2;
  let minStrategyScore = 0.3;
  
  // Tighten thresholds in unfavorable conditions
  if (context.marketCondition === 'UNFAVORABLE') {
    minConfidence += 0.05;
    minScenarioProbability += 0.05;
    minEdgeScore += 0.1;
  }
  
  // Relax in favorable conditions
  if (context.marketCondition === 'FAVORABLE' && decision.riskMode !== 'CONSERVATIVE') {
    minConfidence -= 0.03;
    minEdgeScore -= 0.05;
  }
  
  // Clamp values
  return {
    minConfidence: Math.max(0.4, Math.min(0.8, minConfidence)),
    minScenarioProbability: Math.max(0.35, Math.min(0.75, minScenarioProbability)),
    minEdgeScore: Math.max(0.1, Math.min(0.4, minEdgeScore)),
    minStrategyScore: Math.max(0.2, Math.min(0.5, minStrategyScore))
  };
}
