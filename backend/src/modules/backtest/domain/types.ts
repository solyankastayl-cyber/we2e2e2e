/**
 * Phase 5.1 — Backtest Domain Types
 * 
 * Core contracts for backtest harness
 */

// ═══════════════════════════════════════════════════════════════
// Request/Config Types
// ═══════════════════════════════════════════════════════════════

export interface BacktestRunRequest {
  asset: string;             // "BTCUSDT"
  timeframe: string;         // "1d" | "4h" | "1h"
  from: string;              // ISO date
  to: string;                // ISO date
  warmupBars?: number;       // default 300
  stepBars?: number;         // default 1
  maxTrades?: number;        // optional limit
  feesBps?: number;          // default 2
  slippageBps?: number;      // default 1
  seed?: number;             // default fixed for determinism
}

// ═══════════════════════════════════════════════════════════════
// Run & Trade Documents (MongoDB)
// ═══════════════════════════════════════════════════════════════

export type BacktestRunStatus = 'CREATED' | 'RUNNING' | 'DONE' | 'FAILED';

export interface BacktestConfig {
  warmupBars: number;
  stepBars: number;
  maxTrades?: number;
  feesBps: number;
  slippageBps: number;
  seed: number;
  
  // Versioning for determinism
  labelVersion: string;
  featureSchemaVersion: string;
  entryModelVersion: string;
  rModelVersion: string;
  edgeRunId: string;
}

export interface BacktestRunDoc {
  runId: string;
  createdAt: string;
  
  asset: string;
  timeframe: string;
  from: string;
  to: string;
  
  config: BacktestConfig;
  
  status: BacktestRunStatus;
  error?: string;
  
  summary?: BacktestSummary;
}

export type BacktestExitType = 
  | 'NO_ENTRY' 
  | 'STOP' 
  | 'T1' 
  | 'T2' 
  | 'TIMEOUT' 
  | 'PARTIAL';

export interface DecisionSnapshot {
  scenarioId: string;
  bias: 'LONG' | 'SHORT' | 'WAIT';
  pEntry: number;
  eR: number;
  ev: number;
  patternsUsed: string[];
  edgeMultiplier?: number;
}

export interface BacktestTradeDoc {
  runId: string;
  tradeId: string;
  
  // Candle indices
  signalIndex: number;       // candle where signal was generated
  openedAtIndex: number;     // candle where entry happened (-1 if NO_ENTRY)
  closedAtIndex: number;     // candle where exit happened
  
  // Prices
  entryPrice?: number;       // undefined if NO_ENTRY
  stopPrice?: number;
  target1?: number;
  target2?: number;
  exitPrice?: number;
  
  exitType: BacktestExitType;
  
  // R Metrics
  rMultiple: number;         // 0 for NO_ENTRY
  mfeR: number;
  maeR: number;
  
  // Costs
  feesBps: number;
  slippageBps: number;
  
  // Timing
  barsToEntry: number;
  barsToExit: number;
  
  // Decision context
  decisionSnapshot: DecisionSnapshot;
}

// ═══════════════════════════════════════════════════════════════
// Summary & Metrics
// ═══════════════════════════════════════════════════════════════

export interface EquityCurvePoint {
  index: number;
  cumulativeR: number;
}

export interface BacktestSummary {
  // Counts
  trades: number;            // executed (entry hit)
  noEntry: number;
  wins: number;
  losses: number;
  timeouts: number;
  partials: number;
  
  // Core metrics
  winRate: number;           // wins / (wins + losses)
  avgR: number;
  profitFactor: number;      // sum(positiveR) / abs(sum(negativeR))
  expectancy: number;        // mean R of all trades
  maxDrawdownR: number;      // in R units
  sharpeR: number;           // mean(R) / std(R)
  
  // Equity
  equityCurve: {
    points: number;
    endR: number;
    peakR: number;
  };
  
  // Timing
  avgBarsToEntry: number;
  avgBarsToExit: number;
  
  // Calibration
  evCorrelation: number;     // corr(EV, realizedR) - if positive, model works
}

// ═══════════════════════════════════════════════════════════════
// Trade Plan (from Decision Adapter)
// ═══════════════════════════════════════════════════════════════

export interface TradePlan {
  scenarioId: string;
  bias: 'LONG' | 'SHORT';
  
  entryPrice: number;
  stopPrice: number;
  target1: number;
  target2?: number;
  
  timeoutBars: number;
  
  // ML predictions
  pEntry: number;
  eR: number;
  ev: number;
  
  // Context
  patternsUsed: string[];
  edgeMultiplier?: number;
}

// ═══════════════════════════════════════════════════════════════
// Trade Simulation
// ═══════════════════════════════════════════════════════════════

export type IntrabarPolicy = 'CONSERVATIVE' | 'OPTIMISTIC';

export interface TradeSimulationConfig {
  intrabarPolicy: IntrabarPolicy;
  feesBps: number;
  slippageBps: number;
}

export type TradeStatus = 
  | 'NO_ENTRY' 
  | 'LOSS' 
  | 'WIN_T1' 
  | 'WIN_T2' 
  | 'TIMEOUT' 
  | 'PARTIAL';

export interface TradeResult {
  status: TradeStatus;
  
  entryTs?: number;
  exitTs?: number;
  
  entryPrice?: number;
  exitPrice?: number;
  stopPrice: number;
  target1: number;
  target2?: number;
  
  rMultiple: number;
  mfeR: number;
  maeR: number;
  
  barsToEntry: number;
  barsToExit: number;
  
  debug: {
    entryBarIndex: number;
    exitBarIndex: number;
    reason: string;
  };
}

// ═══════════════════════════════════════════════════════════════
// Candle Type
// ═══════════════════════════════════════════════════════════════

export interface Candle {
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

// ═══════════════════════════════════════════════════════════════
// Default Config
// ═══════════════════════════════════════════════════════════════

export const DEFAULT_BACKTEST_CONFIG = {
  warmupBars: 300,
  stepBars: 1,
  feesBps: 2,
  slippageBps: 1,
  seed: 1337,
  intrabarPolicy: 'CONSERVATIVE' as IntrabarPolicy,
};
