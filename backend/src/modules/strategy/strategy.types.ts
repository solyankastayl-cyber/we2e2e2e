/**
 * Phase 5 — Strategy Platform Types
 * ====================================
 * Strategy = Policy Layer, not Signal Generator
 * Strategies FILTER decisions, not generate them
 */

// ═══════════════════════════════════════════════════════════════
// STRATEGY
// ═══════════════════════════════════════════════════════════════

export interface Strategy {
  id: string;
  name: string;
  description: string;
  
  enabled: boolean;
  
  conditions: StrategyConditions;
  risk: StrategyRisk;
  allocation: number;  // Capital weight 0..1
  
  performance?: StrategyPerformance;
  
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════════════════════
// CONDITIONS (Filter criteria)
// ═══════════════════════════════════════════════════════════════

export interface StrategyConditions {
  // Regime filter
  regime?: string[];
  
  // Pattern filter
  pattern?: string[];
  
  // Scenario filter
  scenario?: string[];
  
  // Minimum score threshold
  minScore?: number;
  
  // Minimum memory confidence
  memoryConfidence?: number;
  
  // Symbol filter (empty = all)
  symbols?: string[];
  
  // Timeframe filter
  timeframes?: string[];
}

// ═══════════════════════════════════════════════════════════════
// RISK MODEL
// ═══════════════════════════════════════════════════════════════

export interface StrategyRisk {
  maxRiskPerTrade: number;     // 0.01 = 1%
  maxPositionSize: number;     // 0.25 = 25% of capital
  leverage?: number;           // Max leverage
  maxDrawdown?: number;        // Stop strategy if DD exceeds
  maxOpenPositions?: number;   // Limit concurrent positions
}

// ═══════════════════════════════════════════════════════════════
// PERFORMANCE
// ═══════════════════════════════════════════════════════════════

export interface StrategyPerformance {
  winRate: number;
  profitFactor: number;
  sharpe?: number;
  maxDrawdown: number;
  totalTrades: number;
  avgReturn: number;
  lastUpdated: number;
}

// ═══════════════════════════════════════════════════════════════
// DECISION INPUT (from Decision Engine)
// ═══════════════════════════════════════════════════════════════

export interface DecisionInput {
  symbol: string;
  timeframe: string;
  signal: 'LONG' | 'SHORT' | 'NO_TRADE';
  score: number;
  confidence: number;
  regime: string;
  scenario: string;
  pattern?: string;
  memoryConfidence?: number;
}

// ═══════════════════════════════════════════════════════════════
// FILTER RESULT
// ═══════════════════════════════════════════════════════════════

export interface StrategyFilterResult {
  allowed: boolean;
  matchedStrategies: Strategy[];
  selectedStrategy?: Strategy;
  positionSize?: number;
  reason?: string;
}

// ═══════════════════════════════════════════════════════════════
// BACKTEST
// ═══════════════════════════════════════════════════════════════

export interface BacktestRequest {
  strategyId: string;
  symbol: string;
  startDate: string;
  endDate: string;
  initialCapital?: number;
}

export interface BacktestResult {
  strategyId: string;
  symbol: string;
  period: { start: string; end: string };
  
  performance: StrategyPerformance;
  
  trades: BacktestTrade[];
  
  equityCurve: { ts: number; equity: number }[];
}

export interface BacktestTrade {
  timestamp: number;
  signal: 'LONG' | 'SHORT';
  entry: number;
  exit: number;
  returnPct: number;
  outcome: 'WIN' | 'LOSS';
}

// ═══════════════════════════════════════════════════════════════
// ALLOCATION
// ═══════════════════════════════════════════════════════════════

export interface StrategyAllocation {
  strategyId: string;
  name: string;
  capitalWeight: number;
  enabled: boolean;
}
