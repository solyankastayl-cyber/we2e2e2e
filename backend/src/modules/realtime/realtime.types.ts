/**
 * Real-time WebSocket Layer — Types
 * 
 * Event-driven architecture for pushing updates to:
 * - UI Dashboard
 * - Trading Bots
 * - Alert Systems
 */

import { MarketRegime } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';
import { AnalysisMode, MetaBrainRiskMode } from '../metabrain_v3/metabrain_v3.types.js';

// ═══════════════════════════════════════════════════════════════
// EVENT TYPES
// ═══════════════════════════════════════════════════════════════

export type RealtimeEventType =
  | 'REGIME_UPDATE'
  | 'STATE_UPDATE'
  | 'SCENARIO_UPDATE'
  | 'TREE_UPDATE'
  | 'MEMORY_MATCH'
  | 'METABRAIN_UPDATE'
  | 'SIGNAL_UPDATE'
  | 'SAFE_MODE_TRIGGER'
  | 'MODULE_GATE_CHANGE'
  | 'EDGE_ALERT'
  | 'TWIN_UPDATE'
  | 'SYSTEM_HEALTH'
  | 'CANDLE_UPDATE'
  | 'PATTERN_DETECTED'
  | 'SIGNAL_CREATED'
  | 'MARKET_MAP_UPDATE';

// ═══════════════════════════════════════════════════════════════
// BASE EVENT
// ═══════════════════════════════════════════════════════════════

export interface BaseRealtimeEvent {
  type: RealtimeEventType;
  asset: string;
  timeframe: string;
  timestamp: number;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

// ═══════════════════════════════════════════════════════════════
// SPECIFIC EVENTS
// ═══════════════════════════════════════════════════════════════

export interface RegimeUpdateEvent extends BaseRealtimeEvent {
  type: 'REGIME_UPDATE';
  previousRegime: MarketRegime;
  newRegime: MarketRegime;
  confidence: number;
  reason: string;
}

export interface StateUpdateEvent extends BaseRealtimeEvent {
  type: 'STATE_UPDATE';
  previousState: MarketStateNode;
  newState: MarketStateNode;
  transitionProbability: number;
}

export interface ScenarioUpdateEvent extends BaseRealtimeEvent {
  type: 'SCENARIO_UPDATE';
  dominantScenario: string;
  probability: number;
  alternatives: { scenario: string; probability: number }[];
  scenarioBreakRisk: number;
}

export interface TreeUpdateEvent extends BaseRealtimeEvent {
  type: 'TREE_UPDATE';
  dominanceScore: number;
  uncertaintyScore: number;
  treeRisk: number;
  totalBranches: number;
  mainBranch: string;
}

export interface MemoryMatchEvent extends BaseRealtimeEvent {
  type: 'MEMORY_MATCH';
  matchCount: number;
  confidence: number;
  dominantBias: 'BULL' | 'BEAR' | 'NEUTRAL';
  historicalWinRate?: number;
  similarityScore: number;
}

export interface MetaBrainUpdateEvent extends BaseRealtimeEvent {
  type: 'METABRAIN_UPDATE';
  analysisMode: AnalysisMode;
  riskMode: MetaBrainRiskMode;
  safeMode: boolean;
  riskMultiplier: number;
  enabledStrategies: string[];
  disabledStrategies: string[];
  reasons: string[];
}

export interface SignalUpdateEvent extends BaseRealtimeEvent {
  type: 'SIGNAL_UPDATE';
  signalType: 'ENTRY' | 'EXIT' | 'ADJUST';
  direction: 'LONG' | 'SHORT' | 'NEUTRAL';
  confidence: number;
  strength: number;
  pattern?: string;
  scenario?: string;
  targetPrice?: number;
  stopLoss?: number;
}

export interface SafeModeTriggerEvent extends BaseRealtimeEvent {
  type: 'SAFE_MODE_TRIGGER';
  triggered: boolean;
  triggers: string[];
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  previousRiskMode: MetaBrainRiskMode;
  newRiskMode: MetaBrainRiskMode;
}

export interface ModuleGateChangeEvent extends BaseRealtimeEvent {
  type: 'MODULE_GATE_CHANGE';
  module: string;
  previousStatus: 'ACTIVE' | 'SOFT_GATED' | 'HARD_GATED';
  newStatus: 'ACTIVE' | 'SOFT_GATED' | 'HARD_GATED';
  reason: string;
}

export interface EdgeAlertEvent extends BaseRealtimeEvent {
  type: 'EDGE_ALERT';
  alertType: 'EDGE_DEGRADATION' | 'EDGE_IMPROVEMENT' | 'EDGE_CRITICAL';
  edgeHealth: number;
  previousHealth: number;
  affectedPatterns: string[];
}

export interface TwinUpdateEvent extends BaseRealtimeEvent {
  type: 'TWIN_UPDATE';
  consistencyScore: number;
  reactorTriggered: boolean;
  stateChanged: boolean;
  anomalyDetected: boolean;
}

export interface SystemHealthEvent extends BaseRealtimeEvent {
  type: 'SYSTEM_HEALTH';
  cpuUsage?: number;
  memoryUsage?: number;
  activeConnections: number;
  avgResponseTime: number;
  errorsLastHour: number;
}

export interface CandleUpdateEvent extends BaseRealtimeEvent {
  type: 'CANDLE_UPDATE';
  interval: string;
  candle: {
    t: number;
    o: number;
    h: number;
    l: number;
    c: number;
    v: number;
  };
}

export interface PatternDetectedEvent extends BaseRealtimeEvent {
  type: 'PATTERN_DETECTED';
  pattern: string;
  direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  confidence: number;
  price: number;
  description?: string;
}

export interface SignalCreatedEvent extends BaseRealtimeEvent {
  type: 'SIGNAL_CREATED';
  direction: 'LONG' | 'SHORT';
  entry: number;
  stop: number;
  target: number;
  confidence: number;
  strategy?: string;
  reason?: string;
}

export interface MarketMapUpdateEvent extends BaseRealtimeEvent {
  type: 'MARKET_MAP_UPDATE';
  currentState: string;
  dominantScenario: string;
  dominantProbability: number;
  uncertainty: number;
  bullishBias: number;
  branchCount: number;
}

// Union type for all events
export type RealtimeEvent =
  | RegimeUpdateEvent
  | StateUpdateEvent
  | ScenarioUpdateEvent
  | TreeUpdateEvent
  | MemoryMatchEvent
  | MetaBrainUpdateEvent
  | SignalUpdateEvent
  | SafeModeTriggerEvent
  | ModuleGateChangeEvent
  | EdgeAlertEvent
  | TwinUpdateEvent
  | SystemHealthEvent
  | CandleUpdateEvent
  | PatternDetectedEvent
  | SignalCreatedEvent
  | MarketMapUpdateEvent;

// ═══════════════════════════════════════════════════════════════
// SUBSCRIPTION
// ═══════════════════════════════════════════════════════════════

export interface SubscriptionFilter {
  assets?: string[];
  timeframes?: string[];
  eventTypes?: RealtimeEventType[];
  minPriority?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

export interface Subscription {
  id: string;
  clientId: string;
  filter: SubscriptionFilter;
  createdAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// CONNECTION
// ═══════════════════════════════════════════════════════════════

export interface ClientConnection {
  id: string;
  socket: any;  // WebSocket instance
  subscriptions: Subscription[];
  connectedAt: Date;
  lastPing: Date;
  metadata?: Record<string, any>;
}

// ═══════════════════════════════════════════════════════════════
// STATS
// ═══════════════════════════════════════════════════════════════

export interface RealtimeStats {
  activeConnections: number;
  totalSubscriptions: number;
  eventsPublishedLastMinute: number;
  eventsPublishedLastHour: number;
  topEventTypes: { type: RealtimeEventType; count: number }[];
  avgLatencyMs: number;
}
