/**
 * Market Memory Engine — Types
 * 
 * MM1-MM2: Memory snapshots, vectors, search, and boost
 */

import { MarketRegime } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';
import { PhysicsState } from '../market_physics/physics.types.js';
import { ScenarioDirection, MarketBehaviorState } from '../scenario_engine/scenario.types.js';
import { LiquidityStateType } from '../digital_twin/digital_twin.types.js';

// ═══════════════════════════════════════════════════════════════
// MM1 — MEMORY SNAPSHOT
// ═══════════════════════════════════════════════════════════════

export interface MemoryOutcome {
  direction: ScenarioDirection;
  moveATR: number;
  scenarioResolved: string;
  barsToResolution: number;
}

export interface MarketMemorySnapshot {
  snapshotId: string;
  
  asset: string;
  timeframe: string;
  ts: number;
  
  // State fields
  regime: MarketRegime;
  marketState: MarketStateNode;
  physicsState: PhysicsState;
  liquidityState: LiquidityStateType;
  dominantScenario: string;
  
  // Metrics
  energy: number;
  instability: number;
  confidence: number;
  
  // Feature vector for similarity search
  featureVector: number[];
  
  // Outcome (filled later when resolved)
  outcome?: MemoryOutcome;
  
  // Metadata
  createdAt: Date;
  resolvedAt?: Date;
}

// ═══════════════════════════════════════════════════════════════
// MM1 — MEMORY MATCH
// ═══════════════════════════════════════════════════════════════

export interface MemoryMatch {
  snapshotId: string;
  similarity: number;
  
  // Snapshot fields
  regime: MarketRegime;
  marketState: MarketStateNode;
  dominantScenario: string;
  
  // Outcome (if resolved)
  outcomeDirection?: ScenarioDirection;
  moveATR?: number;
  scenarioResolved?: string;
  barsToResolution?: number;
}

// ═══════════════════════════════════════════════════════════════
// MM1 — MEMORY SUMMARY
// ═══════════════════════════════════════════════════════════════

export interface MemorySummary {
  matches: number;
  avgSimilarity: number;
  
  // Direction distribution
  bullRate: number;
  bearRate: number;
  neutralRate: number;
  
  // Move statistics
  avgMoveATR: number;
  avgBarsToResolution: number;
  
  // Dominant outcome
  dominantDirection: ScenarioDirection;
  dominantResolvedScenario: string;
  
  // Confidence (based on sample size and consistency)
  memoryConfidence: number;
}

// ═══════════════════════════════════════════════════════════════
// MM2 — MEMORY BOOST
// ═══════════════════════════════════════════════════════════════

export interface MemoryBoostResult {
  memoryConfidence: number;
  
  // Direction boosts (0.85 - 1.20)
  bullishBoost: number;
  bearishBoost: number;
  neutralBoost: number;
  
  // Scenario-specific boosts
  scenarioBoost: Record<string, number>;
  
  // Risk adjustment (based on outcome consistency)
  riskAdjustment: number;
  
  // Summary
  matchCount: number;
  dominantOutcome: ScenarioDirection;
}

// ═══════════════════════════════════════════════════════════════
// FEATURE VECTOR ENCODING
// ═══════════════════════════════════════════════════════════════

export const REGIME_ENCODING: Record<MarketRegime, number> = {
  'COMPRESSION': 0.1,
  'BREAKOUT_PREP': 0.2,
  'TREND_EXPANSION': 0.3,
  'RANGE_ROTATION': 0.4,
  'TREND_CONTINUATION': 0.5,
  'VOLATILITY_EXPANSION': 0.6,
  'LIQUIDITY_HUNT': 0.7,
  'ACCUMULATION': 0.8,
  'DISTRIBUTION': 0.9
};

export const STATE_ENCODING: Record<MarketStateNode, number> = {
  'COMPRESSION': 0.1,
  'BREAKOUT_ATTEMPT': 0.2,
  'BREAKOUT': 0.25,
  'FALSE_BREAKOUT': 0.3,
  'RETEST': 0.35,
  'EXPANSION': 0.4,
  'LIQUIDITY_SWEEP': 0.45,
  'REVERSAL': 0.5,
  'RANGE': 0.55,
  'BALANCE': 0.6,
  'EXHAUSTION': 0.65,
  'CONTINUATION': 0.7
};

export const PHYSICS_ENCODING: Record<PhysicsState, number> = {
  'COMPRESSION': 0.2,
  'RELEASE': 0.4,
  'EXPANSION': 0.6,
  'EXHAUSTION': 0.8,
  'NEUTRAL': 0.5
};

export const LIQUIDITY_ENCODING: Record<LiquidityStateType, number> = {
  'SWEEP_LOW': 0.2,
  'SWEEP_HIGH': 0.8,
  'EQUAL_LOWS': 0.3,
  'EQUAL_HIGHS': 0.7,
  'NEUTRAL': 0.5
};

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

export interface MemoryConfig {
  // Search settings
  minSimilarity: number;
  maxMatches: number;
  
  // Boost settings
  minBoost: number;
  maxBoost: number;
  
  // Confidence thresholds
  minMatchesForConfidence: number;
  consistencyThreshold: number;
  
  // Vector weights
  vectorWeights: {
    regime: number;
    state: number;
    physics: number;
    liquidity: number;
    scenario: number;
    energy: number;
    instability: number;
    confidence: number;
  };
}

export const DEFAULT_MEMORY_CONFIG: MemoryConfig = {
  minSimilarity: 0.6,
  maxMatches: 30,
  
  minBoost: 0.85,
  maxBoost: 1.20,
  
  minMatchesForConfidence: 5,
  consistencyThreshold: 0.6,
  
  vectorWeights: {
    regime: 2.0,
    state: 2.0,
    physics: 1.5,
    liquidity: 1.5,
    scenario: 1.0,
    energy: 1.0,
    instability: 0.8,
    confidence: 0.8
  }
};

// ═══════════════════════════════════════════════════════════════
// API TYPES
// ═══════════════════════════════════════════════════════════════

export interface MemorySearchResponse {
  success: boolean;
  data?: {
    currentSnapshot: Partial<MarketMemorySnapshot>;
    matches: MemoryMatch[];
    summary: MemorySummary;
  };
  error?: string;
}

export interface MemoryBoostResponse {
  success: boolean;
  data?: MemoryBoostResult;
  error?: string;
}
