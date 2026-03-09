/**
 * Phase 2.5 — Market Map Tree Builder
 * =====================================
 * Builds market simulation tree from current state
 * Models future market paths 2-4 steps ahead
 * 
 * Tree structure:
 *   current
 *     ├ breakout 62%
 *     │   └ expansion
 *     └ fakeout 28%
 *         └ range
 */

import { MarketState, TreeNode, MarketTreeResponse } from './market_map.types.js';

// ═══════════════════════════════════════════════════════════════
// STATE TRANSITIONS
// ═══════════════════════════════════════════════════════════════

interface StateTransition {
  to: MarketState;
  probability: number;
  event: string;
}

/**
 * State transition matrix
 * Defines what states can follow from each state
 */
const STATE_TRANSITIONS: Record<MarketState, StateTransition[]> = {
  COMPRESSION: [
    { to: 'BREAKOUT', probability: 0.45, event: 'breakout_init' },
    { to: 'RANGE', probability: 0.30, event: 'stabilize' },
    { to: 'LIQUIDITY_SWEEP', probability: 0.15, event: 'liquidity_hunt' },
    { to: 'REVERSAL', probability: 0.10, event: 'early_reversal' },
  ],
  BREAKOUT: [
    { to: 'EXPANSION', probability: 0.55, event: 'momentum_surge' },
    { to: 'RETEST', probability: 0.30, event: 'pullback' },
    { to: 'REVERSAL', probability: 0.15, event: 'failure' },
  ],
  EXPANSION: [
    { to: 'CONTINUATION', probability: 0.45, event: 'trend_continue' },
    { to: 'EXHAUSTION', probability: 0.35, event: 'exhaust' },
    { to: 'REVERSAL', probability: 0.20, event: 'top_reversal' },
  ],
  RANGE: [
    { to: 'COMPRESSION', probability: 0.40, event: 'compress' },
    { to: 'BREAKOUT', probability: 0.35, event: 'range_break' },
    { to: 'CONTINUATION', probability: 0.25, event: 'trend_resume' },
  ],
  EXHAUSTION: [
    { to: 'REVERSAL', probability: 0.55, event: 'exhaust_reversal' },
    { to: 'RANGE', probability: 0.30, event: 'consolidate' },
    { to: 'CONTINUATION', probability: 0.15, event: 'exhaust_push' },
  ],
  REVERSAL: [
    { to: 'EXPANSION', probability: 0.45, event: 'reversal_expansion' },
    { to: 'RANGE', probability: 0.35, event: 'reversal_range' },
    { to: 'BREAKOUT', probability: 0.20, event: 'reversal_break' },
  ],
  CONTINUATION: [
    { to: 'EXPANSION', probability: 0.45, event: 'expand_more' },
    { to: 'EXHAUSTION', probability: 0.35, event: 'tire_out' },
    { to: 'RETEST', probability: 0.20, event: 'pullback' },
  ],
  LIQUIDITY_SWEEP: [
    { to: 'REVERSAL', probability: 0.50, event: 'sweep_reversal' },
    { to: 'CONTINUATION', probability: 0.30, event: 'sweep_continue' },
    { to: 'RANGE', probability: 0.20, event: 'sweep_range' },
  ],
  RETEST: [
    { to: 'EXPANSION', probability: 0.50, event: 'retest_hold' },
    { to: 'REVERSAL', probability: 0.30, event: 'retest_fail' },
    { to: 'CONTINUATION', probability: 0.20, event: 'continue' },
  ],
};

// ═══════════════════════════════════════════════════════════════
// MOVE EXPECTATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Expected move in ATR units for each state
 */
const STATE_MOVE_ATR: Record<MarketState, number> = {
  COMPRESSION: 0.5,
  BREAKOUT: 1.5,
  EXPANSION: 2.5,
  RANGE: 0.6,
  EXHAUSTION: 1.0,
  REVERSAL: 2.0,
  CONTINUATION: 2.0,
  LIQUIDITY_SWEEP: 1.8,
  RETEST: 0.7,
};

// ═══════════════════════════════════════════════════════════════
// TREE BUILDER
// ═══════════════════════════════════════════════════════════════

let nodeCounter = 0;

/**
 * Build tree recursively
 */
function buildTreeLevel(
  currentState: MarketState,
  parentProbability: number,
  depth: number,
  maxDepth: number,
  minProbability: number
): TreeNode[] {
  if (depth >= maxDepth) {
    return [];
  }
  
  const transitions = STATE_TRANSITIONS[currentState] || [];
  const nodes: TreeNode[] = [];
  
  // Sort by probability descending and take top 3
  const sortedTransitions = [...transitions]
    .sort((a, b) => b.probability - a.probability)
    .slice(0, 3);
  
  for (const transition of sortedTransitions) {
    const nodeProbability = parentProbability * transition.probability;
    
    // Prune low probability branches
    if (nodeProbability < minProbability) {
      continue;
    }
    
    const nodeId = `n${++nodeCounter}`;
    const expectedMove = STATE_MOVE_ATR[transition.to] || 1.0;
    
    // Recursively build children
    const children = buildTreeLevel(
      transition.to,
      nodeProbability,
      depth + 1,
      maxDepth,
      minProbability
    );
    
    nodes.push({
      id: nodeId,
      state: transition.to,
      probability: Math.round(nodeProbability * 100) / 100,
      expectedMove,
      children: children.length > 0 ? children : undefined,
    });
  }
  
  return nodes;
}

/**
 * Build market tree from current state
 */
export function buildMarketTree(
  symbol: string,
  timeframe: string,
  rootState: MarketState,
  maxDepth: number = 3,
  minProbability: number = 0.05
): MarketTreeResponse {
  nodeCounter = 0;
  
  const branches = buildTreeLevel(
    rootState,
    1.0, // Start with 100% probability
    0,
    maxDepth,
    minProbability
  );
  
  // Calculate total nodes and max depth
  let totalNodes = 0;
  let actualMaxDepth = 0;
  
  const countNodes = (nodes: TreeNode[], depth: number) => {
    for (const node of nodes) {
      totalNodes++;
      actualMaxDepth = Math.max(actualMaxDepth, depth);
      if (node.children) {
        countNodes(node.children, depth + 1);
      }
    }
  };
  
  countNodes(branches, 1);
  
  // Get dominance path (highest probability path)
  const dominancePath = getMainPath(branches);
  
  return {
    symbol,
    timeframe,
    ts: Date.now(),
    root: rootState,
    branches,
    stats: {
      totalNodes,
      maxDepth: actualMaxDepth,
      dominancePath,
    },
  };
}

/**
 * Get main path (highest probability path through tree)
 */
export function getMainPath(branches: TreeNode[]): string[] {
  if (branches.length === 0) {
    return [];
  }
  
  const path: string[] = [];
  
  // Find highest probability branch at each level
  let currentLevel = branches;
  
  while (currentLevel.length > 0) {
    const best = currentLevel.reduce((max, node) => 
      node.probability > max.probability ? node : max
    );
    
    path.push(best.state);
    currentLevel = best.children || [];
  }
  
  return path;
}

/**
 * Get all leaf nodes (terminal paths)
 */
export function getLeafNodes(branches: TreeNode[]): TreeNode[] {
  const leaves: TreeNode[] = [];
  
  const traverse = (nodes: TreeNode[]) => {
    for (const node of nodes) {
      if (!node.children || node.children.length === 0) {
        leaves.push(node);
      } else {
        traverse(node.children);
      }
    }
  };
  
  traverse(branches);
  return leaves;
}

/**
 * Calculate tree entropy (measure of uncertainty)
 */
export function calculateTreeEntropy(branches: TreeNode[]): number {
  const probs = branches.map(b => b.probability);
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
