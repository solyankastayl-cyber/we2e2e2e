/**
 * P1.1 — Tree Stats Integration Service
 * 
 * Integrates DT5 Branch Tree Stats into Decision and Execution pipelines
 * 
 * Tree scoring already calculates:
 * - dominanceScore
 * - uncertaintyScore  
 * - treeRisk
 * 
 * This module provides:
 * - Decision adjustment (affects signal score)
 * - Execution adjustment (affects position size)
 * - Risk mode hints for MetaBrain
 */

import { TreeStats, TwinBranchTree } from './digital_twin.types.js';
import {
  calculateTreeDecisionAdjustment,
  calculateTreeExecutionAdjustment,
  getRecommendedRiskMode,
  getTradingRecommendation,
  shouldTightenStop,
  getTreeConfidence
} from './digital_twin.tree_scoring.js';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface TreeAdjustments {
  decisionAdjustment: number;
  executionAdjustment: number;
  riskModeHint: 'CONSERVATIVE' | 'NORMAL' | 'AGGRESSIVE';
  treeConfidence: number;
  shouldTrade: boolean;
  tradeReason: string;
  stopAdjustment?: {
    tighten: boolean;
    factor: number;
    reason: string;
  };
}

export interface TreeIntegrationResult {
  treeStats: TreeStats;
  adjustments: TreeAdjustments;
  applied: boolean;
  appliedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// MAIN INTEGRATION SERVICE
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate all tree-based adjustments for Decision and Execution
 */
export function getTreeAdjustments(treeStats: TreeStats): TreeAdjustments {
  // Decision adjustment (affects score)
  // Formula: (0.5 + dominanceScore * 0.5) × (1 - uncertaintyScore * 0.3) × (1 - treeRisk * 0.4)
  // Clamped: 0.75 .. 1.15
  const decisionAdjustment = calculateTreeDecisionAdjustment(treeStats);
  
  // Execution adjustment (affects position size)
  // Formula: 1 - treeRisk * 0.35
  // Clamped: 0.70 .. 1.00
  const executionAdjustment = calculateTreeExecutionAdjustment(treeStats);
  
  // Risk mode recommendation
  const riskModeHint = getRecommendedRiskMode(treeStats);
  
  // Tree confidence
  const treeConfidence = getTreeConfidence(treeStats);
  
  // Trading recommendation
  const tradingRec = getTradingRecommendation(treeStats);
  
  // Stop adjustment
  const stopAdjustment = shouldTightenStop(treeStats);
  
  return {
    decisionAdjustment: Math.round(decisionAdjustment * 1000) / 1000,
    executionAdjustment: Math.round(executionAdjustment * 1000) / 1000,
    riskModeHint,
    treeConfidence,
    shouldTrade: tradingRec.trade,
    tradeReason: tradingRec.reason,
    stopAdjustment
  };
}

/**
 * Create full integration result
 */
export function createTreeIntegrationResult(
  treeStats: TreeStats,
  applied: boolean = true
): TreeIntegrationResult {
  return {
    treeStats,
    adjustments: getTreeAdjustments(treeStats),
    applied,
    appliedAt: new Date()
  };
}

// ═══════════════════════════════════════════════════════════════
// FETCH TREE INTEGRATION (HTTP)
// ═══════════════════════════════════════════════════════════════

/**
 * Fetch tree integration data via HTTP
 * For cross-service calls from Decision/Execution engines
 */
export async function fetchTreeIntegration(
  asset: string,
  timeframe: string
): Promise<TreeIntegrationResult | null> {
  try {
    const url = `http://localhost:8001/api/ta/twin/tree/integration?asset=${asset}&tf=${timeframe}`;
    const resp = await fetch(url);
    
    if (!resp.ok) {
      console.warn(`[TreeIntegration] Failed to fetch: ${resp.status}`);
      return null;
    }
    
    const data = await resp.json() as { data?: TreeIntegrationResult };
    return data.data ?? null;
  } catch (err) {
    console.warn('[TreeIntegration] Fetch error:', err);
    return null;
  }
}

/**
 * Fetch tree adjustments directly
 */
export async function fetchTreeAdjustments(
  asset: string,
  timeframe: string
): Promise<TreeAdjustments | null> {
  const result = await fetchTreeIntegration(asset, timeframe);
  return result?.adjustments ?? null;
}

// ═══════════════════════════════════════════════════════════════
// DECISION ENGINE INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Apply tree adjustment to decision score
 * 
 * Formula:
 * finalScore = evAfterEdge × directionBoost × scenarioBoost × treeDecisionAdjustment
 */
export function applyTreeDecisionAdjustment(
  baseScore: number,
  adjustments: TreeAdjustments | null
): { score: number; treeApplied: boolean; treeAdjustment: number } {
  if (!adjustments) {
    return { score: baseScore, treeApplied: false, treeAdjustment: 1.0 };
  }
  
  const adjusted = baseScore * adjustments.decisionAdjustment;
  
  return {
    score: Math.round(adjusted * 1000) / 1000,
    treeApplied: true,
    treeAdjustment: adjustments.decisionAdjustment
  };
}

// ═══════════════════════════════════════════════════════════════
// EXECUTION ENGINE INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Apply tree adjustment to position size
 * 
 * Formula:
 * positionSize = baseSize × confidence × edge × regime × portfolio × metaBrain × memory × treeExecutionAdjustment
 */
export function applyTreeExecutionAdjustment(
  baseSize: number,
  adjustments: TreeAdjustments | null
): { size: number; treeApplied: boolean; treeAdjustment: number } {
  if (!adjustments) {
    return { size: baseSize, treeApplied: false, treeAdjustment: 1.0 };
  }
  
  const adjusted = baseSize * adjustments.executionAdjustment;
  
  return {
    size: Math.round(adjusted * 1000) / 1000,
    treeApplied: true,
    treeAdjustment: adjustments.executionAdjustment
  };
}

/**
 * Apply stop adjustment from tree
 */
export function applyTreeStopAdjustment(
  baseStop: number,
  entryPrice: number,
  adjustments: TreeAdjustments | null
): { stop: number; adjusted: boolean; reason: string } {
  if (!adjustments?.stopAdjustment?.tighten) {
    return { stop: baseStop, adjusted: false, reason: 'No tree adjustment' };
  }
  
  const stopDistance = Math.abs(entryPrice - baseStop);
  const newDistance = stopDistance * adjustments.stopAdjustment.factor;
  
  // Determine stop direction
  const isLong = entryPrice < baseStop ? false : true;
  const newStop = isLong 
    ? entryPrice - newDistance
    : entryPrice + newDistance;
  
  return {
    stop: Math.round(newStop * 100) / 100,
    adjusted: true,
    reason: adjustments.stopAdjustment.reason
  };
}

// ═══════════════════════════════════════════════════════════════
// METABRAIN INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get MetaBrain policy hints from tree
 */
export function getTreePolicyHints(adjustments: TreeAdjustments | null): {
  suggestedRiskMode: 'CONSERVATIVE' | 'NORMAL' | 'AGGRESSIVE';
  shouldReduceExposure: boolean;
  confidenceThresholdBoost: number;
  reason: string;
} {
  if (!adjustments) {
    return {
      suggestedRiskMode: 'NORMAL',
      shouldReduceExposure: false,
      confidenceThresholdBoost: 0,
      reason: 'No tree data available'
    };
  }
  
  const shouldReduce = adjustments.executionAdjustment < 0.85;
  const thresholdBoost = adjustments.riskModeHint === 'CONSERVATIVE' ? 0.1 : 0;
  
  return {
    suggestedRiskMode: adjustments.riskModeHint,
    shouldReduceExposure: shouldReduce,
    confidenceThresholdBoost: thresholdBoost,
    reason: `Tree confidence: ${adjustments.treeConfidence}, Trade: ${adjustments.shouldTrade ? 'Yes' : 'No'}`
  };
}

// ═══════════════════════════════════════════════════════════════
// DEFAULT / NEUTRAL VALUES
// ═══════════════════════════════════════════════════════════════

/**
 * Get neutral tree adjustments (no effect)
 */
export function getNeutralTreeAdjustments(): TreeAdjustments {
  return {
    decisionAdjustment: 1.0,
    executionAdjustment: 1.0,
    riskModeHint: 'NORMAL',
    treeConfidence: 0.5,
    shouldTrade: true,
    tradeReason: 'No tree data - neutral',
    stopAdjustment: {
      tighten: false,
      factor: 1.0,
      reason: 'Normal stop placement'
    }
  };
}

/**
 * Create default tree stats
 */
export function getDefaultTreeStats(): TreeStats {
  return {
    dominanceScore: 0.5,
    uncertaintyScore: 0.5,
    treeRisk: 0.3,
    mainBranchProbability: 0.5,
    totalBranches: 1,
    maxDepthReached: 0
  };
}
