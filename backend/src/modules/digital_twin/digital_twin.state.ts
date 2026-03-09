/**
 * DT1 — Twin State Builder
 * 
 * Builds DigitalTwinState from context
 */

import {
  DigitalTwinState,
  TwinContext,
  TwinBranch,
  DEFAULT_TWIN_CONFIG,
  DigitalTwinConfig,
  LiquidityStateType
} from './digital_twin.types.js';
import { buildTwinBranches, calculateBranchConflict, calculateWeightedFailureRisk, getDominantBranch } from './digital_twin.branches.js';
import { deriveLiquidityState, normalizeContext } from './digital_twin.context.js';
import { MarketRegime } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';
import { PhysicsState } from '../market_physics/physics.types.js';

// ═══════════════════════════════════════════════════════════════
// STATE BUILDER
// ═══════════════════════════════════════════════════════════════

/**
 * Build DigitalTwinState from context
 */
export function buildDigitalTwinState(
  context: TwinContext,
  config: DigitalTwinConfig = DEFAULT_TWIN_CONFIG
): DigitalTwinState {
  // Normalize context
  const normalized = normalizeContext(context);
  
  // Build branches
  const branches = buildTwinBranches(normalized, config);
  
  // Get dominant scenario
  const dominantBranch = getDominantBranch(branches);
  const dominantScenario = dominantBranch?.branchId || 
    normalized.scenarios?.[0]?.scenarioId || 
    'UNKNOWN';
  
  // Extract module states
  const regime = normalized.regime?.regime || 'COMPRESSION' as MarketRegime;
  const marketState = normalized.state?.currentState || 'BALANCE' as MarketStateNode;
  const physicsState = normalized.physics?.physicsState || 'NEUTRAL' as PhysicsState;
  const liquidityState = deriveLiquidityState(normalized);
  
  // Calculate energy (from physics)
  const energy = normalized.physics?.energyScore || 0.5;
  
  // Calculate confidence (blended)
  const confidence = calculateBlendedConfidence(normalized, dominantBranch);
  
  // Calculate instability
  const instability = calculateInstability(normalized, branches, config);
  
  return {
    asset: context.asset,
    timeframe: context.timeframe,
    ts: context.ts,
    
    regime,
    marketState,
    physicsState,
    liquidityState,
    
    dominantScenario,
    
    energy,
    instability,
    confidence,
    
    branches,
    
    computedAt: new Date(),
    version: 1
  };
}

// ═══════════════════════════════════════════════════════════════
// CONFIDENCE CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate blended confidence from multiple sources
 */
function calculateBlendedConfidence(
  context: TwinContext,
  dominantBranch: TwinBranch | null
): number {
  const weights = {
    regime: 0.2,
    state: 0.2,
    physics: 0.15,
    scenario: 0.35,
    metabrain: 0.1
  };
  
  let totalWeight = 0;
  let weightedSum = 0;
  
  // Regime confidence
  if (context.regime && typeof context.regime.confidence === 'number' && !isNaN(context.regime.confidence)) {
    weightedSum += context.regime.confidence * weights.regime;
    totalWeight += weights.regime;
  }
  
  // State confidence
  if (context.state && typeof context.state.stateConfidence === 'number' && !isNaN(context.state.stateConfidence)) {
    weightedSum += context.state.stateConfidence * weights.state;
    totalWeight += weights.state;
  }
  
  // Physics confidence (inverse of exhaustion + release probability)
  if (context.physics) {
    const exhaustion = typeof context.physics.exhaustionScore === 'number' && !isNaN(context.physics.exhaustionScore) 
      ? context.physics.exhaustionScore : 0.5;
    const release = typeof context.physics.releaseProbability === 'number' && !isNaN(context.physics.releaseProbability)
      ? context.physics.releaseProbability : 0.5;
    const physicsConfidence = (1 - exhaustion) * 0.5 + (1 - Math.abs(release - 0.5)) * 0.5;
    weightedSum += physicsConfidence * weights.physics;
    totalWeight += weights.physics;
  }
  
  // Scenario confidence
  if (dominantBranch) {
    weightedSum += dominantBranch.probability * weights.scenario;
    totalWeight += weights.scenario;
  } else if (context.scenarios && context.scenarios.length > 0) {
    weightedSum += context.scenarios[0].confidence * weights.scenario;
    totalWeight += weights.scenario;
  }
  
  // MetaBrain adjustment
  if (context.metabrain) {
    const metaConfidence = context.metabrain.riskMode === 'AGGRESSIVE' ? 0.7 :
      context.metabrain.riskMode === 'CONSERVATIVE' ? 0.5 : 0.6;
    weightedSum += metaConfidence * weights.metabrain;
    totalWeight += weights.metabrain;
  }
  
  if (totalWeight === 0) return 0.5;
  
  return Math.min(1, Math.max(0, weightedSum / totalWeight));
}

// ═══════════════════════════════════════════════════════════════
// INSTABILITY CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate market instability score
 * 
 * High instability = high risk of scenario break
 */
function calculateInstability(
  context: TwinContext,
  branches: TwinBranch[],
  config: DigitalTwinConfig
): number {
  const weights = config.instabilityWeights;
  let instability = 0;
  
  // 1. Volatility factor
  if (context.physics && typeof context.physics.releaseProbability === 'number' && !isNaN(context.physics.releaseProbability)) {
    // High release probability = transitional state = unstable
    const volatilityFactor = context.physics.releaseProbability;
    instability += volatilityFactor * weights.volatility;
  }
  
  // 2. Branch conflict
  const branchConflict = calculateBranchConflict(branches);
  if (!isNaN(branchConflict)) {
    instability += branchConflict * weights.branchConflict;
  }
  
  // 3. Failure risk
  const failureRisk = calculateWeightedFailureRisk(branches);
  if (!isNaN(failureRisk)) {
    instability += failureRisk * weights.failureRisk;
  }
  
  // 4. Consistency penalty (will be added by consistency engine)
  // Placeholder - will be updated when consistency is evaluated
  
  // Normalize total
  const totalWeight = weights.volatility + weights.branchConflict + 
    weights.failureRisk + weights.consistencyPenalty;
  
  if (totalWeight > 0) {
    instability = instability / totalWeight;
  }
  
  // Ensure valid number
  if (isNaN(instability)) return 0.5;
  
  return Math.min(1, Math.max(0, instability));
}

// ═══════════════════════════════════════════════════════════════
// STATE UPDATES
// ═══════════════════════════════════════════════════════════════

/**
 * Update twin state with new consistency data
 */
export function updateTwinStateWithConsistency(
  state: DigitalTwinState,
  consistencyScore: number,
  conflicts: DigitalTwinState['conflicts']
): DigitalTwinState {
  // Recalculate instability with consistency penalty
  const consistencyPenalty = (1 - consistencyScore) * DEFAULT_TWIN_CONFIG.instabilityWeights.consistencyPenalty;
  const newInstability = Math.min(1, state.instability + consistencyPenalty);
  
  return {
    ...state,
    consistencyScore,
    conflicts,
    instability: newInstability,
    version: state.version + 1
  };
}

/**
 * Update twin state with counterfactual data
 */
export function updateTwinStateWithCounterfactual(
  state: DigitalTwinState,
  counterfactual: DigitalTwinState['counterfactual']
): DigitalTwinState {
  return {
    ...state,
    counterfactual,
    version: state.version + 1
  };
}

/**
 * P0: Update twin state with memory context
 */
export function updateTwinStateWithMemory(
  state: DigitalTwinState,
  memoryContext: { confidence: number; matches: number; bias: 'BULL' | 'BEAR' | 'NEUTRAL' }
): DigitalTwinState {
  return {
    ...state,
    memory: memoryContext,
    version: state.version + 1
  };
}

// ═══════════════════════════════════════════════════════════════
// STATE COMPARISON
// ═══════════════════════════════════════════════════════════════

/**
 * Compare two states and return changed fields
 */
export function compareStates(
  prev: DigitalTwinState | undefined,
  next: DigitalTwinState
): string[] {
  if (!prev) return ['all'];
  
  const changed: string[] = [];
  
  if (prev.regime !== next.regime) changed.push('regime');
  if (prev.marketState !== next.marketState) changed.push('marketState');
  if (prev.physicsState !== next.physicsState) changed.push('physicsState');
  if (prev.liquidityState !== next.liquidityState) changed.push('liquidityState');
  if (prev.dominantScenario !== next.dominantScenario) changed.push('dominantScenario');
  if (Math.abs(prev.energy - next.energy) > 0.05) changed.push('energy');
  if (Math.abs(prev.instability - next.instability) > 0.05) changed.push('instability');
  if (Math.abs(prev.confidence - next.confidence) > 0.05) changed.push('confidence');
  
  // Check branch changes
  if (prev.branches.length !== next.branches.length) {
    changed.push('branches');
  } else {
    const branchesChanged = prev.branches.some((b, i) => 
      b.branchId !== next.branches[i]?.branchId ||
      Math.abs(b.probability - (next.branches[i]?.probability || 0)) > 0.05
    );
    if (branchesChanged) changed.push('branches');
  }
  
  return changed;
}

/**
 * Check if state has significantly changed
 */
export function hasSignificantChange(
  prev: DigitalTwinState | undefined,
  next: DigitalTwinState
): boolean {
  const changed = compareStates(prev, next);
  
  // Core state changes are always significant
  const coreFields = ['regime', 'marketState', 'dominantScenario'];
  const hasCoreChange = changed.some(f => coreFields.includes(f));
  
  return hasCoreChange || changed.length >= 3;
}
