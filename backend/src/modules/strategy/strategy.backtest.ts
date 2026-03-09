/**
 * Phase 5 — Strategy Backtest Engine
 * ====================================
 * Simulates strategy performance on historical data
 */

import { v4 as uuidv4 } from 'uuid';
import {
  Strategy,
  BacktestRequest,
  BacktestResult,
  BacktestTrade,
  StrategyPerformance,
} from './strategy.types.js';
import { getStrategyById } from './strategy.registry.js';

// ═══════════════════════════════════════════════════════════════
// BACKTEST STORAGE
// ═══════════════════════════════════════════════════════════════

const backtestResults: Map<string, BacktestResult> = new Map();

// ═══════════════════════════════════════════════════════════════
// BACKTEST ENGINE
// ═══════════════════════════════════════════════════════════════

/**
 * Generate simulated trades for backtest
 * In production, would use actual historical data
 */
function generateSimulatedTrades(
  strategy: Strategy,
  symbol: string,
  startDate: string,
  endDate: string
): BacktestTrade[] {
  const trades: BacktestTrade[] = [];
  
  const start = new Date(startDate).getTime();
  const end = new Date(endDate).getTime();
  const durationDays = (end - start) / (24 * 3600000);
  
  // Estimate trades based on strategy type
  const avgTradesPerMonth = strategy.id === 'trend_breakout' ? 15 : 
                            strategy.id === 'mean_reversion' ? 12 : 
                            strategy.id === 'liquidity_sweep' ? 8 : 
                            strategy.id === 'momentum' ? 6 : 5;
  
  const totalTrades = Math.floor((durationDays / 30) * avgTradesPerMonth);
  
  // Simulate trades
  const winRate = strategy.performance?.winRate || 0.55;
  const avgWin = 0.03;
  const avgLoss = 0.015;
  
  const basePrices: Record<string, number> = {
    BTCUSDT: 50000,
    ETHUSDT: 2500,
    SOLUSDT: 100,
  };
  const basePrice = basePrices[symbol] || 1000;
  
  for (let i = 0; i < totalTrades; i++) {
    const timestamp = start + (i / totalTrades) * (end - start);
    const isWin = Math.random() < winRate;
    const signal: 'LONG' | 'SHORT' = Math.random() > 0.45 ? 'LONG' : 'SHORT';
    
    const entry = basePrice * (0.9 + Math.random() * 0.2);
    const returnPct = isWin 
      ? avgWin * (0.5 + Math.random()) 
      : -avgLoss * (0.5 + Math.random());
    const exit = entry * (1 + returnPct);
    
    trades.push({
      timestamp,
      signal,
      entry: Math.round(entry * 100) / 100,
      exit: Math.round(exit * 100) / 100,
      returnPct: Math.round(returnPct * 10000) / 10000,
      outcome: isWin ? 'WIN' : 'LOSS',
    });
  }
  
  return trades;
}

/**
 * Calculate performance from trades
 */
function calculatePerformance(trades: BacktestTrade[]): StrategyPerformance {
  if (trades.length === 0) {
    return {
      winRate: 0,
      profitFactor: 0,
      maxDrawdown: 0,
      totalTrades: 0,
      avgReturn: 0,
      lastUpdated: Date.now(),
    };
  }
  
  const wins = trades.filter(t => t.outcome === 'WIN');
  const losses = trades.filter(t => t.outcome === 'LOSS');
  
  const winRate = wins.length / trades.length;
  
  const totalGain = wins.reduce((sum, t) => sum + t.returnPct, 0);
  const totalLoss = Math.abs(losses.reduce((sum, t) => sum + t.returnPct, 0));
  
  const profitFactor = totalLoss > 0 ? totalGain / totalLoss : totalGain > 0 ? 999 : 0;
  
  const avgReturn = trades.reduce((sum, t) => sum + t.returnPct, 0) / trades.length;
  
  // Calculate max drawdown
  let peak = 1;
  let maxDrawdown = 0;
  let equity = 1;
  
  for (const trade of trades) {
    equity *= (1 + trade.returnPct);
    if (equity > peak) peak = equity;
    const dd = (peak - equity) / peak;
    if (dd > maxDrawdown) maxDrawdown = dd;
  }
  
  // Estimate Sharpe (simplified)
  const returns = trades.map(t => t.returnPct);
  const mean = avgReturn;
  const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length;
  const stdDev = Math.sqrt(variance);
  const sharpe = stdDev > 0 ? (mean / stdDev) * Math.sqrt(252) : 0;  // Annualized
  
  return {
    winRate: Math.round(winRate * 100) / 100,
    profitFactor: Math.round(profitFactor * 100) / 100,
    sharpe: Math.round(sharpe * 100) / 100,
    maxDrawdown: Math.round(maxDrawdown * 100) / 100,
    totalTrades: trades.length,
    avgReturn: Math.round(avgReturn * 10000) / 10000,
    lastUpdated: Date.now(),
  };
}

/**
 * Generate equity curve from trades
 */
function generateEquityCurve(
  trades: BacktestTrade[],
  initialCapital: number
): { ts: number; equity: number }[] {
  const curve: { ts: number; equity: number }[] = [];
  let equity = initialCapital;
  
  // Initial point
  if (trades.length > 0) {
    curve.push({ ts: trades[0].timestamp - 86400000, equity });
  }
  
  for (const trade of trades) {
    equity *= (1 + trade.returnPct);
    curve.push({
      ts: trade.timestamp,
      equity: Math.round(equity * 100) / 100,
    });
  }
  
  return curve;
}

/**
 * Run backtest for a strategy
 */
export async function runBacktest(request: BacktestRequest): Promise<BacktestResult> {
  const strategy = getStrategyById(request.strategyId);
  
  if (!strategy) {
    throw new Error(`Strategy not found: ${request.strategyId}`);
  }
  
  const initialCapital = request.initialCapital || 100000;
  
  // Generate simulated trades
  const trades = generateSimulatedTrades(
    strategy,
    request.symbol,
    request.startDate,
    request.endDate
  );
  
  // Calculate performance
  const performance = calculatePerformance(trades);
  
  // Generate equity curve
  const equityCurve = generateEquityCurve(trades, initialCapital);
  
  const result: BacktestResult = {
    strategyId: request.strategyId,
    symbol: request.symbol,
    period: { start: request.startDate, end: request.endDate },
    performance,
    trades,
    equityCurve,
  };
  
  // Store result
  const id = `bt_${uuidv4().slice(0, 8)}`;
  backtestResults.set(id, result);
  
  return result;
}

/**
 * Get recent backtest results
 */
export function getRecentBacktests(limit: number = 10): BacktestResult[] {
  return [...backtestResults.values()]
    .sort((a, b) => b.performance.lastUpdated - a.performance.lastUpdated)
    .slice(0, limit);
}

/**
 * Compare strategies via backtest
 */
export async function compareStrategies(
  strategyIds: string[],
  symbol: string,
  startDate: string,
  endDate: string
): Promise<{ strategyId: string; performance: StrategyPerformance }[]> {
  const results: { strategyId: string; performance: StrategyPerformance }[] = [];
  
  for (const strategyId of strategyIds) {
    const backtest = await runBacktest({
      strategyId,
      symbol,
      startDate,
      endDate,
    });
    
    results.push({
      strategyId,
      performance: backtest.performance,
    });
  }
  
  // Sort by profit factor
  results.sort((a, b) => b.performance.profitFactor - a.performance.profitFactor);
  
  return results;
}
