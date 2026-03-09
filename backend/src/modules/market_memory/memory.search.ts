/**
 * MM1 — Memory Search Engine
 * 
 * Finds similar historical market states
 */

import {
  MarketMemorySnapshot,
  MemoryMatch,
  MemorySummary,
  DEFAULT_MEMORY_CONFIG,
  MemoryConfig
} from './memory.types.js';
import { weightedSimilarity, buildFeatureVector } from './memory.vector.js';
import { getResolvedSnapshots } from './memory.storage.js';
import { ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// SEARCH ENGINE
// ═══════════════════════════════════════════════════════════════

/**
 * Search for similar historical snapshots
 */
export async function searchSimilarSnapshots(
  current: MarketMemorySnapshot,
  config: MemoryConfig = DEFAULT_MEMORY_CONFIG
): Promise<MemoryMatch[]> {
  // Get resolved snapshots from DB
  const historicalSnapshots = await getResolvedSnapshots(
    undefined, // All assets for now
    undefined, // All timeframes
    1000
  );
  
  if (historicalSnapshots.length === 0) {
    return [];
  }
  
  // Calculate similarity for each
  const matches: MemoryMatch[] = [];
  
  for (const historical of historicalSnapshots) {
    // Skip same snapshot
    if (historical.snapshotId === current.snapshotId) continue;
    
    // Calculate similarity
    const similarity = weightedSimilarity(
      current.featureVector,
      historical.featureVector
    );
    
    // Filter by minimum similarity
    if (similarity < config.minSimilarity) continue;
    
    matches.push({
      snapshotId: historical.snapshotId,
      similarity,
      regime: historical.regime,
      marketState: historical.marketState,
      dominantScenario: historical.dominantScenario,
      outcomeDirection: historical.outcome?.direction,
      moveATR: historical.outcome?.moveATR,
      scenarioResolved: historical.outcome?.scenarioResolved,
      barsToResolution: historical.outcome?.barsToResolution
    });
  }
  
  // Sort by similarity descending
  matches.sort((a, b) => b.similarity - a.similarity);
  
  // Limit results
  return matches.slice(0, config.maxMatches);
}

/**
 * Search with pre-loaded snapshots (faster, no DB call)
 */
export function searchSimilarSnapshotsInMemory(
  current: MarketMemorySnapshot,
  historicalSnapshots: MarketMemorySnapshot[],
  config: MemoryConfig = DEFAULT_MEMORY_CONFIG
): MemoryMatch[] {
  const matches: MemoryMatch[] = [];
  
  for (const historical of historicalSnapshots) {
    if (historical.snapshotId === current.snapshotId) continue;
    if (!historical.outcome) continue;  // Only resolved
    
    const similarity = weightedSimilarity(
      current.featureVector,
      historical.featureVector
    );
    
    if (similarity < config.minSimilarity) continue;
    
    matches.push({
      snapshotId: historical.snapshotId,
      similarity,
      regime: historical.regime,
      marketState: historical.marketState,
      dominantScenario: historical.dominantScenario,
      outcomeDirection: historical.outcome.direction,
      moveATR: historical.outcome.moveATR,
      scenarioResolved: historical.outcome.scenarioResolved,
      barsToResolution: historical.outcome.barsToResolution
    });
  }
  
  matches.sort((a, b) => b.similarity - a.similarity);
  return matches.slice(0, config.maxMatches);
}

// ═══════════════════════════════════════════════════════════════
// SUMMARY CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Summarize memory matches
 */
export function summarizeMemoryMatches(
  matches: MemoryMatch[],
  config: MemoryConfig = DEFAULT_MEMORY_CONFIG
): MemorySummary {
  if (matches.length === 0) {
    return {
      matches: 0,
      avgSimilarity: 0,
      bullRate: 0.33,
      bearRate: 0.33,
      neutralRate: 0.34,
      avgMoveATR: 0,
      avgBarsToResolution: 0,
      dominantDirection: 'NEUTRAL',
      dominantResolvedScenario: 'UNKNOWN',
      memoryConfidence: 0
    };
  }
  
  // Calculate averages
  const avgSimilarity = matches.reduce((sum, m) => sum + m.similarity, 0) / matches.length;
  
  // Count directions
  const directionCounts: Record<string, number> = { BULL: 0, BEAR: 0, NEUTRAL: 0 };
  const scenarioCounts: Record<string, number> = {};
  let totalMoveATR = 0;
  let totalBars = 0;
  let resolvedCount = 0;
  
  for (const match of matches) {
    if (match.outcomeDirection) {
      directionCounts[match.outcomeDirection]++;
    }
    
    if (match.scenarioResolved) {
      scenarioCounts[match.scenarioResolved] = (scenarioCounts[match.scenarioResolved] || 0) + 1;
    }
    
    if (match.moveATR !== undefined) {
      totalMoveATR += match.moveATR;
      resolvedCount++;
    }
    
    if (match.barsToResolution !== undefined) {
      totalBars += match.barsToResolution;
    }
  }
  
  const total = directionCounts.BULL + directionCounts.BEAR + directionCounts.NEUTRAL;
  const bullRate = total > 0 ? directionCounts.BULL / total : 0.33;
  const bearRate = total > 0 ? directionCounts.BEAR / total : 0.33;
  const neutralRate = total > 0 ? directionCounts.NEUTRAL / total : 0.34;
  
  // Find dominant direction
  let dominantDirection: ScenarioDirection = 'NEUTRAL';
  if (directionCounts.BULL > directionCounts.BEAR && directionCounts.BULL > directionCounts.NEUTRAL) {
    dominantDirection = 'BULL';
  } else if (directionCounts.BEAR > directionCounts.BULL && directionCounts.BEAR > directionCounts.NEUTRAL) {
    dominantDirection = 'BEAR';
  }
  
  // Find dominant scenario
  let dominantResolvedScenario = 'UNKNOWN';
  let maxScenarioCount = 0;
  for (const [scenario, count] of Object.entries(scenarioCounts)) {
    if (count > maxScenarioCount) {
      maxScenarioCount = count;
      dominantResolvedScenario = scenario;
    }
  }
  
  // Calculate memory confidence
  const memoryConfidence = calculateMemoryConfidence(
    matches.length,
    avgSimilarity,
    bullRate,
    bearRate,
    neutralRate,
    config
  );
  
  return {
    matches: matches.length,
    avgSimilarity,
    bullRate,
    bearRate,
    neutralRate,
    avgMoveATR: resolvedCount > 0 ? totalMoveATR / resolvedCount : 0,
    avgBarsToResolution: resolvedCount > 0 ? totalBars / resolvedCount : 0,
    dominantDirection,
    dominantResolvedScenario,
    memoryConfidence
  };
}

/**
 * Calculate memory confidence based on matches quality
 */
function calculateMemoryConfidence(
  matchCount: number,
  avgSimilarity: number,
  bullRate: number,
  bearRate: number,
  neutralRate: number,
  config: MemoryConfig
): number {
  // Base confidence from sample size
  const sampleSizeConf = Math.min(1, Math.log10(matchCount + 1) / Math.log10(config.minMatchesForConfidence + 1));
  
  // Similarity contribution
  const similarityConf = avgSimilarity;
  
  // Consistency (how concentrated are outcomes)
  const maxRate = Math.max(bullRate, bearRate, neutralRate);
  const consistencyConf = (maxRate - 0.33) / 0.67;  // Normalize to 0-1
  
  // Combine
  const confidence = (
    sampleSizeConf * 0.3 +
    similarityConf * 0.4 +
    consistencyConf * 0.3
  );
  
  return Math.min(1, Math.max(0, confidence));
}
