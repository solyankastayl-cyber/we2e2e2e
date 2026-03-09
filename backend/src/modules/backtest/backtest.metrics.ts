/**
 * Phase 5.1 B1.4 — Backtest Metrics Engine
 * 
 * Calculates all backtest statistics from trade results.
 */

import { BacktestTradeDoc, BacktestSummary, EquityCurvePoint } from './domain/types.js';

// ═══════════════════════════════════════════════════════════════
// Main Metrics Function
// ═══════════════════════════════════════════════════════════════

export function computeBacktestSummary(
  trades: BacktestTradeDoc[]
): BacktestSummary {
  // Filter executed trades (entry hit)
  const executedTrades = trades.filter(t => t.exitType !== 'NO_ENTRY');
  const noEntryTrades = trades.filter(t => t.exitType === 'NO_ENTRY');
  
  // Counts
  const wins = executedTrades.filter(t => t.exitType === 'T1' || t.exitType === 'T2').length;
  const losses = executedTrades.filter(t => t.exitType === 'STOP').length;
  const timeouts = executedTrades.filter(t => t.exitType === 'TIMEOUT').length;
  const partials = executedTrades.filter(t => t.exitType === 'PARTIAL').length;
  
  // Win rate (wins / (wins + losses))
  const winRate = (wins + losses) > 0 ? wins / (wins + losses) : 0;
  
  // R metrics
  const rMultiples = executedTrades.map(t => t.rMultiple);
  const avgR = rMultiples.length > 0 
    ? rMultiples.reduce((a, b) => a + b, 0) / rMultiples.length 
    : 0;
  
  // Profit Factor
  const positiveR = rMultiples.filter(r => r > 0);
  const negativeR = rMultiples.filter(r => r < 0);
  const sumPositive = positiveR.reduce((a, b) => a + b, 0);
  const sumNegative = Math.abs(negativeR.reduce((a, b) => a + b, 0));
  const profitFactor = sumNegative > 0 ? sumPositive / sumNegative : sumPositive > 0 ? Infinity : 0;
  
  // Expectancy (same as avgR for simple case)
  const expectancy = avgR;
  
  // Sharpe Ratio in R terms
  const sharpeR = calculateSharpeR(rMultiples);
  
  // Equity curve and max drawdown
  const equityCurve = buildEquityCurve(executedTrades);
  const maxDrawdownR = calculateMaxDrawdown(equityCurve);
  
  // Timing averages
  const avgBarsToEntry = executedTrades.length > 0
    ? executedTrades.reduce((sum, t) => sum + t.barsToEntry, 0) / executedTrades.length
    : 0;
  const avgBarsToExit = executedTrades.length > 0
    ? executedTrades.reduce((sum, t) => sum + t.barsToExit, 0) / executedTrades.length
    : 0;
  
  // EV Correlation (key metric: does our EV predict actual R?)
  const evCorrelation = calculateEVCorrelation(executedTrades);
  
  return {
    trades: executedTrades.length,
    noEntry: noEntryTrades.length,
    wins,
    losses,
    timeouts,
    partials,
    
    winRate,
    avgR,
    profitFactor,
    expectancy,
    maxDrawdownR,
    sharpeR,
    
    equityCurve: {
      points: equityCurve.length,
      endR: equityCurve.length > 0 ? equityCurve[equityCurve.length - 1].cumulativeR : 0,
      peakR: equityCurve.length > 0 ? Math.max(...equityCurve.map(p => p.cumulativeR)) : 0,
    },
    
    avgBarsToEntry,
    avgBarsToExit,
    
    evCorrelation,
  };
}

// ═══════════════════════════════════════════════════════════════
// Helper Functions
// ═══════════════════════════════════════════════════════════════

/**
 * Build cumulative equity curve in R units
 */
function buildEquityCurve(trades: BacktestTradeDoc[]): EquityCurvePoint[] {
  const curve: EquityCurvePoint[] = [];
  let cumR = 0;
  
  // Sort by closed index
  const sorted = [...trades].sort((a, b) => a.closedAtIndex - b.closedAtIndex);
  
  for (let i = 0; i < sorted.length; i++) {
    cumR += sorted[i].rMultiple;
    curve.push({
      index: i,
      cumulativeR: cumR,
    });
  }
  
  return curve;
}

/**
 * Calculate max drawdown from equity curve
 */
function calculateMaxDrawdown(curve: EquityCurvePoint[]): number {
  if (curve.length === 0) return 0;
  
  let peak = 0;
  let maxDD = 0;
  
  for (const point of curve) {
    if (point.cumulativeR > peak) {
      peak = point.cumulativeR;
    }
    const drawdown = peak - point.cumulativeR;
    if (drawdown > maxDD) {
      maxDD = drawdown;
    }
  }
  
  return maxDD;
}

/**
 * Calculate Sharpe Ratio in R terms
 */
function calculateSharpeR(rMultiples: number[]): number {
  if (rMultiples.length < 2) return 0;
  
  const mean = rMultiples.reduce((a, b) => a + b, 0) / rMultiples.length;
  const variance = rMultiples.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / (rMultiples.length - 1);
  const std = Math.sqrt(variance);
  
  return std > 0 ? mean / std : 0;
}

/**
 * Calculate correlation between EV and realized R
 * Positive correlation = model works
 */
function calculateEVCorrelation(trades: BacktestTradeDoc[]): number {
  if (trades.length < 3) return 0;
  
  const evs = trades.map(t => t.decisionSnapshot?.ev || 0);
  const rs = trades.map(t => t.rMultiple);
  
  return pearsonCorrelation(evs, rs);
}

/**
 * Pearson correlation coefficient
 */
function pearsonCorrelation(x: number[], y: number[]): number {
  const n = x.length;
  if (n !== y.length || n < 2) return 0;
  
  const meanX = x.reduce((a, b) => a + b, 0) / n;
  const meanY = y.reduce((a, b) => a + b, 0) / n;
  
  let numerator = 0;
  let denomX = 0;
  let denomY = 0;
  
  for (let i = 0; i < n; i++) {
    const dx = x[i] - meanX;
    const dy = y[i] - meanY;
    numerator += dx * dy;
    denomX += dx * dx;
    denomY += dy * dy;
  }
  
  const denom = Math.sqrt(denomX * denomY);
  return denom > 0 ? numerator / denom : 0;
}

// ═══════════════════════════════════════════════════════════════
// Calibration Buckets (for future reliability analysis)
// ═══════════════════════════════════════════════════════════════

export interface CalibrationBucket {
  range: string;       // "0.4-0.5"
  predictedWin: number;
  actualWin: number;
  count: number;
  gap: number;         // predicted - actual
}

export function computeCalibrationBuckets(
  trades: BacktestTradeDoc[]
): CalibrationBucket[] {
  const buckets: Map<string, { total: number; wins: number; sumP: number }> = new Map();
  const ranges = ['0.0-0.4', '0.4-0.5', '0.5-0.6', '0.6-0.7', '0.7-0.8', '0.8-1.0'];
  
  // Initialize buckets
  for (const range of ranges) {
    buckets.set(range, { total: 0, wins: 0, sumP: 0 });
  }
  
  // Classify each trade
  for (const trade of trades) {
    if (trade.exitType === 'NO_ENTRY') continue;
    
    const p = trade.decisionSnapshot?.pEntry || 0;
    const isWin = trade.exitType === 'T1' || trade.exitType === 'T2';
    
    const range = getBucketRange(p, ranges);
    const bucket = buckets.get(range)!;
    bucket.total++;
    bucket.sumP += p;
    if (isWin) bucket.wins++;
  }
  
  // Build result
  const result: CalibrationBucket[] = [];
  for (const range of ranges) {
    const bucket = buckets.get(range)!;
    const predictedWin = bucket.total > 0 ? bucket.sumP / bucket.total : 0;
    const actualWin = bucket.total > 0 ? bucket.wins / bucket.total : 0;
    
    result.push({
      range,
      predictedWin,
      actualWin,
      count: bucket.total,
      gap: predictedWin - actualWin,
    });
  }
  
  return result;
}

function getBucketRange(p: number, ranges: string[]): string {
  if (p < 0.4) return '0.0-0.4';
  if (p < 0.5) return '0.4-0.5';
  if (p < 0.6) return '0.5-0.6';
  if (p < 0.7) return '0.6-0.7';
  if (p < 0.8) return '0.7-0.8';
  return '0.8-1.0';
}
