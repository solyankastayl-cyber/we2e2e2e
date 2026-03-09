/**
 * Phase 8 — Adaptive Strategy Builder Types
 * 
 * Auto-generates trading strategies from edge combinations
 */

// ═══════════════════════════════════════════════════════════════
// STRATEGY CANDIDATE
// ═══════════════════════════════════════════════════════════════

export interface StrategyCandidate {
  strategyId: string;
  
  // Condition dimensions
  pattern: string;
  state: string;
  liquidity: string;
  scenario?: string;
  regime?: string;
  
  // Entry/Exit rules
  entryRule: string;
  exitRule: string;
  
  // Risk parameters
  stopATR: number;
  targetATR: number;
  riskReward: number;
  
  // Meta
  createdAt: Date;
  source: 'GENERATED' | 'MANUAL' | 'OPTIMIZED';
}

// ═══════════════════════════════════════════════════════════════
// STRATEGY PERFORMANCE
// ═══════════════════════════════════════════════════════════════

export interface StrategyPerformance {
  // Sample
  trades: number;
  wins: number;
  losses: number;
  breakevens: number;
  
  // Performance metrics
  winRate: number;
  avgR: number;
  profitFactor: number;
  sharpe: number;
  maxDD: number;
  
  // Derived
  expectancy: number;  // avgR per trade
  avgWin: number;
  avgLoss: number;
  
  // Time stats
  avgBarsInTrade: number;
  maxConsecutiveLosses: number;
}

// ═══════════════════════════════════════════════════════════════
// STRATEGY ENTITY (Stored)
// ═══════════════════════════════════════════════════════════════

export interface Strategy {
  strategyId: string;
  
  // Conditions
  pattern: string;
  state: string;
  liquidity: string;
  scenario?: string;
  regime?: string;
  
  // Rules
  entryRule: string;
  exitRule: string;
  
  // Risk params
  stopATR: number;
  targetATR: number;
  riskReward: number;
  
  // Performance
  performance: StrategyPerformance;
  
  // Score for ranking
  strategyScore: number;
  
  // Status
  status: 'CANDIDATE' | 'ACTIVE' | 'PAUSED' | 'RETIRED';
  
  // Meta
  createdAt: Date;
  updatedAt: Date;
  lastBacktestAt?: Date;
  
  // Segmentation
  asset?: string;
  timeframe?: string;
}

// ═══════════════════════════════════════════════════════════════
// STRATEGY SCORE CALCULATION
// ═══════════════════════════════════════════════════════════════

export function calculateStrategyScore(perf: StrategyPerformance): number {
  if (perf.trades < 30) return 0;
  
  // Score = PF × log(trades) × sharpe
  const pfComponent = Math.max(0, perf.profitFactor - 1);
  const sizeComponent = Math.log10(perf.trades) / 2;
  const sharpeComponent = Math.max(0, perf.sharpe);
  
  return pfComponent * sizeComponent * (1 + sharpeComponent * 0.3);
}

// ═══════════════════════════════════════════════════════════════
// GENERATION CONFIG
// ═══════════════════════════════════════════════════════════════

export interface StrategyGeneratorConfig {
  minTrades: number;
  minProfitFactor: number;
  minWinRate: number;
  maxStrategies: number;
  
  // ATR variations to test
  stopATROptions: number[];
  targetATROptions: number[];
  
  // Dimensions to combine
  topPatternsCount: number;
  topStatesCount: number;
  topLiquidityCount: number;
}

export const DEFAULT_GENERATOR_CONFIG: StrategyGeneratorConfig = {
  minTrades: 30,
  minProfitFactor: 1.1,
  minWinRate: 0.45,
  maxStrategies: 100,
  
  stopATROptions: [1, 1.5, 2],
  targetATROptions: [2, 2.5, 3, 4],
  
  topPatternsCount: 10,
  topStatesCount: 5,
  topLiquidityCount: 4
};

// ═══════════════════════════════════════════════════════════════
// ENTRY/EXIT RULE TYPES
// ═══════════════════════════════════════════════════════════════

export type EntryRule = 
  | 'BREAKOUT_CLOSE'
  | 'BREAKOUT_RETEST'
  | 'PATTERN_COMPLETE'
  | 'SWEEP_REVERSAL'
  | 'STATE_TRANSITION';

export type ExitRule =
  | 'FIXED_TARGET'
  | 'TRAILING_STOP'
  | 'TIME_EXIT'
  | 'OPPOSITE_SIGNAL';

export const ENTRY_RULES: Record<EntryRule, string> = {
  'BREAKOUT_CLOSE': 'Enter on breakout candle close',
  'BREAKOUT_RETEST': 'Enter on retest after breakout',
  'PATTERN_COMPLETE': 'Enter when pattern completes',
  'SWEEP_REVERSAL': 'Enter after liquidity sweep',
  'STATE_TRANSITION': 'Enter on state change'
};

export const EXIT_RULES: Record<ExitRule, string> = {
  'FIXED_TARGET': 'Exit at fixed target ATR',
  'TRAILING_STOP': 'Exit with trailing stop',
  'TIME_EXIT': 'Exit after N bars',
  'OPPOSITE_SIGNAL': 'Exit on opposite signal'
};

// ═══════════════════════════════════════════════════════════════
// BACKTEST TRADE
// ═══════════════════════════════════════════════════════════════

export interface BacktestTrade {
  strategyId: string;
  entryTime: Date;
  exitTime: Date;
  direction: 'LONG' | 'SHORT';
  entryPrice: number;
  exitPrice: number;
  stopPrice: number;
  targetPrice: number;
  resultR: number;
  outcome: 'WIN' | 'LOSS' | 'BREAKEVEN';
  barsInTrade: number;
}

// ═══════════════════════════════════════════════════════════════
// STRATEGY MATCH (for real-time)
// ═══════════════════════════════════════════════════════════════

export interface StrategyMatch {
  strategy: Strategy;
  matchScore: number;  // How well current conditions match
  dimensions: {
    pattern: boolean;
    state: boolean;
    liquidity: boolean;
    scenario: boolean;
    regime: boolean;
  };
}
