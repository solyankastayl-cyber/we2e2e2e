/**
 * DT5 — Branch Tree Builder
 * 
 * Builds market simulation tree from Digital Twin state
 * Models future market paths 2-4 steps ahead
 */

import {
  DigitalTwinState,
  TwinTreeNode,
  TwinBranchTree,
  TreeConfig,
  DEFAULT_TREE_CONFIG
} from './digital_twin.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';

// ═══════════════════════════════════════════════════════════════
// STATE TRANSITIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Valid state transitions and their base probabilities
 */
const STATE_TRANSITIONS: Record<MarketStateNode, Array<{ state: MarketStateNode; prob: number; event: string }>> = {
  'COMPRESSION': [
    { state: 'BREAKOUT_ATTEMPT', prob: 0.45, event: 'BREAKOUT_INIT' },
    { state: 'BALANCE', prob: 0.30, event: 'STABILIZE' },
    { state: 'LIQUIDITY_SWEEP', prob: 0.15, event: 'LIQUIDITY_HUNT' },
    { state: 'REVERSAL', prob: 0.10, event: 'EARLY_REVERSAL' }
  ],
  'BREAKOUT_ATTEMPT': [
    { state: 'BREAKOUT', prob: 0.50, event: 'BREAKOUT_CONFIRM' },
    { state: 'FALSE_BREAKOUT', prob: 0.30, event: 'BREAKOUT_FAIL' },
    { state: 'RETEST', prob: 0.20, event: 'RETEST_INIT' }
  ],
  'BREAKOUT': [
    { state: 'EXPANSION', prob: 0.55, event: 'EXPANSION_START' },
    { state: 'RETEST', prob: 0.30, event: 'RETEST_NEEDED' },
    { state: 'FALSE_BREAKOUT', prob: 0.15, event: 'LATE_FAILURE' }
  ],
  'FALSE_BREAKOUT': [
    { state: 'RANGE', prob: 0.45, event: 'RANGE_RETURN' },
    { state: 'REVERSAL', prob: 0.35, event: 'REVERSAL_INIT' },
    { state: 'COMPRESSION', prob: 0.20, event: 'RECOMPRESS' }
  ],
  'RETEST': [
    { state: 'EXPANSION', prob: 0.50, event: 'RETEST_HOLD' },
    { state: 'FALSE_BREAKOUT', prob: 0.30, event: 'RETEST_FAIL' },
    { state: 'CONTINUATION', prob: 0.20, event: 'CONTINUE' }
  ],
  'EXPANSION': [
    { state: 'CONTINUATION', prob: 0.45, event: 'TREND_CONTINUE' },
    { state: 'EXHAUSTION', prob: 0.35, event: 'EXHAUST' },
    { state: 'REVERSAL', prob: 0.20, event: 'EXPANSION_REVERSAL' }
  ],
  'LIQUIDITY_SWEEP': [
    { state: 'REVERSAL', prob: 0.50, event: 'SWEEP_REVERSAL' },
    { state: 'CONTINUATION', prob: 0.30, event: 'SWEEP_CONTINUE' },
    { state: 'RANGE', prob: 0.20, event: 'SWEEP_RANGE' }
  ],
  'REVERSAL': [
    { state: 'EXPANSION', prob: 0.45, event: 'REVERSAL_EXPANSION' },
    { state: 'RANGE', prob: 0.35, event: 'REVERSAL_RANGE' },
    { state: 'FALSE_BREAKOUT', prob: 0.20, event: 'REVERSAL_FAIL' }
  ],
  'RANGE': [
    { state: 'COMPRESSION', prob: 0.40, event: 'COMPRESS' },
    { state: 'BREAKOUT_ATTEMPT', prob: 0.35, event: 'RANGE_BREAK' },
    { state: 'BALANCE', prob: 0.25, event: 'BALANCE_HOLD' }
  ],
  'BALANCE': [
    { state: 'COMPRESSION', prob: 0.40, event: 'START_COMPRESS' },
    { state: 'RANGE', prob: 0.35, event: 'ENTER_RANGE' },
    { state: 'BREAKOUT_ATTEMPT', prob: 0.25, event: 'BREAK_BALANCE' }
  ],
  'EXHAUSTION': [
    { state: 'REVERSAL', prob: 0.55, event: 'EXHAUST_REVERSAL' },
    { state: 'RANGE', prob: 0.30, event: 'EXHAUST_RANGE' },
    { state: 'CONTINUATION', prob: 0.15, event: 'EXHAUST_PUSH' }
  ],
  'CONTINUATION': [
    { state: 'EXPANSION', prob: 0.45, event: 'EXPAND_MORE' },
    { state: 'EXHAUSTION', prob: 0.35, event: 'TIRE_OUT' },
    { state: 'RETEST', prob: 0.20, event: 'PULLBACK' }
  ]
};

// ═══════════════════════════════════════════════════════════════
// MOVE ATR EXPECTATIONS
// ═══════════════════════════════════════════════════════════════

const STATE_MOVE_ATR: Record<MarketStateNode, number> = {
  'COMPRESSION': 0.5,
  'BREAKOUT_ATTEMPT': 0.8,
  'BREAKOUT': 1.5,
  'FALSE_BREAKOUT': 1.2,
  'RETEST': 0.7,
  'EXPANSION': 2.5,
  'LIQUIDITY_SWEEP': 1.8,
  'REVERSAL': 2.0,
  'RANGE': 0.6,
  'BALANCE': 0.4,
  'EXHAUSTION': 1.0,
  'CONTINUATION': 2.0
};

// ═══════════════════════════════════════════════════════════════
// TREE BUILDER
// ═══════════════════════════════════════════════════════════════

let nodeCounter = 0;

/**
 * Build branch tree from Digital Twin state
 */
export function buildBranchTree(
  twin: DigitalTwinState,
  config: TreeConfig = DEFAULT_TREE_CONFIG
): TwinBranchTree {
  nodeCounter = 0;
  
  const rootState = twin.marketState;
  
  // Build tree recursively
  const branches = buildTreeLevel(
    rootState,
    1.0, // Start with 100% probability
    0,   // Current depth
    config
  );
  
  // Calculate tree stats
  const treeStats = calculateTreeStats(branches, rootState, config);
  
  return {
    asset: twin.asset,
    timeframe: twin.timeframe,
    ts: twin.ts,
    rootState,
    depth: config.maxDepth,
    branches,
    treeStats
  };
}

/**
 * Build one level of tree recursively
 */
function buildTreeLevel(
  currentState: MarketStateNode,
  parentProbability: number,
  currentDepth: number,
  config: TreeConfig
): TwinTreeNode[] {
  if (currentDepth >= config.maxDepth) {
    return [];
  }
  
  const transitions = STATE_TRANSITIONS[currentState] || [];
  const nodes: TwinTreeNode[] = [];
  
  // Sort by probability and take top N
  const sortedTransitions = [...transitions]
    .sort((a, b) => b.prob - a.prob)
    .slice(0, config.maxChildrenPerNode);
  
  for (const transition of sortedTransitions) {
    const nodeProbability = parentProbability * transition.prob;
    
    // Pruning: skip low probability branches
    if (nodeProbability < config.minBranchProbability) {
      continue;
    }
    
    const nodeId = `n${++nodeCounter}`;
    const expectedMoveATR = STATE_MOVE_ATR[transition.state] || 1.0;
    const failureRisk = calculateNodeFailureRisk(transition.state, nodeProbability);
    
    // Recursively build children
    const children = buildTreeLevel(
      transition.state,
      nodeProbability,
      currentDepth + 1,
      config
    );
    
    nodes.push({
      nodeId,
      state: transition.state,
      event: transition.event,
      probability: Math.round(nodeProbability * 100) / 100,
      expectedMoveATR,
      failureRisk: Math.round(failureRisk * 100) / 100,
      children: children.length > 0 ? children : undefined
    });
  }
  
  return nodes;
}

/**
 * Calculate failure risk for a node
 */
function calculateNodeFailureRisk(state: MarketStateNode, probability: number): number {
  // High-risk states
  const highRiskStates: MarketStateNode[] = ['FALSE_BREAKOUT', 'REVERSAL', 'EXHAUSTION'];
  
  if (highRiskStates.includes(state)) {
    return Math.min(1, probability + 0.2);
  }
  
  return 1 - probability;
}

// ═══════════════════════════════════════════════════════════════
// TREE STATS
// ═══════════════════════════════════════════════════════════════

import { TreeStats } from './digital_twin.types.js';

/**
 * Calculate tree statistics
 */
export function calculateTreeStats(
  branches: TwinTreeNode[],
  rootState: MarketStateNode,
  config: TreeConfig
): TreeStats {
  if (branches.length === 0) {
    return {
      dominanceScore: 1,
      uncertaintyScore: 0,
      treeRisk: 0,
      mainBranchProbability: 1,
      totalBranches: 0,
      maxDepthReached: 0
    };
  }
  
  // Get all probabilities at first level
  const firstLevelProbs = branches.map(b => b.probability);
  const totalProb = firstLevelProbs.reduce((sum, p) => sum + p, 0);
  
  // Dominance: how much the top branch dominates
  const maxProb = Math.max(...firstLevelProbs);
  const dominanceScore = totalProb > 0 ? maxProb / totalProb : 0;
  
  // Uncertainty: 1 - dominance (or entropy-based)
  const uncertaintyScore = 1 - dominanceScore;
  
  // Tree risk: sum of failure risks weighted by probability
  let treeRisk = 0;
  let totalBranches = 0;
  let maxDepthReached = 0;
  
  const traverseForStats = (nodes: TwinTreeNode[], depth: number) => {
    for (const node of nodes) {
      treeRisk += node.failureRisk * node.probability;
      totalBranches++;
      maxDepthReached = Math.max(maxDepthReached, depth);
      
      if (node.children) {
        traverseForStats(node.children, depth + 1);
      }
    }
  };
  
  traverseForStats(branches, 1);
  
  // Normalize tree risk
  treeRisk = totalBranches > 0 ? treeRisk / totalBranches : 0;
  
  // Main branch probability
  const mainBranchProbability = maxProb;
  
  return {
    dominanceScore: Math.round(dominanceScore * 100) / 100,
    uncertaintyScore: Math.round(uncertaintyScore * 100) / 100,
    treeRisk: Math.round(treeRisk * 100) / 100,
    mainBranchProbability: Math.round(mainBranchProbability * 100) / 100,
    totalBranches,
    maxDepthReached
  };
}

// ═══════════════════════════════════════════════════════════════
// TREE UTILITIES
// ═══════════════════════════════════════════════════════════════

/**
 * Get main branch (highest probability path)
 */
export function getMainBranch(tree: TwinBranchTree): TwinTreeNode | null {
  if (tree.branches.length === 0) return null;
  
  return tree.branches.reduce((max, node) => 
    node.probability > max.probability ? node : max
  );
}

/**
 * Get all leaf nodes (terminal paths)
 */
export function getLeafNodes(tree: TwinBranchTree): TwinTreeNode[] {
  const leaves: TwinTreeNode[] = [];
  
  const traverse = (nodes: TwinTreeNode[]) => {
    for (const node of nodes) {
      if (!node.children || node.children.length === 0) {
        leaves.push(node);
      } else {
        traverse(node.children);
      }
    }
  };
  
  traverse(tree.branches);
  return leaves;
}

/**
 * Get path to specific node
 */
export function getPathToNode(
  tree: TwinBranchTree,
  targetNodeId: string
): MarketStateNode[] {
  const path: MarketStateNode[] = [tree.rootState];
  
  const findPath = (nodes: TwinTreeNode[], currentPath: MarketStateNode[]): boolean => {
    for (const node of nodes) {
      const newPath = [...currentPath, node.state];
      
      if (node.nodeId === targetNodeId) {
        path.push(...newPath.slice(1));
        return true;
      }
      
      if (node.children && findPath(node.children, newPath)) {
        return true;
      }
    }
    return false;
  };
  
  findPath(tree.branches, path);
  return path;
}

/**
 * Calculate tree entropy (measure of uncertainty)
 */
export function calculateTreeEntropy(tree: TwinBranchTree): number {
  const probs = tree.branches.map(b => b.probability);
  const total = probs.reduce((sum, p) => sum + p, 0);
  
  if (total === 0) return 0;
  
  let entropy = 0;
  for (const p of probs) {
    const normalized = p / total;
    if (normalized > 0) {
      entropy -= normalized * Math.log2(normalized);
    }
  }
  
  return Math.round(entropy * 100) / 100;
}
