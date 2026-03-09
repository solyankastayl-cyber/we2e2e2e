/**
 * Phase 4 — Observability Types
 * ===============================
 * Types for logging and explaining system decisions
 */

// ═══════════════════════════════════════════════════════════════
// DECISION LOG
// ═══════════════════════════════════════════════════════════════

export interface DecisionLog {
  id: string;
  symbol: string;
  timeframe: string;
  signal: 'LONG' | 'SHORT' | 'NO_TRADE';
  score: number;
  confidence: number;
  timestamp: number;
  
  // Score breakdown
  breakdown: ScoreBreakdown;
  
  // Context at decision time
  regime: string;
  scenario: string;
  memoryMatches: number;
  
  // Result (filled later)
  outcome?: 'WIN' | 'LOSS' | 'PENDING';
  pnl?: number;
}

export interface ScoreBreakdown {
  pattern: number;
  liquidity: number;
  scenario: number;
  memory: number;
  regime: number;
  graph?: number;
  physics?: number;
}

// ═══════════════════════════════════════════════════════════════
// EXECUTION LOG
// ═══════════════════════════════════════════════════════════════

export interface ExecutionLog {
  id: string;
  decisionId: string;
  symbol: string;
  timestamp: number;
  
  positionSize: number;
  riskAmount: number;
  leverage: number;
  
  entry: number;
  stop: number;
  target: number;
  riskReward: number;
  
  strategy: string;
  riskMode: string;
}

// ═══════════════════════════════════════════════════════════════
// METABRAIN LOG
// ═══════════════════════════════════════════════════════════════

export interface MetaBrainLog {
  id: string;
  timestamp: number;
  
  event: 'RISK_MODE_CHANGE' | 'SAFE_MODE_TOGGLE' | 'MODULE_GATE' | 'WEIGHT_ADJUST' | 'RECOMPUTE';
  
  previousState: Record<string, any>;
  newState: Record<string, any>;
  
  reason: string;
  trigger: 'AUTO' | 'MANUAL' | 'REGIME' | 'VOLATILITY';
}

// ═══════════════════════════════════════════════════════════════
// MEMORY LOG
// ═══════════════════════════════════════════════════════════════

export interface MemoryLog {
  id: string;
  symbol: string;
  timestamp: number;
  
  queryContext: string;
  matchCount: number;
  
  topMatches: MemoryMatch[];
  
  bias: 'BULL' | 'BEAR' | 'NEUTRAL';
  avgSimilarity: number;
  memoryBoost: number;
}

export interface MemoryMatch {
  historicalDate: string;
  similarity: number;
  outcome: string;
  returnPct: number;
}

// ═══════════════════════════════════════════════════════════════
// TREE LOG (Scenario Tree)
// ═══════════════════════════════════════════════════════════════

export interface TreeLog {
  id: string;
  symbol: string;
  timestamp: number;
  
  rootState: string;
  branches: TreeBranch[];
  
  dominantPath: string[];
  entropy: number;
}

export interface TreeBranch {
  scenario: string;
  probability: number;
  expectedMove: number;
  confidence: number;
}

// ═══════════════════════════════════════════════════════════════
// SYSTEM LOG
// ═══════════════════════════════════════════════════════════════

export interface SystemLog {
  timestamp: number;
  
  signalsToday: number;
  decisionsToday: number;
  executionsToday: number;
  
  activeStrategies: number;
  memoryMatches: number;
  
  avgConfidence: number;
  winRate: number;
}

// ═══════════════════════════════════════════════════════════════
// EXPLAIN RESPONSE
// ═══════════════════════════════════════════════════════════════

export interface ExplainResponse {
  symbol: string;
  timestamp: number;
  
  decision: {
    signal: string;
    score: number;
    confidence: number;
  };
  
  scoreBreakdown: ScoreBreakdown;
  
  factors: ExplainFactor[];
  
  narrative: string;  // Human-readable explanation
}

export interface ExplainFactor {
  name: string;
  contribution: number;
  weight: number;
  description: string;
}

// ═══════════════════════════════════════════════════════════════
// QUERY OPTIONS
// ═══════════════════════════════════════════════════════════════

export interface LogQueryOptions {
  symbol?: string;
  fromTs?: number;
  toTs?: number;
  limit?: number;
  offset?: number;
  signal?: string;
}
