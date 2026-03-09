/**
 * MetaBrain v2.1 — Module Attribution Computation
 * 
 * Computes edge contribution of each analysis module
 */

import {
  AnalysisModule,
  ALL_MODULES,
  ModuleContribution,
  ModuleAttributionResult,
  AttributionTradeRecord,
  LearningConfig,
  DEFAULT_LEARNING_CONFIG
} from './module_attribution.types.js';

// ═══════════════════════════════════════════════════════════════
// STATISTICS HELPERS
// ═══════════════════════════════════════════════════════════════

function calcWinRate(records: AttributionTradeRecord[]): number {
  if (records.length === 0) return 0.5;
  const wins = records.filter(r => r.outcome === 'WIN').length;
  return wins / records.length;
}

function calcAvgR(records: AttributionTradeRecord[]): number {
  if (records.length === 0) return 0;
  return records.reduce((sum, r) => sum + r.resultR, 0) / records.length;
}

function calcProfitFactor(records: AttributionTradeRecord[]): number {
  const grossWin = records.filter(r => r.resultR > 0).reduce((sum, r) => sum + r.resultR, 0);
  const grossLoss = Math.abs(records.filter(r => r.resultR < 0).reduce((sum, r) => sum + r.resultR, 0));
  if (grossLoss === 0) return grossWin > 0 ? 10 : 1;
  return grossWin / grossLoss;
}

function calcSharpe(records: AttributionTradeRecord[]): number {
  if (records.length < 2) return 0;
  const returns = records.map(r => r.resultR);
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / (returns.length - 1);
  const std = Math.sqrt(variance);
  if (std === 0) return 0;
  return (mean / std) * Math.sqrt(252);  // Annualized
}

// ═══════════════════════════════════════════════════════════════
// MODULE FILTERING
// ═══════════════════════════════════════════════════════════════

/**
 * Filter trades where a specific module had high activation
 */
export function filterByModuleActivation(
  records: AttributionTradeRecord[],
  module: AnalysisModule,
  minBoost: number = 0.5
): AttributionTradeRecord[] {
  return records.filter(r => {
    const activation = r.moduleActivations.find(a => a.module === module);
    return activation && activation.boost >= minBoost;
  });
}

/**
 * Split trades by module activation level
 */
export function splitByActivation(
  records: AttributionTradeRecord[],
  module: AnalysisModule
): { high: AttributionTradeRecord[]; low: AttributionTradeRecord[] } {
  const high: AttributionTradeRecord[] = [];
  const low: AttributionTradeRecord[] = [];
  
  for (const record of records) {
    const activation = record.moduleActivations.find(a => a.module === module);
    if (activation && activation.boost >= 0.5) {
      high.push(record);
    } else {
      low.push(record);
    }
  }
  
  return { high, low };
}

// ═══════════════════════════════════════════════════════════════
// EDGE SCORE CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate edge score for a module
 * Scale: 0-3 where 1.5 is neutral
 */
export function calculateEdgeScore(
  winRate: number,
  profitFactor: number,
  avgR: number,
  sampleSize: number,
  config: LearningConfig = DEFAULT_LEARNING_CONFIG
): number {
  // Base score from metrics
  let score = 1.5;  // Neutral
  
  // Win rate contribution (WR 50% -> 0, WR 55% -> +0.25, WR 60% -> +0.5)
  score += (winRate - 0.5) * 2.5;
  
  // Profit factor contribution (PF 1 -> 0, PF 1.3 -> +0.3, PF 1.5 -> +0.5)
  score += Math.min(0.8, (profitFactor - 1) * 1);
  
  // Avg R contribution (R 0 -> 0, R 0.3 -> +0.15, R 0.5 -> +0.25)
  score += Math.min(0.3, avgR * 0.5);
  
  // Sample size confidence adjustment
  const sampleConfidence = Math.min(1, sampleSize / (config.minSampleSize * 2));
  
  // Shrink toward neutral based on sample size
  const shrunkScore = 1.5 + (score - 1.5) * sampleConfidence;
  
  // Clamp to 0-3
  return Math.max(0, Math.min(3, shrunkScore));
}

// ═══════════════════════════════════════════════════════════════
// MAIN ATTRIBUTION COMPUTATION
// ═══════════════════════════════════════════════════════════════

/**
 * Compute module attribution from trade records
 */
export function computeModuleAttribution(
  records: AttributionTradeRecord[],
  config: LearningConfig = DEFAULT_LEARNING_CONFIG,
  options?: {
    asset?: string;
    timeframe?: string;
    regime?: string;
  }
): ModuleAttributionResult {
  
  // Calculate global baseline
  const baseline = {
    winRate: calcWinRate(records),
    avgR: calcAvgR(records),
    profitFactor: calcProfitFactor(records),
    totalTrades: records.length
  };
  
  // Calculate per-module contributions
  const moduleContributions: ModuleContribution[] = [];
  
  for (const module of ALL_MODULES) {
    // Filter trades with high module activation
    const highActivation = filterByModuleActivation(records, module, 0.5);
    
    if (highActivation.length < config.minSampleSize) {
      // Not enough data, use neutral contribution
      moduleContributions.push({
        module,
        winRate: baseline.winRate,
        avgR: baseline.avgR,
        profitFactor: baseline.profitFactor,
        sharpe: 0,
        sampleSize: highActivation.length,
        confidence: highActivation.length / config.minSampleSize,
        edgeScore: 1.5,  // Neutral
        impact: 'NEUTRAL',
        calculatedAt: new Date()
      });
      continue;
    }
    
    // Calculate metrics for high-activation trades
    const winRate = calcWinRate(highActivation);
    const avgR = calcAvgR(highActivation);
    const profitFactor = calcProfitFactor(highActivation);
    const sharpe = calcSharpe(highActivation);
    
    // Calculate edge score
    const edgeScore = calculateEdgeScore(winRate, profitFactor, avgR, highActivation.length, config);
    
    // Determine impact direction
    let impact: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE' = 'NEUTRAL';
    if (edgeScore > 1.8) impact = 'POSITIVE';
    else if (edgeScore < 1.2) impact = 'NEGATIVE';
    
    // Confidence based on sample size
    const confidence = Math.min(1, highActivation.length / (config.minSampleSize * 2));
    
    moduleContributions.push({
      module,
      winRate,
      avgR,
      profitFactor,
      sharpe,
      sampleSize: highActivation.length,
      confidence,
      edgeScore,
      impact,
      calculatedAt: new Date()
    });
  }
  
  // Sort by edge score
  const sorted = [...moduleContributions].sort((a, b) => b.edgeScore - a.edgeScore);
  
  // Get top and weak modules
  const topModules = sorted
    .filter(m => m.impact === 'POSITIVE' && m.confidence >= 0.5)
    .map(m => m.module);
  
  const weakModules = sorted
    .filter(m => m.impact === 'NEGATIVE' && m.confidence >= 0.5)
    .map(m => m.module);
  
  return {
    asset: options?.asset,
    timeframe: options?.timeframe,
    regime: options?.regime,
    baseline,
    modules: moduleContributions,
    topModules,
    weakModules,
    calculatedAt: new Date(),
    dataWindowDays: config.dataWindowDays
  };
}

// ═══════════════════════════════════════════════════════════════
// DIFFERENTIAL ATTRIBUTION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate the differential impact of a module
 * by comparing high vs low activation trades
 */
export function computeDifferentialAttribution(
  records: AttributionTradeRecord[],
  module: AnalysisModule,
  config: LearningConfig = DEFAULT_LEARNING_CONFIG
): {
  module: AnalysisModule;
  highActivation: { pf: number; winRate: number; avgR: number; n: number };
  lowActivation: { pf: number; winRate: number; avgR: number; n: number };
  differential: number;
  confidence: number;
} {
  const { high, low } = splitByActivation(records, module);
  
  const highPF = calcProfitFactor(high);
  const lowPF = calcProfitFactor(low);
  
  // Differential: how much better is high activation
  const differential = high.length >= 10 && low.length >= 10
    ? highPF / lowPF
    : 1;
  
  const totalSample = Math.min(high.length, low.length);
  const confidence = Math.min(1, totalSample / config.minSampleSize);
  
  return {
    module,
    highActivation: {
      pf: highPF,
      winRate: calcWinRate(high),
      avgR: calcAvgR(high),
      n: high.length
    },
    lowActivation: {
      pf: lowPF,
      winRate: calcWinRate(low),
      avgR: calcAvgR(low),
      n: low.length
    },
    differential,
    confidence
  };
}
