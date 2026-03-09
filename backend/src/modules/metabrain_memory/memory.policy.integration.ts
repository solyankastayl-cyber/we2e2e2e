/**
 * P1.3 — MM3 Memory Policy Integration
 * 
 * Integration layer for Memory Policies with:
 * - MetaBrain
 * - Decision Engine
 * - Execution Engine
 * - Digital Twin
 */

import { MemoryContext, MemoryPolicy, MemoryStrength, MemoryPolicyApplication } from './memory.policy.types.js';
import { computeMemoryPolicy, classifyMemoryStrength, applyMemoryPolicy, getNeutralMemoryPolicy } from './memory.policies.js';
import { getLatestMemoryPolicy, saveMemoryPolicy } from './memory.policy.storage.js';
import { ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// FETCH FROM MEMORY ENGINE
// ═══════════════════════════════════════════════════════════════

/**
 * Fetch memory context from Memory Engine API
 */
export async function fetchMemoryContext(
  asset: string,
  timeframe: string
): Promise<MemoryContext | null> {
  try {
    const url = `http://localhost:8001/api/ta/memory/boost?asset=${asset}&tf=${timeframe}`;
    const resp = await fetch(url);
    
    if (!resp.ok) return null;
    
    const data = await resp.json() as { data?: any };
    
    if (!data.data) return null;
    
    // Convert memory boost result to memory context
    const boost = data.data;
    
    return {
      confidence: boost.memoryConfidence ?? 0,
      matches: boost.matchCount ?? 0,
      bias: boost.dominantOutcome === 'BULLISH' ? 'BULL' :
            boost.dominantOutcome === 'BEARISH' ? 'BEAR' : 'NEUTRAL'
    };
  } catch {
    return null;
  }
}

/**
 * Fetch and compute policy
 */
export async function fetchMemoryPolicy(
  asset: string,
  timeframe: string,
  signalDirection?: ScenarioDirection
): Promise<MemoryPolicy | null> {
  const context = await fetchMemoryContext(asset, timeframe);
  
  if (!context) return null;
  
  return computeMemoryPolicy(context, signalDirection);
}

// ═══════════════════════════════════════════════════════════════
// METABRAIN INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get memory policy for MetaBrain
 * Returns policy info that MetaBrain uses for risk decisions
 */
export async function getMemoryPolicyForMetaBrain(
  asset: string,
  timeframe: string
): Promise<{
  hasPolicy: boolean;
  policy: MemoryPolicy;
  strength: MemoryStrength;
  context?: MemoryContext;
}> {
  const context = await fetchMemoryContext(asset, timeframe);
  
  if (!context || context.matches < 5) {
    return {
      hasPolicy: false,
      policy: getNeutralMemoryPolicy(),
      strength: 'NONE'
    };
  }
  
  const strength = classifyMemoryStrength(context);
  const policy = computeMemoryPolicy(context);
  
  return {
    hasPolicy: true,
    policy,
    strength,
    context
  };
}

/**
 * Apply memory policy to MetaBrain risk multiplier
 */
export function applyMemoryPolicyToMetaBrain(
  baseRiskMultiplier: number,
  policy: MemoryPolicy
): { adjustedMultiplier: number; policyApplied: boolean } {
  if (policy.policyStrength === 0) {
    return { adjustedMultiplier: baseRiskMultiplier, policyApplied: false };
  }
  
  const adjusted = baseRiskMultiplier * policy.riskMultiplier;
  
  return {
    adjustedMultiplier: Math.round(Math.max(0.5, Math.min(1.5, adjusted)) * 1000) / 1000,
    policyApplied: true
  };
}

// ═══════════════════════════════════════════════════════════════
// DECISION ENGINE INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Apply memory policy to decision confidence
 */
export function applyMemoryPolicyToDecision(
  baseConfidence: number,
  policy: MemoryPolicy
): { adjustedConfidence: number; policyApplied: boolean } {
  if (policy.policyStrength === 0) {
    return { adjustedConfidence: baseConfidence, policyApplied: false };
  }
  
  const adjusted = baseConfidence + policy.confidenceAdjustment;
  
  return {
    adjustedConfidence: Math.round(Math.max(0, Math.min(1, adjusted)) * 1000) / 1000,
    policyApplied: true
  };
}

/**
 * Apply memory policy to signal approval threshold
 */
export function applyMemoryPolicyToThreshold(
  baseThreshold: number,
  policy: MemoryPolicy
): { adjustedThreshold: number; policyApplied: boolean } {
  if (policy.policyStrength === 0) {
    return { adjustedThreshold: baseThreshold, policyApplied: false };
  }
  
  const adjusted = baseThreshold + policy.signalApprovalThreshold;
  
  return {
    adjustedThreshold: Math.round(Math.max(0, Math.min(1, adjusted)) * 1000) / 1000,
    policyApplied: true
  };
}

// ═══════════════════════════════════════════════════════════════
// EXECUTION ENGINE INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Apply memory policy to position sizing
 */
export function applyMemoryPolicyToExecution(
  baseSize: number,
  policy: MemoryPolicy
): { adjustedSize: number; policyApplied: boolean } {
  if (policy.policyStrength === 0) {
    return { adjustedSize: baseSize, policyApplied: false };
  }
  
  const adjusted = baseSize * policy.riskMultiplier;
  
  return {
    adjustedSize: Math.round(adjusted * 1000) / 1000,
    policyApplied: true
  };
}

// ═══════════════════════════════════════════════════════════════
// DIGITAL TWIN INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get memory policy for Digital Twin state
 */
export async function getMemoryPolicyForTwin(
  asset: string,
  timeframe: string
): Promise<MemoryPolicy | undefined> {
  const result = await getMemoryPolicyForMetaBrain(asset, timeframe);
  
  if (!result.hasPolicy) return undefined;
  
  return result.policy;
}

// ═══════════════════════════════════════════════════════════════
// EXPLAIN API INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get memory policy data for explain API
 */
export async function getMemoryPolicyForExplain(
  asset: string,
  timeframe: string,
  signalDirection?: ScenarioDirection
): Promise<{
  memoryPolicy: MemoryPolicy;
  memoryStrength: MemoryStrength;
  memoryContext?: MemoryContext;
} | null> {
  const context = await fetchMemoryContext(asset, timeframe);
  
  if (!context) {
    return {
      memoryPolicy: getNeutralMemoryPolicy(),
      memoryStrength: 'NONE'
    };
  }
  
  const strength = classifyMemoryStrength(context);
  const policy = computeMemoryPolicy(context, signalDirection);
  
  return {
    memoryPolicy: policy,
    memoryStrength: strength,
    memoryContext: context
  };
}
