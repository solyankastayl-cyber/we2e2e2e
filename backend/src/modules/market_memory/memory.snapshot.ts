/**
 * MM1 — Memory Snapshot Builder
 * 
 * Creates memory snapshots from Digital Twin state
 */

import {
  MarketMemorySnapshot,
  MemoryOutcome,
  DEFAULT_MEMORY_CONFIG
} from './memory.types.js';
import { DigitalTwinState } from '../digital_twin/digital_twin.types.js';
import { buildFeatureVector } from './memory.vector.js';
import { v4 as uuidv4 } from 'uuid';

// ═══════════════════════════════════════════════════════════════
// SNAPSHOT BUILDER
// ═══════════════════════════════════════════════════════════════

/**
 * Build memory snapshot from Digital Twin state
 */
export function buildMemorySnapshot(
  twinState: DigitalTwinState
): MarketMemorySnapshot {
  const snapshot: MarketMemorySnapshot = {
    snapshotId: `MEM_${uuidv4().substring(0, 8)}`,
    
    asset: twinState.asset,
    timeframe: twinState.timeframe,
    ts: twinState.ts,
    
    regime: twinState.regime,
    marketState: twinState.marketState,
    physicsState: twinState.physicsState,
    liquidityState: twinState.liquidityState,
    dominantScenario: twinState.dominantScenario,
    
    energy: twinState.energy,
    instability: twinState.instability,
    confidence: twinState.confidence,
    
    featureVector: [],  // Will be built below
    
    createdAt: new Date()
  };
  
  // Build feature vector
  snapshot.featureVector = buildFeatureVector(snapshot);
  
  return snapshot;
}

/**
 * Build memory snapshot from raw data (without Digital Twin)
 */
export function buildMemorySnapshotFromRaw(data: {
  asset: string;
  timeframe: string;
  ts: number;
  regime: string;
  marketState: string;
  physicsState: string;
  liquidityState: string;
  dominantScenario: string;
  energy: number;
  instability: number;
  confidence: number;
}): MarketMemorySnapshot {
  const snapshot: MarketMemorySnapshot = {
    snapshotId: `MEM_${uuidv4().substring(0, 8)}`,
    
    asset: data.asset,
    timeframe: data.timeframe,
    ts: data.ts,
    
    regime: data.regime as MarketMemorySnapshot['regime'],
    marketState: data.marketState as MarketMemorySnapshot['marketState'],
    physicsState: data.physicsState as MarketMemorySnapshot['physicsState'],
    liquidityState: data.liquidityState as MarketMemorySnapshot['liquidityState'],
    dominantScenario: data.dominantScenario,
    
    energy: data.energy,
    instability: data.instability,
    confidence: data.confidence,
    
    featureVector: [],
    
    createdAt: new Date()
  };
  
  snapshot.featureVector = buildFeatureVector(snapshot);
  
  return snapshot;
}

// ═══════════════════════════════════════════════════════════════
// OUTCOME RESOLUTION
// ═══════════════════════════════════════════════════════════════

/**
 * Update snapshot with resolved outcome
 */
export function resolveSnapshotOutcome(
  snapshot: MarketMemorySnapshot,
  outcome: MemoryOutcome
): MarketMemorySnapshot {
  return {
    ...snapshot,
    outcome,
    resolvedAt: new Date()
  };
}

/**
 * Determine outcome direction from price move
 */
export function determineOutcomeDirection(
  moveATR: number,
  threshold: number = 0.5
): 'BULL' | 'BEAR' | 'NEUTRAL' {
  if (moveATR > threshold) return 'BULL';
  if (moveATR < -threshold) return 'BEAR';
  return 'NEUTRAL';
}

/**
 * Create outcome from resolved scenario
 */
export function createOutcome(
  direction: 'BULL' | 'BEAR' | 'NEUTRAL',
  moveATR: number,
  scenarioResolved: string,
  barsToResolution: number
): MemoryOutcome {
  return {
    direction,
    moveATR: Math.abs(moveATR),
    scenarioResolved,
    barsToResolution
  };
}

// ═══════════════════════════════════════════════════════════════
// SNAPSHOT VALIDATION
// ═══════════════════════════════════════════════════════════════

/**
 * Validate snapshot has required fields
 */
export function validateSnapshot(snapshot: MarketMemorySnapshot): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];
  
  if (!snapshot.snapshotId) errors.push('Missing snapshotId');
  if (!snapshot.asset) errors.push('Missing asset');
  if (!snapshot.timeframe) errors.push('Missing timeframe');
  if (!snapshot.regime) errors.push('Missing regime');
  if (!snapshot.marketState) errors.push('Missing marketState');
  if (!snapshot.featureVector || snapshot.featureVector.length === 0) {
    errors.push('Missing or empty featureVector');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * Check if snapshot has outcome
 */
export function hasOutcome(snapshot: MarketMemorySnapshot): boolean {
  return snapshot.outcome !== undefined && snapshot.resolvedAt !== undefined;
}
