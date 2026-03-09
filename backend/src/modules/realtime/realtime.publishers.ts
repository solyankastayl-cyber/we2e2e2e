/**
 * Real-time WebSocket Layer — Event Publishers
 * 
 * Helper functions to publish specific event types
 */

import { realtimeHub, createBaseEvent } from './realtime.hub.js';
import {
  RegimeUpdateEvent,
  StateUpdateEvent,
  ScenarioUpdateEvent,
  TreeUpdateEvent,
  MemoryMatchEvent,
  MetaBrainUpdateEvent,
  SignalUpdateEvent,
  SafeModeTriggerEvent,
  ModuleGateChangeEvent,
  EdgeAlertEvent,
  TwinUpdateEvent,
  SystemHealthEvent,
  CandleUpdateEvent,
  PatternDetectedEvent,
  SignalCreatedEvent
} from './realtime.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';
import { AnalysisMode, MetaBrainRiskMode } from '../metabrain_v3/metabrain_v3.types.js';

// ═══════════════════════════════════════════════════════════════
// REGIME UPDATE
// ═══════════════════════════════════════════════════════════════

export function publishRegimeUpdate(
  asset: string,
  timeframe: string,
  previousRegime: MarketRegime,
  newRegime: MarketRegime,
  confidence: number,
  reason: string
): void {
  const event: RegimeUpdateEvent = {
    ...createBaseEvent('REGIME_UPDATE', asset, timeframe, 'HIGH'),
    type: 'REGIME_UPDATE',
    previousRegime,
    newRegime,
    confidence,
    reason
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// STATE UPDATE
// ═══════════════════════════════════════════════════════════════

export function publishStateUpdate(
  asset: string,
  timeframe: string,
  previousState: MarketStateNode,
  newState: MarketStateNode,
  transitionProbability: number
): void {
  const event: StateUpdateEvent = {
    ...createBaseEvent('STATE_UPDATE', asset, timeframe, 'MEDIUM'),
    type: 'STATE_UPDATE',
    previousState,
    newState,
    transitionProbability
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// SCENARIO UPDATE
// ═══════════════════════════════════════════════════════════════

export function publishScenarioUpdate(
  asset: string,
  timeframe: string,
  dominantScenario: string,
  probability: number,
  alternatives: { scenario: string; probability: number }[],
  scenarioBreakRisk: number
): void {
  const priority = scenarioBreakRisk > 0.5 ? 'HIGH' : 'MEDIUM';
  const event: ScenarioUpdateEvent = {
    ...createBaseEvent('SCENARIO_UPDATE', asset, timeframe, priority),
    type: 'SCENARIO_UPDATE',
    dominantScenario,
    probability,
    alternatives,
    scenarioBreakRisk
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// TREE UPDATE
// ═══════════════════════════════════════════════════════════════

export function publishTreeUpdate(
  asset: string,
  timeframe: string,
  dominanceScore: number,
  uncertaintyScore: number,
  treeRisk: number,
  totalBranches: number,
  mainBranch: string
): void {
  const priority = treeRisk > 0.5 ? 'HIGH' : 'MEDIUM';
  const event: TreeUpdateEvent = {
    ...createBaseEvent('TREE_UPDATE', asset, timeframe, priority),
    type: 'TREE_UPDATE',
    dominanceScore,
    uncertaintyScore,
    treeRisk,
    totalBranches,
    mainBranch
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// MEMORY MATCH
// ═══════════════════════════════════════════════════════════════

export function publishMemoryMatch(
  asset: string,
  timeframe: string,
  matchCount: number,
  confidence: number,
  dominantBias: 'BULL' | 'BEAR' | 'NEUTRAL',
  similarityScore: number,
  historicalWinRate?: number
): void {
  const priority = confidence > 0.7 ? 'HIGH' : 'MEDIUM';
  const event: MemoryMatchEvent = {
    ...createBaseEvent('MEMORY_MATCH', asset, timeframe, priority),
    type: 'MEMORY_MATCH',
    matchCount,
    confidence,
    dominantBias,
    historicalWinRate,
    similarityScore
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// METABRAIN UPDATE
// ═══════════════════════════════════════════════════════════════

export function publishMetaBrainUpdate(
  asset: string,
  timeframe: string,
  analysisMode: AnalysisMode,
  riskMode: MetaBrainRiskMode,
  safeMode: boolean,
  riskMultiplier: number,
  enabledStrategies: string[],
  disabledStrategies: string[],
  reasons: string[]
): void {
  const priority = safeMode ? 'CRITICAL' : riskMode === 'AGGRESSIVE' ? 'HIGH' : 'MEDIUM';
  const event: MetaBrainUpdateEvent = {
    ...createBaseEvent('METABRAIN_UPDATE', asset, timeframe, priority),
    type: 'METABRAIN_UPDATE',
    analysisMode,
    riskMode,
    safeMode,
    riskMultiplier,
    enabledStrategies,
    disabledStrategies,
    reasons
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// SIGNAL UPDATE
// ═══════════════════════════════════════════════════════════════

export function publishSignalUpdate(
  asset: string,
  timeframe: string,
  signalType: 'ENTRY' | 'EXIT' | 'ADJUST',
  direction: 'LONG' | 'SHORT' | 'NEUTRAL',
  confidence: number,
  strength: number,
  pattern?: string,
  scenario?: string,
  targetPrice?: number,
  stopLoss?: number
): void {
  const priority = signalType === 'ENTRY' && confidence > 0.7 ? 'HIGH' : 'MEDIUM';
  const event: SignalUpdateEvent = {
    ...createBaseEvent('SIGNAL_UPDATE', asset, timeframe, priority),
    type: 'SIGNAL_UPDATE',
    signalType,
    direction,
    confidence,
    strength,
    pattern,
    scenario,
    targetPrice,
    stopLoss
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// SAFE MODE TRIGGER
// ═══════════════════════════════════════════════════════════════

export function publishSafeModeTrigger(
  asset: string,
  timeframe: string,
  triggered: boolean,
  triggers: string[],
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL',
  previousRiskMode: MetaBrainRiskMode,
  newRiskMode: MetaBrainRiskMode
): void {
  const event: SafeModeTriggerEvent = {
    ...createBaseEvent('SAFE_MODE_TRIGGER', asset, timeframe, 'CRITICAL'),
    type: 'SAFE_MODE_TRIGGER',
    triggered,
    triggers,
    severity,
    previousRiskMode,
    newRiskMode
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// MODULE GATE CHANGE
// ═══════════════════════════════════════════════════════════════

export function publishModuleGateChange(
  asset: string,
  timeframe: string,
  module: string,
  previousStatus: 'ACTIVE' | 'SOFT_GATED' | 'HARD_GATED',
  newStatus: 'ACTIVE' | 'SOFT_GATED' | 'HARD_GATED',
  reason: string
): void {
  const priority = newStatus === 'HARD_GATED' ? 'HIGH' : 'MEDIUM';
  const event: ModuleGateChangeEvent = {
    ...createBaseEvent('MODULE_GATE_CHANGE', asset, timeframe, priority),
    type: 'MODULE_GATE_CHANGE',
    module,
    previousStatus,
    newStatus,
    reason
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// EDGE ALERT
// ═══════════════════════════════════════════════════════════════

export function publishEdgeAlert(
  asset: string,
  timeframe: string,
  alertType: 'EDGE_DEGRADATION' | 'EDGE_IMPROVEMENT' | 'EDGE_CRITICAL',
  edgeHealth: number,
  previousHealth: number,
  affectedPatterns: string[]
): void {
  const priority = alertType === 'EDGE_CRITICAL' ? 'CRITICAL' : 'HIGH';
  const event: EdgeAlertEvent = {
    ...createBaseEvent('EDGE_ALERT', asset, timeframe, priority),
    type: 'EDGE_ALERT',
    alertType,
    edgeHealth,
    previousHealth,
    affectedPatterns
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// TWIN UPDATE
// ═══════════════════════════════════════════════════════════════

export function publishTwinUpdate(
  asset: string,
  timeframe: string,
  consistencyScore: number,
  reactorTriggered: boolean,
  stateChanged: boolean,
  anomalyDetected: boolean
): void {
  const priority = anomalyDetected ? 'HIGH' : 'LOW';
  const event: TwinUpdateEvent = {
    ...createBaseEvent('TWIN_UPDATE', asset, timeframe, priority),
    type: 'TWIN_UPDATE',
    consistencyScore,
    reactorTriggered,
    stateChanged,
    anomalyDetected
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// SYSTEM HEALTH
// ═══════════════════════════════════════════════════════════════

export function publishSystemHealth(
  activeConnections: number,
  avgResponseTime: number,
  errorsLastHour: number,
  cpuUsage?: number,
  memoryUsage?: number
): void {
  const priority = errorsLastHour > 10 ? 'HIGH' : 'LOW';
  const event: SystemHealthEvent = {
    ...createBaseEvent('SYSTEM_HEALTH', 'SYSTEM', 'GLOBAL', priority),
    type: 'SYSTEM_HEALTH',
    cpuUsage,
    memoryUsage,
    activeConnections,
    avgResponseTime,
    errorsLastHour
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// CANDLE UPDATE
// ═══════════════════════════════════════════════════════════════

export function publishCandleUpdate(
  asset: string,
  interval: string,
  candle: { t: number; o: number; h: number; l: number; c: number; v: number }
): void {
  const event: CandleUpdateEvent = {
    ...createBaseEvent('CANDLE_UPDATE', asset, interval, 'LOW'),
    type: 'CANDLE_UPDATE',
    interval,
    candle
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// PATTERN DETECTED
// ═══════════════════════════════════════════════════════════════

export function publishPatternDetected(
  asset: string,
  timeframe: string,
  pattern: string,
  direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL',
  confidence: number,
  price: number,
  description?: string
): void {
  const priority = confidence > 0.7 ? 'HIGH' : 'MEDIUM';
  const event: PatternDetectedEvent = {
    ...createBaseEvent('PATTERN_DETECTED', asset, timeframe, priority),
    type: 'PATTERN_DETECTED',
    pattern,
    direction,
    confidence,
    price,
    description
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// SIGNAL CREATED
// ═══════════════════════════════════════════════════════════════

export function publishSignalCreated(
  asset: string,
  timeframe: string,
  direction: 'LONG' | 'SHORT',
  entry: number,
  stop: number,
  target: number,
  confidence: number,
  strategy?: string,
  reason?: string
): void {
  const priority = confidence > 0.7 ? 'HIGH' : 'MEDIUM';
  const event: SignalCreatedEvent = {
    ...createBaseEvent('SIGNAL_CREATED', asset, timeframe, priority),
    type: 'SIGNAL_CREATED',
    direction,
    entry,
    stop,
    target,
    confidence,
    strategy,
    reason
  };
  realtimeHub.publish(event);
}

// ═══════════════════════════════════════════════════════════════
// MARKET MAP UPDATE
// ═══════════════════════════════════════════════════════════════

import { MarketMapUpdateEvent } from './realtime.types.js';

export function publishMarketMapUpdate(
  asset: string,
  timeframe: string,
  currentState: string,
  dominantScenario: string,
  dominantProbability: number,
  uncertainty: number,
  bullishBias: number,
  branchCount: number
): void {
  const priority = uncertainty > 0.7 ? 'HIGH' : 'MEDIUM';
  const event: MarketMapUpdateEvent = {
    ...createBaseEvent('MARKET_MAP_UPDATE', asset, timeframe, priority),
    type: 'MARKET_MAP_UPDATE',
    currentState,
    dominantScenario,
    dominantProbability,
    uncertainty,
    bullishBias,
    branchCount
  };
  realtimeHub.publish(event);
}
