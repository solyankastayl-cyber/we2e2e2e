/**
 * Phase 6 — Scenario Simulator 2.0
 * 
 * Simulates market behavior scenarios and calculates probabilities
 */

import {
  MarketScenario,
  ScenarioSimulationInput,
  ScenarioSimulationResult,
  ScenarioDirection,
  ScenarioEngineConfig,
  DEFAULT_SCENARIO_CONFIG
} from './scenario.types.js';
import { generateScenarios, determineCurrentState } from './scenario.generator.js';
import { scoreScenarios, selectTopScenarios } from './scenario.scoring.js';

// ═══════════════════════════════════════════════════════════════
// MAIN SIMULATOR
// ═══════════════════════════════════════════════════════════════

/**
 * Run full scenario simulation
 */
export function simulateScenarios(
  input: ScenarioSimulationInput,
  config: ScenarioEngineConfig = DEFAULT_SCENARIO_CONFIG
): ScenarioSimulationResult {
  // Generate candidate scenarios
  const candidates = generateScenarios(input, config);
  
  // Score all scenarios
  const scoredScenarios = scoreScenarios(candidates, input);
  
  // Select top scenarios
  const topScenarios = selectTopScenarios(scoredScenarios, config.topScenariosCount);
  
  // Normalize probabilities
  const normalizedScenarios = normalizeProbabilities(topScenarios);
  
  // Calculate aggregate direction probabilities
  const { bullish, bearish, neutral } = calculateDirectionProbabilities(normalizedScenarios);
  
  // Determine primary, alternative, and risk scenarios
  const primary = normalizedScenarios[0];
  const alternative = normalizedScenarios.find(s => s.direction !== primary?.direction);
  const risk = findRiskScenario(normalizedScenarios, primary);
  
  // Determine recommended action
  const { action, confidence } = determineRecommendedAction(
    normalizedScenarios,
    bullish,
    bearish,
    neutral
  );
  
  return {
    asset: input.asset,
    timeframe: input.timeframe,
    timestamp: new Date(),
    scenarios: normalizedScenarios,
    primaryScenario: primary,
    alternativeScenario: alternative,
    riskScenario: risk,
    bullishProbability: bullish,
    bearishProbability: bearish,
    neutralProbability: neutral,
    recommendedAction: action,
    actionConfidence: confidence
  };
}

// ═══════════════════════════════════════════════════════════════
// PROBABILITY CALCULATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Normalize scenario probabilities to sum to 1
 */
function normalizeProbabilities(scenarios: MarketScenario[]): MarketScenario[] {
  if (scenarios.length === 0) return [];
  
  const totalProb = scenarios.reduce((sum, s) => sum + s.probability, 0);
  
  if (totalProb === 0) return scenarios;
  
  return scenarios.map(s => ({
    ...s,
    probability: s.probability / totalProb
  }));
}

/**
 * Calculate aggregate direction probabilities
 */
function calculateDirectionProbabilities(
  scenarios: MarketScenario[]
): { bullish: number; bearish: number; neutral: number } {
  let bullish = 0;
  let bearish = 0;
  let neutral = 0;
  
  for (const scenario of scenarios) {
    switch (scenario.direction) {
      case 'BULL':
        bullish += scenario.probability;
        break;
      case 'BEAR':
        bearish += scenario.probability;
        break;
      case 'NEUTRAL':
        neutral += scenario.probability;
        break;
    }
  }
  
  // Normalize
  const total = bullish + bearish + neutral;
  if (total > 0) {
    bullish /= total;
    bearish /= total;
    neutral /= total;
  } else {
    neutral = 1; // Default to neutral
  }
  
  return { bullish, bearish, neutral };
}

/**
 * Find the risk scenario (worst case)
 */
function findRiskScenario(
  scenarios: MarketScenario[],
  primary: MarketScenario | undefined
): MarketScenario | undefined {
  if (!primary) return undefined;
  
  // Risk scenario is opposite direction with reasonable probability
  const oppositeDirection: ScenarioDirection = 
    primary.direction === 'BULL' ? 'BEAR' :
    primary.direction === 'BEAR' ? 'BULL' : 'NEUTRAL';
  
  return scenarios.find(s => 
    s.direction === oppositeDirection && 
    s.probability > 0.1
  );
}

// ═══════════════════════════════════════════════════════════════
// ACTION RECOMMENDATION
// ═══════════════════════════════════════════════════════════════

/**
 * Determine recommended action based on scenarios
 */
function determineRecommendedAction(
  scenarios: MarketScenario[],
  bullish: number,
  bearish: number,
  neutral: number
): { action: 'LONG' | 'SHORT' | 'WAIT' | 'REDUCE'; confidence: number } {
  const primary = scenarios[0];
  
  if (!primary) {
    return { action: 'WAIT', confidence: 0.3 };
  }
  
  // Calculate edge (difference between primary and alternative directions)
  const edge = Math.abs(bullish - bearish);
  const primaryConfidence = primary.confidence * primary.probability;
  
  // Decision logic
  if (edge < 0.15 || primaryConfidence < 0.3) {
    // No clear edge - wait
    return { action: 'WAIT', confidence: 0.5 - edge };
  }
  
  if (neutral > 0.5) {
    // High neutral probability - reduce exposure
    return { action: 'REDUCE', confidence: neutral };
  }
  
  if (bullish > bearish && bullish > 0.4) {
    const confidence = Math.min(1, bullish * primaryConfidence * 1.5);
    return { action: 'LONG', confidence };
  }
  
  if (bearish > bullish && bearish > 0.4) {
    const confidence = Math.min(1, bearish * primaryConfidence * 1.5);
    return { action: 'SHORT', confidence };
  }
  
  return { action: 'WAIT', confidence: 0.4 };
}

// ═══════════════════════════════════════════════════════════════
// MONTE CARLO ENHANCEMENT
// ═══════════════════════════════════════════════════════════════

/**
 * Monte Carlo simulation for probability refinement
 */
export function refineWithMonteCarlo(
  scenario: MarketScenario,
  input: ScenarioSimulationInput,
  numSimulations: number = 1000
): { refinedProbability: number; expectedBars: number; confidenceInterval: [number, number] } {
  const results: number[] = [];
  
  for (let i = 0; i < numSimulations; i++) {
    // Simulate path success with randomness
    let pathSuccess = 1;
    
    for (let j = 0; j < scenario.path.length - 1; j++) {
      // Add random noise to transition probability
      const baseProb = scenario.probability;
      const noise = (Math.random() - 0.5) * 0.2;
      const adjustedProb = Math.max(0.05, Math.min(0.95, baseProb + noise));
      
      pathSuccess *= adjustedProb;
    }
    
    results.push(pathSuccess);
  }
  
  // Calculate statistics
  results.sort((a, b) => a - b);
  const mean = results.reduce((a, b) => a + b, 0) / numSimulations;
  const p10 = results[Math.floor(numSimulations * 0.1)];
  const p90 = results[Math.floor(numSimulations * 0.9)];
  
  // Estimate expected bars based on path length
  const expectedBars = scenario.path.length * 3; // Rough estimate
  
  return {
    refinedProbability: mean,
    expectedBars,
    confidenceInterval: [p10, p90]
  };
}

// ═══════════════════════════════════════════════════════════════
// PATH ANALYSIS
// ═══════════════════════════════════════════════════════════════

/**
 * Analyze critical points in scenario path
 */
export function analyzeCriticalPoints(
  scenario: MarketScenario
): Array<{ state: string; importance: number; trigger: string }> {
  const criticalPoints: Array<{ state: string; importance: number; trigger: string }> = [];
  
  for (let i = 0; i < scenario.path.length; i++) {
    const state = scenario.path[i];
    let importance = 0.5;
    let trigger = 'time';
    
    switch (state) {
      case 'BREAKOUT':
        importance = 0.9;
        trigger = 'price_level_break';
        break;
      case 'RETEST':
        importance = 0.7;
        trigger = 'price_return_to_level';
        break;
      case 'FALSE_BREAKOUT':
        importance = 0.8;
        trigger = 'failed_breakout_candle';
        break;
      case 'REVERSAL':
        importance = 0.85;
        trigger = 'momentum_shift';
        break;
      case 'LIQUIDITY_SWEEP':
        importance = 0.75;
        trigger = 'wick_beyond_level';
        break;
      case 'EXHAUSTION':
        importance = 0.65;
        trigger = 'momentum_decay';
        break;
    }
    
    criticalPoints.push({ state, importance, trigger });
  }
  
  return criticalPoints;
}

// ═══════════════════════════════════════════════════════════════
// SCENARIO COMPARISON
// ═══════════════════════════════════════════════════════════════

/**
 * Compare two scenarios
 */
export function compareScenarios(
  a: MarketScenario,
  b: MarketScenario
): {
  probabilityDiff: number;
  directionMatch: boolean;
  pathSimilarity: number;
  evDiff: number;
} {
  // Path similarity (Jaccard)
  const setA = new Set(a.path);
  const setB = new Set(b.path);
  const intersection = new Set([...setA].filter(x => setB.has(x)));
  const union = new Set([...setA, ...setB]);
  const pathSimilarity = intersection.size / union.size;
  
  // EV calculation
  const evA = a.probability * a.expectedMoveATR;
  const evB = b.probability * b.expectedMoveATR;
  
  return {
    probabilityDiff: a.probability - b.probability,
    directionMatch: a.direction === b.direction,
    pathSimilarity,
    evDiff: evA - evB
  };
}
