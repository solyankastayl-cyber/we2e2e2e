/**
 * Phase 4 — Tree Logs Service
 * =============================
 * Logs scenario tree branches and decisions
 */

import { v4 as uuidv4 } from 'uuid';
import { TreeLog, TreeBranch } from './observability.types.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY STORAGE
// ═══════════════════════════════════════════════════════════════

const treeLogs: TreeLog[] = [];

// Seed demo data
const seedTreeLogs = () => {
  const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
  const rootStates = ['COMPRESSION', 'BREAKOUT', 'RANGE', 'EXPANSION', 'RETEST'];
  const scenarios = ['breakout', 'range', 'fakeout', 'continuation', 'reversal'];
  
  const now = Date.now();
  
  for (let i = 0; i < 20; i++) {
    const branches: TreeBranch[] = [];
    let remainingProb = 1.0;
    
    const numBranches = 3 + Math.floor(Math.random() * 3);
    for (let j = 0; j < numBranches; j++) {
      const prob = j === numBranches - 1 
        ? remainingProb 
        : Math.round(Math.random() * remainingProb * 0.6 * 100) / 100;
      remainingProb -= prob;
      
      branches.push({
        scenario: scenarios[j % scenarios.length],
        probability: prob,
        expectedMove: Math.round((0.5 + Math.random() * 2.5) * 10) / 10,
        confidence: Math.round((0.5 + Math.random() * 0.4) * 100) / 100,
      });
    }
    
    branches.sort((a, b) => b.probability - a.probability);
    
    treeLogs.push({
      id: `tree_${uuidv4().slice(0, 8)}`,
      symbol: symbols[i % symbols.length],
      timestamp: now - (20 - i) * 3600000,
      rootState: rootStates[Math.floor(Math.random() * rootStates.length)],
      branches,
      dominantPath: [branches[0]?.scenario || 'unknown', 'expansion'],
      entropy: Math.round(Math.random() * 0.8 * 100) / 100,
    });
  }
};

seedTreeLogs();

// ═══════════════════════════════════════════════════════════════
// LOG FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Log tree computation
 */
export function logTree(
  symbol: string,
  rootState: string,
  branches: TreeBranch[],
  dominantPath: string[],
  entropy: number
): TreeLog {
  const log: TreeLog = {
    id: `tree_${uuidv4().slice(0, 8)}`,
    symbol,
    timestamp: Date.now(),
    rootState,
    branches,
    dominantPath,
    entropy,
  };
  
  treeLogs.push(log);
  
  if (treeLogs.length > 200) {
    treeLogs.shift();
  }
  
  return log;
}

/**
 * Get tree logs
 */
export function getTreeLogs(options: {
  symbol?: string;
  limit?: number;
} = {}): TreeLog[] {
  let filtered = [...treeLogs];
  
  if (options.symbol) {
    filtered = filtered.filter(l => l.symbol === options.symbol);
  }
  
  filtered.sort((a, b) => b.timestamp - a.timestamp);
  
  return filtered.slice(0, options.limit || 50);
}

/**
 * Get tree stats
 */
export function getTreeStats(): {
  totalTrees: number;
  avgEntropy: number;
  avgBranches: number;
  rootStateDist: Record<string, number>;
  dominantScenarioDist: Record<string, number>;
} {
  const rootStateDist: Record<string, number> = {};
  const dominantScenarioDist: Record<string, number> = {};
  
  for (const log of treeLogs) {
    rootStateDist[log.rootState] = (rootStateDist[log.rootState] || 0) + 1;
    const dominant = log.branches[0]?.scenario;
    if (dominant) {
      dominantScenarioDist[dominant] = (dominantScenarioDist[dominant] || 0) + 1;
    }
  }
  
  return {
    totalTrees: treeLogs.length,
    avgEntropy: treeLogs.length > 0
      ? Math.round((treeLogs.reduce((s, l) => s + l.entropy, 0) / treeLogs.length) * 100) / 100
      : 0,
    avgBranches: treeLogs.length > 0
      ? Math.round(treeLogs.reduce((s, l) => s + l.branches.length, 0) / treeLogs.length)
      : 0,
    rootStateDist,
    dominantScenarioDist,
  };
}
