/**
 * P1.3 — MM3 Memory-conditioned MetaBrain Policies Engine
 * 
 * Computes MetaBrain policies based on Market Memory context.
 * Uses historical analogs to adjust:
 * - Risk multiplier
 * - Confidence
 * - Signal thresholds
 */

import {
  MemoryContext,
  MemoryPolicy,
  MemoryStrength,
  MemoryPolicyRules,
  MemoryPolicyApplication,
  DEFAULT_MEMORY_POLICY_RULES
} from './memory.policy.types.js';
import { ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// MEMORY STRENGTH CLASSIFICATION
// ═══════════════════════════════════════════════════════════════

/**
 * Classify memory strength based on matches and confidence
 */
export function classifyMemoryStrength(
  context: MemoryContext,
  rules: MemoryPolicyRules = DEFAULT_MEMORY_POLICY_RULES
): MemoryStrength {
  const { matches, confidence } = context;
  
  // Strong memory
  if (matches >= rules.strongMinMatches && confidence >= rules.strongMinConfidence) {
    return 'STRONG';
  }
  
  // Moderate memory
  if (matches >= rules.moderateMinMatches && confidence >= rules.moderateMinConfidence) {
    return 'MODERATE';
  }
  
  // Weak memory
  if (matches >= rules.weakMinMatches && confidence >= rules.weakMinConfidence) {
    return 'WEAK';
  }
  
  // No significant memory
  return 'NONE';
}

// ═══════════════════════════════════════════════════════════════
// BASE POLICY COMPUTATION
// ═══════════════════════════════════════════════════════════════

/**
 * Compute base policy values by memory strength
 */
export function getBasePolicyByStrength(
  strength: MemoryStrength,
  rules: MemoryPolicyRules = DEFAULT_MEMORY_POLICY_RULES
): { riskMultiplier: number; confidenceAdjustment: number; thresholdAdjustment: number; policyStrength: number } {
  switch (strength) {
    case 'STRONG':
      return {
        riskMultiplier: rules.strongRiskMultiplier,
        confidenceAdjustment: rules.strongConfidenceAdjustment,
        thresholdAdjustment: rules.strongThresholdAdjustment,
        policyStrength: 0.9
      };
    
    case 'MODERATE':
      return {
        riskMultiplier: rules.moderateRiskMultiplier,
        confidenceAdjustment: rules.moderateConfidenceAdjustment,
        thresholdAdjustment: rules.moderateThresholdAdjustment,
        policyStrength: 0.6
      };
    
    case 'WEAK':
      return {
        riskMultiplier: rules.weakRiskMultiplier,
        confidenceAdjustment: rules.weakConfidenceAdjustment,
        thresholdAdjustment: rules.weakThresholdAdjustment,
        policyStrength: 0.3
      };
    
    case 'NONE':
    default:
      return {
        riskMultiplier: 1.0,
        confidenceAdjustment: 0,
        thresholdAdjustment: 0,
        policyStrength: 0
      };
  }
}

// ═══════════════════════════════════════════════════════════════
// BIAS ALIGNMENT
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate bias alignment adjustment
 * - Same direction as memory bias → boost
 * - Opposite direction → reduce
 */
export function calculateBiasAlignment(
  memoryBias: 'BULL' | 'BEAR' | 'NEUTRAL',
  signalDirection: ScenarioDirection,
  rules: MemoryPolicyRules = DEFAULT_MEMORY_POLICY_RULES
): { aligned: boolean; multiplier: number; description: string } {
  // Neutral memory → no adjustment
  if (memoryBias === 'NEUTRAL') {
    return {
      aligned: true,
      multiplier: 1.0,
      description: 'Memory bias neutral - no directional adjustment'
    };
  }
  
  // Check alignment
  const bullSignal = signalDirection === 'BULLISH';
  const bearSignal = signalDirection === 'BEARISH';
  const bullMemory = memoryBias === 'BULL';
  const bearMemory = memoryBias === 'BEAR';
  
  const aligned = (bullSignal && bullMemory) || (bearSignal && bearMemory);
  const opposite = (bullSignal && bearMemory) || (bearSignal && bullMemory);
  
  if (aligned) {
    return {
      aligned: true,
      multiplier: rules.sameDirectionMultiplier,
      description: `Signal ${signalDirection} aligned with memory bias ${memoryBias} - boosted`
    };
  }
  
  if (opposite) {
    return {
      aligned: false,
      multiplier: rules.oppositeDirectionMultiplier,
      description: `Signal ${signalDirection} opposite to memory bias ${memoryBias} - reduced`
    };
  }
  
  // Neutral signal or other cases
  return {
    aligned: true,
    multiplier: 1.0,
    description: 'No directional conflict'
  };
}

// ═══════════════════════════════════════════════════════════════
// MAIN POLICY COMPUTATION
// ═══════════════════════════════════════════════════════════════

/**
 * Compute full memory policy
 */
export function computeMemoryPolicy(
  context: MemoryContext,
  signalDirection?: ScenarioDirection,
  rules: MemoryPolicyRules = DEFAULT_MEMORY_POLICY_RULES
): MemoryPolicy {
  // Classify memory strength
  const strength = classifyMemoryStrength(context, rules);
  
  // Get base policy
  const basePolicy = getBasePolicyByStrength(strength, rules);
  
  // Calculate bias alignment if signal direction provided
  let biasAlignment = undefined;
  let finalRiskMultiplier = basePolicy.riskMultiplier;
  
  if (signalDirection && context.bias !== 'NEUTRAL') {
    biasAlignment = calculateBiasAlignment(context.bias, signalDirection, rules);
    finalRiskMultiplier = basePolicy.riskMultiplier * biasAlignment.multiplier;
  }
  
  // Build policy reason
  let reason = '';
  switch (strength) {
    case 'STRONG':
      reason = `Strong historical analogs: ${context.matches} matches, ${(context.confidence * 100).toFixed(0)}% confidence`;
      break;
    case 'MODERATE':
      reason = `Moderate historical analogs: ${context.matches} matches, ${(context.confidence * 100).toFixed(0)}% confidence`;
      break;
    case 'WEAK':
      reason = `Weak historical analogs: ${context.matches} matches, ${(context.confidence * 100).toFixed(0)}% confidence`;
      break;
    case 'NONE':
      reason = 'Insufficient historical data for policy';
      break;
  }
  
  if (biasAlignment && biasAlignment.multiplier !== 1.0) {
    reason += `. ${biasAlignment.description}`;
  }
  
  return {
    riskMultiplier: Math.round(finalRiskMultiplier * 1000) / 1000,
    confidenceAdjustment: basePolicy.confidenceAdjustment,
    signalApprovalThreshold: basePolicy.thresholdAdjustment,
    policyStrength: basePolicy.policyStrength,
    policyReason: reason,
    biasAlignment
  };
}

// ═══════════════════════════════════════════════════════════════
// POLICY APPLICATION
// ═══════════════════════════════════════════════════════════════

/**
 * Apply memory policy to confidence value
 */
export function applyConfidencePolicy(
  originalConfidence: number,
  policy: MemoryPolicy
): number {
  const adjusted = originalConfidence + policy.confidenceAdjustment;
  return Math.max(0, Math.min(1, Math.round(adjusted * 1000) / 1000));
}

/**
 * Apply memory policy to risk multiplier
 */
export function applyRiskPolicy(
  originalRiskMultiplier: number,
  policy: MemoryPolicy
): number {
  const adjusted = originalRiskMultiplier * policy.riskMultiplier;
  // Clamp between 0.5 and 1.5
  return Math.max(0.5, Math.min(1.5, Math.round(adjusted * 1000) / 1000));
}

/**
 * Apply memory policy to signal threshold
 */
export function applyThresholdPolicy(
  originalThreshold: number,
  policy: MemoryPolicy
): number {
  const adjusted = originalThreshold + policy.signalApprovalThreshold;
  return Math.max(0, Math.min(1, Math.round(adjusted * 1000) / 1000));
}

/**
 * Full policy application
 */
export function applyMemoryPolicy(
  context: MemoryContext,
  originalConfidence: number,
  originalRiskMultiplier: number,
  signalDirection?: ScenarioDirection,
  rules: MemoryPolicyRules = DEFAULT_MEMORY_POLICY_RULES
): MemoryPolicyApplication {
  const strength = classifyMemoryStrength(context, rules);
  const policy = computeMemoryPolicy(context, signalDirection, rules);
  
  return {
    originalConfidence,
    originalRiskMultiplier,
    adjustedConfidence: applyConfidencePolicy(originalConfidence, policy),
    adjustedRiskMultiplier: applyRiskPolicy(originalRiskMultiplier, policy),
    memoryStrength: strength,
    policyApplied: strength !== 'NONE',
    policyDetails: policy
  };
}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════

/**
 * Get neutral policy (no effect)
 */
export function getNeutralMemoryPolicy(): MemoryPolicy {
  return {
    riskMultiplier: 1.0,
    confidenceAdjustment: 0,
    signalApprovalThreshold: 0,
    policyStrength: 0,
    policyReason: 'No memory policy applied'
  };
}

/**
 * Create memory context from memory boost result
 */
export function createMemoryContext(
  matches: number,
  confidence: number,
  dominantDirection: 'BULLISH' | 'BEARISH' | 'NEUTRAL',
  historicalWinRate?: number,
  avgMoveATR?: number
): MemoryContext {
  const bias: 'BULL' | 'BEAR' | 'NEUTRAL' = 
    dominantDirection === 'BULLISH' ? 'BULL' :
    dominantDirection === 'BEARISH' ? 'BEAR' : 'NEUTRAL';
  
  return {
    confidence,
    matches,
    bias,
    historicalWinRate,
    avgMoveATR
  };
}
