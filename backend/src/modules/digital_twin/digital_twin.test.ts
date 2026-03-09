/**
 * Digital Twin Module Tests
 * 
 * Tests for DT1-DT4 functionality
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';

// DT1 imports
import { buildTwinContext, buildMockTwinContext, validateContext, deriveLiquidityState } from './digital_twin.context.js';
import { buildTwinBranches, getDominantBranch, calculateBranchConflict, calculateWeightedFailureRisk, getCommonPathPrefix } from './digital_twin.branches.js';
import { buildDigitalTwinState, updateTwinStateWithConsistency, updateTwinStateWithCounterfactual, compareStates, hasSignificantChange } from './digital_twin.state.js';

// DT2 imports
import { handleTwinEvent, detectEventFromContext } from './digital_twin.reactor.js';

// DT3 imports
import { evaluateTwinConsistency, getMostCriticalConflict, isConsistencyAcceptable } from './digital_twin.consistency.js';

// DT4 imports
import { buildCounterfactuals, computeScenarioBreakRisk } from './digital_twin.counterfactual.js';

// Types
import { TwinContext, DigitalTwinState, TwinEvent, DEFAULT_TWIN_CONFIG } from './digital_twin.types.js';

// ═══════════════════════════════════════════════════════════════
// TEST DATA
// ═══════════════════════════════════════════════════════════════

const TEST_ASSET = 'BTCUSDT';
const TEST_TF = '1d';

function createTestContext(overrides?: Partial<TwinContext>): TwinContext {
  return {
    ...buildMockTwinContext(TEST_ASSET, TEST_TF),
    ...overrides
  };
}

// ═══════════════════════════════════════════════════════════════
// DT1 — CONTEXT TESTS
// ═══════════════════════════════════════════════════════════════

describe('DT1 - Twin Context', () => {
  it('should build mock context with all modules', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    
    expect(context.asset).toBe(TEST_ASSET);
    expect(context.timeframe).toBe(TEST_TF);
    expect(context.regime).toBeDefined();
    expect(context.state).toBeDefined();
    expect(context.physics).toBeDefined();
    expect(context.liquidity).toBeDefined();
    expect(context.scenarios).toBeDefined();
  });
  
  it('should validate complete context', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const validation = validateContext(context);
    
    expect(validation.valid).toBe(true);
    expect(validation.missingModules).toHaveLength(0);
  });
  
  it('should detect missing modules in context', () => {
    const context: TwinContext = {
      asset: TEST_ASSET,
      timeframe: TEST_TF,
      ts: Date.now()
    };
    
    const validation = validateContext(context);
    
    expect(validation.valid).toBe(false);
    expect(validation.missingModules).toContain('regime');
    expect(validation.missingModules).toContain('state');
  });
  
  it('should derive correct liquidity state from sweeps', () => {
    const contextSweepLow = createTestContext({
      liquidity: {
        liquidityBias: 'BULLISH',
        recentSweepUp: false,
        recentSweepDown: true,
        zonesAbove: 2,
        zonesBelow: 3
      }
    });
    
    expect(deriveLiquidityState(contextSweepLow)).toBe('SWEEP_LOW');
    
    const contextSweepHigh = createTestContext({
      liquidity: {
        liquidityBias: 'BEARISH',
        recentSweepUp: true,
        recentSweepDown: false,
        zonesAbove: 3,
        zonesBelow: 2
      }
    });
    
    expect(deriveLiquidityState(contextSweepHigh)).toBe('SWEEP_HIGH');
  });
});

// ═══════════════════════════════════════════════════════════════
// DT1 — BRANCHES TESTS
// ═══════════════════════════════════════════════════════════════

describe('DT1 - Twin Branches', () => {
  it('should build branches from scenarios', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const branches = buildTwinBranches(context);
    
    expect(branches.length).toBeGreaterThan(0);
    expect(branches.length).toBeLessThanOrEqual(DEFAULT_TWIN_CONFIG.maxBranches);
    
    const branch = branches[0];
    expect(branch.branchId).toBeDefined();
    expect(branch.path).toBeDefined();
    expect(branch.direction).toBeDefined();
    expect(branch.probability).toBeGreaterThan(0);
  });
  
  it('should get dominant branch', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const branches = buildTwinBranches(context);
    const dominant = getDominantBranch(branches);
    
    expect(dominant).toBeDefined();
    expect(dominant!.probability).toBeGreaterThanOrEqual(branches[1]?.probability || 0);
  });
  
  it('should calculate branch conflict', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const branches = buildTwinBranches(context);
    const conflict = calculateBranchConflict(branches);
    
    expect(conflict).toBeGreaterThanOrEqual(0);
    expect(conflict).toBeLessThanOrEqual(1);
  });
  
  it('should calculate weighted failure risk', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const branches = buildTwinBranches(context);
    const risk = calculateWeightedFailureRisk(branches);
    
    expect(risk).toBeGreaterThanOrEqual(0);
    expect(risk).toBeLessThanOrEqual(1);
  });
});

// ═══════════════════════════════════════════════════════════════
// DT1 — STATE TESTS
// ═══════════════════════════════════════════════════════════════

describe('DT1 - Twin State', () => {
  it('should build complete DigitalTwinState', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const state = buildDigitalTwinState(context);
    
    expect(state.asset).toBe(TEST_ASSET);
    expect(state.timeframe).toBe(TEST_TF);
    expect(state.regime).toBeDefined();
    expect(state.marketState).toBeDefined();
    expect(state.physicsState).toBeDefined();
    expect(state.liquidityState).toBeDefined();
    expect(state.dominantScenario).toBeDefined();
    expect(state.energy).toBeGreaterThanOrEqual(0);
    expect(state.energy).toBeLessThanOrEqual(1);
    expect(state.instability).toBeGreaterThanOrEqual(0);
    expect(state.instability).toBeLessThanOrEqual(1);
    expect(state.confidence).toBeGreaterThanOrEqual(0);
    expect(state.confidence).toBeLessThanOrEqual(1);
    expect(state.branches).toBeDefined();
  });
  
  it('should compare states and detect changes', () => {
    const context1 = buildMockTwinContext(TEST_ASSET, TEST_TF, { regime: 'COMPRESSION' });
    const context2 = buildMockTwinContext(TEST_ASSET, TEST_TF, { regime: 'BREAKOUT_PREP' });
    
    const state1 = buildDigitalTwinState(context1);
    const state2 = buildDigitalTwinState(context2);
    
    const changes = compareStates(state1, state2);
    
    expect(changes).toContain('regime');
  });
  
  it('should detect significant changes', () => {
    const context1 = buildMockTwinContext(TEST_ASSET, TEST_TF, { regime: 'COMPRESSION' });
    const context2 = buildMockTwinContext(TEST_ASSET, TEST_TF, { regime: 'TREND_EXPANSION' });
    
    const state1 = buildDigitalTwinState(context1);
    const state2 = buildDigitalTwinState(context2);
    
    const significant = hasSignificantChange(state1, state2);
    
    expect(significant).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════
// DT2 — REACTOR TESTS
// ═══════════════════════════════════════════════════════════════

describe('DT2 - Twin Reactor', () => {
  it('should handle NEW_CANDLE event', async () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const event: TwinEvent = {
      type: 'NEW_CANDLE',
      asset: TEST_ASSET,
      timeframe: TEST_TF,
      ts: Date.now()
    };
    
    const result = await handleTwinEvent(event, undefined, context);
    
    expect(result.newState).toBeDefined();
    expect(result.event.type).toBe('NEW_CANDLE');
    expect(result.changedFields).toContain('all');
  });
  
  it('should handle REGIME_CHANGE event', async () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF, { regime: 'TREND_EXPANSION' });
    const prevState = buildDigitalTwinState(buildMockTwinContext(TEST_ASSET, TEST_TF));
    
    const event: TwinEvent = {
      type: 'REGIME_CHANGE',
      asset: TEST_ASSET,
      timeframe: TEST_TF,
      ts: Date.now(),
      payload: { from: 'COMPRESSION', to: 'TREND_EXPANSION' }
    };
    
    const result = await handleTwinEvent(event, prevState, context);
    
    expect(result.newState.regime).toBe('TREND_EXPANSION');
  });
  
  it('should detect event from context change', () => {
    const prevContext = buildMockTwinContext(TEST_ASSET, TEST_TF, { regime: 'COMPRESSION' });
    const newContext = buildMockTwinContext(TEST_ASSET, TEST_TF, { regime: 'BREAKOUT_PREP' });
    
    const event = detectEventFromContext(prevContext, newContext);
    
    expect(event).toBeDefined();
    expect(event!.type).toBe('REGIME_CHANGE');
  });
  
  it('should handle LIQUIDITY_EVENT', async () => {
    const context = createTestContext({
      liquidity: {
        liquidityBias: 'BULLISH',
        recentSweepUp: false,
        recentSweepDown: true,
        zonesAbove: 2,
        zonesBelow: 3
      }
    });
    
    const event: TwinEvent = {
      type: 'LIQUIDITY_EVENT',
      asset: TEST_ASSET,
      timeframe: TEST_TF,
      ts: Date.now(),
      payload: { sweepDown: true }
    };
    
    const result = await handleTwinEvent(event, undefined, context);
    
    expect(result.newState.liquidityState).toBe('SWEEP_LOW');
  });
});

// ═══════════════════════════════════════════════════════════════
// DT3 — CONSISTENCY TESTS
// ═══════════════════════════════════════════════════════════════

describe('DT3 - Twin Consistency', () => {
  it('should detect regime vs physics conflict', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const state = buildDigitalTwinState(context);
    
    // Force conflict: COMPRESSION regime with EXPANSION physics
    const conflictState: DigitalTwinState = {
      ...state,
      regime: 'COMPRESSION',
      physicsState: 'EXPANSION'
    };
    
    const consistency = evaluateTwinConsistency(conflictState);
    
    expect(consistency.conflicts.length).toBeGreaterThan(0);
    const regimePhysicsConflict = consistency.conflicts.find(c => c.type === 'REGIME_PHYSICS');
    expect(regimePhysicsConflict).toBeDefined();
  });
  
  it('should calculate consistency score', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const state = buildDigitalTwinState(context);
    const consistency = evaluateTwinConsistency(state);
    
    expect(consistency.score).toBeGreaterThanOrEqual(0);
    expect(consistency.score).toBeLessThanOrEqual(1);
  });
  
  it('should get most critical conflict', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const state = buildDigitalTwinState(context);
    
    // Force multiple conflicts
    const conflictState: DigitalTwinState = {
      ...state,
      regime: 'COMPRESSION',
      physicsState: 'EXPANSION',
      energy: 0.2
    };
    
    const consistency = evaluateTwinConsistency(conflictState);
    const critical = getMostCriticalConflict(consistency);
    
    if (consistency.conflicts.length > 0) {
      expect(critical).toBeDefined();
      expect(critical!.severityScore).toBeGreaterThanOrEqual(
        consistency.conflicts[consistency.conflicts.length - 1].severityScore
      );
    }
  });
  
  it('should check if consistency is acceptable', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    const state = buildDigitalTwinState(context);
    const consistency = evaluateTwinConsistency(state);
    
    const acceptable = isConsistencyAcceptable(consistency);
    
    expect(typeof acceptable).toBe('boolean');
    expect(acceptable).toBe(consistency.score >= DEFAULT_TWIN_CONFIG.minConsistencyScore);
  });
});

// ═══════════════════════════════════════════════════════════════
// DT4 — COUNTERFACTUAL TESTS
// ═══════════════════════════════════════════════════════════════

describe('DT4 - Counterfactual Engine', () => {
  it('should build counterfactual alternatives', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    let state = buildDigitalTwinState(context);
    
    // Add consistency for counterfactual
    const consistency = evaluateTwinConsistency(state);
    state = updateTwinStateWithConsistency(state, consistency.score, consistency.conflicts);
    
    const counterfactual = buildCounterfactuals(state);
    
    expect(counterfactual.mainScenarioId).toBeDefined();
    expect(counterfactual.alternatives).toBeDefined();
    expect(counterfactual.scenarioBreakRisk).toBeGreaterThanOrEqual(0);
    expect(counterfactual.scenarioBreakRisk).toBeLessThanOrEqual(1);
  });
  
  it('should generate alternatives with trigger events', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    let state = buildDigitalTwinState(context);
    
    const consistency = evaluateTwinConsistency(state);
    state = updateTwinStateWithConsistency(state, consistency.score, consistency.conflicts);
    
    const counterfactual = buildCounterfactuals(state);
    
    for (const alt of counterfactual.alternatives) {
      expect(alt.branchId).toBeDefined();
      expect(alt.triggerEvent).toBeDefined();
      expect(alt.path).toBeDefined();
      expect(alt.direction).toBeDefined();
      expect(alt.probability).toBeGreaterThan(0);
      expect(alt.riskToMainScenario).toBeGreaterThanOrEqual(0);
    }
  });
  
  it('should compute scenario break risk', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    let state = buildDigitalTwinState(context);
    
    const consistency = evaluateTwinConsistency(state);
    state = updateTwinStateWithConsistency(state, consistency.score, consistency.conflicts);
    
    const counterfactual = buildCounterfactuals(state);
    const risk = computeScenarioBreakRisk(counterfactual.alternatives, state);
    
    expect(risk).toBeGreaterThanOrEqual(0);
    expect(risk).toBeLessThanOrEqual(1);
  });
  
  it('should identify dominant alternative', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    let state = buildDigitalTwinState(context);
    
    const consistency = evaluateTwinConsistency(state);
    state = updateTwinStateWithConsistency(state, consistency.score, consistency.conflicts);
    
    const counterfactual = buildCounterfactuals(state);
    
    if (counterfactual.alternatives.length > 0) {
      expect(counterfactual.dominantAlternative).toBeDefined();
      expect(counterfactual.dominantAlternative!.probability).toBeGreaterThanOrEqual(
        counterfactual.alternatives[counterfactual.alternatives.length - 1].probability
      );
    }
  });
});

// ═══════════════════════════════════════════════════════════════
// FULL PIPELINE TESTS
// ═══════════════════════════════════════════════════════════════

describe('Digital Twin - Full Pipeline', () => {
  it('should build complete twin with consistency and counterfactual', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF);
    
    // Build state
    let state = buildDigitalTwinState(context);
    expect(state.regime).toBeDefined();
    expect(state.branches.length).toBeGreaterThan(0);
    
    // Add consistency
    const consistency = evaluateTwinConsistency(state);
    state = updateTwinStateWithConsistency(state, consistency.score, consistency.conflicts);
    expect(state.consistencyScore).toBeDefined();
    
    // Add counterfactual
    const counterfactual = buildCounterfactuals(state);
    state = updateTwinStateWithCounterfactual(state, counterfactual);
    expect(state.counterfactual).toBeDefined();
    
    // Final validation
    expect(state.version).toBeGreaterThan(1);
  });
  
  it('should handle event-driven update pipeline', async () => {
    const initialContext = buildMockTwinContext(TEST_ASSET, TEST_TF, { regime: 'COMPRESSION' });
    const initialState = buildDigitalTwinState(initialContext);
    
    // Simulate regime change event
    const newContext = buildMockTwinContext(TEST_ASSET, TEST_TF, { regime: 'BREAKOUT_PREP' });
    const event: TwinEvent = {
      type: 'REGIME_CHANGE',
      asset: TEST_ASSET,
      timeframe: TEST_TF,
      ts: Date.now(),
      payload: { from: 'COMPRESSION', to: 'BREAKOUT_PREP' }
    };
    
    const result = await handleTwinEvent(event, initialState, newContext);
    
    expect(result.stateChanged).toBe(true);
    expect(result.newState.regime).toBe('BREAKOUT_PREP');
    expect(result.changedFields).toContain('regime');
  });
  
  it('should produce coherent analysis across all layers', () => {
    const context = buildMockTwinContext(TEST_ASSET, TEST_TF, {
      regime: 'COMPRESSION',
      state: 'COMPRESSION',
      physicsState: 'COMPRESSION',
      direction: 'BULL'
    });
    
    let state = buildDigitalTwinState(context);
    
    // All states should be coherent
    expect(state.regime).toBe('COMPRESSION');
    expect(state.marketState).toBe('COMPRESSION');
    expect(state.physicsState).toBe('COMPRESSION');
    
    // Consistency should be high for coherent state
    const consistency = evaluateTwinConsistency(state);
    expect(consistency.score).toBeGreaterThan(0.5);
    
    state = updateTwinStateWithConsistency(state, consistency.score, consistency.conflicts);
    
    // Counterfactual should reflect coherent state
    const counterfactual = buildCounterfactuals(state);
    expect(counterfactual.scenarioBreakRisk).toBeLessThan(0.7);
  });
});
