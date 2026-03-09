/**
 * Phase 8 — Strategy Generator
 * 
 * Generates strategy candidates from edge combinations
 */

import { v4 as uuidv4 } from 'uuid';
import {
  StrategyCandidate,
  StrategyGeneratorConfig,
  DEFAULT_GENERATOR_CONFIG,
  EntryRule,
  ExitRule
} from './strategy.types.js';

// ═══════════════════════════════════════════════════════════════
// EDGE INPUT TYPES
// ═══════════════════════════════════════════════════════════════

export interface EdgeDimensionData {
  key: string;
  edgeScore: number;
  profitFactor: number;
  sampleSize: number;
}

export interface EdgeCombination {
  pattern: EdgeDimensionData;
  state: EdgeDimensionData;
  liquidity: EdgeDimensionData;
  scenario?: EdgeDimensionData;
  regime?: string;
  
  // Combined metrics
  combinedPF?: number;
  synergy?: number;
}

// ═══════════════════════════════════════════════════════════════
// ENTRY/EXIT RULE MAPPING
// ═══════════════════════════════════════════════════════════════

const PATTERN_ENTRY_RULES: Record<string, EntryRule> = {
  'TRIANGLE_ASC': 'BREAKOUT_CLOSE',
  'TRIANGLE_DESC': 'BREAKOUT_CLOSE',
  'TRIANGLE_SYM': 'BREAKOUT_CLOSE',
  'FLAG_BULL': 'BREAKOUT_CLOSE',
  'FLAG_BEAR': 'BREAKOUT_CLOSE',
  'DOUBLE_BOTTOM': 'BREAKOUT_RETEST',
  'DOUBLE_TOP': 'BREAKOUT_RETEST',
  'HNS': 'BREAKOUT_RETEST',
  'IHNS': 'BREAKOUT_RETEST',
  'HARMONIC_GARTLEY_BULL': 'PATTERN_COMPLETE',
  'HARMONIC_GARTLEY_BEAR': 'PATTERN_COMPLETE',
  'HARMONIC_BAT_BULL': 'PATTERN_COMPLETE',
  'HARMONIC_BAT_BEAR': 'PATTERN_COMPLETE',
  'LIQUIDITY_SWEEP_HIGH': 'SWEEP_REVERSAL',
  'LIQUIDITY_SWEEP_LOW': 'SWEEP_REVERSAL',
  'BOS_BULL': 'STATE_TRANSITION',
  'BOS_BEAR': 'STATE_TRANSITION',
  'CHOCH_BULL': 'STATE_TRANSITION',
  'CHOCH_BEAR': 'STATE_TRANSITION'
};

const STATE_ENTRY_MODIFIERS: Record<string, EntryRule | null> = {
  'COMPRESSION': null,  // Use pattern default
  'BREAKOUT': 'BREAKOUT_CLOSE',
  'EXPANSION': null,
  'REVERSAL': 'SWEEP_REVERSAL',
  'RETEST': 'BREAKOUT_RETEST'
};

const LIQUIDITY_EXIT_RULES: Record<string, ExitRule> = {
  'SWEEP_UP': 'TRAILING_STOP',
  'SWEEP_DOWN': 'TRAILING_STOP',
  'NEUTRAL': 'FIXED_TARGET',
  'HIGH_LIQUIDITY': 'TRAILING_STOP',
  'LOW_LIQUIDITY': 'FIXED_TARGET'
};

// ═══════════════════════════════════════════════════════════════
// MAIN GENERATOR
// ═══════════════════════════════════════════════════════════════

/**
 * Generate strategy candidates from top edge combinations
 */
export function generateStrategyCandidates(
  topPatterns: EdgeDimensionData[],
  topStates: EdgeDimensionData[],
  topLiquidity: EdgeDimensionData[],
  config: StrategyGeneratorConfig = DEFAULT_GENERATOR_CONFIG
): StrategyCandidate[] {
  const candidates: StrategyCandidate[] = [];
  
  // Limit inputs
  const patterns = topPatterns.slice(0, config.topPatternsCount);
  const states = topStates.slice(0, config.topStatesCount);
  const liquidities = topLiquidity.slice(0, config.topLiquidityCount);
  
  // Generate combinations
  for (const pattern of patterns) {
    for (const state of states) {
      for (const liquidity of liquidities) {
        // Skip if combined edge is too low
        const combinedEdge = (pattern.edgeScore + state.edgeScore + liquidity.edgeScore) / 3;
        if (combinedEdge < 0.1) continue;
        
        // Generate ATR variations
        for (const stopATR of config.stopATROptions) {
          for (const targetATR of config.targetATROptions) {
            // Skip if R:R is too low
            const riskReward = targetATR / stopATR;
            if (riskReward < 1.5) continue;
            
            // Determine rules
            const entryRule = determineEntryRule(pattern.key, state.key);
            const exitRule = determineExitRule(liquidity.key, state.key);
            
            candidates.push({
              strategyId: `STR_${uuidv4().slice(0, 8).toUpperCase()}`,
              pattern: pattern.key,
              state: state.key,
              liquidity: liquidity.key,
              entryRule,
              exitRule,
              stopATR,
              targetATR,
              riskReward,
              createdAt: new Date(),
              source: 'GENERATED'
            });
          }
        }
      }
    }
  }
  
  // Limit total candidates
  return candidates.slice(0, config.maxStrategies);
}

/**
 * Generate from edge attributions (pre-computed combinations)
 */
export function generateFromAttributions(
  attributions: EdgeCombination[],
  config: StrategyGeneratorConfig = DEFAULT_GENERATOR_CONFIG
): StrategyCandidate[] {
  const candidates: StrategyCandidate[] = [];
  
  for (const attr of attributions) {
    // Skip low-synergy combinations
    if (attr.synergy && attr.synergy < 0.9) continue;
    if (attr.combinedPF && attr.combinedPF < config.minProfitFactor) continue;
    
    for (const stopATR of config.stopATROptions) {
      for (const targetATR of config.targetATROptions) {
        const riskReward = targetATR / stopATR;
        if (riskReward < 1.5) continue;
        
        const entryRule = determineEntryRule(attr.pattern.key, attr.state.key);
        const exitRule = determineExitRule(attr.liquidity.key, attr.state.key);
        
        candidates.push({
          strategyId: `STR_${uuidv4().slice(0, 8).toUpperCase()}`,
          pattern: attr.pattern.key,
          state: attr.state.key,
          liquidity: attr.liquidity.key,
          scenario: attr.scenario?.key,
          regime: attr.regime,
          entryRule,
          exitRule,
          stopATR,
          targetATR,
          riskReward,
          createdAt: new Date(),
          source: 'GENERATED'
        });
      }
    }
  }
  
  return candidates.slice(0, config.maxStrategies);
}

// ═══════════════════════════════════════════════════════════════
// RULE DETERMINATION
// ═══════════════════════════════════════════════════════════════

function determineEntryRule(pattern: string, state: string): string {
  // Check state modifier first
  const stateRule = STATE_ENTRY_MODIFIERS[state];
  if (stateRule) return stateRule;
  
  // Use pattern-specific rule
  const patternRule = PATTERN_ENTRY_RULES[pattern];
  if (patternRule) return patternRule;
  
  // Default
  return 'BREAKOUT_CLOSE';
}

function determineExitRule(liquidity: string, state: string): string {
  // High volatility states prefer trailing
  if (state === 'EXPANSION' || state === 'BREAKOUT') {
    return 'TRAILING_STOP';
  }
  
  // Use liquidity-based rule
  const liqRule = LIQUIDITY_EXIT_RULES[liquidity];
  if (liqRule) return liqRule;
  
  // Default
  return 'FIXED_TARGET';
}

// ═══════════════════════════════════════════════════════════════
// OPTIMIZATION
// ═══════════════════════════════════════════════════════════════

/**
 * Optimize strategy parameters based on backtest results
 */
export function optimizeStrategyParams(
  candidate: StrategyCandidate,
  backtestResults: Array<{ stopATR: number; targetATR: number; pf: number; trades: number }>
): StrategyCandidate | null {
  if (backtestResults.length === 0) return null;
  
  // Find best configuration
  let bestConfig = backtestResults[0];
  let bestScore = 0;
  
  for (const result of backtestResults) {
    if (result.trades < 30) continue;
    
    const score = result.pf * Math.log10(result.trades);
    if (score > bestScore) {
      bestScore = score;
      bestConfig = result;
    }
  }
  
  if (bestScore === 0) return null;
  
  return {
    ...candidate,
    strategyId: `STR_${uuidv4().slice(0, 8).toUpperCase()}`,
    stopATR: bestConfig.stopATR,
    targetATR: bestConfig.targetATR,
    riskReward: bestConfig.targetATR / bestConfig.stopATR,
    source: 'OPTIMIZED'
  };
}
