/**
 * MM2 — Memory Boost Engine
 * 
 * Converts memory matches to actionable boosts
 */

import {
  MemoryMatch,
  MemorySummary,
  MemoryBoostResult,
  DEFAULT_MEMORY_CONFIG,
  MemoryConfig
} from './memory.types.js';
import { ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// BOOST BUILDER
// ═══════════════════════════════════════════════════════════════

/**
 * Build memory boost from matches and summary
 */
export function buildMemoryBoost(
  matches: MemoryMatch[],
  summary: MemorySummary,
  currentScenarios?: Array<{ scenarioId: string; direction: ScenarioDirection }>,
  config: MemoryConfig = DEFAULT_MEMORY_CONFIG
): MemoryBoostResult {
  if (matches.length === 0 || summary.memoryConfidence < 0.1) {
    return createNeutralBoost();
  }
  
  const { memoryConfidence, bullRate, bearRate, neutralRate } = summary;
  
  // Calculate direction boosts
  const bullishBoost = calculateDirectionBoost(bullRate, memoryConfidence, config);
  const bearishBoost = calculateDirectionBoost(bearRate, memoryConfidence, config);
  const neutralBoost = calculateDirectionBoost(neutralRate, memoryConfidence, config);
  
  // Calculate scenario-specific boosts
  const scenarioBoost = calculateScenarioBoosts(matches, summary, currentScenarios, config);
  
  // Calculate risk adjustment
  const riskAdjustment = calculateRiskAdjustment(summary, config);
  
  return {
    memoryConfidence,
    bullishBoost,
    bearishBoost,
    neutralBoost,
    scenarioBoost,
    riskAdjustment,
    matchCount: matches.length,
    dominantOutcome: summary.dominantDirection
  };
}

/**
 * Create neutral (no effect) boost
 */
function createNeutralBoost(): MemoryBoostResult {
  return {
    memoryConfidence: 0,
    bullishBoost: 1.0,
    bearishBoost: 1.0,
    neutralBoost: 1.0,
    scenarioBoost: {},
    riskAdjustment: 1.0,
    matchCount: 0,
    dominantOutcome: 'NEUTRAL'
  };
}

// ═══════════════════════════════════════════════════════════════
// DIRECTION BOOST
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate boost for a direction based on historical rate
 * 
 * Formula: boost = 1 + (rate - 0.33) * confidence * scale
 * Rate > 0.33 → boost > 1
 * Rate < 0.33 → boost < 1
 */
function calculateDirectionBoost(
  rate: number,
  confidence: number,
  config: MemoryConfig
): number {
  const scale = 0.6;  // Max deviation from 1.0
  
  // Deviation from expected (33.3%)
  const deviation = rate - 0.333;
  
  // Apply confidence scaling
  const rawBoost = 1 + (deviation * confidence * scale);
  
  // Clamp to allowed range
  return Math.max(config.minBoost, Math.min(config.maxBoost, rawBoost));
}

// ═══════════════════════════════════════════════════════════════
// SCENARIO BOOST
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate boosts for each current scenario based on memory
 */
function calculateScenarioBoosts(
  matches: MemoryMatch[],
  summary: MemorySummary,
  currentScenarios: Array<{ scenarioId: string; direction: ScenarioDirection }> | undefined,
  config: MemoryConfig
): Record<string, number> {
  const boosts: Record<string, number> = {};
  
  if (!currentScenarios || currentScenarios.length === 0) {
    return boosts;
  }
  
  // Count historical scenario outcomes
  const historicalScenarios: Record<string, number> = {};
  for (const match of matches) {
    if (match.scenarioResolved) {
      historicalScenarios[match.scenarioResolved] = 
        (historicalScenarios[match.scenarioResolved] || 0) + 1;
    }
  }
  
  const totalMatches = matches.length || 1;
  
  for (const current of currentScenarios) {
    // Direct scenario match boost
    const directMatchCount = historicalScenarios[current.scenarioId] || 0;
    const directMatchRate = directMatchCount / totalMatches;
    
    // Direction alignment boost
    const directionRate = 
      current.direction === 'BULL' ? summary.bullRate :
      current.direction === 'BEAR' ? summary.bearRate :
      summary.neutralRate;
    
    // Combined boost
    let scenarioBoost = 1.0;
    
    // Direct match contribution
    if (directMatchRate > 0.1) {
      scenarioBoost += (directMatchRate - 0.1) * summary.memoryConfidence * 0.5;
    }
    
    // Direction alignment contribution
    if (directionRate > 0.4) {
      scenarioBoost += (directionRate - 0.4) * summary.memoryConfidence * 0.3;
    } else if (directionRate < 0.25) {
      scenarioBoost -= (0.25 - directionRate) * summary.memoryConfidence * 0.3;
    }
    
    boosts[current.scenarioId] = Math.max(config.minBoost, Math.min(config.maxBoost, scenarioBoost));
  }
  
  return boosts;
}

// ═══════════════════════════════════════════════════════════════
// RISK ADJUSTMENT
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate risk adjustment based on historical outcome consistency
 * 
 * Mixed historical outcomes → lower risk adjustment
 * Consistent outcomes → neutral/higher risk adjustment
 */
function calculateRiskAdjustment(
  summary: MemorySummary,
  config: MemoryConfig
): number {
  const { bullRate, bearRate, neutralRate, memoryConfidence, matches } = summary;
  
  // Not enough data → neutral
  if (matches < config.minMatchesForConfidence) {
    return 1.0;
  }
  
  // Calculate concentration (how unanimous are outcomes)
  const maxRate = Math.max(bullRate, bearRate, neutralRate);
  const minRate = Math.min(bullRate, bearRate, neutralRate);
  const concentration = maxRate - minRate;
  
  // High concentration → confident about direction
  // Low concentration → uncertain, reduce risk
  
  if (concentration < 0.2) {
    // Very mixed outcomes
    return 0.8;
  } else if (concentration < 0.4) {
    // Somewhat mixed
    return 0.9 + (concentration - 0.2) * 0.5;
  } else {
    // Clear direction
    return 1.0 + (concentration - 0.4) * 0.1 * memoryConfidence;
  }
}

// ═══════════════════════════════════════════════════════════════
// INTEGRATION HELPERS
// ═══════════════════════════════════════════════════════════════

/**
 * Apply memory boost to scenario probability
 */
export function applyMemoryBoostToScenario(
  probability: number,
  direction: ScenarioDirection,
  boost: MemoryBoostResult
): number {
  const directionBoost = 
    direction === 'BULL' ? boost.bullishBoost :
    direction === 'BEAR' ? boost.bearishBoost :
    boost.neutralBoost;
  
  return Math.min(1, probability * directionBoost);
}

/**
 * Get scenario-specific boost
 */
export function getScenarioMemoryBoost(
  scenarioId: string,
  boost: MemoryBoostResult
): number {
  return boost.scenarioBoost[scenarioId] || 1.0;
}

/**
 * Apply risk adjustment to position size
 */
export function applyRiskAdjustment(
  baseSize: number,
  boost: MemoryBoostResult
): number {
  return baseSize * boost.riskAdjustment;
}
