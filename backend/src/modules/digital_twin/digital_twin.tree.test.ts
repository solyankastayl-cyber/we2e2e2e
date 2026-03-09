/**
 * DT5 — Branch Tree Tests
 * 
 * Tests:
 * 1. Tree builds from rootState
 * 2. maxDepth is respected
 * 3. Low-probability branches are pruned
 * 4. dominanceScore is calculated
 * 5. uncertaintyScore is calculated
 * 6. API works
 * 7. Decision/Execution use treeStats
 */

import { describe, it, expect } from 'vitest';
import {
  buildBranchTree,
  getMainBranch,
  getLeafNodes,
  calculateTreeEntropy,
  calculateTreeStats
} from './digital_twin.tree_builder.js';
import {
  calculateTreeDecisionAdjustment,
  calculateTreeExecutionAdjustment,
  getRecommendedRiskMode,
  getTradingRecommendation,
  analyzeAlternativeBranches,
  calculateScenarioBreakProbability
} from './digital_twin.tree_scoring.js';
import { DigitalTwinState, DEFAULT_TREE_CONFIG, TreeStats } from './digital_twin.types.js';

// ═══════════════════════════════════════════════════════════════
// MOCK DATA
// ═══════════════════════════════════════════════════════════════

const mockTwinState: DigitalTwinState = {
  asset: 'BTCUSDT',
  timeframe: '1d',
  ts: Date.now(),
  regime: 'COMPRESSION',
  marketState: 'COMPRESSION',
  physicsState: 'NEUTRAL',
  liquidityState: 'NEUTRAL',
  dominantScenario: 'BREAKOUT',
  energy: 0.5,
  instability: 0.3,
  confidence: 0.7,
  branches: [],
  computedAt: new Date(),
  version: 1
};

// ═══════════════════════════════════════════════════════════════
// TEST 1: Tree Building
// ═══════════════════════════════════════════════════════════════

describe('Tree Building', () => {
  it('should build tree from rootState', () => {
    const tree = buildBranchTree(mockTwinState);
    
    expect(tree.asset).toBe('BTCUSDT');
    expect(tree.timeframe).toBe('1d');
    expect(tree.rootState).toBe('COMPRESSION');
    expect(tree.branches.length).toBeGreaterThan(0);
  });

  it('should respect maxDepth', () => {
    const config = { ...DEFAULT_TREE_CONFIG, maxDepth: 2 };
    const tree = buildBranchTree(mockTwinState, config);
    
    expect(tree.depth).toBe(2);
    
    // Check no node goes deeper than maxDepth
    const checkDepth = (nodes: any[], currentDepth: number): boolean => {
      if (currentDepth > config.maxDepth) return false;
      for (const node of nodes) {
        if (node.children && !checkDepth(node.children, currentDepth + 1)) {
          return false;
        }
      }
      return true;
    };
    
    expect(checkDepth(tree.branches, 1)).toBe(true);
  });

  it('should prune low-probability branches', () => {
    const config = { ...DEFAULT_TREE_CONFIG, minBranchProbability: 0.15 };
    const tree = buildBranchTree(mockTwinState, config);
    
    // All branches should have probability >= minBranchProbability
    const checkProbability = (nodes: any[]): boolean => {
      for (const node of nodes) {
        if (node.probability < config.minBranchProbability) return false;
        if (node.children && !checkProbability(node.children)) return false;
      }
      return true;
    };
    
    expect(checkProbability(tree.branches)).toBe(true);
  });

  it('should limit children per node', () => {
    const config = { ...DEFAULT_TREE_CONFIG, maxChildrenPerNode: 2 };
    const tree = buildBranchTree(mockTwinState, config);
    
    expect(tree.branches.length).toBeLessThanOrEqual(2);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 2: Tree Stats
// ═══════════════════════════════════════════════════════════════

describe('Tree Stats', () => {
  it('should calculate dominanceScore', () => {
    const tree = buildBranchTree(mockTwinState);
    
    expect(tree.treeStats.dominanceScore).toBeGreaterThanOrEqual(0);
    expect(tree.treeStats.dominanceScore).toBeLessThanOrEqual(1);
  });

  it('should calculate uncertaintyScore', () => {
    const tree = buildBranchTree(mockTwinState);
    
    expect(tree.treeStats.uncertaintyScore).toBeGreaterThanOrEqual(0);
    expect(tree.treeStats.uncertaintyScore).toBeLessThanOrEqual(1);
  });

  it('should calculate treeRisk', () => {
    const tree = buildBranchTree(mockTwinState);
    
    expect(tree.treeStats.treeRisk).toBeGreaterThanOrEqual(0);
    expect(tree.treeStats.treeRisk).toBeLessThanOrEqual(1);
  });

  it('should have inverse relationship between dominance and uncertainty', () => {
    const tree = buildBranchTree(mockTwinState);
    
    const sum = tree.treeStats.dominanceScore + tree.treeStats.uncertaintyScore;
    expect(sum).toBeCloseTo(1, 1);
  });

  it('should count total branches', () => {
    const tree = buildBranchTree(mockTwinState);
    
    expect(tree.treeStats.totalBranches).toBeGreaterThan(0);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 3: Decision Adjustment
// ═══════════════════════════════════════════════════════════════

describe('Decision Adjustment', () => {
  it('should increase adjustment for high dominance', () => {
    const highDominance: TreeStats = {
      dominanceScore: 0.85,
      uncertaintyScore: 0.15,
      treeRisk: 0.2,
      mainBranchProbability: 0.7,
      totalBranches: 5,
      maxDepthReached: 3
    };
    
    const adjustment = calculateTreeDecisionAdjustment(highDominance);
    expect(adjustment).toBeGreaterThan(1);
  });

  it('should decrease adjustment for high uncertainty', () => {
    const highUncertainty: TreeStats = {
      dominanceScore: 0.35,
      uncertaintyScore: 0.65,
      treeRisk: 0.5,
      mainBranchProbability: 0.35,
      totalBranches: 10,
      maxDepthReached: 3
    };
    
    const adjustment = calculateTreeDecisionAdjustment(highUncertainty);
    expect(adjustment).toBeLessThan(1);
  });

  it('should clamp to valid range', () => {
    const extremeStats: TreeStats = {
      dominanceScore: 0.1,
      uncertaintyScore: 0.9,
      treeRisk: 0.9,
      mainBranchProbability: 0.1,
      totalBranches: 20,
      maxDepthReached: 3
    };
    
    const adjustment = calculateTreeDecisionAdjustment(extremeStats);
    expect(adjustment).toBeGreaterThanOrEqual(0.7);
    expect(adjustment).toBeLessThanOrEqual(1.2);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 4: Execution Adjustment
// ═══════════════════════════════════════════════════════════════

describe('Execution Adjustment', () => {
  it('should reduce position for high uncertainty', () => {
    const highUncertainty: TreeStats = {
      dominanceScore: 0.3,
      uncertaintyScore: 0.7,
      treeRisk: 0.5,
      mainBranchProbability: 0.3,
      totalBranches: 10,
      maxDepthReached: 3
    };
    
    const adjustment = calculateTreeExecutionAdjustment(highUncertainty);
    expect(adjustment).toBeLessThan(1);
  });

  it('should reduce position for high tree risk', () => {
    const highRisk: TreeStats = {
      dominanceScore: 0.5,
      uncertaintyScore: 0.5,
      treeRisk: 0.8,
      mainBranchProbability: 0.5,
      totalBranches: 8,
      maxDepthReached: 3
    };
    
    const adjustment = calculateTreeExecutionAdjustment(highRisk);
    expect(adjustment).toBeLessThan(1);
  });

  it('should allow normal position for strong tree', () => {
    const strongTree: TreeStats = {
      dominanceScore: 0.8,
      uncertaintyScore: 0.2,
      treeRisk: 0.15,
      mainBranchProbability: 0.75,
      totalBranches: 4,
      maxDepthReached: 3
    };
    
    const adjustment = calculateTreeExecutionAdjustment(strongTree);
    expect(adjustment).toBeGreaterThanOrEqual(1);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 5: Risk Mode Recommendation
// ═══════════════════════════════════════════════════════════════

describe('Risk Mode Recommendation', () => {
  it('should recommend CONSERVATIVE for high uncertainty', () => {
    const highUncertainty: TreeStats = {
      dominanceScore: 0.3,
      uncertaintyScore: 0.7,
      treeRisk: 0.4,
      mainBranchProbability: 0.3,
      totalBranches: 10,
      maxDepthReached: 3
    };
    
    expect(getRecommendedRiskMode(highUncertainty)).toBe('CONSERVATIVE');
  });

  it('should recommend AGGRESSIVE for strong dominance', () => {
    const strongTree: TreeStats = {
      dominanceScore: 0.85,
      uncertaintyScore: 0.15,
      treeRisk: 0.2,
      mainBranchProbability: 0.8,
      totalBranches: 3,
      maxDepthReached: 3
    };
    
    expect(getRecommendedRiskMode(strongTree)).toBe('AGGRESSIVE');
  });

  it('should recommend NORMAL for balanced tree', () => {
    const balancedTree: TreeStats = {
      dominanceScore: 0.55,
      uncertaintyScore: 0.45,
      treeRisk: 0.35,
      mainBranchProbability: 0.5,
      totalBranches: 5,
      maxDepthReached: 3
    };
    
    expect(getRecommendedRiskMode(balancedTree)).toBe('NORMAL');
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 6: Trading Recommendation
// ═══════════════════════════════════════════════════════════════

describe('Trading Recommendation', () => {
  it('should not recommend trade for very high uncertainty', () => {
    const veryUncertain: TreeStats = {
      dominanceScore: 0.15,
      uncertaintyScore: 0.85,
      treeRisk: 0.6,
      mainBranchProbability: 0.2,
      totalBranches: 15,
      maxDepthReached: 3
    };
    
    const recommendation = getTradingRecommendation(veryUncertain);
    expect(recommendation.trade).toBe(false);
  });

  it('should recommend trade for strong tree', () => {
    const strongTree: TreeStats = {
      dominanceScore: 0.8,
      uncertaintyScore: 0.2,
      treeRisk: 0.2,
      mainBranchProbability: 0.75,
      totalBranches: 4,
      maxDepthReached: 3
    };
    
    const recommendation = getTradingRecommendation(strongTree);
    expect(recommendation.trade).toBe(true);
    expect(recommendation.confidence).toBeGreaterThan(0.7);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 7: Tree Utilities
// ═══════════════════════════════════════════════════════════════

describe('Tree Utilities', () => {
  it('should get main branch', () => {
    const tree = buildBranchTree(mockTwinState);
    const mainBranch = getMainBranch(tree);
    
    expect(mainBranch).not.toBeNull();
    
    // Main branch should have highest probability
    for (const branch of tree.branches) {
      expect(mainBranch!.probability).toBeGreaterThanOrEqual(branch.probability);
    }
  });

  it('should get leaf nodes', () => {
    const tree = buildBranchTree(mockTwinState);
    const leaves = getLeafNodes(tree);
    
    expect(leaves.length).toBeGreaterThan(0);
    
    // Leaf nodes should have no children
    for (const leaf of leaves) {
      expect(leaf.children).toBeUndefined();
    }
  });

  it('should calculate tree entropy', () => {
    const tree = buildBranchTree(mockTwinState);
    const entropy = calculateTreeEntropy(tree);
    
    expect(entropy).toBeGreaterThanOrEqual(0);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 8: Alternative Branch Analysis
// ═══════════════════════════════════════════════════════════════

describe('Alternative Branch Analysis', () => {
  it('should separate main from alternatives', () => {
    const tree = buildBranchTree(mockTwinState);
    const analysis = analyzeAlternativeBranches(tree);
    
    expect(analysis.mainBranch).not.toBeNull();
    expect(analysis.alternatives.length).toBe(tree.branches.length - 1);
  });

  it('should calculate scenario break probability', () => {
    const tree = buildBranchTree(mockTwinState);
    const breakProb = calculateScenarioBreakProbability(tree);
    
    expect(breakProb).toBeGreaterThanOrEqual(0);
    expect(breakProb).toBeLessThanOrEqual(1);
  });
});
