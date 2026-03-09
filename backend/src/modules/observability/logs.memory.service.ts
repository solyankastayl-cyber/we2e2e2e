/**
 * Phase 4 — Memory Logs Service
 * ===============================
 * Logs memory engine matches and historical analogies
 */

import { v4 as uuidv4 } from 'uuid';
import { MemoryLog, MemoryMatch } from './observability.types.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY STORAGE
// ═══════════════════════════════════════════════════════════════

const memoryLogs: MemoryLog[] = [];

// Seed demo data
const seedMemoryLogs = () => {
  const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
  const contexts = ['COMPRESSION_PRE_BREAKOUT', 'LIQUIDITY_SWEEP', 'TREND_CONTINUATION', 'REVERSAL_PATTERN'];
  const biases: MemoryLog['bias'][] = ['BULL', 'BEAR', 'NEUTRAL'];
  
  const historicalDates = [
    '2024-11-15', '2024-08-22', '2023-12-18', '2023-06-05',
    '2022-11-09', '2022-04-17', '2021-09-07', '2021-05-19',
  ];
  
  const now = Date.now();
  
  for (let i = 0; i < 25; i++) {
    const matchCount = 5 + Math.floor(Math.random() * 20);
    const topMatches: MemoryMatch[] = [];
    
    for (let j = 0; j < Math.min(5, matchCount); j++) {
      topMatches.push({
        historicalDate: historicalDates[Math.floor(Math.random() * historicalDates.length)],
        similarity: Math.round((0.6 + Math.random() * 0.35) * 100) / 100,
        outcome: Math.random() > 0.4 ? 'BULLISH' : 'BEARISH',
        returnPct: Math.round((Math.random() * 20 - 5) * 100) / 100,
      });
    }
    
    memoryLogs.push({
      id: `mem_${uuidv4().slice(0, 8)}`,
      symbol: symbols[i % symbols.length],
      timestamp: now - (25 - i) * 3600000,
      queryContext: contexts[Math.floor(Math.random() * contexts.length)],
      matchCount,
      topMatches,
      bias: biases[Math.floor(Math.random() * biases.length)],
      avgSimilarity: Math.round((topMatches.reduce((s, m) => s + m.similarity, 0) / topMatches.length) * 100) / 100,
      memoryBoost: Math.round((0.9 + Math.random() * 0.3) * 100) / 100,
    });
  }
};

seedMemoryLogs();

// ═══════════════════════════════════════════════════════════════
// LOG FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Log memory query
 */
export function logMemoryQuery(
  symbol: string,
  queryContext: string,
  matchCount: number,
  topMatches: MemoryMatch[],
  bias: MemoryLog['bias'],
  memoryBoost: number
): MemoryLog {
  const avgSimilarity = topMatches.length > 0
    ? Math.round((topMatches.reduce((s, m) => s + m.similarity, 0) / topMatches.length) * 100) / 100
    : 0;
  
  const log: MemoryLog = {
    id: `mem_${uuidv4().slice(0, 8)}`,
    symbol,
    timestamp: Date.now(),
    queryContext,
    matchCount,
    topMatches,
    bias,
    avgSimilarity,
    memoryBoost,
  };
  
  memoryLogs.push(log);
  
  if (memoryLogs.length > 300) {
    memoryLogs.shift();
  }
  
  return log;
}

/**
 * Get memory logs
 */
export function getMemoryLogs(options: {
  symbol?: string;
  limit?: number;
} = {}): MemoryLog[] {
  let filtered = [...memoryLogs];
  
  if (options.symbol) {
    filtered = filtered.filter(l => l.symbol === options.symbol);
  }
  
  filtered.sort((a, b) => b.timestamp - a.timestamp);
  
  return filtered.slice(0, options.limit || 50);
}

/**
 * Get memory stats
 */
export function getMemoryStats(): {
  totalQueries: number;
  avgMatchCount: number;
  avgSimilarity: number;
  biasDist: Record<string, number>;
} {
  const biasDist: Record<string, number> = { BULL: 0, BEAR: 0, NEUTRAL: 0 };
  
  for (const log of memoryLogs) {
    biasDist[log.bias]++;
  }
  
  return {
    totalQueries: memoryLogs.length,
    avgMatchCount: memoryLogs.length > 0
      ? Math.round(memoryLogs.reduce((s, l) => s + l.matchCount, 0) / memoryLogs.length)
      : 0,
    avgSimilarity: memoryLogs.length > 0
      ? Math.round((memoryLogs.reduce((s, l) => s + l.avgSimilarity, 0) / memoryLogs.length) * 100) / 100
      : 0,
    biasDist,
  };
}
