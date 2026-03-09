/**
 * DT5 — Tree Scoring Engine
 * 
 * Calculates Decision and Execution adjustments based on tree structure
 */

import {
  TwinBranchTree,
  TreeStats,
  TwinTreeNode
} from './digital_twin.types.js';

// ═══════════════════════════════════════════════════════════════
// DECISION SCORING
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate decision score adjustment from tree
 * 
 * High dominance → trust main scenario
 * High uncertainty → reduce score
 */
export function calculateTreeDecisionAdjustment(treeStats: TreeStats): number {
  // Base: 1.0 (no adjustment)
  let adjustment = 1.0;
  
  // Dominance boost (max +15%)
  if (treeStats.dominanceScore > 0.6) {
    adjustment += (treeStats.dominanceScore - 0.6) * 0.375; // 0.6→0, 1.0→0.15
  }
  
  // Uncertainty penalty (max -20%)
  if (treeStats.uncertaintyScore > 0.4) {
    adjustment -= (treeStats.uncertaintyScore - 0.4) * 0.333; // 0.4→0, 1.0→0.20
  }
  
  // Tree risk penalty (max -15%)
  if (treeStats.treeRisk > 0.3) {
    adjustment -= (treeStats.treeRisk - 0.3) * 0.214; // 0.3→0, 1.0→0.15
  }
  
  // Clamp to reasonable range
  return Math.max(0.7, Math.min(1.2, adjustment));
}

/**
 * Get decision confidence from tree
 */
export function getTreeConfidence(treeStats: TreeStats): number {
  // Combine dominance and inverse uncertainty
  const confidence = (treeStats.dominanceScore + (1 - treeStats.uncertaintyScore)) / 2;
  return Math.round(confidence * 100) / 100;
}

// ═══════════════════════════════════════════════════════════════
// EXECUTION SCORING
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate position size adjustment from tree
 * 
 * High uncertainty → reduce position
 * High tree risk → reduce position
 * Strong dominance → allow normal size
 */
export function calculateTreeExecutionAdjustment(treeStats: TreeStats): number {
  // Start at 1.0
  let adjustment = 1.0;
  
  // Uncertainty reduction (max -30%)
  if (treeStats.uncertaintyScore > 0.3) {
    adjustment -= (treeStats.uncertaintyScore - 0.3) * 0.428; // 0.3→0, 1.0→0.30
  }
  
  // Tree risk reduction (max -25%)
  if (treeStats.treeRisk > 0.2) {
    adjustment -= (treeStats.treeRisk - 0.2) * 0.312; // 0.2→0, 1.0→0.25
  }
  
  // Dominance bonus (max +10%)
  if (treeStats.dominanceScore > 0.7) {
    adjustment += (treeStats.dominanceScore - 0.7) * 0.333; // 0.7→0, 1.0→0.10
  }
  
  // Clamp to reasonable range
  return Math.max(0.5, Math.min(1.15, adjustment));
}

/**
 * Should reduce stop tightness based on tree?
 */
export function shouldTightenStop(treeStats: TreeStats): {
  tighten: boolean;
  factor: number;
  reason: string;
} {
  // Tighten stop if tree risk is high
  if (treeStats.treeRisk > 0.5) {
    return {
      tighten: true,
      factor: 0.8, // 20% tighter
      reason: 'High tree risk detected'
    };
  }
  
  // Tighten if multiple strong alternatives
  if (treeStats.uncertaintyScore > 0.6 && treeStats.totalBranches > 5) {
    return {
      tighten: true,
      factor: 0.85, // 15% tighter
      reason: 'High uncertainty with multiple alternatives'
    };
  }
  
  return {
    tighten: false,
    factor: 1.0,
    reason: 'Normal stop placement'
  };
}

// ═══════════════════════════════════════════════════════════════
// METABRAIN SCORING
// ═══════════════════════════════════════════════════════════════

/**
 * Get recommended risk mode from tree
 */
export function getRecommendedRiskMode(
  treeStats: TreeStats
): 'CONSERVATIVE' | 'NORMAL' | 'AGGRESSIVE' {
  // High uncertainty → conservative
  if (treeStats.uncertaintyScore > 0.6) {
    return 'CONSERVATIVE';
  }
  
  // High tree risk → conservative
  if (treeStats.treeRisk > 0.5) {
    return 'CONSERVATIVE';
  }
  
  // Strong dominance → can be aggressive
  if (treeStats.dominanceScore > 0.7 && treeStats.treeRisk < 0.3) {
    return 'AGGRESSIVE';
  }
  
  return 'NORMAL';
}

/**
 * Get tree-based trading recommendation
 */
export function getTradingRecommendation(
  treeStats: TreeStats
): {
  trade: boolean;
  confidence: number;
  reason: string;
} {
  // Don't trade if very uncertain
  if (treeStats.uncertaintyScore > 0.8) {
    return {
      trade: false,
      confidence: 0.2,
      reason: 'Tree uncertainty too high - no clear path'
    };
  }
  
  // Don't trade if high risk and low dominance
  if (treeStats.treeRisk > 0.6 && treeStats.dominanceScore < 0.5) {
    return {
      trade: false,
      confidence: 0.3,
      reason: 'High risk without dominant branch'
    };
  }
  
  // Strong signal if dominant with low risk
  if (treeStats.dominanceScore > 0.7 && treeStats.treeRisk < 0.3) {
    return {
      trade: true,
      confidence: 0.9,
      reason: 'Strong dominant branch with low risk'
    };
  }
  
  // Normal trade
  const confidence = (treeStats.dominanceScore * 0.6 + (1 - treeStats.treeRisk) * 0.4);
  return {
    trade: confidence > 0.5,
    confidence: Math.round(confidence * 100) / 100,
    reason: confidence > 0.5 ? 'Acceptable tree structure' : 'Marginal tree structure'
  };
}

// ═══════════════════════════════════════════════════════════════
// BRANCH ANALYSIS
// ═══════════════════════════════════════════════════════════════

/**
 * Analyze alternative branches for risk assessment
 */
export function analyzeAlternativeBranches(
  tree: TwinBranchTree
): {
  mainBranch: TwinTreeNode | null;
  alternatives: TwinTreeNode[];
  alternativeRisk: number;
  divergencePoint: string | null;
} {
  if (tree.branches.length === 0) {
    return {
      mainBranch: null,
      alternatives: [],
      alternativeRisk: 0,
      divergencePoint: null
    };
  }
  
  // Sort by probability
  const sorted = [...tree.branches].sort((a, b) => b.probability - a.probability);
  const mainBranch = sorted[0];
  const alternatives = sorted.slice(1);
  
  // Calculate alternative risk
  const alternativeRisk = alternatives.reduce((sum, alt) => 
    sum + alt.probability * alt.failureRisk, 0
  );
  
  // Find first divergence point
  let divergencePoint: string | null = null;
  if (alternatives.length > 0 && mainBranch.state !== alternatives[0].state) {
    divergencePoint = tree.rootState;
  }
  
  return {
    mainBranch,
    alternatives,
    alternativeRisk: Math.round(alternativeRisk * 100) / 100,
    divergencePoint
  };
}

/**
 * Calculate scenario break probability from tree
 */
export function calculateScenarioBreakProbability(tree: TwinBranchTree): number {
  const analysis = analyzeAlternativeBranches(tree);
  
  if (!analysis.mainBranch) return 0;
  
  // Break probability = sum of alternative probabilities weighted by their "divergence"
  const mainProb = analysis.mainBranch.probability;
  const altProbSum = analysis.alternatives.reduce((sum, alt) => sum + alt.probability, 0);
  
  // Normalize
  const totalProb = mainProb + altProbSum;
  const breakProb = totalProb > 0 ? altProbSum / totalProb : 0;
  
  return Math.round(breakProb * 100) / 100;
}
