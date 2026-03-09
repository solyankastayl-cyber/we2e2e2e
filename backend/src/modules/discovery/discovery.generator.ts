/**
 * Phase 9 — Strategy Discovery Engine: Generator
 * 
 * Generates trading strategies from discovered combinations
 */

import {
  SignalRecord,
  FeatureCombination,
  GeneratedStrategy,
  SetupCluster,
  AnyFeature,
  RegimeFeature,
  DiscoveryConfig,
  DEFAULT_DISCOVERY_CONFIG
} from './discovery.types.js';
import { analyzeFeatureCombinations } from './discovery.analyzer.js';

let strategyCounter = 0;

/**
 * Generate strategy name from features
 */
function generateStrategyName(features: AnyFeature[]): string {
  const parts = features.slice(0, 3).map(f => 
    f.replace(/_/g, ' ').split(' ').map(w => w.charAt(0)).join('')
  );
  return `AUTO_${parts.join('_')}_${++strategyCounter}`;
}

/**
 * Calculate strategy robustness (consistency across regimes)
 */
function calculateRobustness(
  regimePerformance: Record<RegimeFeature, { winRate: number; sampleSize: number }>
): number {
  const regimes: RegimeFeature[] = ['TREND_UP', 'TREND_DOWN', 'RANGE'];
  const winRates: number[] = [];
  
  for (const regime of regimes) {
    const perf = regimePerformance[regime];
    if (perf && perf.sampleSize >= 10) {
      winRates.push(perf.winRate);
    }
  }
  
  if (winRates.length < 2) return 0.5;  // Not enough data
  
  // Calculate variance in win rates
  const avg = winRates.reduce((a, b) => a + b, 0) / winRates.length;
  const variance = winRates.reduce((sum, r) => sum + Math.pow(r - avg, 2), 0) / winRates.length;
  
  // Lower variance = higher robustness
  return Math.max(0, 1 - variance * 4);  // Scale to 0-1
}

/**
 * Calculate strategy stability (consistency over time)
 */
function calculateStability(signals: SignalRecord[]): number {
  if (signals.length < 20) return 0.5;
  
  // Split into halves
  const sorted = [...signals].sort((a, b) => a.timestamp - b.timestamp);
  const mid = Math.floor(sorted.length / 2);
  const firstHalf = sorted.slice(0, mid);
  const secondHalf = sorted.slice(mid);
  
  const firstWinRate = firstHalf.filter(s => s.outcome.result === 'WIN').length / firstHalf.length;
  const secondWinRate = secondHalf.filter(s => s.outcome.result === 'WIN').length / secondHalf.length;
  
  // Compare win rates
  const diff = Math.abs(firstWinRate - secondWinRate);
  
  return Math.max(0, 1 - diff * 3);  // Scale to 0-1
}

/**
 * Generate strategy from feature combination
 */
export function generateStrategy(
  combination: FeatureCombination,
  matchingSignals: SignalRecord[],
  config: DiscoveryConfig = DEFAULT_DISCOVERY_CONFIG
): GeneratedStrategy {
  // Split data for in-sample / out-of-sample
  const sorted = [...matchingSignals].sort((a, b) => a.timestamp - b.timestamp);
  const splitIdx = Math.floor(sorted.length * 0.7);
  const inSample = sorted.slice(0, splitIdx);
  const outOfSample = sorted.slice(splitIdx);
  
  const inSampleWinRate = inSample.filter(s => s.outcome.result === 'WIN').length / inSample.length;
  const outOfSampleWinRate = outOfSample.length > 0 
    ? outOfSample.filter(s => s.outcome.result === 'WIN').length / outOfSample.length
    : 0;
  
  // Calculate robustness and stability
  const robustness = calculateRobustness(combination.regimePerformance);
  const stability = calculateStability(matchingSignals);
  
  // Calculate confidence
  const sampleConfidence = Math.min(1, combination.sampleSize / 100);
  const performanceConfidence = combination.winRate > 0.6 ? 1 : combination.winRate / 0.6;
  const confidence = (sampleConfidence * 0.3 + robustness * 0.3 + stability * 0.2 + performanceConfidence * 0.2);
  
  // Determine best direction
  let direction: 'LONG' | 'SHORT' | 'BOTH' = 'BOTH';
  const longWR = combination.directionPerformance.LONG.winRate;
  const shortWR = combination.directionPerformance.SHORT.winRate;
  
  if (longWR > shortWR + 0.1 && combination.directionPerformance.LONG.sampleSize >= 20) {
    direction = 'LONG';
  } else if (shortWR > longWR + 0.1 && combination.directionPerformance.SHORT.sampleSize >= 20) {
    direction = 'SHORT';
  }
  
  // Determine best regimes
  const bestRegimes: RegimeFeature[] = [];
  for (const [regime, perf] of Object.entries(combination.regimePerformance)) {
    if (perf.winRate >= config.minWinRate && perf.sampleSize >= 10) {
      bestRegimes.push(regime as RegimeFeature);
    }
  }
  
  // Build regime breakdown
  const regimeBreakdown: Record<RegimeFeature, { winRate: number; profitFactor: number; trades: number }> = 
    {} as any;
  
  for (const [regime, perf] of Object.entries(combination.regimePerformance)) {
    regimeBreakdown[regime as RegimeFeature] = {
      winRate: perf.winRate,
      profitFactor: combination.profitFactor,  // Simplified
      trades: perf.sampleSize
    };
  }
  
  // Determine status based on thresholds
  let status: 'CANDIDATE' | 'TESTING' | 'APPROVED' = 'CANDIDATE';
  
  if (combination.sampleSize >= config.strategyMinTrades &&
      combination.winRate >= config.strategyMinWinRate &&
      robustness >= config.strategyMinRobustness &&
      confidence >= config.strategyMinConfidence) {
    status = 'APPROVED';
  } else if (combination.sampleSize >= config.minSampleSize) {
    status = 'TESTING';
  }
  
  return {
    id: `strat_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
    name: generateStrategyName(combination.features),
    
    rules: {
      required: combination.features,
      preferred: [],
      excluded: [],
      direction,
      regimes: bestRegimes.length > 0 ? bestRegimes : undefined
    },
    
    metrics: {
      winRate: combination.winRate,
      avgRMultiple: combination.avgRMultiple,
      profitFactor: combination.profitFactor,
      maxDrawdown: combination.maxDrawdown,
      sharpeRatio: combination.sharpeRatio,
      trades: combination.sampleSize,
      inSampleWinRate,
      outOfSampleWinRate
    },
    
    confidence,
    robustness,
    stability,
    
    regimeBreakdown,
    
    status,
    
    sourceCombination: combination.id,
    
    discoveredAt: Date.now(),
    lastTestedAt: Date.now()
  };
}

/**
 * Generate strategies from all top combinations
 */
export function generateStrategies(
  signals: SignalRecord[],
  config: DiscoveryConfig = DEFAULT_DISCOVERY_CONFIG
): GeneratedStrategy[] {
  // Find top combinations
  const combinations = analyzeFeatureCombinations(signals, config);
  
  // Generate strategies for top combinations
  const strategies: GeneratedStrategy[] = [];
  
  for (const combo of combinations.slice(0, config.maxAutoStrategies)) {
    // Find matching signals
    const matchingSignals = signals.filter(s => 
      combo.features.every(f => s.features.includes(f))
    );
    
    if (matchingSignals.length >= config.minSampleSize) {
      strategies.push(generateStrategy(combo, matchingSignals, config));
    }
  }
  
  // Sort by confidence
  return strategies.sort((a, b) => b.confidence - a.confidence);
}

/**
 * Cluster similar strategies
 */
export function clusterStrategies(strategies: GeneratedStrategy[]): SetupCluster[] {
  if (strategies.length === 0) return [];
  
  const clusters: SetupCluster[] = [];
  const used = new Set<string>();
  
  for (const strategy of strategies) {
    if (used.has(strategy.id)) continue;
    
    // Find similar strategies
    const similar = strategies.filter(s => {
      if (s.id === strategy.id || used.has(s.id)) return false;
      
      // Calculate feature overlap
      const overlap = strategy.rules.required.filter(f => 
        s.rules.required.includes(f)
      ).length;
      
      const minLen = Math.min(strategy.rules.required.length, s.rules.required.length);
      const similarity = minLen > 0 ? overlap / minLen : 0;
      
      return similarity >= 0.5;
    });
    
    // Create cluster
    const clusterMembers = [strategy, ...similar];
    clusterMembers.forEach(s => used.add(s.id));
    
    // Find core features (present in all members)
    const coreFeatures = strategy.rules.required.filter(f =>
      clusterMembers.every(m => m.rules.required.includes(f))
    );
    
    // Find optional features (present in some)
    const allFeatures = new Set<AnyFeature>();
    clusterMembers.forEach(m => m.rules.required.forEach(f => allFeatures.add(f)));
    const optionalFeatures = Array.from(allFeatures).filter(f => !coreFeatures.includes(f));
    
    // Calculate cluster stats
    const avgWinRate = clusterMembers.reduce((sum, s) => sum + s.metrics.winRate, 0) / clusterMembers.length;
    const avgRMultiple = clusterMembers.reduce((sum, s) => sum + s.metrics.avgRMultiple, 0) / clusterMembers.length;
    const avgPF = clusterMembers.reduce((sum, s) => sum + s.metrics.profitFactor, 0) / clusterMembers.length;
    const totalTrades = clusterMembers.reduce((sum, s) => sum + s.metrics.trades, 0);
    
    clusters.push({
      id: `cluster_${clusters.length + 1}`,
      name: `${coreFeatures.slice(0, 2).join(' + ')} Strategies`,
      description: `Strategies based on ${coreFeatures.join(', ')}`,
      coreFeatures,
      optionalFeatures,
      sampleSize: totalTrades,
      winRate: avgWinRate,
      avgRMultiple,
      profitFactor: avgPF,
      memberSignals: [],  // Not tracking individual signals here
      coherence: coreFeatures.length / (coreFeatures.length + optionalFeatures.length),
      stability: clusterMembers.reduce((sum, s) => sum + s.stability, 0) / clusterMembers.length
    });
  }
  
  return clusters;
}
