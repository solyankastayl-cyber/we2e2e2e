/**
 * Phase 9.5 — Edge Validation: Robustness Analyzer
 */

import {
  RegimeType,
  MarketType,
  RegimePerformance,
  MarketPerformance,
  RobustnessScore,
  EdgeValidationConfig,
  DEFAULT_EDGE_CONFIG,
  ALL_REGIMES,
  ALL_MARKETS
} from './edge.types.js';

/**
 * Analyze regime robustness
 */
export function analyzeRegimeRobustness(
  regimeData: RegimePerformance[],
  config: EdgeValidationConfig = DEFAULT_EDGE_CONFIG
): {
  score: number;
  strongRegimes: RegimeType[];
  weakRegimes: RegimeType[];
} {
  const strongRegimes: RegimeType[] = [];
  const weakRegimes: RegimeType[] = [];
  
  const validRegimes = regimeData.filter(r => r.trades >= config.minTradesPerRegime);
  
  if (validRegimes.length === 0) {
    return { score: 0, strongRegimes: [], weakRegimes: ALL_REGIMES };
  }
  
  for (const regime of validRegimes) {
    if (regime.winRate >= config.strongWinRate && regime.profitFactor >= config.minProfitFactor) {
      strongRegimes.push(regime.regime);
    } else if (regime.winRate < config.minWinRate || regime.profitFactor < 1.0) {
      weakRegimes.push(regime.regime);
    }
  }
  
  // Calculate consistency score
  const winRates = validRegimes.map(r => r.winRate);
  const avgWinRate = winRates.reduce((a, b) => a + b, 0) / winRates.length;
  const variance = winRates.reduce((sum, r) => sum + Math.pow(r - avgWinRate, 2), 0) / winRates.length;
  
  // Lower variance = higher robustness
  const consistencyScore = Math.max(0, 1 - variance * 10);
  
  // Coverage score (how many regimes have data)
  const coverageScore = validRegimes.length / ALL_REGIMES.length;
  
  // Strong regime score
  const strengthScore = strongRegimes.length / Math.max(1, validRegimes.length);
  
  // Combined score
  const score = consistencyScore * 0.4 + coverageScore * 0.3 + strengthScore * 0.3;
  
  return {
    score: Math.min(1, Math.max(0, score)),
    strongRegimes,
    weakRegimes
  };
}

/**
 * Analyze cross-market robustness
 */
export function analyzeMarketRobustness(
  marketData: MarketPerformance[],
  config: EdgeValidationConfig = DEFAULT_EDGE_CONFIG
): {
  score: number;
  validMarkets: MarketType[];
  failedMarkets: MarketType[];
} {
  const validMarkets: MarketType[] = [];
  const failedMarkets: MarketType[] = [];
  
  const testedMarkets = marketData.filter(m => m.trades >= config.minTradesPerMarket);
  
  if (testedMarkets.length === 0) {
    return { score: 0, validMarkets: [], failedMarkets: [] };
  }
  
  for (const market of testedMarkets) {
    if (market.winRate >= config.minWinRate && market.profitFactor >= config.minProfitFactor) {
      validMarkets.push(market.market);
    } else {
      failedMarkets.push(market.market);
    }
  }
  
  // Cross-market score
  const validRatio = validMarkets.length / testedMarkets.length;
  
  // Diversity bonus (more markets tested = higher score)
  const diversityBonus = Math.min(0.2, testedMarkets.length * 0.05);
  
  const score = validRatio * 0.8 + diversityBonus;
  
  return {
    score: Math.min(1, Math.max(0, score)),
    validMarkets,
    failedMarkets
  };
}

/**
 * Analyze stability over time (walk-forward style)
 */
export function analyzeStability(
  periodResults: number[],  // Win rates or PF per period
  config: EdgeValidationConfig = DEFAULT_EDGE_CONFIG
): {
  score: number;
  trend: 'IMPROVING' | 'STABLE' | 'DECLINING';
  walkForwardResults: number[];
} {
  if (periodResults.length < 2) {
    return { score: 0.5, trend: 'STABLE', walkForwardResults: periodResults };
  }
  
  // Calculate variance
  const avg = periodResults.reduce((a, b) => a + b, 0) / periodResults.length;
  const variance = periodResults.reduce((sum, r) => sum + Math.pow(r - avg, 2), 0) / periodResults.length;
  
  // Lower variance = higher stability
  const varianceScore = Math.max(0, 1 - variance * 5);
  
  // Trend analysis (compare first half vs second half)
  const mid = Math.floor(periodResults.length / 2);
  const firstHalf = periodResults.slice(0, mid);
  const secondHalf = periodResults.slice(mid);
  
  const firstAvg = firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length;
  const secondAvg = secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length;
  
  let trend: 'IMPROVING' | 'STABLE' | 'DECLINING' = 'STABLE';
  let trendScore = 1.0;
  
  if (secondAvg > firstAvg + 0.05) {
    trend = 'IMPROVING';
    trendScore = 1.1;  // Bonus
  } else if (secondAvg < firstAvg - 0.05) {
    trend = 'DECLINING';
    trendScore = 0.8;  // Penalty
  }
  
  const score = varianceScore * trendScore;
  
  return {
    score: Math.min(1, Math.max(0, score)),
    trend,
    walkForwardResults: periodResults
  };
}

/**
 * Build complete robustness score
 */
export function buildRobustnessScore(
  regimeData: RegimePerformance[],
  marketData: MarketPerformance[],
  periodResults: number[],
  config: EdgeValidationConfig = DEFAULT_EDGE_CONFIG
): RobustnessScore {
  const regimeAnalysis = analyzeRegimeRobustness(regimeData, config);
  const marketAnalysis = analyzeMarketRobustness(marketData, config);
  const stabilityAnalysis = analyzeStability(periodResults, config);
  
  // Overall robustness
  const overallRobustness = 
    regimeAnalysis.score * 0.4 +
    marketAnalysis.score * 0.35 +
    stabilityAnalysis.score * 0.25;
  
  return {
    regimeScore: regimeAnalysis.score,
    strongRegimes: regimeAnalysis.strongRegimes,
    weakRegimes: regimeAnalysis.weakRegimes,
    
    crossMarketScore: marketAnalysis.score,
    validMarkets: marketAnalysis.validMarkets,
    failedMarkets: marketAnalysis.failedMarkets,
    
    stabilityScore: stabilityAnalysis.score,
    walkForwardResults: stabilityAnalysis.walkForwardResults,
    
    overallRobustness: Math.min(1, Math.max(0, overallRobustness))
  };
}
