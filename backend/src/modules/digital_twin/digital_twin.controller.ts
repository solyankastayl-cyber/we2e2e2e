/**
 * Digital Twin Controller
 * 
 * Main orchestration for Digital Twin operations
 */

import {
  DigitalTwinState,
  TwinContext,
  TwinEvent,
  TwinConsistency,
  CounterfactualResult,
  TwinBranch,
  TwinStateResponse,
  TwinBranchesResponse,
  TwinConsistencyResponse,
  TwinCounterfactualResponse,
  TwinHistoryResponse,
  DEFAULT_TWIN_CONFIG,
  DigitalTwinConfig
} from './digital_twin.types.js';
import { buildTwinContext, buildMockTwinContext, validateContext } from './digital_twin.context.js';
import { buildLiveTwinContext, checkModuleAvailability } from './digital_twin.live_context.js';
import { buildDigitalTwinState, updateTwinStateWithConsistency, updateTwinStateWithCounterfactual } from './digital_twin.state.js';
import { buildTwinBranches, getDominantBranch } from './digital_twin.branches.js';
import { evaluateTwinConsistency, isConsistencyAcceptable } from './digital_twin.consistency.js';
import { buildCounterfactuals } from './digital_twin.counterfactual.js';
import { handleTwinEvent, emitTwinUpdate } from './digital_twin.reactor.js';
import * as storage from './digital_twin.storage.js';

// ═══════════════════════════════════════════════════════════════
// MAIN CONTROLLER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Compute full twin state from scratch
 * Attempts to use live context first, falls back to mock if needed
 */
export async function computeTwinState(
  asset: string,
  timeframe: string,
  context?: TwinContext,
  config: DigitalTwinConfig = DEFAULT_TWIN_CONFIG
): Promise<DigitalTwinState> {
  // Build context: use provided, try live, fallback to mock
  let twinContext: TwinContext;
  
  if (context) {
    twinContext = context;
  } else {
    // Try live context first
    try {
      twinContext = await buildLiveTwinContext(asset, timeframe, { timeout: 3000 });
      const validation = validateContext(twinContext);
      
      // If live context is incomplete, supplement with mock
      if (!validation.valid) {
        console.log(`[DigitalTwin] Live context incomplete (missing: ${validation.missingModules.join(', ')}), using mock for missing modules`);
        const mockContext = buildMockTwinContext(asset, timeframe);
        
        // Merge: prefer live data, fallback to mock
        twinContext = {
          ...twinContext,
          regime: twinContext.regime || mockContext.regime,
          state: twinContext.state || mockContext.state,
          physics: twinContext.physics || mockContext.physics,
          liquidity: twinContext.liquidity || mockContext.liquidity,
          scenarios: twinContext.scenarios?.length ? twinContext.scenarios : mockContext.scenarios,
          metabrain: twinContext.metabrain || mockContext.metabrain,
          execution: twinContext.execution || mockContext.execution
        };
      }
    } catch (err) {
      console.log('[DigitalTwin] Live context unavailable, using mock');
      twinContext = buildMockTwinContext(asset, timeframe);
    }
  }
  
  // Validate final context
  const validation = validateContext(twinContext);
  if (!validation.valid) {
    console.warn(`Twin context missing modules: ${validation.missingModules.join(', ')}`);
  }
  
  // Build base state
  let state = buildDigitalTwinState(twinContext, config);
  
  // Evaluate consistency
  const consistency = evaluateTwinConsistency(state, config);
  state = updateTwinStateWithConsistency(state, consistency.score, consistency.conflicts);
  
  // Build counterfactuals
  const counterfactual = buildCounterfactuals(state, config);
  state = updateTwinStateWithCounterfactual(state, counterfactual);
  
  // Save to storage
  await storage.saveTwinState(state);
  
  return state;
}

/**
 * Recompute twin state (force recalculation)
 */
export async function recomputeTwin(
  asset: string,
  timeframe: string,
  context?: TwinContext,
  config: DigitalTwinConfig = DEFAULT_TWIN_CONFIG
): Promise<DigitalTwinState> {
  // Get current state for comparison
  const currentState = await storage.getLatestTwinState(asset, timeframe);
  
  // Compute new state
  const newState = await computeTwinState(asset, timeframe, context, config);
  
  // Emit update if changed
  if (currentState) {
    emitTwinUpdate({
      event: {
        type: 'NEW_CANDLE',
        asset,
        timeframe,
        ts: Date.now()
      },
      previousState: currentState,
      newState,
      stateChanged: true,
      changedFields: ['all']
    });
  }
  
  return newState;
}

/**
 * Get current twin state
 */
export async function getTwinState(
  asset: string,
  timeframe: string
): Promise<TwinStateResponse> {
  try {
    let state = await storage.getLatestTwinState(asset, timeframe);
    
    // If no state exists, compute one
    if (!state) {
      state = await computeTwinState(asset, timeframe);
    }
    
    return {
      success: true,
      data: state
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Get twin branches
 */
export async function getTwinBranches(
  asset: string,
  timeframe: string
): Promise<TwinBranchesResponse> {
  try {
    const state = await storage.getLatestTwinState(asset, timeframe);
    
    if (!state) {
      return {
        success: false,
        error: 'No twin state found. Call recompute first.'
      };
    }
    
    const dominantBranch = getDominantBranch(state.branches);
    
    return {
      success: true,
      data: {
        asset,
        timeframe,
        branches: state.branches,
        dominantBranch: dominantBranch || undefined
      }
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Get twin consistency
 */
export async function getTwinConsistency(
  asset: string,
  timeframe: string
): Promise<TwinConsistencyResponse> {
  try {
    const state = await storage.getLatestTwinState(asset, timeframe);
    
    if (!state) {
      return {
        success: false,
        error: 'No twin state found. Call recompute first.'
      };
    }
    
    // If consistency not computed, compute it
    if (state.consistencyScore === undefined) {
      const consistency = evaluateTwinConsistency(state);
      return {
        success: true,
        data: consistency
      };
    }
    
    return {
      success: true,
      data: {
        score: state.consistencyScore,
        conflicts: state.conflicts || [],
        totalConflictWeight: state.conflicts?.reduce((sum, c) => sum + c.severityScore, 0) || 0
      }
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Get counterfactual analysis
 */
export async function getTwinCounterfactual(
  asset: string,
  timeframe: string
): Promise<TwinCounterfactualResponse> {
  try {
    const state = await storage.getLatestTwinState(asset, timeframe);
    
    if (!state) {
      return {
        success: false,
        error: 'No twin state found. Call recompute first.'
      };
    }
    
    // If counterfactual not computed, compute it
    if (!state.counterfactual) {
      const counterfactual = buildCounterfactuals(state);
      return {
        success: true,
        data: counterfactual
      };
    }
    
    return {
      success: true,
      data: state.counterfactual
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Get twin state history
 */
export async function getTwinHistory(
  asset: string,
  timeframe: string,
  limit: number = 100
): Promise<TwinHistoryResponse> {
  try {
    const history = await storage.getTwinStateHistory(asset, timeframe, limit);
    
    return {
      success: true,
      data: {
        asset,
        timeframe,
        history,
        count: history.length
      }
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Process event and update twin
 */
export async function processEvent(
  event: TwinEvent,
  context?: TwinContext,
  config: DigitalTwinConfig = DEFAULT_TWIN_CONFIG
): Promise<DigitalTwinState> {
  // Get current state
  const currentState = await storage.getLatestTwinState(event.asset, event.timeframe);
  
  // Build context if not provided
  const twinContext = context || buildMockTwinContext(event.asset, event.timeframe);
  
  // Process event
  const result = await handleTwinEvent(event, currentState || undefined, twinContext, config);
  
  // Save new state
  await storage.saveTwinState(result.newState);
  
  // Emit update
  emitTwinUpdate(result);
  
  return result.newState;
}

// ═══════════════════════════════════════════════════════════════
// STATUS & METRICS
// ═══════════════════════════════════════════════════════════════

export interface TwinStatus {
  enabled: boolean;
  trackedAssets: Array<{ asset: string; timeframe: string }>;
  totalSnapshots: number;
  lastUpdate?: Date;
  config: DigitalTwinConfig;
}

/**
 * Get Digital Twin module status
 */
export async function getTwinStatus(): Promise<TwinStatus> {
  const trackedAssets = await storage.getTrackedAssets();
  
  // Get total count from all tracked
  let totalSnapshots = 0;
  for (const { asset, timeframe } of trackedAssets) {
    totalSnapshots += await storage.countTwinStates(asset, timeframe);
  }
  
  // Get last update from first tracked asset
  let lastUpdate: Date | undefined;
  if (trackedAssets.length > 0) {
    const latest = await storage.getLatestTwinState(
      trackedAssets[0].asset,
      trackedAssets[0].timeframe
    );
    lastUpdate = latest?.computedAt;
  }
  
  return {
    enabled: true,
    trackedAssets,
    totalSnapshots,
    lastUpdate,
    config: DEFAULT_TWIN_CONFIG
  };
}

/**
 * Check module availability for live context
 */
export { checkModuleAvailability } from './digital_twin.live_context.js';

/**
 * Get twin metrics for asset
 */
export async function getTwinMetrics(
  asset: string,
  timeframe: string
): Promise<{
  snapshotCount: number;
  avgConsistency: number;
  avgBreakRisk: number;
  regimeDistribution: Record<string, number>;
}> {
  const history = await storage.getTwinStateHistory(asset, timeframe, 100);
  
  const snapshotCount = history.length;
  
  const avgConsistency = history.length > 0
    ? history.reduce((sum, s) => sum + (s.consistencyScore || 1), 0) / history.length
    : 1;
  
  const avgBreakRisk = history.length > 0
    ? history.reduce((sum, s) => sum + (s.counterfactual?.scenarioBreakRisk || 0), 0) / history.length
    : 0;
  
  const regimeDistribution = await storage.getRegimeDistribution(asset, timeframe);
  
  return {
    snapshotCount,
    avgConsistency,
    avgBreakRisk,
    regimeDistribution
  };
}

// ═══════════════════════════════════════════════════════════════
// CLEANUP
// ═══════════════════════════════════════════════════════════════

/**
 * Cleanup old twin states
 */
export async function cleanupTwinHistory(
  keepDays: number = DEFAULT_TWIN_CONFIG.keepHistoryDays
): Promise<{ deletedCount: number }> {
  const deletedCount = await storage.cleanupOldStates(keepDays);
  return { deletedCount };
}
