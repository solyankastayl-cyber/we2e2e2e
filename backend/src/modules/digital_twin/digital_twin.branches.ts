/**
 * DT1 — Twin Branch Builder
 * 
 * Converts scenarios to twin branches
 */

import {
  TwinBranch,
  TwinContext,
  DEFAULT_TWIN_CONFIG,
  DigitalTwinConfig
} from './digital_twin.types.js';
import { MarketBehaviorState, ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// BRANCH BUILDER
// ═══════════════════════════════════════════════════════════════

/**
 * Build twin branches from scenarios
 */
export function buildTwinBranches(
  context: TwinContext,
  config: DigitalTwinConfig = DEFAULT_TWIN_CONFIG
): TwinBranch[] {
  if (!context.scenarios || context.scenarios.length === 0) {
    return [];
  }
  
  // Sort by probability descending
  const sortedScenarios = [...context.scenarios].sort((a, b) => b.probability - a.probability);
  
  // Filter by minimum probability and take top N
  const filteredScenarios = sortedScenarios
    .filter(s => s.probability >= config.minBranchProbability)
    .slice(0, config.maxBranches);
  
  // Convert to branches
  const branches: TwinBranch[] = filteredScenarios.map((scenario, index) => ({
    branchId: scenario.scenarioId || `BR_${String(index + 1).padStart(3, '0')}`,
    path: scenario.path,
    direction: scenario.direction,
    probability: scenario.probability,
    expectedMoveATR: scenario.expectedMoveATR,
    failureRisk: calculateFailureRisk(scenario, context)
  }));
  
  return branches;
}

/**
 * Calculate failure risk for a scenario
 */
function calculateFailureRisk(
  scenario: {
    direction: ScenarioDirection;
    probability: number;
    confidence: number;
    path: MarketBehaviorState[];
  },
  context: TwinContext
): number {
  let risk = 1 - scenario.confidence;
  
  // Increase risk if path contains risky states
  const riskyStates: MarketBehaviorState[] = ['FALSE_BREAKOUT', 'REVERSAL', 'EXHAUSTION'];
  const hasRiskyState = scenario.path.some(state => riskyStates.includes(state));
  if (hasRiskyState) {
    risk += 0.1;
  }
  
  // Increase risk if physics doesn't support scenario
  if (context.physics) {
    // Low energy but expecting expansion
    if (scenario.path.includes('EXPANSION') && context.physics.energyScore < 0.4) {
      risk += 0.15;
    }
    // High exhaustion but expecting continuation
    if (scenario.path.includes('CONTINUATION') && context.physics.exhaustionScore > 0.6) {
      risk += 0.1;
    }
  }
  
  // Increase risk if liquidity bias opposes direction
  if (context.liquidity) {
    const liquiditySupports = (
      (scenario.direction === 'BULL' && context.liquidity.liquidityBias === 'BULLISH') ||
      (scenario.direction === 'BEAR' && context.liquidity.liquidityBias === 'BEARISH')
    );
    if (!liquiditySupports && scenario.direction !== 'NEUTRAL') {
      risk += 0.1;
    }
  }
  
  return Math.min(1, Math.max(0, risk));
}

// ═══════════════════════════════════════════════════════════════
// BRANCH ANALYSIS
// ═══════════════════════════════════════════════════════════════

/**
 * Get dominant branch (highest probability)
 */
export function getDominantBranch(branches: TwinBranch[]): TwinBranch | null {
  if (branches.length === 0) return null;
  return branches.reduce((max, branch) => 
    branch.probability > max.probability ? branch : max
  );
}

/**
 * Calculate branch conflict score (0 = aligned, 1 = conflicting)
 */
export function calculateBranchConflict(branches: TwinBranch[]): number {
  if (branches.length < 2) return 0;
  
  // Check direction alignment
  const directions = branches.map(b => b.direction);
  const uniqueDirections = new Set(directions);
  
  // If all same direction, low conflict
  if (uniqueDirections.size === 1) return 0.1;
  
  // If contains both BULL and BEAR, high conflict
  if (uniqueDirections.has('BULL') && uniqueDirections.has('BEAR')) {
    // Weight by probabilities
    const bullProb = branches
      .filter(b => b.direction === 'BULL')
      .reduce((sum, b) => sum + b.probability, 0);
    const bearProb = branches
      .filter(b => b.direction === 'BEAR')
      .reduce((sum, b) => sum + b.probability, 0);
    
    // More balanced = more conflict
    const ratio = Math.min(bullProb, bearProb) / Math.max(bullProb, bearProb);
    return 0.5 + ratio * 0.5;
  }
  
  // Mixed with NEUTRAL
  return 0.3;
}

/**
 * Calculate weighted failure risk across branches
 */
export function calculateWeightedFailureRisk(branches: TwinBranch[]): number {
  if (branches.length === 0) return 0;
  
  const totalProb = branches.reduce((sum, b) => sum + b.probability, 0);
  if (totalProb === 0) return 0;
  
  const weightedRisk = branches.reduce(
    (sum, b) => sum + (b.failureRisk * b.probability / totalProb),
    0
  );
  
  return weightedRisk;
}

// ═══════════════════════════════════════════════════════════════
// PATH ANALYSIS
// ═══════════════════════════════════════════════════════════════

/**
 * Get common path prefix across branches
 */
export function getCommonPathPrefix(branches: TwinBranch[]): MarketBehaviorState[] {
  if (branches.length === 0) return [];
  if (branches.length === 1) return branches[0].path;
  
  const firstPath = branches[0].path;
  const commonPrefix: MarketBehaviorState[] = [];
  
  for (let i = 0; i < firstPath.length; i++) {
    const state = firstPath[i];
    const allHave = branches.every(b => b.path[i] === state);
    if (allHave) {
      commonPrefix.push(state);
    } else {
      break;
    }
  }
  
  return commonPrefix;
}

/**
 * Get divergence point index where branches split
 */
export function getDivergencePoint(branches: TwinBranch[]): number {
  return getCommonPathPrefix(branches).length;
}

/**
 * Check if branches have opposing outcomes
 */
export function hasOpposingOutcomes(branches: TwinBranch[]): boolean {
  const directions = new Set(branches.map(b => b.direction));
  return directions.has('BULL') && directions.has('BEAR');
}
