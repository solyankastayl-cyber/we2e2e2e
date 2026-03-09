/**
 * Phase 5 — Strategy Filter
 * ===========================
 * Strategies FILTER decisions, not generate them.
 * 
 * Pipeline:
 *   Decision Engine → Strategy Filter → Portfolio → Execution
 */

import {
  Strategy,
  DecisionInput,
  StrategyFilterResult,
} from './strategy.types.js';
import { getEnabledStrategies } from './strategy.registry.js';

// ═══════════════════════════════════════════════════════════════
// FILTER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Check if a decision matches a strategy's conditions
 */
function matchesStrategy(decision: DecisionInput, strategy: Strategy): boolean {
  const { conditions } = strategy;
  
  // Skip NO_TRADE signals
  if (decision.signal === 'NO_TRADE') {
    return false;
  }
  
  // Check minimum score
  if (conditions.minScore !== undefined && decision.score < conditions.minScore) {
    return false;
  }
  
  // Check memory confidence
  if (conditions.memoryConfidence !== undefined && 
      decision.memoryConfidence !== undefined &&
      decision.memoryConfidence < conditions.memoryConfidence) {
    return false;
  }
  
  // Check regime
  if (conditions.regime && conditions.regime.length > 0) {
    if (!conditions.regime.includes(decision.regime)) {
      return false;
    }
  }
  
  // Check scenario
  if (conditions.scenario && conditions.scenario.length > 0) {
    if (!conditions.scenario.includes(decision.scenario)) {
      return false;
    }
  }
  
  // Check pattern
  if (conditions.pattern && conditions.pattern.length > 0 && decision.pattern) {
    if (!conditions.pattern.includes(decision.pattern)) {
      return false;
    }
  }
  
  // Check symbol filter
  if (conditions.symbols && conditions.symbols.length > 0) {
    if (!conditions.symbols.includes(decision.symbol)) {
      return false;
    }
  }
  
  // Check timeframe filter
  if (conditions.timeframes && conditions.timeframes.length > 0) {
    if (!conditions.timeframes.includes(decision.timeframe)) {
      return false;
    }
  }
  
  return true;
}

/**
 * Find all strategies that match a decision
 */
export function matchStrategies(decision: DecisionInput): Strategy[] {
  const strategies = getEnabledStrategies();
  return strategies.filter(s => matchesStrategy(decision, s));
}

/**
 * Select best strategy from matched ones
 * Priority: highest win rate * profit factor
 */
export function selectBestStrategy(matched: Strategy[]): Strategy | undefined {
  if (matched.length === 0) return undefined;
  
  // Sort by composite score: winRate * profitFactor
  const sorted = [...matched].sort((a, b) => {
    const scoreA = (a.performance?.winRate || 0.5) * (a.performance?.profitFactor || 1);
    const scoreB = (b.performance?.winRate || 0.5) * (b.performance?.profitFactor || 1);
    return scoreB - scoreA;
  });
  
  return sorted[0];
}

/**
 * Calculate position size based on strategy
 */
export function calculatePositionSize(
  decision: DecisionInput,
  strategy: Strategy,
  baseCapital: number = 100000
): number {
  const { risk, allocation } = strategy;
  
  // Base position from allocation
  let size = baseCapital * allocation;
  
  // Apply max position size limit
  if (size > baseCapital * risk.maxPositionSize) {
    size = baseCapital * risk.maxPositionSize;
  }
  
  // Adjust by confidence
  size *= decision.confidence;
  
  // Adjust by score (higher score = larger position)
  const scoreMultiplier = 0.8 + (decision.score * 0.4);  // 0.8 to 1.2
  size *= scoreMultiplier;
  
  return Math.round(size * 100) / 100;
}

/**
 * Main filter function
 * Returns whether decision is allowed and which strategy handles it
 */
export function applyStrategyFilter(decision: DecisionInput): StrategyFilterResult {
  // Find matching strategies
  const matched = matchStrategies(decision);
  
  if (matched.length === 0) {
    return {
      allowed: false,
      matchedStrategies: [],
      reason: 'No strategy conditions matched',
    };
  }
  
  // Select best strategy
  const selected = selectBestStrategy(matched);
  
  if (!selected) {
    return {
      allowed: false,
      matchedStrategies: matched,
      reason: 'Could not select strategy',
    };
  }
  
  // Calculate position size
  const positionSize = calculatePositionSize(decision, selected);
  
  return {
    allowed: true,
    matchedStrategies: matched,
    selectedStrategy: selected,
    positionSize,
  };
}

/**
 * Get strategy matching summary for a decision
 */
export function getMatchingSummary(decision: DecisionInput): {
  totalStrategies: number;
  matched: number;
  matchedNames: string[];
  selected?: string;
} {
  const matched = matchStrategies(decision);
  const selected = selectBestStrategy(matched);
  
  return {
    totalStrategies: getEnabledStrategies().length,
    matched: matched.length,
    matchedNames: matched.map(s => s.name),
    selected: selected?.name,
  };
}
