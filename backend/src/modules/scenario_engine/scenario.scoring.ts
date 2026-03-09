/**
 * Phase 6 — Scenario Scoring
 * 
 * Scores and ranks market scenarios
 */

import {
  MarketScenario,
  ScenarioSimulationInput,
  ScenarioDirection
} from './scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// SCORING WEIGHTS
// ═══════════════════════════════════════════════════════════════

interface ScoringWeights {
  probability: number;
  expectedMove: number;
  confidence: number;
  pathQuality: number;
  directionalAlignment: number;
}

const DEFAULT_WEIGHTS: ScoringWeights = {
  probability: 0.35,
  expectedMove: 0.25,
  confidence: 0.20,
  pathQuality: 0.10,
  directionalAlignment: 0.10
};

// ═══════════════════════════════════════════════════════════════
// MAIN SCORING
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate comprehensive scenario score
 */
export function calculateScenarioScore(
  scenario: MarketScenario,
  input: ScenarioSimulationInput,
  weights: ScoringWeights = DEFAULT_WEIGHTS
): number {
  // Probability score (already 0-1)
  const probScore = scenario.probability;
  
  // Expected move score (normalize to 0-1, cap at 3 ATR)
  const moveScore = Math.min(1, scenario.expectedMoveATR / 3);
  
  // Confidence score (already 0-1)
  const confScore = scenario.confidence;
  
  // Path quality score
  const pathScore = calculatePathQuality(scenario);
  
  // Directional alignment score
  const alignmentScore = calculateDirectionalAlignment(scenario, input);
  
  // Weighted combination
  const finalScore = 
    probScore * weights.probability +
    moveScore * weights.expectedMove +
    confScore * weights.confidence +
    pathScore * weights.pathQuality +
    alignmentScore * weights.directionalAlignment;
  
  return Math.min(1, Math.max(0, finalScore));
}

/**
 * Score all scenarios
 */
export function scoreScenarios(
  scenarios: MarketScenario[],
  input: ScenarioSimulationInput,
  weights: ScoringWeights = DEFAULT_WEIGHTS
): MarketScenario[] {
  return scenarios.map(scenario => ({
    ...scenario,
    score: calculateScenarioScore(scenario, input, weights)
  })).sort((a, b) => b.score - a.score);
}

/**
 * Select top N scenarios ensuring diversity
 */
export function selectTopScenarios(
  scenarios: MarketScenario[],
  count: number
): MarketScenario[] {
  if (scenarios.length <= count) return scenarios;
  
  const selected: MarketScenario[] = [];
  const directions = new Set<ScenarioDirection>();
  
  // First pass: get highest scoring from each direction
  for (const scenario of scenarios) {
    if (!directions.has(scenario.direction) && selected.length < count) {
      selected.push(scenario);
      directions.add(scenario.direction);
    }
  }
  
  // Second pass: fill remaining with highest scores
  for (const scenario of scenarios) {
    if (selected.length >= count) break;
    if (!selected.includes(scenario)) {
      selected.push(scenario);
    }
  }
  
  return selected.sort((a, b) => b.score - a.score);
}

// ═══════════════════════════════════════════════════════════════
// PATH QUALITY
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate path quality score
 */
function calculatePathQuality(scenario: MarketScenario): number {
  let quality = 0.5;
  
  // Shorter paths = higher quality (more certain)
  const pathLength = scenario.path.length;
  if (pathLength <= 3) quality += 0.2;
  else if (pathLength <= 4) quality += 0.1;
  else quality -= 0.1;
  
  // Logical state transitions bonus
  if (hasLogicalTransitions(scenario.path)) {
    quality += 0.15;
  }
  
  // Penalize paths with back-and-forth
  if (hasOscillatingStates(scenario.path)) {
    quality -= 0.2;
  }
  
  // Bonus for classic patterns
  if (isClassicPattern(scenario.path)) {
    quality += 0.15;
  }
  
  return Math.min(1, Math.max(0, quality));
}

/**
 * Check if path has logical transitions
 */
function hasLogicalTransitions(path: string[]): boolean {
  const logicalPairs = [
    ['COMPRESSION', 'BREAKOUT'],
    ['BREAKOUT', 'RETEST'],
    ['RETEST', 'EXPANSION'],
    ['EXHAUSTION', 'REVERSAL'],
    ['LIQUIDITY_SWEEP', 'REVERSAL']
  ];
  
  let logicalCount = 0;
  for (let i = 0; i < path.length - 1; i++) {
    const pair = [path[i], path[i + 1]];
    if (logicalPairs.some(lp => lp[0] === pair[0] && lp[1] === pair[1])) {
      logicalCount++;
    }
  }
  
  return logicalCount >= (path.length - 1) * 0.5;
}

/**
 * Check for oscillating states (back and forth)
 */
function hasOscillatingStates(path: string[]): boolean {
  for (let i = 0; i < path.length - 2; i++) {
    if (path[i] === path[i + 2]) {
      return true;
    }
  }
  return false;
}

/**
 * Check if path matches classic patterns
 */
function isClassicPattern(path: string[]): boolean {
  const classicPatterns = [
    ['COMPRESSION', 'BREAKOUT', 'RETEST', 'EXPANSION'],
    ['COMPRESSION', 'BREAKOUT', 'EXPANSION'],
    ['EXPANSION', 'EXHAUSTION', 'REVERSAL'],
    ['LIQUIDITY_SWEEP', 'REVERSAL', 'EXPANSION'],
    ['FALSE_BREAKOUT', 'LIQUIDITY_SWEEP', 'REVERSAL']
  ];
  
  const pathStr = path.join(',');
  return classicPatterns.some(cp => pathStr.includes(cp.join(',')));
}

// ═══════════════════════════════════════════════════════════════
// DIRECTIONAL ALIGNMENT
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate directional alignment score
 */
function calculateDirectionalAlignment(
  scenario: MarketScenario,
  input: ScenarioSimulationInput
): number {
  let alignment = 0.5;
  
  // Trend alignment
  if (input.trendDirection) {
    if (scenario.direction === input.trendDirection) {
      alignment += 0.25 * (input.trendStrength || 0.5);
    } else if (scenario.direction !== 'NEUTRAL' && input.trendDirection !== 'NEUTRAL') {
      alignment -= 0.2;
    }
  }
  
  // Liquidity sweep alignment
  if (input.recentSweepDown && scenario.direction === 'BULL') {
    alignment += 0.15; // Sweep down + bullish = potential reversal
  }
  if (input.recentSweepUp && scenario.direction === 'BEAR') {
    alignment += 0.15; // Sweep up + bearish = potential reversal
  }
  
  // Energy alignment
  if (input.energyScore && input.energyScore > 0.6) {
    // High energy favors directional moves
    if (scenario.direction !== 'NEUTRAL') {
      alignment += 0.1;
    }
  }
  
  // Release probability alignment
  if (input.releaseProbability && input.releaseProbability > 0.5) {
    if (scenario.path.includes('BREAKOUT') || scenario.path.includes('EXPANSION')) {
      alignment += 0.1;
    }
  }
  
  return Math.min(1, Math.max(0, alignment));
}

// ═══════════════════════════════════════════════════════════════
// EV CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate Expected Value for scenario
 */
export function calculateScenarioEV(
  scenario: MarketScenario,
  riskMultiple: number = 1
): number {
  // EV = Probability × Expected Move - (1 - Probability) × Risk
  const winCase = scenario.probability * scenario.expectedMoveATR;
  const lossCase = (1 - scenario.probability) * riskMultiple;
  
  return winCase - lossCase;
}

/**
 * Calculate risk-adjusted score
 */
export function calculateRiskAdjustedScore(
  scenario: MarketScenario,
  volatility: number = 0.02
): number {
  // Sharpe-like ratio: (EV - risk-free) / volatility
  const ev = calculateScenarioEV(scenario);
  const riskFree = 0.0001; // Daily risk-free rate approximation
  
  if (volatility === 0) return ev;
  
  return (ev - riskFree) / (volatility * Math.sqrt(scenario.path.length));
}

// ═══════════════════════════════════════════════════════════════
// SCENARIO COMPARISON
// ═══════════════════════════════════════════════════════════════

/**
 * Rank scenarios by multiple criteria
 */
export function rankScenarios(
  scenarios: MarketScenario[],
  criteria: 'score' | 'probability' | 'ev' | 'risk_adjusted' = 'score'
): MarketScenario[] {
  switch (criteria) {
    case 'probability':
      return [...scenarios].sort((a, b) => b.probability - a.probability);
    case 'ev':
      return [...scenarios].sort((a, b) => calculateScenarioEV(b) - calculateScenarioEV(a));
    case 'risk_adjusted':
      return [...scenarios].sort((a, b) => 
        calculateRiskAdjustedScore(b) - calculateRiskAdjustedScore(a)
      );
    case 'score':
    default:
      return [...scenarios].sort((a, b) => b.score - a.score);
  }
}
