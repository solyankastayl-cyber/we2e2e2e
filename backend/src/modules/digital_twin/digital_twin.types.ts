/**
 * Digital Twin Types
 * 
 * DT1-DT4: Complete Digital Twin module types
 * - Twin State Snapshot
 * - Branch modeling
 * - Consistency Engine
 * - Counterfactual Engine
 */

import { MarketRegime } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';
import { PhysicsState } from '../market_physics/physics.types.js';
import { MarketBehaviorState, ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// DT1 — TWIN BRANCH
// ═══════════════════════════════════════════════════════════════

export interface TwinBranch {
  branchId: string;
  path: MarketBehaviorState[];
  direction: ScenarioDirection;
  probability: number;
  expectedMoveATR: number;
  failureRisk: number;
}

// ═══════════════════════════════════════════════════════════════
// DT1 — DIGITAL TWIN STATE (Core)
// ═══════════════════════════════════════════════════════════════

export type LiquidityStateType = 
  | 'SWEEP_LOW'
  | 'SWEEP_HIGH'
  | 'EQUAL_HIGHS'
  | 'EQUAL_LOWS'
  | 'NEUTRAL';

export interface DigitalTwinState {
  asset: string;
  timeframe: string;
  ts: number;
  
  // Module states
  regime: MarketRegime;
  marketState: MarketStateNode;
  physicsState: PhysicsState;
  liquidityState: LiquidityStateType;
  
  // Dominant scenario
  dominantScenario: string;
  
  // Energy and metrics
  energy: number;           // 0-1 from physics
  instability: number;      // 0-1 calculated
  confidence: number;       // 0-1 overall
  
  // Branches (top 3)
  branches: TwinBranch[];
  
  // DT3 — Consistency
  consistencyScore?: number;
  conflicts?: TwinConflict[];
  
  // DT4 — Counterfactual
  counterfactual?: CounterfactualResult;
  
  // P0 — Memory Context (from Market Memory Engine)
  memory?: {
    confidence: number;
    matches: number;
    bias: 'BULL' | 'BEAR' | 'NEUTRAL';
  };
  
  // Metadata
  computedAt: Date;
  version: number;
}

// ═══════════════════════════════════════════════════════════════
// DT2 — TWIN REACTOR (Event-driven updates)
// ═══════════════════════════════════════════════════════════════

export type TwinEventType =
  | 'NEW_CANDLE'
  | 'PATTERN_DETECTED'
  | 'LIQUIDITY_EVENT'
  | 'REGIME_CHANGE'
  | 'STATE_CHANGE'
  | 'SCENARIO_UPDATE'
  | 'EXECUTION_EVENT';

export interface TwinEvent {
  type: TwinEventType;
  asset: string;
  timeframe: string;
  ts: number;
  payload?: unknown;
}

export interface TwinReactorResult {
  event: TwinEvent;
  previousState?: DigitalTwinState;
  newState: DigitalTwinState;
  stateChanged: boolean;
  changedFields: string[];
}

// ═══════════════════════════════════════════════════════════════
// DT3 — CONSISTENCY ENGINE
// ═══════════════════════════════════════════════════════════════

export type ConflictType =
  | 'REGIME_PHYSICS'        // Regime vs physics state mismatch
  | 'REGIME_SCENARIO'       // Regime vs scenario direction mismatch
  | 'LIQUIDITY_DIRECTION'   // Liquidity event vs scenario direction
  | 'PHYSICS_SCENARIO'      // Physics state vs scenario expectation
  | 'STATE_SCENARIO'        // Market state vs scenario path
  | 'ENERGY_SCENARIO';      // Energy level vs scenario type

export type ConflictSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface TwinConflict {
  type: ConflictType;
  modules: string[];
  severity: ConflictSeverity;
  severityScore: number;    // 0.1-0.9
  description: string;
  resolution: string;
}

export interface TwinConsistency {
  score: number;            // 0-1 (1 = fully consistent)
  conflicts: TwinConflict[];
  totalConflictWeight: number;
}

// ═══════════════════════════════════════════════════════════════
// DT4 — COUNTERFACTUAL ENGINE
// ═══════════════════════════════════════════════════════════════

export interface CounterfactualBranch {
  branchId: string;
  triggerEvent: string;
  path: MarketBehaviorState[];
  direction: ScenarioDirection;
  probability: number;
  expectedMoveATR: number;
  riskToMainScenario: number;
}

export interface CounterfactualResult {
  mainScenarioId: string;
  mainScenarioProb: number;
  alternatives: CounterfactualBranch[];
  scenarioBreakRisk: number;  // 0-1
  dominantAlternative?: CounterfactualBranch;
}

// ═══════════════════════════════════════════════════════════════
// TWIN CONTEXT (Input from all modules)
// ═══════════════════════════════════════════════════════════════

export interface TwinContext {
  asset: string;
  timeframe: string;
  ts: number;
  
  // From Regime Engine
  regime?: {
    regime: MarketRegime;
    confidence: number;
    probabilities?: Record<MarketRegime, number>;
  };
  
  // From State Engine
  state?: {
    currentState: MarketStateNode;
    stateConfidence: number;
    nextStateProbabilities?: Array<{
      state: MarketStateNode;
      probability: number;
    }>;
    stateBoost: number;
  };
  
  // From Physics Engine
  physics?: {
    physicsState: PhysicsState;
    energyScore: number;
    compressionScore: number;
    releaseProbability: number;
    exhaustionScore: number;
    physicsBoost: number;
  };
  
  // From Liquidity Engine
  liquidity?: {
    liquidityBias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    recentSweepUp: boolean;
    recentSweepDown: boolean;
    zonesAbove: number;
    zonesBelow: number;
  };
  
  // From Scenario Engine
  scenarios?: Array<{
    scenarioId: string;
    direction: ScenarioDirection;
    probability: number;
    confidence: number;
    path: MarketBehaviorState[];
    expectedMoveATR: number;
  }>;
  
  // From MetaBrain
  metabrain?: {
    riskMode: 'CONSERVATIVE' | 'NORMAL' | 'AGGRESSIVE';
    confidenceThreshold: number;
    metaRiskMultiplier: number;
  };
  
  // From Execution
  execution?: {
    portfolioExposure: number;
    openPositions: number;
    portfolioStress: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

export interface DigitalTwinConfig {
  // Branch limits
  maxBranches: number;
  minBranchProbability: number;
  
  // Consistency thresholds
  minConsistencyScore: number;
  conflictSeverityThresholds: {
    low: number;
    medium: number;
    high: number;
    critical: number;
  };
  
  // Counterfactual settings
  maxAlternatives: number;
  minAlternativeProbability: number;
  
  // Instability calculation
  instabilityWeights: {
    volatility: number;
    branchConflict: number;
    failureRisk: number;
    consistencyPenalty: number;
  };
  
  // Storage
  keepHistoryDays: number;
  snapshotInterval: number;  // Minutes
}

export const DEFAULT_TWIN_CONFIG: DigitalTwinConfig = {
  maxBranches: 3,
  minBranchProbability: 0.05,
  
  minConsistencyScore: 0.5,
  conflictSeverityThresholds: {
    low: 0.1,
    medium: 0.3,
    high: 0.6,
    critical: 0.9
  },
  
  maxAlternatives: 3,
  minAlternativeProbability: 0.1,
  
  instabilityWeights: {
    volatility: 0.3,
    branchConflict: 0.25,
    failureRisk: 0.25,
    consistencyPenalty: 0.2
  },
  
  keepHistoryDays: 30,
  snapshotInterval: 15
};

// ═══════════════════════════════════════════════════════════════
// API TYPES
// ═══════════════════════════════════════════════════════════════

export interface TwinStateResponse {
  success: boolean;
  data?: DigitalTwinState;
  error?: string;
}

export interface TwinBranchesResponse {
  success: boolean;
  data?: {
    asset: string;
    timeframe: string;
    branches: TwinBranch[];
    dominantBranch?: TwinBranch;
  };
  error?: string;
}

export interface TwinConsistencyResponse {
  success: boolean;
  data?: TwinConsistency;
  error?: string;
}

export interface TwinCounterfactualResponse {
  success: boolean;
  data?: CounterfactualResult;
  error?: string;
}

export interface TwinHistoryResponse {
  success: boolean;
  data?: {
    asset: string;
    timeframe: string;
    history: DigitalTwinState[];
    count: number;
  };
  error?: string;
}

// ═══════════════════════════════════════════════════════════════
// DT5 — BRANCH TREE EXPANSION
// ═══════════════════════════════════════════════════════════════

export interface TwinTreeNode {
  nodeId: string;
  state: MarketStateNode;
  event?: string;
  
  probability: number;
  expectedMoveATR: number;
  failureRisk: number;
  
  children?: TwinTreeNode[];
}

export interface TwinBranchTree {
  asset: string;
  timeframe: string;
  ts: number;
  
  rootState: MarketStateNode;
  depth: number;
  
  branches: TwinTreeNode[];
  
  treeStats: TreeStats;
}

export interface TreeStats {
  dominanceScore: number;     // How much one branch dominates (0-1)
  uncertaintyScore: number;   // Overall tree uncertainty (0-1)
  treeRisk: number;           // Risk from alternative branches (0-1)
  mainBranchProbability: number;
  totalBranches: number;
  maxDepthReached: number;
}

export interface TreeConfig {
  maxDepth: number;
  maxChildrenPerNode: number;
  minBranchProbability: number;
}

export const DEFAULT_TREE_CONFIG: TreeConfig = {
  maxDepth: 3,
  maxChildrenPerNode: 3,
  minBranchProbability: 0.10
};

export interface TwinTreeResponse {
  success: boolean;
  data?: TwinBranchTree;
  error?: string;
}

