/**
 * DT4 — Counterfactual Engine
 * 
 * Models alternative scenarios and calculates break risk
 */

import {
  DigitalTwinState,
  TwinBranch,
  CounterfactualBranch,
  CounterfactualResult,
  DEFAULT_TWIN_CONFIG,
  DigitalTwinConfig
} from './digital_twin.types.js';
import { MarketBehaviorState, ScenarioDirection, STATE_TRANSITIONS } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// COUNTERFACTUAL TRIGGERS
// ═══════════════════════════════════════════════════════════════

/**
 * Map of state to possible failure triggers
 */
const FAILURE_TRIGGERS: Record<MarketBehaviorState, string[]> = {
  'COMPRESSION': ['FAILED_COMPRESSION', 'EARLY_BREAKOUT'],
  'BREAKOUT': ['FAILED_BREAKOUT', 'REJECTED_BREAKOUT'],
  'FALSE_BREAKOUT': [],  // Already a failure
  'RETEST': ['FAILED_RETEST', 'RETEST_REJECTION'],
  'EXPANSION': ['EXHAUSTION_EARLY', 'MOMENTUM_FAILURE'],
  'LIQUIDITY_SWEEP': ['SWEEP_FAILURE', 'NO_RECOVERY'],
  'REVERSAL': ['REVERSAL_FAILURE', 'CONTINUATION_INSTEAD'],
  'RANGE': ['RANGE_BREAK', 'UNEXPECTED_VOLATILITY'],
  'EXHAUSTION': [],  // Already a terminal state
  'CONTINUATION': ['TREND_REVERSAL', 'MOMENTUM_LOSS']
};

/**
 * Alternative paths for each trigger
 */
const ALTERNATIVE_PATHS: Record<string, MarketBehaviorState[]> = {
  'FAILED_BREAKOUT': ['FALSE_BREAKOUT', 'RANGE'],
  'REJECTED_BREAKOUT': ['FALSE_BREAKOUT', 'REVERSAL'],
  'FAILED_RETEST': ['REVERSAL', 'EXPANSION'],  // Opposite direction
  'RETEST_REJECTION': ['FALSE_BREAKOUT', 'RANGE'],
  'EXHAUSTION_EARLY': ['EXHAUSTION', 'REVERSAL'],
  'MOMENTUM_FAILURE': ['EXHAUSTION', 'RANGE'],
  'SWEEP_FAILURE': ['RANGE', 'CONTINUATION'],
  'NO_RECOVERY': ['EXPANSION'],  // Continue in sweep direction
  'REVERSAL_FAILURE': ['RANGE', 'CONTINUATION'],
  'CONTINUATION_INSTEAD': ['CONTINUATION', 'EXPANSION'],
  'RANGE_BREAK': ['BREAKOUT', 'EXPANSION'],
  'UNEXPECTED_VOLATILITY': ['LIQUIDITY_SWEEP', 'EXPANSION'],
  'TREND_REVERSAL': ['REVERSAL', 'EXHAUSTION'],
  'MOMENTUM_LOSS': ['RANGE', 'COMPRESSION'],
  'FAILED_COMPRESSION': ['RANGE', 'EXPANSION'],
  'EARLY_BREAKOUT': ['BREAKOUT', 'EXPANSION']
};

// ═══════════════════════════════════════════════════════════════
// COUNTERFACTUAL BUILDER
// ═══════════════════════════════════════════════════════════════

/**
 * Build counterfactual alternatives from twin state
 */
export function buildCounterfactuals(
  state: DigitalTwinState,
  config: DigitalTwinConfig = DEFAULT_TWIN_CONFIG
): CounterfactualResult {
  const mainBranch = state.branches[0];
  
  if (!mainBranch) {
    return {
      mainScenarioId: 'UNKNOWN',
      mainScenarioProb: 0,
      alternatives: [],
      scenarioBreakRisk: 0
    };
  }
  
  // Generate alternatives
  const alternatives = generateAlternatives(state, mainBranch, config);
  
  // Calculate scenario break risk
  const scenarioBreakRisk = computeScenarioBreakRisk(alternatives, state);
  
  // Get dominant alternative
  const dominantAlternative = alternatives.length > 0 ?
    alternatives.reduce((max, alt) => alt.probability > max.probability ? alt : max) :
    undefined;
  
  return {
    mainScenarioId: mainBranch.branchId,
    mainScenarioProb: mainBranch.probability,
    alternatives,
    scenarioBreakRisk,
    dominantAlternative
  };
}

/**
 * Generate alternative branches
 */
function generateAlternatives(
  state: DigitalTwinState,
  mainBranch: TwinBranch,
  config: DigitalTwinConfig
): CounterfactualBranch[] {
  const alternatives: CounterfactualBranch[] = [];
  let altIndex = 1;
  
  // 1. Generate from main branch path failures
  for (let i = 0; i < mainBranch.path.length - 1; i++) {
    const currentState = mainBranch.path[i];
    const triggers = FAILURE_TRIGGERS[currentState] || [];
    
    for (const trigger of triggers) {
      const altPath = ALTERNATIVE_PATHS[trigger];
      if (!altPath) continue;
      
      // Calculate probability
      const baseProbability = calculateTriggerProbability(trigger, state, mainBranch);
      if (baseProbability < config.minAlternativeProbability) continue;
      
      // Build full alternative path
      const fullPath: MarketBehaviorState[] = [
        ...mainBranch.path.slice(0, i),
        ...altPath
      ];
      
      // Determine direction
      const direction = determineAlternativeDirection(altPath, mainBranch.direction);
      
      // Calculate risk to main
      const riskToMain = calculateRiskToMain(baseProbability, direction, mainBranch);
      
      alternatives.push({
        branchId: `CF_${String(altIndex++).padStart(2, '0')}`,
        triggerEvent: trigger,
        path: fullPath,
        direction,
        probability: baseProbability,
        expectedMoveATR: estimateAlternativeMoveATR(altPath, state.energy),
        riskToMainScenario: riskToMain
      });
      
      if (alternatives.length >= config.maxAlternatives) break;
    }
    
    if (alternatives.length >= config.maxAlternatives) break;
  }
  
  // 2. Add opposing branch from twin branches if exists
  const opposingBranch = state.branches.find(b => 
    b.direction !== mainBranch.direction && b.direction !== 'NEUTRAL'
  );
  
  if (opposingBranch && alternatives.length < config.maxAlternatives) {
    alternatives.push({
      branchId: `CF_OPP`,
      triggerEvent: 'DIRECTION_REVERSAL',
      path: opposingBranch.path,
      direction: opposingBranch.direction,
      probability: opposingBranch.probability,
      expectedMoveATR: opposingBranch.expectedMoveATR,
      riskToMainScenario: calculateRiskToMain(
        opposingBranch.probability,
        opposingBranch.direction,
        mainBranch
      )
    });
  }
  
  // 3. Add consistency-based alternatives
  if (state.conflicts && state.conflicts.length > 0 && alternatives.length < config.maxAlternatives) {
    const consistencyAlt = generateConsistencyBasedAlternative(state, mainBranch, altIndex);
    if (consistencyAlt && consistencyAlt.probability >= config.minAlternativeProbability) {
      alternatives.push(consistencyAlt);
    }
  }
  
  // Sort by probability descending
  return alternatives
    .sort((a, b) => b.probability - a.probability)
    .slice(0, config.maxAlternatives);
}

// ═══════════════════════════════════════════════════════════════
// PROBABILITY CALCULATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate trigger probability based on state
 */
function calculateTriggerProbability(
  trigger: string,
  state: DigitalTwinState,
  mainBranch: TwinBranch
): number {
  let baseProb = 0.15;  // Default base
  
  // Adjust based on trigger type
  switch (trigger) {
    case 'FAILED_BREAKOUT':
    case 'REJECTED_BREAKOUT':
      // Higher if low energy or compression
      baseProb = state.energy < 0.5 ? 0.25 : 0.15;
      if (state.physicsState === 'COMPRESSION') baseProb += 0.1;
      break;
      
    case 'FAILED_RETEST':
    case 'RETEST_REJECTION':
      // Higher if high instability
      baseProb = state.instability > 0.5 ? 0.22 : 0.12;
      break;
      
    case 'EXHAUSTION_EARLY':
    case 'MOMENTUM_FAILURE':
      // Higher if exhaustion score is elevated
      if (state.physicsState === 'EXHAUSTION') baseProb = 0.35;
      else baseProb = 0.18;
      break;
      
    case 'REVERSAL_FAILURE':
    case 'CONTINUATION_INSTEAD':
      // Higher in trending regimes
      if (state.regime === 'TREND_EXPANSION' || state.regime === 'TREND_CONTINUATION') {
        baseProb = 0.28;
      }
      break;
      
    default:
      baseProb = 0.15;
  }
  
  // Adjust by main branch failure risk
  baseProb *= (1 + mainBranch.failureRisk * 0.5);
  
  // Adjust by consistency
  if (state.consistencyScore !== undefined) {
    baseProb *= (2 - state.consistencyScore);  // Lower consistency = higher alt prob
  }
  
  return Math.min(0.6, Math.max(0.05, baseProb));
}

/**
 * Calculate risk to main scenario
 */
function calculateRiskToMain(
  altProbability: number,
  altDirection: ScenarioDirection,
  mainBranch: TwinBranch
): number {
  // Opposing directions have higher risk impact
  const directionMultiplier = 
    (mainBranch.direction === 'BULL' && altDirection === 'BEAR') ||
    (mainBranch.direction === 'BEAR' && altDirection === 'BULL')
      ? 1.5 : 1.0;
  
  return Math.min(1, altProbability * directionMultiplier);
}

/**
 * Compute overall scenario break risk
 */
export function computeScenarioBreakRisk(
  alternatives: CounterfactualBranch[],
  state: DigitalTwinState
): number {
  if (alternatives.length === 0) return 0;
  
  // Sum of weighted risks
  let totalRisk = alternatives.reduce(
    (sum, alt) => {
      const risk = alt.riskToMainScenario * alt.probability;
      return sum + (isNaN(risk) ? 0 : risk);
    },
    0
  );
  
  // Amplify by instability
  if (!isNaN(state.instability)) {
    totalRisk *= (1 + state.instability * 0.5);
  }
  
  // Amplify by consistency issues
  if (state.consistencyScore !== undefined && !isNaN(state.consistencyScore)) {
    totalRisk *= (2 - state.consistencyScore);
  }
  
  // Ensure valid number
  if (isNaN(totalRisk)) return 0.3;
  
  return Math.min(1, Math.max(0, totalRisk));
}

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Determine direction of alternative path
 */
function determineAlternativeDirection(
  path: MarketBehaviorState[],
  mainDirection: ScenarioDirection
): ScenarioDirection {
  // If path ends in reversal, opposite direction
  if (path.includes('REVERSAL')) {
    return mainDirection === 'BULL' ? 'BEAR' : 
           mainDirection === 'BEAR' ? 'BULL' : 'NEUTRAL';
  }
  
  // If path ends in range, neutral
  if (path[path.length - 1] === 'RANGE') {
    return 'NEUTRAL';
  }
  
  // FALSE_BREAKOUT often leads to opposite
  if (path.includes('FALSE_BREAKOUT')) {
    return mainDirection === 'BULL' ? 'BEAR' :
           mainDirection === 'BEAR' ? 'BULL' : 'NEUTRAL';
  }
  
  // Default to neutral
  return 'NEUTRAL';
}

/**
 * Estimate expected move for alternative
 */
function estimateAlternativeMoveATR(
  path: MarketBehaviorState[],
  energy: number
): number {
  let move = 0.5;  // Base move
  
  for (const state of path) {
    switch (state) {
      case 'EXPANSION':
        move += 1.0 * energy;
        break;
      case 'REVERSAL':
        move += 0.8;
        break;
      case 'BREAKOUT':
        move += 0.5;
        break;
      case 'RANGE':
        move += 0.3;
        break;
      case 'FALSE_BREAKOUT':
        move += 0.4;
        break;
      default:
        move += 0.2;
    }
  }
  
  return Math.min(4.0, move);
}

/**
 * Generate alternative based on consistency conflicts
 */
function generateConsistencyBasedAlternative(
  state: DigitalTwinState,
  mainBranch: TwinBranch,
  altIndex: number
): CounterfactualBranch | null {
  if (!state.conflicts || state.conflicts.length === 0) return null;
  
  // Get most severe conflict
  const severest = state.conflicts.reduce((max, c) => 
    c.severityScore > max.severityScore ? c : max
  );
  
  // Generate path based on conflict type
  let path: MarketBehaviorState[] = [];
  let trigger = severest.type;
  let direction: ScenarioDirection = 'NEUTRAL';
  
  switch (severest.type) {
    case 'REGIME_PHYSICS':
      path = ['COMPRESSION', 'RANGE'];
      break;
    case 'LIQUIDITY_DIRECTION':
      path = ['LIQUIDITY_SWEEP', 'REVERSAL', 'EXPANSION'];
      direction = mainBranch.direction === 'BULL' ? 'BEAR' : 'BULL';
      break;
    case 'PHYSICS_SCENARIO':
      path = ['EXHAUSTION', 'RANGE'];
      break;
    default:
      path = ['RANGE', 'COMPRESSION'];
  }
  
  return {
    branchId: `CF_CST_${altIndex}`,
    triggerEvent: `CONSISTENCY_${trigger}`,
    path,
    direction,
    probability: severest.severityScore * 0.4,
    expectedMoveATR: 0.8,
    riskToMainScenario: severest.severityScore * 0.5
  };
}
