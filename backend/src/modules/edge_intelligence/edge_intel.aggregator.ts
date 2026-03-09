/**
 * Phase 7 — Edge Aggregator
 * 
 * Aggregates edge statistics by dimension
 */

import {
  EdgeRecord,
  EdgeStats,
  EdgeDimension,
  EdgeIntelligenceConfig,
  DEFAULT_EDGE_CONFIG
} from './edge_intel.types.js';
import { groupByDimension } from './edge_intel.extractor.js';

// ═══════════════════════════════════════════════════════════════
// STATISTICAL CALCULATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate win rate
 */
export function calcWinRate(records: EdgeRecord[]): number {
  if (records.length === 0) return 0;
  const wins = records.filter(r => r.outcome === 'WIN').length;
  return wins / records.length;
}

/**
 * Calculate average R
 */
export function calcAvgR(records: EdgeRecord[]): number {
  if (records.length === 0) return 0;
  return records.reduce((sum, r) => sum + r.resultR, 0) / records.length;
}

/**
 * Calculate median R
 */
export function calcMedianR(records: EdgeRecord[]): number {
  if (records.length === 0) return 0;
  const sorted = [...records].sort((a, b) => a.resultR - b.resultR);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1].resultR + sorted[mid].resultR) / 2
    : sorted[mid].resultR;
}

/**
 * Calculate profit factor
 */
export function calcProfitFactor(records: EdgeRecord[]): number {
  const grossWin = records
    .filter(r => r.resultR > 0)
    .reduce((sum, r) => sum + r.resultR, 0);
  const grossLoss = Math.abs(
    records
      .filter(r => r.resultR < 0)
      .reduce((sum, r) => sum + r.resultR, 0)
  );
  
  if (grossLoss === 0) return grossWin > 0 ? 10 : 1;
  return grossWin / grossLoss;
}

/**
 * Calculate Sharpe ratio of R values
 */
export function calcSharpe(records: EdgeRecord[]): number {
  if (records.length < 2) return 0;
  
  const avgR = calcAvgR(records);
  const variance = records.reduce((sum, r) => sum + Math.pow(r.resultR - avgR, 2), 0) / records.length;
  const stdDev = Math.sqrt(variance);
  
  if (stdDev === 0) return avgR > 0 ? 3 : 0;
  return avgR / stdDev;
}

/**
 * Calculate maximum drawdown in R terms
 */
export function calcMaxDD(records: EdgeRecord[]): number {
  if (records.length === 0) return 0;
  
  let peak = 0;
  let cumulative = 0;
  let maxDD = 0;
  
  for (const record of records) {
    cumulative += record.resultR;
    if (cumulative > peak) peak = cumulative;
    const dd = peak - cumulative;
    if (dd > maxDD) maxDD = dd;
  }
  
  return maxDD;
}

/**
 * Calculate edge score (composite metric)
 */
export function calcEdgeScore(
  winRate: number,
  avgR: number,
  profitFactor: number,
  sampleSize: number,
  config: EdgeIntelligenceConfig = DEFAULT_EDGE_CONFIG
): number {
  // Sample size factor (penalize small samples)
  const sampleFactor = Math.min(1, sampleSize / (config.minSampleSize * 2));
  
  // Win rate component (deviation from 50%)
  const wrComponent = (winRate - 0.5) * 2;
  
  // PF component (log scale)
  const pfComponent = profitFactor > 1 
    ? Math.log(profitFactor) / Math.log(3) 
    : -(Math.log(1 / profitFactor) / Math.log(3));
  
  // R component
  const rComponent = avgR;
  
  // Weighted combination
  const rawScore = (wrComponent * 0.3 + pfComponent * 0.4 + rComponent * 0.3) * sampleFactor;
  
  return Math.max(-1, Math.min(1, rawScore));
}

/**
 * Shrink estimate toward global baseline
 */
export function shrinkEstimate(
  observed: number,
  globalBaseline: number,
  sampleSize: number,
  strength: number = 0.5
): number {
  // Shrinkage factor decreases with sample size
  const shrinkage = strength / (1 + sampleSize / 100);
  return observed * (1 - shrinkage) + globalBaseline * shrinkage;
}

// ═══════════════════════════════════════════════════════════════
// AGGREGATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate stats for a group of records
 */
export function calculateGroupStats(
  dimension: EdgeDimension,
  key: string,
  records: EdgeRecord[],
  globalBaseline: { winRate: number; avgR: number; profitFactor: number },
  config: EdgeIntelligenceConfig = DEFAULT_EDGE_CONFIG
): EdgeStats | null {
  if (records.length < config.minSampleSize) {
    return null;
  }
  
  const wins = records.filter(r => r.outcome === 'WIN').length;
  const losses = records.filter(r => r.outcome === 'LOSS').length;
  const breakevens = records.filter(r => r.outcome === 'BREAKEVEN').length;
  
  const winRate = calcWinRate(records);
  const avgR = calcAvgR(records);
  const medianR = calcMedianR(records);
  const profitFactor = calcProfitFactor(records);
  const sharpe = calcSharpe(records);
  const maxDD = calcMaxDD(records);
  
  const edgeScore = calcEdgeScore(winRate, avgR, profitFactor, records.length, config);
  const edgeShrunk = shrinkEstimate(edgeScore, 0, records.length, config.shrinkageStrength);
  
  // Statistical significance (simple t-test approximation)
  const tStat = records.length > 1 ? avgR / (Math.sqrt(calcSharpe(records) || 0.01) / Math.sqrt(records.length)) : 0;
  const significance = Math.min(1, Math.abs(tStat) / 2);
  
  return {
    dimension,
    key,
    sampleSize: records.length,
    wins,
    losses,
    breakevens,
    winRate,
    avgR,
    medianR,
    profitFactor,
    sharpe,
    maxDD,
    edgeScore,
    edgeShrunk,
    confidence: Math.min(1, records.length / (config.minSampleSize * 3)),
    statisticalSignificance: significance,
    updatedAt: new Date()
  };
}

/**
 * Aggregate stats by dimension
 */
export function aggregateByDimension(
  records: EdgeRecord[],
  dimension: EdgeDimension,
  globalBaseline: { winRate: number; avgR: number; profitFactor: number },
  config: EdgeIntelligenceConfig = DEFAULT_EDGE_CONFIG
): EdgeStats[] {
  const groups = groupByDimension(records, dimension);
  const stats: EdgeStats[] = [];
  
  for (const [key, groupRecords] of groups) {
    const groupStats = calculateGroupStats(dimension, key, groupRecords, globalBaseline, config);
    if (groupStats) {
      stats.push(groupStats);
    }
  }
  
  // Sort by edge score
  return stats.sort((a, b) => b.edgeScore - a.edgeScore);
}

/**
 * Aggregate all dimensions
 */
export function aggregateAllDimensions(
  records: EdgeRecord[],
  globalBaseline: { winRate: number; avgR: number; profitFactor: number },
  config: EdgeIntelligenceConfig = DEFAULT_EDGE_CONFIG
): Map<EdgeDimension, EdgeStats[]> {
  const dimensions: EdgeDimension[] = [
    'PATTERN',
    'STATE',
    'FRACTAL',
    'SCENARIO',
    'LIQUIDITY',
    'MARKET_STATE',
    'TIMEFRAME',
    'ASSET'
  ];
  
  const results = new Map<EdgeDimension, EdgeStats[]>();
  
  for (const dimension of dimensions) {
    const stats = aggregateByDimension(records, dimension, globalBaseline, config);
    results.set(dimension, stats);
  }
  
  return results;
}

/**
 * Get top performers across all dimensions
 */
export function getTopPerformers(
  allStats: Map<EdgeDimension, EdgeStats[]>,
  count: number = 10
): EdgeStats[] {
  const all: EdgeStats[] = [];
  
  for (const stats of allStats.values()) {
    all.push(...stats);
  }
  
  return all
    .sort((a, b) => b.edgeScore - a.edgeScore)
    .slice(0, count);
}

/**
 * Get worst performers across all dimensions
 */
export function getWorstPerformers(
  allStats: Map<EdgeDimension, EdgeStats[]>,
  count: number = 10
): EdgeStats[] {
  const all: EdgeStats[] = [];
  
  for (const stats of allStats.values()) {
    all.push(...stats);
  }
  
  return all
    .sort((a, b) => a.edgeScore - b.edgeScore)
    .slice(0, count);
}
