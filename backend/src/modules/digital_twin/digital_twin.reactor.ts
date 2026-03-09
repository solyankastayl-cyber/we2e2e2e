/**
 * DT2 — Twin Reactor
 * 
 * Event-driven twin state updates
 */

import {
  DigitalTwinState,
  TwinEvent,
  TwinEventType,
  TwinReactorResult,
  TwinContext,
  DEFAULT_TWIN_CONFIG,
  DigitalTwinConfig
} from './digital_twin.types.js';
import { buildDigitalTwinState, compareStates, hasSignificantChange, updateTwinStateWithConsistency, updateTwinStateWithCounterfactual } from './digital_twin.state.js';
import { evaluateTwinConsistency } from './digital_twin.consistency.js';
import { buildCounterfactuals } from './digital_twin.counterfactual.js';
import { buildMockTwinContext } from './digital_twin.context.js';

// ═══════════════════════════════════════════════════════════════
// EVENT HANDLERS
// ═══════════════════════════════════════════════════════════════

type EventHandler = (
  event: TwinEvent,
  currentState: DigitalTwinState | undefined,
  context: TwinContext
) => Promise<DigitalTwinState>;

/**
 * Handle NEW_CANDLE event
 */
async function handleNewCandle(
  event: TwinEvent,
  currentState: DigitalTwinState | undefined,
  context: TwinContext
): Promise<DigitalTwinState> {
  // Build fresh state from context
  let newState = buildDigitalTwinState(context);
  
  // Evaluate consistency
  const consistency = evaluateTwinConsistency(newState);
  newState = updateTwinStateWithConsistency(
    newState,
    consistency.score,
    consistency.conflicts
  );
  
  // Build counterfactuals
  const counterfactual = buildCounterfactuals(newState);
  newState = updateTwinStateWithCounterfactual(newState, counterfactual);
  
  return newState;
}

/**
 * Handle PATTERN_DETECTED event
 */
async function handlePatternDetected(
  event: TwinEvent,
  currentState: DigitalTwinState | undefined,
  context: TwinContext
): Promise<DigitalTwinState> {
  // Pattern detection may change dominant scenario
  let newState = buildDigitalTwinState(context);
  
  // Re-evaluate consistency with pattern impact
  const consistency = evaluateTwinConsistency(newState);
  newState = updateTwinStateWithConsistency(
    newState,
    consistency.score,
    consistency.conflicts
  );
  
  // Rebuild counterfactuals
  const counterfactual = buildCounterfactuals(newState);
  newState = updateTwinStateWithCounterfactual(newState, counterfactual);
  
  return newState;
}

/**
 * Handle LIQUIDITY_EVENT event
 */
async function handleLiquidityEvent(
  event: TwinEvent,
  currentState: DigitalTwinState | undefined,
  context: TwinContext
): Promise<DigitalTwinState> {
  let newState = buildDigitalTwinState(context);
  
  // Liquidity events significantly affect consistency
  const consistency = evaluateTwinConsistency(newState);
  newState = updateTwinStateWithConsistency(
    newState,
    consistency.score,
    consistency.conflicts
  );
  
  // Counterfactuals with liquidity impact
  const counterfactual = buildCounterfactuals(newState);
  newState = updateTwinStateWithCounterfactual(newState, counterfactual);
  
  return newState;
}

/**
 * Handle REGIME_CHANGE event
 */
async function handleRegimeChange(
  event: TwinEvent,
  currentState: DigitalTwinState | undefined,
  context: TwinContext
): Promise<DigitalTwinState> {
  // Regime change is a major event
  let newState = buildDigitalTwinState(context);
  
  // Full re-evaluation
  const consistency = evaluateTwinConsistency(newState);
  newState = updateTwinStateWithConsistency(
    newState,
    consistency.score,
    consistency.conflicts
  );
  
  const counterfactual = buildCounterfactuals(newState);
  newState = updateTwinStateWithCounterfactual(newState, counterfactual);
  
  return newState;
}

/**
 * Handle STATE_CHANGE event
 */
async function handleStateChange(
  event: TwinEvent,
  currentState: DigitalTwinState | undefined,
  context: TwinContext
): Promise<DigitalTwinState> {
  let newState = buildDigitalTwinState(context);
  
  const consistency = evaluateTwinConsistency(newState);
  newState = updateTwinStateWithConsistency(
    newState,
    consistency.score,
    consistency.conflicts
  );
  
  const counterfactual = buildCounterfactuals(newState);
  newState = updateTwinStateWithCounterfactual(newState, counterfactual);
  
  return newState;
}

/**
 * Handle SCENARIO_UPDATE event
 */
async function handleScenarioUpdate(
  event: TwinEvent,
  currentState: DigitalTwinState | undefined,
  context: TwinContext
): Promise<DigitalTwinState> {
  // Scenario update directly affects branches
  let newState = buildDigitalTwinState(context);
  
  const consistency = evaluateTwinConsistency(newState);
  newState = updateTwinStateWithConsistency(
    newState,
    consistency.score,
    consistency.conflicts
  );
  
  // Scenario update = rebuild counterfactuals
  const counterfactual = buildCounterfactuals(newState);
  newState = updateTwinStateWithCounterfactual(newState, counterfactual);
  
  return newState;
}

/**
 * Handle EXECUTION_EVENT event
 */
async function handleExecutionEvent(
  event: TwinEvent,
  currentState: DigitalTwinState | undefined,
  context: TwinContext
): Promise<DigitalTwinState> {
  // Execution events don't change core twin state
  // but may affect confidence/instability
  if (!currentState) {
    return buildDigitalTwinState(context);
  }
  
  // Only rebuild if execution stress is high
  const portfolioStress = context.execution?.portfolioStress || 0;
  if (portfolioStress > 0.5) {
    let newState = buildDigitalTwinState(context);
    
    const consistency = evaluateTwinConsistency(newState);
    newState = updateTwinStateWithConsistency(
      newState,
      consistency.score,
      consistency.conflicts
    );
    
    const counterfactual = buildCounterfactuals(newState);
    newState = updateTwinStateWithCounterfactual(newState, counterfactual);
    
    return newState;
  }
  
  return currentState;
}

// ═══════════════════════════════════════════════════════════════
// EVENT HANDLER MAP
// ═══════════════════════════════════════════════════════════════

const EVENT_HANDLERS: Record<TwinEventType, EventHandler> = {
  'NEW_CANDLE': handleNewCandle,
  'PATTERN_DETECTED': handlePatternDetected,
  'LIQUIDITY_EVENT': handleLiquidityEvent,
  'REGIME_CHANGE': handleRegimeChange,
  'STATE_CHANGE': handleStateChange,
  'SCENARIO_UPDATE': handleScenarioUpdate,
  'EXECUTION_EVENT': handleExecutionEvent
};

// ═══════════════════════════════════════════════════════════════
// MAIN REACTOR
// ═══════════════════════════════════════════════════════════════

/**
 * Process twin event and update state
 */
export async function handleTwinEvent(
  event: TwinEvent,
  currentState: DigitalTwinState | undefined,
  context: TwinContext,
  config: DigitalTwinConfig = DEFAULT_TWIN_CONFIG
): Promise<TwinReactorResult> {
  const handler = EVENT_HANDLERS[event.type];
  
  if (!handler) {
    throw new Error(`Unknown event type: ${event.type}`);
  }
  
  // Process event
  const newState = await handler(event, currentState, context);
  
  // Compare states
  const changedFields = compareStates(currentState, newState);
  const stateChanged = hasSignificantChange(currentState, newState);
  
  return {
    event,
    previousState: currentState,
    newState,
    stateChanged,
    changedFields
  };
}

/**
 * Create event from context change
 */
export function detectEventFromContext(
  previousContext: TwinContext | undefined,
  newContext: TwinContext
): TwinEvent | null {
  if (!previousContext) {
    return {
      type: 'NEW_CANDLE',
      asset: newContext.asset,
      timeframe: newContext.timeframe,
      ts: newContext.ts
    };
  }
  
  // Check for regime change
  if (previousContext.regime?.regime !== newContext.regime?.regime) {
    return {
      type: 'REGIME_CHANGE',
      asset: newContext.asset,
      timeframe: newContext.timeframe,
      ts: newContext.ts,
      payload: {
        from: previousContext.regime?.regime,
        to: newContext.regime?.regime
      }
    };
  }
  
  // Check for state change
  if (previousContext.state?.currentState !== newContext.state?.currentState) {
    return {
      type: 'STATE_CHANGE',
      asset: newContext.asset,
      timeframe: newContext.timeframe,
      ts: newContext.ts,
      payload: {
        from: previousContext.state?.currentState,
        to: newContext.state?.currentState
      }
    };
  }
  
  // Check for liquidity event
  const prevSweepUp = previousContext.liquidity?.recentSweepUp || false;
  const prevSweepDown = previousContext.liquidity?.recentSweepDown || false;
  const newSweepUp = newContext.liquidity?.recentSweepUp || false;
  const newSweepDown = newContext.liquidity?.recentSweepDown || false;
  
  if ((!prevSweepUp && newSweepUp) || (!prevSweepDown && newSweepDown)) {
    return {
      type: 'LIQUIDITY_EVENT',
      asset: newContext.asset,
      timeframe: newContext.timeframe,
      ts: newContext.ts,
      payload: {
        sweepUp: newSweepUp,
        sweepDown: newSweepDown
      }
    };
  }
  
  // Check for scenario update (dominant scenario changed)
  const prevDominant = previousContext.scenarios?.[0]?.scenarioId;
  const newDominant = newContext.scenarios?.[0]?.scenarioId;
  
  if (prevDominant !== newDominant) {
    return {
      type: 'SCENARIO_UPDATE',
      asset: newContext.asset,
      timeframe: newContext.timeframe,
      ts: newContext.ts,
      payload: {
        from: prevDominant,
        to: newDominant
      }
    };
  }
  
  // Default to candle update
  return {
    type: 'NEW_CANDLE',
    asset: newContext.asset,
    timeframe: newContext.timeframe,
    ts: newContext.ts
  };
}

// ═══════════════════════════════════════════════════════════════
// EVENT EMITTER (Placeholder for future WebSocket/EventBus)
// ═══════════════════════════════════════════════════════════════

export type TwinUpdateListener = (result: TwinReactorResult) => void;

const listeners: TwinUpdateListener[] = [];

/**
 * Subscribe to twin updates
 */
export function subscribeTwinUpdates(listener: TwinUpdateListener): () => void {
  listeners.push(listener);
  return () => {
    const index = listeners.indexOf(listener);
    if (index >= 0) listeners.splice(index, 1);
  };
}

/**
 * Emit twin update to all listeners
 */
export function emitTwinUpdate(result: TwinReactorResult): void {
  for (const listener of listeners) {
    try {
      listener(result);
    } catch (error) {
      console.error('Twin update listener error:', error);
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// BATCH PROCESSING
// ═══════════════════════════════════════════════════════════════

/**
 * Process multiple events in sequence
 */
export async function processEventBatch(
  events: TwinEvent[],
  initialState: DigitalTwinState | undefined,
  contextProvider: (event: TwinEvent) => Promise<TwinContext>,
  config: DigitalTwinConfig = DEFAULT_TWIN_CONFIG
): Promise<{
  finalState: DigitalTwinState;
  results: TwinReactorResult[];
}> {
  let currentState = initialState;
  const results: TwinReactorResult[] = [];
  
  for (const event of events) {
    const context = await contextProvider(event);
    const result = await handleTwinEvent(event, currentState, context, config);
    
    results.push(result);
    currentState = result.newState;
  }
  
  if (!currentState) {
    throw new Error('No state after processing events');
  }
  
  return {
    finalState: currentState,
    results
  };
}
