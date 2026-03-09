/**
 * Phase 9 — Strategy Discovery Engine: Analyzer
 * 
 * Analyzes feature combinations and finds edge
 */

import {
  SignalRecord,
  FeatureCombination,
  AnyFeature,
  RegimeFeature,
  DiscoveryConfig,
  DEFAULT_DISCOVERY_CONFIG
} from './discovery.types.js';

/**
 * Generate all feature combinations up to maxSize
 */
function generateCombinations(
  features: AnyFeature[],
  maxSize: number
): AnyFeature[][] {
  const combinations: AnyFeature[][] = [];
  
  function generate(current: AnyFeature[], startIdx: number) {
    if (current.length > 0 && current.length <= maxSize) {
      combinations.push([...current]);
    }
    
    if (current.length >= maxSize) return;
    
    for (let i = startIdx; i < features.length; i++) {
      current.push(features[i]);
      generate(current, i + 1);
      current.pop();
    }
  }
  
  generate([], 0);
  return combinations;
}

/**
 * Check if signal has all required features
 */
function signalHasFeatures(signal: SignalRecord, features: AnyFeature[]): boolean {
  return features.every(f => signal.features.includes(f));
}

/**
 * Calculate statistics for a set of signals
 */
function calculateStats(signals: SignalRecord[]): {
  winRate: number;
  avgRMultiple: number;
  profitFactor: number;
  maxDrawdown: number;
  sharpeRatio: number;
  edge: number;
} {
  if (signals.length === 0) {
    return { winRate: 0, avgRMultiple: 0, profitFactor: 0, maxDrawdown: 0, sharpeRatio: 0, edge: 0 };
  }
  
  const wins = signals.filter(s => s.outcome.result === 'WIN');
  const losses = signals.filter(s => s.outcome.result === 'LOSS');
  
  const winRate = wins.length / signals.length;
  
  const avgWin = wins.length > 0 
    ? wins.reduce((sum, s) => sum + s.outcome.rMultiple, 0) / wins.length 
    : 0;
  const avgLoss = losses.length > 0 
    ? Math.abs(losses.reduce((sum, s) => sum + s.outcome.rMultiple, 0) / losses.length)
    : 0;
  
  const avgRMultiple = signals.reduce((sum, s) => sum + s.outcome.rMultiple, 0) / signals.length;
  
  const totalWin = wins.reduce((sum, s) => sum + Math.abs(s.outcome.pnl), 0);
  const totalLoss = losses.reduce((sum, s) => sum + Math.abs(s.outcome.pnl), 0);
  const profitFactor = totalLoss > 0 ? totalWin / totalLoss : totalWin > 0 ? 10 : 0;
  
  // Calculate drawdown
  let peak = 0;
  let maxDrawdown = 0;
  let cumulative = 0;
  
  for (const signal of signals) {
    cumulative += signal.outcome.pnl;
    peak = Math.max(peak, cumulative);
    const drawdown = (peak - cumulative) / Math.max(peak, 1);
    maxDrawdown = Math.max(maxDrawdown, drawdown);
  }
  
  // Sharpe ratio approximation
  const returns = signals.map(s => s.outcome.rMultiple);
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length;
  const stdDev = Math.sqrt(variance);
  const sharpeRatio = stdDev > 0 ? avgReturn / stdDev : 0;
  
  // Edge = expected value
  const edge = winRate * avgWin - (1 - winRate) * avgLoss;
  
  return { winRate, avgRMultiple, profitFactor, maxDrawdown, sharpeRatio, edge };
}

/**
 * Analyze feature combinations
 */
export function analyzeFeatureCombinations(
  signals: SignalRecord[],
  config: DiscoveryConfig = DEFAULT_DISCOVERY_CONFIG
): FeatureCombination[] {
  // Collect all unique features
  const allFeatures = new Set<AnyFeature>();
  for (const signal of signals) {
    for (const feature of signal.features) {
      allFeatures.add(feature);
    }
  }
  
  // Generate combinations
  const featureArray = Array.from(allFeatures);
  const combinations = generateCombinations(featureArray, config.maxFeatureCombinationSize);
  
  // Analyze each combination
  const results: FeatureCombination[] = [];
  
  for (const combo of combinations) {
    // Find signals with this combination
    const matchingSignals = signals.filter(s => signalHasFeatures(s, combo));
    
    if (matchingSignals.length < config.minSampleSize) continue;
    
    const stats = calculateStats(matchingSignals);
    
    // Calculate regime breakdown
    const regimes: RegimeFeature[] = ['TREND_UP', 'TREND_DOWN', 'RANGE'];
    const regimePerformance: any = {};
    
    for (const regime of regimes) {
      const regimeSignals = matchingSignals.filter(s => s.regime === regime);
      if (regimeSignals.length > 0) {
        const regimeStats = calculateStats(regimeSignals);
        regimePerformance[regime] = {
          winRate: regimeStats.winRate,
          sampleSize: regimeSignals.length
        };
      }
    }
    
    // Calculate direction breakdown
    const longSignals = matchingSignals.filter(s => s.direction === 'LONG');
    const shortSignals = matchingSignals.filter(s => s.direction === 'SHORT');
    
    const directionPerformance = {
      LONG: {
        winRate: longSignals.length > 0 ? calculateStats(longSignals).winRate : 0,
        sampleSize: longSignals.length
      },
      SHORT: {
        winRate: shortSignals.length > 0 ? calculateStats(shortSignals).winRate : 0,
        sampleSize: shortSignals.length
      }
    };
    
    // Calculate confidence (based on sample size)
    const edgeConfidence = Math.min(1, matchingSignals.length / 100);
    
    results.push({
      id: `combo_${combo.join('_')}`,
      features: combo,
      sampleSize: matchingSignals.length,
      winRate: stats.winRate,
      avgRMultiple: stats.avgRMultiple,
      profitFactor: stats.profitFactor,
      maxDrawdown: stats.maxDrawdown,
      sharpeRatio: stats.sharpeRatio,
      edge: stats.edge,
      edgeConfidence,
      regimePerformance,
      directionPerformance,
      firstSeen: Math.min(...matchingSignals.map(s => s.timestamp)),
      lastSeen: Math.max(...matchingSignals.map(s => s.timestamp))
    });
  }
  
  // Filter by thresholds and sort by edge
  return results
    .filter(c => 
      c.winRate >= config.minWinRate &&
      c.profitFactor >= config.minProfitFactor &&
      c.edge >= config.minEdge
    )
    .sort((a, b) => b.edge - a.edge);
}

/**
 * Find top feature combinations
 */
export function findTopCombinations(
  signals: SignalRecord[],
  topN: number = 10,
  config: DiscoveryConfig = DEFAULT_DISCOVERY_CONFIG
): FeatureCombination[] {
  const all = analyzeFeatureCombinations(signals, config);
  return all.slice(0, topN);
}

/**
 * Analyze single feature performance
 */
export function analyzeFeatures(
  signals: SignalRecord[]
): Record<AnyFeature, { winRate: number; sampleSize: number; edge: number }> {
  const featureStats: Record<string, { wins: number; total: number; rSum: number }> = {};
  
  for (const signal of signals) {
    for (const feature of signal.features) {
      if (!featureStats[feature]) {
        featureStats[feature] = { wins: 0, total: 0, rSum: 0 };
      }
      
      featureStats[feature].total++;
      if (signal.outcome.result === 'WIN') {
        featureStats[feature].wins++;
      }
      featureStats[feature].rSum += signal.outcome.rMultiple;
    }
  }
  
  const result: Record<string, { winRate: number; sampleSize: number; edge: number }> = {};
  
  for (const [feature, stats] of Object.entries(featureStats)) {
    const winRate = stats.total > 0 ? stats.wins / stats.total : 0;
    const avgR = stats.total > 0 ? stats.rSum / stats.total : 0;
    
    result[feature as AnyFeature] = {
      winRate,
      sampleSize: stats.total,
      edge: avgR
    };
  }
  
  return result as Record<AnyFeature, { winRate: number; sampleSize: number; edge: number }>;
}
