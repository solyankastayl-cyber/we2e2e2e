/**
 * MetaBrain v3 — Strategy Controller
 */

import {
  MetaBrainV3Context,
  StrategyPolicy,
  StrategyConfig,
  DEFAULT_STRATEGY_CONFIG,
  MetaBrainRiskMode
} from './metabrain_v3.types.js';
import { MarketRegime } from '../regime/regime.types.js';

// ═══════════════════════════════════════════════════════════════
// STRATEGY SELECTION
// ═══════════════════════════════════════════════════════════════

/**
 * Get appropriate strategies for regime
 */
export function getStrategiesForRegime(
  regime: MarketRegime,
  config: StrategyConfig = DEFAULT_STRATEGY_CONFIG
): string[] {
  switch (regime) {
    case 'TREND_EXPANSION':
    case 'TREND_CONTINUATION':
      return [...config.trendStrategies, ...config.breakoutStrategies];
    
    case 'RANGE_ROTATION':
      return config.rangeStrategies;
    
    case 'BREAKOUT_PREP':
    case 'COMPRESSION':
      return config.breakoutStrategies;
    
    case 'VOLATILITY_EXPANSION':
    case 'LIQUIDITY_HUNT':
      return [...config.breakoutStrategies, ...config.reversalStrategies];
    
    case 'ACCUMULATION':
    case 'DISTRIBUTION':
      return [...config.reversalStrategies, ...config.rangeStrategies];
    
    default:
      return [...config.trendStrategies, ...config.rangeStrategies];
  }
}

/**
 * Get strategies to disable for regime
 */
export function getDisabledStrategiesForRegime(
  regime: MarketRegime,
  config: StrategyConfig = DEFAULT_STRATEGY_CONFIG
): string[] {
  switch (regime) {
    case 'TREND_EXPANSION':
    case 'TREND_CONTINUATION':
      return config.rangeStrategies;  // Disable range strategies in trend
    
    case 'RANGE_ROTATION':
      return config.trendStrategies;  // Disable trend strategies in range
    
    default:
      return [];
  }
}

/**
 * Calculate strategy multiplier based on context
 */
export function calculateStrategyMultiplier(
  context: MetaBrainV3Context,
  riskMode: MetaBrainRiskMode
): number {
  let multiplier = 1.0;
  
  // Adjust by risk mode
  switch (riskMode) {
    case 'SAFE':
      multiplier = 0.5;
      break;
    case 'CONSERVATIVE':
      multiplier = 0.75;
      break;
    case 'NORMAL':
      multiplier = 1.0;
      break;
    case 'AGGRESSIVE':
      multiplier = 1.15;
      break;
  }
  
  // Adjust by memory confidence
  if (context.memoryConfidence > 0.7) {
    multiplier *= 1.1;
  } else if (context.memoryConfidence < 0.3 && context.memoryMatches > 10) {
    multiplier *= 0.9;
  }
  
  // Adjust by tree risk
  if (context.treeRisk > 0.4) {
    multiplier *= 0.9;
  }
  
  return Math.round(Math.max(0.5, Math.min(1.3, multiplier)) * 1000) / 1000;
}

/**
 * Build strategy policy
 */
export function buildStrategyPolicy(
  context: MetaBrainV3Context,
  riskMode: MetaBrainRiskMode,
  safeMode: boolean,
  config: StrategyConfig = DEFAULT_STRATEGY_CONFIG
): StrategyPolicy {
  // In safe mode, minimal strategies
  if (safeMode) {
    return {
      enabledStrategies: ['CONSERVATIVE_TREND'],
      disabledStrategies: [
        ...config.trendStrategies,
        ...config.rangeStrategies,
        ...config.breakoutStrategies,
        ...config.reversalStrategies
      ],
      strategyMultiplier: 0.5
    };
  }
  
  const enabled = getStrategiesForRegime(context.regime, config);
  const disabled = getDisabledStrategiesForRegime(context.regime, config);
  const multiplier = calculateStrategyMultiplier(context, riskMode);
  
  return {
    enabledStrategies: enabled,
    disabledStrategies: disabled,
    strategyMultiplier: multiplier
  };
}
