/**
 * Market Memory — Controller
 * 
 * Orchestrates memory operations
 */

import {
  MarketMemorySnapshot,
  MemoryMatch,
  MemorySummary,
  MemoryBoostResult,
  DEFAULT_MEMORY_CONFIG,
  MemoryConfig
} from './memory.types.js';
import { buildMemorySnapshot, buildMemorySnapshotFromRaw } from './memory.snapshot.js';
import { buildFeatureVector } from './memory.vector.js';
import { searchSimilarSnapshots, summarizeMemoryMatches } from './memory.search.js';
import { buildMemoryBoost } from './memory.boost.js';
import * as storage from './memory.storage.js';
import { DigitalTwinState } from '../digital_twin/digital_twin.types.js';
import { ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// MAIN CONTROLLER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Create and save memory snapshot from Twin state
 */
export async function captureMemorySnapshot(
  twinState: DigitalTwinState
): Promise<MarketMemorySnapshot> {
  const snapshot = buildMemorySnapshot(twinState);
  await storage.saveMemorySnapshot(snapshot);
  return snapshot;
}

/**
 * Search for similar historical states
 */
export async function searchMemory(
  current: MarketMemorySnapshot | DigitalTwinState,
  config: MemoryConfig = DEFAULT_MEMORY_CONFIG
): Promise<{
  matches: MemoryMatch[];
  summary: MemorySummary;
}> {
  // Convert Twin state to snapshot if needed
  let snapshot: MarketMemorySnapshot;
  
  if ('snapshotId' in current && current.featureVector) {
    snapshot = current as MarketMemorySnapshot;
  } else {
    snapshot = buildMemorySnapshot(current as DigitalTwinState);
  }
  
  // Search for similar
  const matches = await searchSimilarSnapshots(snapshot, config);
  
  // Summarize results
  const summary = summarizeMemoryMatches(matches, config);
  
  return { matches, summary };
}

/**
 * Get memory boost for current state
 */
export async function getMemoryBoost(
  current: MarketMemorySnapshot | DigitalTwinState,
  currentScenarios?: Array<{ scenarioId: string; direction: ScenarioDirection }>,
  config: MemoryConfig = DEFAULT_MEMORY_CONFIG
): Promise<MemoryBoostResult> {
  const { matches, summary } = await searchMemory(current, config);
  return buildMemoryBoost(matches, summary, currentScenarios, config);
}

/**
 * Full memory analysis pipeline
 */
export async function analyzeWithMemory(
  asset: string,
  timeframe: string,
  twinState: DigitalTwinState,
  currentScenarios?: Array<{ scenarioId: string; direction: ScenarioDirection }>,
  config: MemoryConfig = DEFAULT_MEMORY_CONFIG
): Promise<{
  snapshot: MarketMemorySnapshot;
  matches: MemoryMatch[];
  summary: MemorySummary;
  boost: MemoryBoostResult;
}> {
  // Build snapshot
  const snapshot = buildMemorySnapshot(twinState);
  
  // Search
  const matches = await searchSimilarSnapshots(snapshot, config);
  
  // Summarize
  const summary = summarizeMemoryMatches(matches, config);
  
  // Calculate boost
  const boost = buildMemoryBoost(matches, summary, currentScenarios, config);
  
  return { snapshot, matches, summary, boost };
}

// ═══════════════════════════════════════════════════════════════
// OUTCOME RESOLUTION
// ═══════════════════════════════════════════════════════════════

/**
 * Resolve snapshot outcome
 */
export async function resolveOutcome(
  snapshotId: string,
  direction: 'BULL' | 'BEAR' | 'NEUTRAL',
  moveATR: number,
  scenarioResolved: string,
  barsToResolution: number
): Promise<void> {
  await storage.updateSnapshotOutcome(snapshotId, {
    direction,
    moveATR,
    scenarioResolved,
    barsToResolution
  });
}

// ═══════════════════════════════════════════════════════════════
// STATUS & STATS
// ═══════════════════════════════════════════════════════════════

export interface MemoryStatus {
  enabled: boolean;
  totalSnapshots: number;
  resolvedSnapshots: number;
  assetTimeframes: Array<{ asset: string; timeframe: string; count: number }>;
  outcomeDistribution: Record<string, number>;
  config: MemoryConfig;
}

/**
 * Get memory module status
 */
export async function getMemoryStatus(): Promise<MemoryStatus> {
  const stats = await storage.getMemoryStats();
  
  return {
    enabled: true,
    totalSnapshots: stats.totalSnapshots,
    resolvedSnapshots: stats.resolvedSnapshots,
    assetTimeframes: stats.assetTimeframes,
    outcomeDistribution: stats.outcomeDistribution,
    config: DEFAULT_MEMORY_CONFIG
  };
}

// ═══════════════════════════════════════════════════════════════
// SYNTHETIC DATA GENERATION (for testing)
// ═══════════════════════════════════════════════════════════════

/**
 * Generate synthetic memory snapshots for testing
 */
export async function generateSyntheticMemory(
  asset: string,
  timeframe: string,
  count: number = 100
): Promise<number> {
  const regimes = ['COMPRESSION', 'BREAKOUT_PREP', 'TREND_EXPANSION', 'RANGE_ROTATION', 'TREND_CONTINUATION'];
  const states = ['COMPRESSION', 'BREAKOUT_ATTEMPT', 'BREAKOUT', 'RETEST', 'EXPANSION', 'RANGE'];
  const physics = ['COMPRESSION', 'RELEASE', 'EXPANSION', 'NEUTRAL'];
  const liquidity = ['SWEEP_LOW', 'SWEEP_HIGH', 'NEUTRAL'];
  const scenarios = ['CLASSIC_BREAKOUT', 'FALSE_BREAKOUT', 'SWEEP_REVERSAL', 'RANGE_CONTINUATION'];
  const directions: Array<'BULL' | 'BEAR' | 'NEUTRAL'> = ['BULL', 'BEAR', 'NEUTRAL'];
  
  let created = 0;
  const now = Date.now();
  
  for (let i = 0; i < count; i++) {
    const ts = now - (count - i) * 86400000;  // 1 day apart
    
    const snapshot = buildMemorySnapshotFromRaw({
      asset,
      timeframe,
      ts,
      regime: regimes[Math.floor(Math.random() * regimes.length)],
      marketState: states[Math.floor(Math.random() * states.length)],
      physicsState: physics[Math.floor(Math.random() * physics.length)],
      liquidityState: liquidity[Math.floor(Math.random() * liquidity.length)],
      dominantScenario: scenarios[Math.floor(Math.random() * scenarios.length)],
      energy: 0.3 + Math.random() * 0.5,
      instability: 0.1 + Math.random() * 0.6,
      confidence: 0.4 + Math.random() * 0.4
    });
    
    // Add resolved outcome (80% of snapshots)
    if (Math.random() < 0.8) {
      const direction = directions[Math.floor(Math.random() * directions.length)];
      snapshot.outcome = {
        direction,
        moveATR: 0.5 + Math.random() * 3,
        scenarioResolved: scenarios[Math.floor(Math.random() * scenarios.length)],
        barsToResolution: Math.floor(3 + Math.random() * 15)
      };
      snapshot.resolvedAt = new Date(ts + Math.floor(Math.random() * 86400000 * 10));
    }
    
    await storage.saveMemorySnapshot(snapshot);
    created++;
  }
  
  return created;
}

/**
 * Cleanup old memory
 */
export async function cleanupMemory(keepDays: number = 365): Promise<number> {
  return storage.cleanupOldSnapshots(keepDays);
}
