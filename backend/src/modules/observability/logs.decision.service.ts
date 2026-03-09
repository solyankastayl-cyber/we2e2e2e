/**
 * Phase 4 — Decision Logs Service
 * =================================
 * Logs all trading decisions with full context
 */

import { v4 as uuidv4 } from 'uuid';
import { DecisionLog, ScoreBreakdown, LogQueryOptions } from './observability.types.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY STORAGE (in prod would use MongoDB ta_decision_logs)
// ═══════════════════════════════════════════════════════════════

const decisionLogs: DecisionLog[] = [];

// Seed some demo data
const seedDecisionLogs = () => {
  const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
  const signals: Array<'LONG' | 'SHORT' | 'NO_TRADE'> = ['LONG', 'SHORT', 'NO_TRADE'];
  const regimes = ['TREND_UP', 'TREND_DOWN', 'RANGE', 'EXPANSION'];
  const scenarios = ['BREAKOUT', 'REVERSAL', 'CONTINUATION', 'RANGE_BOUND'];
  
  const now = Date.now();
  
  for (let i = 0; i < 50; i++) {
    const signal = signals[Math.floor(Math.random() * signals.length)];
    
    decisionLogs.push({
      id: `dec_${uuidv4().slice(0, 8)}`,
      symbol: symbols[i % symbols.length],
      timeframe: '1d',
      signal,
      score: Math.round((0.4 + Math.random() * 0.5) * 100) / 100,
      confidence: Math.round((0.5 + Math.random() * 0.4) * 100) / 100,
      timestamp: now - (50 - i) * 3600000,
      breakdown: {
        pattern: Math.round(Math.random() * 0.3 * 100) / 100,
        liquidity: Math.round(Math.random() * 0.25 * 100) / 100,
        scenario: Math.round(Math.random() * 0.35 * 100) / 100,
        memory: Math.round(Math.random() * 0.15 * 100) / 100,
        regime: Math.round(Math.random() * 0.2 * 100) / 100,
      },
      regime: regimes[Math.floor(Math.random() * regimes.length)],
      scenario: scenarios[Math.floor(Math.random() * scenarios.length)],
      memoryMatches: Math.floor(Math.random() * 30),
      outcome: signal !== 'NO_TRADE' ? (Math.random() > 0.4 ? 'WIN' : 'LOSS') : undefined,
      pnl: signal !== 'NO_TRADE' ? Math.round((Math.random() * 4 - 1) * 100) / 100 : undefined,
    });
  }
};

seedDecisionLogs();

// ═══════════════════════════════════════════════════════════════
// LOG FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Log a new decision
 */
export function logDecision(
  symbol: string,
  timeframe: string,
  signal: 'LONG' | 'SHORT' | 'NO_TRADE',
  score: number,
  confidence: number,
  breakdown: ScoreBreakdown,
  regime: string,
  scenario: string,
  memoryMatches: number
): DecisionLog {
  const log: DecisionLog = {
    id: `dec_${uuidv4().slice(0, 8)}`,
    symbol,
    timeframe,
    signal,
    score,
    confidence,
    timestamp: Date.now(),
    breakdown,
    regime,
    scenario,
    memoryMatches,
  };
  
  decisionLogs.push(log);
  
  // Keep only last 1000
  if (decisionLogs.length > 1000) {
    decisionLogs.shift();
  }
  
  return log;
}

/**
 * Get decision logs with filters
 */
export function getDecisionLogs(options: LogQueryOptions = {}): {
  logs: DecisionLog[];
  total: number;
} {
  let filtered = [...decisionLogs];
  
  if (options.symbol) {
    filtered = filtered.filter(l => l.symbol === options.symbol);
  }
  
  if (options.signal) {
    filtered = filtered.filter(l => l.signal === options.signal);
  }
  
  if (options.fromTs) {
    filtered = filtered.filter(l => l.timestamp >= options.fromTs!);
  }
  
  if (options.toTs) {
    filtered = filtered.filter(l => l.timestamp <= options.toTs!);
  }
  
  // Sort by timestamp descending
  filtered.sort((a, b) => b.timestamp - a.timestamp);
  
  const total = filtered.length;
  
  // Pagination
  const offset = options.offset || 0;
  const limit = options.limit || 50;
  filtered = filtered.slice(offset, offset + limit);
  
  return { logs: filtered, total };
}

/**
 * Get single decision by ID
 */
export function getDecisionById(id: string): DecisionLog | undefined {
  return decisionLogs.find(l => l.id === id);
}

/**
 * Update decision outcome
 */
export function updateDecisionOutcome(
  id: string,
  outcome: 'WIN' | 'LOSS',
  pnl: number
): boolean {
  const log = decisionLogs.find(l => l.id === id);
  if (!log) return false;
  
  log.outcome = outcome;
  log.pnl = pnl;
  return true;
}

/**
 * Get decision statistics
 */
export function getDecisionStats(symbol?: string): {
  total: number;
  longs: number;
  shorts: number;
  noTrades: number;
  winRate: number;
  avgScore: number;
  avgConfidence: number;
} {
  let logs = decisionLogs;
  if (symbol) {
    logs = logs.filter(l => l.symbol === symbol);
  }
  
  const withOutcome = logs.filter(l => l.outcome);
  const wins = withOutcome.filter(l => l.outcome === 'WIN').length;
  
  return {
    total: logs.length,
    longs: logs.filter(l => l.signal === 'LONG').length,
    shorts: logs.filter(l => l.signal === 'SHORT').length,
    noTrades: logs.filter(l => l.signal === 'NO_TRADE').length,
    winRate: withOutcome.length > 0 ? Math.round((wins / withOutcome.length) * 100) / 100 : 0,
    avgScore: logs.length > 0 ? Math.round((logs.reduce((s, l) => s + l.score, 0) / logs.length) * 100) / 100 : 0,
    avgConfidence: logs.length > 0 ? Math.round((logs.reduce((s, l) => s + l.confidence, 0) / logs.length) * 100) / 100 : 0,
  };
}

/**
 * Get recent decisions
 */
export function getRecentDecisions(limit: number = 10): DecisionLog[] {
  return [...decisionLogs]
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, limit);
}
