/**
 * Phase 4 — Execution Logs Service
 * ==================================
 * Logs position sizing and execution details
 */

import { v4 as uuidv4 } from 'uuid';
import { ExecutionLog, LogQueryOptions } from './observability.types.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY STORAGE
// ═══════════════════════════════════════════════════════════════

const executionLogs: ExecutionLog[] = [];

// Seed demo data
const seedExecutionLogs = () => {
  const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
  const strategies = ['breakout', 'trend_follow', 'mean_reversion', 'momentum'];
  const riskModes = ['NORMAL', 'CONSERVATIVE', 'AGGRESSIVE'];
  
  const now = Date.now();
  const basePrices: Record<string, number> = { BTCUSDT: 87000, ETHUSDT: 3200, SOLUSDT: 145 };
  
  for (let i = 0; i < 30; i++) {
    const symbol = symbols[i % symbols.length];
    const basePrice = basePrices[symbol];
    const entry = basePrice * (0.98 + Math.random() * 0.04);
    const isLong = Math.random() > 0.4;
    
    executionLogs.push({
      id: `exec_${uuidv4().slice(0, 8)}`,
      decisionId: `dec_${uuidv4().slice(0, 8)}`,
      symbol,
      timestamp: now - (30 - i) * 3600000,
      positionSize: Math.round((0.1 + Math.random() * 0.3) * 100) / 100,
      riskAmount: Math.round((100 + Math.random() * 400) * 100) / 100,
      leverage: Math.floor(1 + Math.random() * 5),
      entry: Math.round(entry * 100) / 100,
      stop: Math.round((isLong ? entry * 0.97 : entry * 1.03) * 100) / 100,
      target: Math.round((isLong ? entry * 1.06 : entry * 0.94) * 100) / 100,
      riskReward: Math.round((1.5 + Math.random() * 2) * 100) / 100,
      strategy: strategies[Math.floor(Math.random() * strategies.length)],
      riskMode: riskModes[Math.floor(Math.random() * riskModes.length)],
    });
  }
};

seedExecutionLogs();

// ═══════════════════════════════════════════════════════════════
// LOG FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Log execution
 */
export function logExecution(
  decisionId: string,
  symbol: string,
  positionSize: number,
  riskAmount: number,
  leverage: number,
  entry: number,
  stop: number,
  target: number,
  strategy: string,
  riskMode: string
): ExecutionLog {
  const log: ExecutionLog = {
    id: `exec_${uuidv4().slice(0, 8)}`,
    decisionId,
    symbol,
    timestamp: Date.now(),
    positionSize,
    riskAmount,
    leverage,
    entry,
    stop,
    target,
    riskReward: Math.round(Math.abs(target - entry) / Math.abs(entry - stop) * 100) / 100,
    strategy,
    riskMode,
  };
  
  executionLogs.push(log);
  
  if (executionLogs.length > 500) {
    executionLogs.shift();
  }
  
  return log;
}

/**
 * Get execution logs
 */
export function getExecutionLogs(options: LogQueryOptions = {}): {
  logs: ExecutionLog[];
  total: number;
} {
  let filtered = [...executionLogs];
  
  if (options.symbol) {
    filtered = filtered.filter(l => l.symbol === options.symbol);
  }
  
  if (options.fromTs) {
    filtered = filtered.filter(l => l.timestamp >= options.fromTs!);
  }
  
  if (options.toTs) {
    filtered = filtered.filter(l => l.timestamp <= options.toTs!);
  }
  
  filtered.sort((a, b) => b.timestamp - a.timestamp);
  
  const total = filtered.length;
  const offset = options.offset || 0;
  const limit = options.limit || 50;
  
  return { logs: filtered.slice(offset, offset + limit), total };
}

/**
 * Get execution by decision ID
 */
export function getExecutionByDecision(decisionId: string): ExecutionLog | undefined {
  return executionLogs.find(l => l.decisionId === decisionId);
}

/**
 * Get execution stats
 */
export function getExecutionStats(): {
  total: number;
  avgPositionSize: number;
  avgRiskReward: number;
  avgLeverage: number;
  byStrategy: Record<string, number>;
} {
  const byStrategy: Record<string, number> = {};
  
  for (const log of executionLogs) {
    byStrategy[log.strategy] = (byStrategy[log.strategy] || 0) + 1;
  }
  
  return {
    total: executionLogs.length,
    avgPositionSize: executionLogs.length > 0 
      ? Math.round((executionLogs.reduce((s, l) => s + l.positionSize, 0) / executionLogs.length) * 100) / 100 
      : 0,
    avgRiskReward: executionLogs.length > 0 
      ? Math.round((executionLogs.reduce((s, l) => s + l.riskReward, 0) / executionLogs.length) * 100) / 100 
      : 0,
    avgLeverage: executionLogs.length > 0 
      ? Math.round((executionLogs.reduce((s, l) => s + l.leverage, 0) / executionLogs.length) * 10) / 10 
      : 0,
    byStrategy,
  };
}
