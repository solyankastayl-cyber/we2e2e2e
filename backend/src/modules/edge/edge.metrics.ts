/**
 * Edge Metrics (P5.0.3)
 * 
 * Statistical metrics and shrinkage calculations
 */

import type { EdgeRow, GlobalBaseline } from './domain/types.js';

/**
 * Shrinkage configuration
 */
export const SHRINKAGE_CONFIG = {
  priorWeight: 50,        // Weight for global baseline
  minSampleForRaw: 100,   // Min samples to use raw metric
  minSampleForEdge: 30,   // Min samples to compute edge
};

/**
 * Calculate win rate
 */
export function calcWinRate(rows: EdgeRow[]): number {
  if (rows.length === 0) return 0;
  
  const wins = rows.filter(r => 
    r.outcomeClass === 'WIN' || r.outcomeClass === 'PARTIAL'
  ).length;
  
  return wins / rows.length;
}

/**
 * Calculate average R
 */
export function calcAvgR(rows: EdgeRow[]): number {
  if (rows.length === 0) return 0;
  return rows.reduce((sum, r) => sum + r.realizedR, 0) / rows.length;
}

/**
 * Calculate median R
 */
export function calcMedianR(rows: EdgeRow[]): number {
  if (rows.length === 0) return 0;
  
  const sorted = [...rows].sort((a, b) => a.realizedR - b.realizedR);
  const mid = Math.floor(sorted.length / 2);
  
  return sorted.length % 2 === 0
    ? (sorted[mid - 1].realizedR + sorted[mid].realizedR) / 2
    : sorted[mid].realizedR;
}

/**
 * Calculate percentile R
 */
export function calcPercentileR(rows: EdgeRow[], percentile: number): number {
  if (rows.length === 0) return 0;
  
  const sorted = [...rows].sort((a, b) => a.realizedR - b.realizedR);
  const index = Math.floor((percentile / 100) * (sorted.length - 1));
  
  return sorted[index].realizedR;
}

/**
 * Calculate average EV
 */
export function calcAvgEV(rows: EdgeRow[]): number {
  if (rows.length === 0) return 0;
  return rows.reduce((sum, r) => sum + r.ev, 0) / rows.length;
}

/**
 * Calculate edge (avgR - avgEV)
 */
export function calcEdge(rows: EdgeRow[]): number {
  return calcAvgR(rows) - calcAvgEV(rows);
}

/**
 * Calculate profit factor
 */
export function calcProfitFactor(rows: EdgeRow[]): number {
  const wins = rows.filter(r => r.realizedR > 0);
  const losses = rows.filter(r => r.realizedR < 0);
  
  const totalWins = wins.reduce((sum, r) => sum + r.realizedR, 0);
  const totalLosses = Math.abs(losses.reduce((sum, r) => sum + r.realizedR, 0));
  
  if (totalLosses === 0) return totalWins > 0 ? 10 : 0;
  return totalWins / totalLosses;
}

/**
 * Calculate max drawdown on R
 */
export function calcMaxDrawdownR(rows: EdgeRow[]): number {
  if (rows.length === 0) return 0;
  
  let cumulative = 0;
  let peak = 0;
  let maxDrawdown = 0;
  
  for (const row of rows) {
    cumulative += row.realizedR;
    if (cumulative > peak) peak = cumulative;
    const drawdown = peak - cumulative;
    if (drawdown > maxDrawdown) maxDrawdown = drawdown;
  }
  
  return maxDrawdown;
}

/**
 * Calculate Sharpe-like ratio on R
 */
export function calcSharpeR(rows: EdgeRow[]): number {
  if (rows.length < 2) return 0;
  
  const avgR = calcAvgR(rows);
  const variance = rows.reduce((sum, r) => sum + Math.pow(r.realizedR - avgR, 2), 0) / rows.length;
  const stdR = Math.sqrt(variance);
  
  if (stdR === 0) return 0;
  return avgR / stdR;
}

/**
 * Calculate correlation between EV and realized R
 */
export function calcEVCorrelation(rows: EdgeRow[]): number {
  if (rows.length < 3) return 0;
  
  const evValues = rows.map(r => r.ev);
  const rValues = rows.map(r => r.realizedR);
  
  const meanEV = evValues.reduce((a, b) => a + b, 0) / evValues.length;
  const meanR = rValues.reduce((a, b) => a + b, 0) / rValues.length;
  
  let numerator = 0;
  let denomEV = 0;
  let denomR = 0;
  
  for (let i = 0; i < rows.length; i++) {
    const devEV = evValues[i] - meanEV;
    const devR = rValues[i] - meanR;
    numerator += devEV * devR;
    denomEV += devEV * devEV;
    denomR += devR * devR;
  }
  
  const denom = Math.sqrt(denomEV * denomR);
  if (denom === 0) return 0;
  
  return numerator / denom;
}

/**
 * Apply shrinkage to metric
 */
export function shrink(
  metric: number,
  sampleSize: number,
  globalMetric: number,
  priorWeight: number = SHRINKAGE_CONFIG.priorWeight
): number {
  if (sampleSize >= SHRINKAGE_CONFIG.minSampleForRaw) {
    return metric;
  }
  
  return (sampleSize * metric + priorWeight * globalMetric) / (sampleSize + priorWeight);
}

/**
 * Calculate edge score (composite metric)
 */
export function calcEdgeScore(
  avgR: number,
  winRate: number,
  sampleSize: number,
  stabilityMultiplier: number = 1.0
): number {
  if (sampleSize < SHRINKAGE_CONFIG.minSampleForEdge) {
    return 0;
  }
  
  // Edge score formula
  // avgR * winRate * log(sampleSize) * stability
  const sampleFactor = Math.log10(Math.max(10, sampleSize));
  
  return avgR * winRate * sampleFactor * stabilityMultiplier;
}

/**
 * Calculate global baseline from all rows
 */
export function calcGlobalBaseline(rows: EdgeRow[]): GlobalBaseline {
  return {
    totalSamples: rows.length,
    globalWinRate: calcWinRate(rows),
    globalAvgR: calcAvgR(rows),
    globalAvgEV: calcAvgEV(rows),
    globalPF: calcProfitFactor(rows)
  };
}

/**
 * Calculate outcome counts
 */
export function calcOutcomeCounts(rows: EdgeRow[]): {
  winCount: number;
  lossCount: number;
  partialCount: number;
  timeoutCount: number;
} {
  return {
    winCount: rows.filter(r => r.outcomeClass === 'WIN').length,
    lossCount: rows.filter(r => r.outcomeClass === 'LOSS').length,
    partialCount: rows.filter(r => r.outcomeClass === 'PARTIAL').length,
    timeoutCount: rows.filter(r => r.outcomeClass === 'TIMEOUT').length
  };
}
