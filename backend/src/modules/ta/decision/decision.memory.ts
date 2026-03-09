/**
 * P0 — Memory Boost Integration for Decision Engine
 * 
 * Fetches memory boost data from Market Memory Engine
 * and provides it to Decision Engine for score adjustment
 */

import { MemoryBoostResult } from '../../market_memory/memory.types.js';
import { ScenarioDirection } from '../../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface DecisionMemoryBoost {
  memoryConfidence: number;
  bullishBoost: number;
  bearishBoost: number;
  neutralBoost: number;
  scenarioBoost: Record<string, number>;
  riskAdjustment: number;
  matchCount: number;
  dominantOutcome: ScenarioDirection;
  historicalBias: 'BULL' | 'BEAR' | 'NEUTRAL';
}

export interface MemoryIntegrationResult {
  directionBoost: number;
  scenarioBoost: number;
  riskAdjustment: number;
  memoryConfidence: number;
  matchCount: number;
  historicalBias: 'BULL' | 'BEAR' | 'NEUTRAL';
}

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

// Clamp ranges per user spec
const MIN_DIRECTION_BOOST = 0.85;
const MAX_DIRECTION_BOOST = 1.20;
const MIN_SCENARIO_BOOST = 0.85;
const MAX_SCENARIO_BOOST = 1.20;

// ═══════════════════════════════════════════════════════════════
// MEMORY BOOST FETCHER
// ═══════════════════════════════════════════════════════════════

/**
 * Fetch memory boost from Market Memory Engine
 * Returns neutral values on failure (system must not crash)
 */
export async function fetchMemoryBoost(
  asset: string,
  timeframe: string
): Promise<DecisionMemoryBoost> {
  try {
    const res = await fetch(
      `http://localhost:8001/api/ta/memory/boost?asset=${asset}&tf=${timeframe}`
    );

    if (!res.ok) {
      return createNeutralMemoryBoost();
    }

    const json = await res.json() as any;
    
    if (!json.success || !json.data) {
      return createNeutralMemoryBoost();
    }

    const data = json.data as MemoryBoostResult;

    return {
      memoryConfidence: data.memoryConfidence ?? 0,
      bullishBoost: data.bullishBoost ?? 1,
      bearishBoost: data.bearishBoost ?? 1,
      neutralBoost: data.neutralBoost ?? 1,
      scenarioBoost: data.scenarioBoost ?? {},
      riskAdjustment: data.riskAdjustment ?? 1,
      matchCount: data.matchCount ?? 0,
      dominantOutcome: data.dominantOutcome ?? 'NEUTRAL',
      historicalBias: mapDominantToBias(data.dominantOutcome)
    };
  } catch (err) {
    // Fallback — system must continue working
    return createNeutralMemoryBoost();
  }
}

/**
 * Create neutral memory boost (no effect on system)
 */
function createNeutralMemoryBoost(): DecisionMemoryBoost {
  return {
    memoryConfidence: 0,
    bullishBoost: 1,
    bearishBoost: 1,
    neutralBoost: 1,
    scenarioBoost: {},
    riskAdjustment: 1,
    matchCount: 0,
    dominantOutcome: 'NEUTRAL',
    historicalBias: 'NEUTRAL'
  };
}

/**
 * Map dominant outcome to bias string
 */
function mapDominantToBias(outcome: ScenarioDirection | undefined): 'BULL' | 'BEAR' | 'NEUTRAL' {
  if (outcome === 'BULL') return 'BULL';
  if (outcome === 'BEAR') return 'BEAR';
  return 'NEUTRAL';
}

// ═══════════════════════════════════════════════════════════════
// BOOST CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get direction boost for scenario
 * Clamped to 0.85 - 1.20 range
 */
export function getDirectionBoost(
  direction: 'LONG' | 'SHORT' | 'BULL' | 'BEAR' | 'NEUTRAL',
  memory: DecisionMemoryBoost
): number {
  let boost: number;

  if (direction === 'LONG' || direction === 'BULL') {
    boost = memory.bullishBoost;
  } else if (direction === 'SHORT' || direction === 'BEAR') {
    boost = memory.bearishBoost;
  } else {
    boost = memory.neutralBoost;
  }

  // Clamp to safe range
  return clamp(boost, MIN_DIRECTION_BOOST, MAX_DIRECTION_BOOST);
}

/**
 * Get scenario-specific boost
 * Clamped to 0.85 - 1.20 range
 */
export function getScenarioBoost(
  scenarioId: string,
  memory: DecisionMemoryBoost
): number {
  const boost = memory.scenarioBoost[scenarioId] ?? 1;
  return clamp(boost, MIN_SCENARIO_BOOST, MAX_SCENARIO_BOOST);
}

/**
 * Calculate complete memory integration for a scenario
 */
export function calculateMemoryIntegration(
  scenarioId: string,
  direction: 'LONG' | 'SHORT',
  memory: DecisionMemoryBoost
): MemoryIntegrationResult {
  const directionBoost = getDirectionBoost(direction, memory);
  const scenarioBoost = getScenarioBoost(scenarioId, memory);

  return {
    directionBoost,
    scenarioBoost,
    riskAdjustment: memory.riskAdjustment,
    memoryConfidence: memory.memoryConfidence,
    matchCount: memory.matchCount,
    historicalBias: memory.historicalBias
  };
}

// ═══════════════════════════════════════════════════════════════
// RISK ADJUSTMENT
// ═══════════════════════════════════════════════════════════════

/**
 * Apply risk adjustment to position size
 * 
 * Example:
 * baseSize = 0.20, riskAdjustment = 0.82
 * → adjustedSize = 0.164
 */
export function applyRiskAdjustment(
  baseSize: number,
  riskAdjustment: number
): number {
  return baseSize * riskAdjustment;
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
