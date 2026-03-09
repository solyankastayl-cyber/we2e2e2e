/**
 * Intelligence Mapper (P4.1)
 * 
 * Pure functions to build IntelligencePack components
 */

import type {
  Bias,
  TopScenario,
  ProbabilitySet,
  Expectation,
  SignalSummary,
  Projection,
  IntelligenceMeta,
  ProbabilitySource
} from './intelligence.types.js';

/**
 * Determine top bias from ranking results
 */
export function buildBias(
  netSignal: number,
  topScenario: TopScenario | null
): Bias {
  if (!topScenario) return 'WAIT';
  
  // Strong signal threshold
  if (netSignal > 0.2 && topScenario.ev > 0.1) return 'LONG';
  if (netSignal < -0.2 && topScenario.ev > 0.1) return 'SHORT';
  
  // Moderate signal with pattern type hint
  if (topScenario.type.includes('BULL') || topScenario.type.includes('BOTTOM') || topScenario.type.includes('ASC')) {
    return netSignal >= 0 ? 'LONG' : 'WAIT';
  }
  if (topScenario.type.includes('BEAR') || topScenario.type.includes('TOP') || topScenario.type.includes('DESC')) {
    return netSignal <= 0 ? 'SHORT' : 'WAIT';
  }
  
  return 'WAIT';
}

/**
 * Build top scenario from decision results
 */
export function buildTopScenario(
  rankedScenarios: Array<{
    patternId?: string;
    type?: string;
    score?: number;
    probability?: number;
    ev?: number;
    riskReward?: number;
  }>
): TopScenario | null {
  if (!rankedScenarios || rankedScenarios.length === 0) return null;
  
  const top = rankedScenarios[0];
  return {
    id: top.patternId || `scenario_${Date.now()}`,
    type: top.type || 'UNKNOWN',
    score: top.score || 0,
    probability: top.probability || 0.5,
    ev: top.ev || 0,
    riskReward: top.riskReward || 1.5
  };
}

/**
 * Build probability set from ML and scenario results
 */
export function buildProbability(
  mlProb: number | null,
  scenarioProb: { pTarget: number; pStop: number; pTimeout: number } | null,
  calibrationProb: number | null
): { probabilities: ProbabilitySet; source: ProbabilitySource } {
  
  // Priority: Calibrated > ML > Scenario > Fallback
  let source: ProbabilitySource = 'FALLBACK';
  let pEntry = 0.5;
  let pWin = 0.5;
  let pStop = 0.3;
  let pTimeout = 0.2;
  
  if (calibrationProb !== null) {
    source = 'CALIBRATED';
    pEntry = calibrationProb;
    pWin = calibrationProb * 0.9;
    pStop = (1 - calibrationProb) * 0.7;
    pTimeout = 1 - pWin - pStop;
  } else if (mlProb !== null) {
    source = 'ML';
    pEntry = mlProb;
    pWin = mlProb * 0.85;
    pStop = (1 - mlProb) * 0.65;
    pTimeout = 1 - pWin - pStop;
  } else if (scenarioProb !== null) {
    source = 'SCENARIO';
    pEntry = scenarioProb.pTarget;
    pWin = scenarioProb.pTarget;
    pStop = scenarioProb.pStop;
    pTimeout = scenarioProb.pTimeout;
  }
  
  // Normalize
  const total = pWin + pStop + pTimeout;
  if (total > 0 && total !== 1) {
    pWin /= total;
    pStop /= total;
    pTimeout /= total;
  }
  
  return {
    probabilities: {
      pEntry: Math.max(0, Math.min(1, pEntry)),
      pWin: Math.max(0, Math.min(1, pWin)),
      pStop: Math.max(0, Math.min(1, pStop)),
      pTimeout: Math.max(0, Math.min(1, pTimeout))
    },
    source
  };
}

/**
 * Build expectation values
 */
export function buildExpectation(
  pWin: number,
  expectedR: number | null,
  avgRR: number = 1.5
): Expectation {
  const r = expectedR !== null ? expectedR : avgRR;
  const ev = pWin * r - (1 - pWin) * 1.0; // Assume 1R loss on stop
  
  return {
    expectedR: r,
    expectedEV: ev
  };
}

/**
 * Build signal summary from patterns
 */
export function buildSignals(
  patterns: Array<{
    direction?: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    score?: number;
  }>,
  conflicts: number = 0
): SignalSummary {
  let bullish = 0;
  let bearish = 0;
  let neutral = 0;
  
  for (const p of patterns) {
    const dir = p.direction || 'NEUTRAL';
    if (dir === 'BULLISH') bullish++;
    else if (dir === 'BEARISH') bearish++;
    else neutral++;
  }
  
  const total = bullish + bearish + neutral;
  const netBias = total > 0 ? (bullish - bearish) / total : 0;
  
  return {
    bullish,
    bearish,
    neutral,
    conflictCount: conflicts,
    netBias
  };
}

/**
 * Build projection bands
 */
export function buildProjection(
  scenarioBands: { p10: number; p50: number; p90: number } | null,
  priceNow?: number
): Projection {
  const bands = scenarioBands || { p10: -1.0, p50: 0.5, p90: 2.5 };
  
  const projection: Projection = {
    r_p10: bands.p10,
    r_p50: bands.p50,
    r_p90: bands.p90
  };
  
  // Calculate price projections if current price available
  if (priceNow && priceNow > 0) {
    // Assuming 1R = 2% move as baseline
    const rToPrice = (r: number) => priceNow * (1 + r * 0.02);
    projection.priceNow = priceNow;
    projection.price_p10 = rToPrice(bands.p10);
    projection.price_p50 = rToPrice(bands.p50);
    projection.price_p90 = rToPrice(bands.p90);
  }
  
  return projection;
}

/**
 * Calculate composite confidence score
 */
export function buildConfidence(
  baseProb: number,
  stabilityScore: number,
  scenarioConsistency: number,
  conflictPenalty: number
): number {
  const raw = 
    baseProb * 0.4 +
    stabilityScore * 0.25 +
    scenarioConsistency * 0.25 -
    conflictPenalty * 0.1;
  
  return Math.max(0, Math.min(1, raw));
}

/**
 * Build metadata
 */
export function buildMeta(
  modelEntry: string | null,
  modelR: string | null,
  featureSchema: string | null,
  probabilitySource: ProbabilitySource
): IntelligenceMeta {
  return {
    modelEntry: modelEntry || undefined,
    modelR: modelR || undefined,
    featureSchema: featureSchema || undefined,
    probabilitySource,
    engineVersion: 'P4.1'
  };
}
