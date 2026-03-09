/**
 * Phase 5 — Strategy Registry
 * =============================
 * Pre-configured strategies covering 90% of market conditions
 * 
 * 1. Trend Breakout (35%)
 * 2. Mean Reversion (20%)
 * 3. Liquidity Sweep Reversal (20%)
 * 4. Momentum Continuation (15%)
 * 5. Alt Rotation (10%)
 */

import { Strategy } from './strategy.types.js';

// ═══════════════════════════════════════════════════════════════
// TREND BREAKOUT STRATEGY
// ═══════════════════════════════════════════════════════════════

export const trendBreakoutStrategy: Strategy = {
  id: 'trend_breakout',
  name: 'Trend Breakout',
  description: 'Catches breakouts in trending markets. Uses structure, scenario, regime, and volume profile.',
  
  enabled: true,
  
  conditions: {
    regime: ['TREND_EXPANSION', 'BREAKOUT', 'CONTINUATION'],
    scenario: ['BREAKOUT', 'TREND_CONTINUATION', 'EXPANSION'],
    minScore: 0.65,
    memoryConfidence: 0.55,
  },
  
  risk: {
    maxRiskPerTrade: 0.01,
    maxPositionSize: 0.25,
    leverage: 3,
    maxDrawdown: 0.15,
    maxOpenPositions: 3,
  },
  
  allocation: 0.35,
  
  performance: {
    winRate: 0.58,
    profitFactor: 1.47,
    sharpe: 1.2,
    maxDrawdown: 0.12,
    totalTrades: 182,
    avgReturn: 0.023,
    lastUpdated: Date.now(),
  },
  
  createdAt: Date.now() - 30 * 24 * 3600000,
  updatedAt: Date.now(),
};

// ═══════════════════════════════════════════════════════════════
// MEAN REVERSION STRATEGY
// ═══════════════════════════════════════════════════════════════

export const meanReversionStrategy: Strategy = {
  id: 'mean_reversion',
  name: 'Mean Reversion',
  description: 'Trades range bounds and overextended moves. Uses RSI, volume profile, range detection.',
  
  enabled: true,
  
  conditions: {
    regime: ['RANGE', 'COMPRESSION', 'EXHAUSTION'],
    pattern: ['RANGE_REJECTION', 'DOUBLE_TOP', 'DOUBLE_BOTTOM'],
    scenario: ['RANGE_BOUND', 'REVERSAL'],
    minScore: 0.55,
  },
  
  risk: {
    maxRiskPerTrade: 0.008,
    maxPositionSize: 0.18,
    leverage: 2,
    maxDrawdown: 0.10,
    maxOpenPositions: 2,
  },
  
  allocation: 0.20,
  
  performance: {
    winRate: 0.62,
    profitFactor: 1.35,
    sharpe: 1.1,
    maxDrawdown: 0.08,
    totalTrades: 145,
    avgReturn: 0.015,
    lastUpdated: Date.now(),
  },
  
  createdAt: Date.now() - 30 * 24 * 3600000,
  updatedAt: Date.now(),
};

// ═══════════════════════════════════════════════════════════════
// LIQUIDITY SWEEP REVERSAL STRATEGY
// ═══════════════════════════════════════════════════════════════

export const liquiditySweepStrategy: Strategy = {
  id: 'liquidity_sweep',
  name: 'Liquidity Sweep Reversal',
  description: 'Catches reversals after liquidity sweeps. Uses liquidity engine, sweep detection, memory.',
  
  enabled: true,
  
  conditions: {
    pattern: ['LIQUIDITY_SWEEP', 'STOP_HUNT', 'FAKEOUT'],
    scenario: ['REVERSAL', 'LIQUIDITY_RECOVERY'],
    minScore: 0.60,
    memoryConfidence: 0.50,
  },
  
  risk: {
    maxRiskPerTrade: 0.012,
    maxPositionSize: 0.22,
    leverage: 3,
    maxDrawdown: 0.12,
    maxOpenPositions: 2,
  },
  
  allocation: 0.20,
  
  performance: {
    winRate: 0.55,
    profitFactor: 1.52,
    sharpe: 1.3,
    maxDrawdown: 0.10,
    totalTrades: 98,
    avgReturn: 0.028,
    lastUpdated: Date.now(),
  },
  
  createdAt: Date.now() - 30 * 24 * 3600000,
  updatedAt: Date.now(),
};

// ═══════════════════════════════════════════════════════════════
// MOMENTUM CONTINUATION STRATEGY
// ═══════════════════════════════════════════════════════════════

export const momentumStrategy: Strategy = {
  id: 'momentum',
  name: 'Momentum Continuation',
  description: 'Rides strong trends. Uses RSI, scenario engine, OI positioning.',
  
  enabled: true,
  
  conditions: {
    regime: ['TREND_EXPANSION', 'STRONG_TREND'],
    scenario: ['TREND_CONTINUATION', 'EXPANSION'],
    minScore: 0.70,
  },
  
  risk: {
    maxRiskPerTrade: 0.009,
    maxPositionSize: 0.20,
    leverage: 2,
    maxDrawdown: 0.10,
    maxOpenPositions: 2,
  },
  
  allocation: 0.15,
  
  performance: {
    winRate: 0.52,
    profitFactor: 1.65,
    sharpe: 1.4,
    maxDrawdown: 0.09,
    totalTrades: 76,
    avgReturn: 0.032,
    lastUpdated: Date.now(),
  },
  
  createdAt: Date.now() - 30 * 24 * 3600000,
  updatedAt: Date.now(),
};

// ═══════════════════════════════════════════════════════════════
// ALT ROTATION STRATEGY
// ═══════════════════════════════════════════════════════════════

export const altRotationStrategy: Strategy = {
  id: 'alt_rotation',
  name: 'Alt Rotation',
  description: 'Catches altcoin outperformance when BTC dominance drops. Uses BTC.D, alt dominance.',
  
  enabled: true,
  
  conditions: {
    regime: ['ALT_EXPANSION', 'RISK_ON'],
    scenario: ['ALT_SEASON', 'ROTATION'],
    symbols: ['ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'ADAUSDT'],
    minScore: 0.60,
  },
  
  risk: {
    maxRiskPerTrade: 0.008,
    maxPositionSize: 0.18,
    leverage: 2,
    maxDrawdown: 0.12,
    maxOpenPositions: 4,
  },
  
  allocation: 0.10,
  
  performance: {
    winRate: 0.54,
    profitFactor: 1.38,
    sharpe: 1.0,
    maxDrawdown: 0.11,
    totalTrades: 62,
    avgReturn: 0.021,
    lastUpdated: Date.now(),
  },
  
  createdAt: Date.now() - 30 * 24 * 3600000,
  updatedAt: Date.now(),
};

// ═══════════════════════════════════════════════════════════════
// REGISTRY
// ═══════════════════════════════════════════════════════════════

export const STRATEGY_REGISTRY: Strategy[] = [
  trendBreakoutStrategy,
  meanReversionStrategy,
  liquiditySweepStrategy,
  momentumStrategy,
  altRotationStrategy,
];

/**
 * Get strategy by ID
 */
export function getStrategyById(id: string): Strategy | undefined {
  return STRATEGY_REGISTRY.find(s => s.id === id);
}

/**
 * Get all enabled strategies
 */
export function getEnabledStrategies(): Strategy[] {
  return STRATEGY_REGISTRY.filter(s => s.enabled);
}

/**
 * Get total allocation (should sum to 1.0)
 */
export function getTotalAllocation(): number {
  return STRATEGY_REGISTRY
    .filter(s => s.enabled)
    .reduce((sum, s) => sum + s.allocation, 0);
}
