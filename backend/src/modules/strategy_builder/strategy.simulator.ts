/**
 * Phase 8 — Strategy Simulator
 * 
 * Backtests strategy candidates on historical data
 */

import {
  StrategyCandidate,
  Strategy,
  StrategyPerformance,
  BacktestTrade,
  calculateStrategyScore
} from './strategy.types.js';

// ═══════════════════════════════════════════════════════════════
// CANDLE TYPE
// ═══════════════════════════════════════════════════════════════

export interface Candle {
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  atr?: number;
}

// ═══════════════════════════════════════════════════════════════
// SIGNAL TYPE
// ═══════════════════════════════════════════════════════════════

export interface TradeSignal {
  time: number;
  direction: 'LONG' | 'SHORT';
  pattern: string;
  state: string;
  liquidity: string;
  entryPrice: number;
  atr: number;
}

// ═══════════════════════════════════════════════════════════════
// SIMULATION CONFIG
// ═══════════════════════════════════════════════════════════════

export interface SimulationConfig {
  slippage: number;  // As fraction of ATR
  commission: number;  // As fraction of position
  maxBarsInTrade: number;
  useTrailingStop: boolean;
  trailActivation: number;  // ATR profit to activate
  trailDistance: number;  // ATR distance
}

export const DEFAULT_SIM_CONFIG: SimulationConfig = {
  slippage: 0.1,
  commission: 0.001,
  maxBarsInTrade: 50,
  useTrailingStop: false,
  trailActivation: 1.5,
  trailDistance: 1.0
};

// ═══════════════════════════════════════════════════════════════
// MAIN SIMULATOR
// ═══════════════════════════════════════════════════════════════

/**
 * Simulate strategy on signals
 */
export function simulateStrategy(
  candidate: StrategyCandidate,
  signals: TradeSignal[],
  candles: Candle[],
  config: SimulationConfig = DEFAULT_SIM_CONFIG
): { trades: BacktestTrade[]; performance: StrategyPerformance } {
  const trades: BacktestTrade[] = [];
  
  // Filter signals matching strategy conditions
  const matchingSignals = signals.filter(s => 
    s.pattern === candidate.pattern &&
    s.state === candidate.state &&
    s.liquidity === candidate.liquidity
  );
  
  for (const signal of matchingSignals) {
    // Find entry candle
    const entryIdx = candles.findIndex(c => c.openTime >= signal.time);
    if (entryIdx < 0 || entryIdx >= candles.length - 1) continue;
    
    const entryCandle = candles[entryIdx];
    const atr = signal.atr || entryCandle.atr || 0;
    if (atr === 0) continue;
    
    // Calculate entry, stop, target
    const slippage = atr * config.slippage;
    const entryPrice = signal.direction === 'LONG'
      ? signal.entryPrice + slippage
      : signal.entryPrice - slippage;
    
    const stopDistance = atr * candidate.stopATR;
    const targetDistance = atr * candidate.targetATR;
    
    const stopPrice = signal.direction === 'LONG'
      ? entryPrice - stopDistance
      : entryPrice + stopDistance;
    
    const targetPrice = signal.direction === 'LONG'
      ? entryPrice + targetDistance
      : entryPrice - targetDistance;
    
    // Simulate trade
    const trade = simulateTrade(
      candidate.strategyId,
      signal.direction,
      entryPrice,
      stopPrice,
      targetPrice,
      entryIdx,
      candles,
      config
    );
    
    if (trade) {
      trades.push(trade);
    }
  }
  
  // Calculate performance
  const performance = calculatePerformance(trades);
  
  return { trades, performance };
}

/**
 * Simulate single trade
 */
function simulateTrade(
  strategyId: string,
  direction: 'LONG' | 'SHORT',
  entryPrice: number,
  stopPrice: number,
  targetPrice: number,
  entryIdx: number,
  candles: Candle[],
  config: SimulationConfig
): BacktestTrade | null {
  let trailStop = stopPrice;
  let exitPrice = 0;
  let exitIdx = 0;
  let outcome: 'WIN' | 'LOSS' | 'BREAKEVEN' = 'BREAKEVEN';
  
  const useTrailing = config.useTrailingStop || false;
  const trailActive = config.trailActivation;
  const trailDist = config.trailDistance;
  
  for (let i = entryIdx + 1; i < candles.length && i < entryIdx + config.maxBarsInTrade; i++) {
    const candle = candles[i];
    const atr = candle.atr || Math.abs(candle.high - candle.low);
    
    // Check stop hit
    if (direction === 'LONG') {
      if (candle.low <= trailStop) {
        exitPrice = trailStop;
        exitIdx = i;
        outcome = exitPrice < entryPrice ? 'LOSS' : (exitPrice > entryPrice ? 'WIN' : 'BREAKEVEN');
        break;
      }
      
      // Check target hit
      if (candle.high >= targetPrice) {
        exitPrice = targetPrice;
        exitIdx = i;
        outcome = 'WIN';
        break;
      }
      
      // Update trailing stop
      if (useTrailing) {
        const unrealizedR = (candle.close - entryPrice) / (entryPrice - stopPrice);
        if (unrealizedR >= trailActive) {
          const newTrail = candle.close - atr * trailDist;
          trailStop = Math.max(trailStop, newTrail);
        }
      }
    } else {
      // SHORT
      if (candle.high >= trailStop) {
        exitPrice = trailStop;
        exitIdx = i;
        outcome = exitPrice > entryPrice ? 'LOSS' : (exitPrice < entryPrice ? 'WIN' : 'BREAKEVEN');
        break;
      }
      
      if (candle.low <= targetPrice) {
        exitPrice = targetPrice;
        exitIdx = i;
        outcome = 'WIN';
        break;
      }
      
      if (useTrailing) {
        const unrealizedR = (entryPrice - candle.close) / (stopPrice - entryPrice);
        if (unrealizedR >= trailActive) {
          const newTrail = candle.close + atr * trailDist;
          trailStop = Math.min(trailStop, newTrail);
        }
      }
    }
  }
  
  // Time exit if no stop/target hit
  if (exitPrice === 0) {
    exitIdx = Math.min(entryIdx + config.maxBarsInTrade, candles.length - 1);
    exitPrice = candles[exitIdx].close;
    
    if (direction === 'LONG') {
      outcome = exitPrice > entryPrice ? 'WIN' : (exitPrice < entryPrice ? 'LOSS' : 'BREAKEVEN');
    } else {
      outcome = exitPrice < entryPrice ? 'WIN' : (exitPrice > entryPrice ? 'LOSS' : 'BREAKEVEN');
    }
  }
  
  // Calculate R
  const risk = Math.abs(entryPrice - stopPrice);
  const pnl = direction === 'LONG' 
    ? exitPrice - entryPrice 
    : entryPrice - exitPrice;
  const resultR = risk > 0 ? pnl / risk : 0;
  
  return {
    strategyId,
    entryTime: new Date(candles[entryIdx].openTime),
    exitTime: new Date(candles[exitIdx].openTime),
    direction,
    entryPrice,
    exitPrice,
    stopPrice,
    targetPrice,
    resultR,
    outcome,
    barsInTrade: exitIdx - entryIdx
  };
}

// ═══════════════════════════════════════════════════════════════
// PERFORMANCE CALCULATION
// ═══════════════════════════════════════════════════════════════

function calculatePerformance(trades: BacktestTrade[]): StrategyPerformance {
  if (trades.length === 0) {
    return {
      trades: 0,
      wins: 0,
      losses: 0,
      breakevens: 0,
      winRate: 0,
      avgR: 0,
      profitFactor: 1,
      sharpe: 0,
      maxDD: 0,
      expectancy: 0,
      avgWin: 0,
      avgLoss: 0,
      avgBarsInTrade: 0,
      maxConsecutiveLosses: 0
    };
  }
  
  const wins = trades.filter(t => t.outcome === 'WIN');
  const losses = trades.filter(t => t.outcome === 'LOSS');
  const breakevens = trades.filter(t => t.outcome === 'BREAKEVEN');
  
  const winRate = wins.length / trades.length;
  const avgR = trades.reduce((s, t) => s + t.resultR, 0) / trades.length;
  
  const grossWin = wins.reduce((s, t) => s + t.resultR, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.resultR, 0));
  const profitFactor = grossLoss > 0 ? grossWin / grossLoss : (grossWin > 0 ? 10 : 1);
  
  const avgWin = wins.length > 0 ? grossWin / wins.length : 0;
  const avgLoss = losses.length > 0 ? grossLoss / losses.length : 0;
  
  // Sharpe
  const variance = trades.reduce((s, t) => s + Math.pow(t.resultR - avgR, 2), 0) / trades.length;
  const stdDev = Math.sqrt(variance);
  const sharpe = stdDev > 0 ? avgR / stdDev : 0;
  
  // Max DD
  let peak = 0;
  let cumulative = 0;
  let maxDD = 0;
  for (const trade of trades) {
    cumulative += trade.resultR;
    if (cumulative > peak) peak = cumulative;
    const dd = peak - cumulative;
    if (dd > maxDD) maxDD = dd;
  }
  
  // Max consecutive losses
  let consecutiveLosses = 0;
  let maxConsecutiveLosses = 0;
  for (const trade of trades) {
    if (trade.outcome === 'LOSS') {
      consecutiveLosses++;
      maxConsecutiveLosses = Math.max(maxConsecutiveLosses, consecutiveLosses);
    } else {
      consecutiveLosses = 0;
    }
  }
  
  const avgBarsInTrade = trades.reduce((s, t) => s + t.barsInTrade, 0) / trades.length;
  
  return {
    trades: trades.length,
    wins: wins.length,
    losses: losses.length,
    breakevens: breakevens.length,
    winRate,
    avgR,
    profitFactor,
    sharpe,
    maxDD,
    expectancy: avgR,
    avgWin,
    avgLoss,
    avgBarsInTrade,
    maxConsecutiveLosses
  };
}

// ═══════════════════════════════════════════════════════════════
// STRATEGY EVALUATION
// ═══════════════════════════════════════════════════════════════

/**
 * Convert candidate to full strategy with performance
 */
export function evaluateCandidate(
  candidate: StrategyCandidate,
  signals: TradeSignal[],
  candles: Candle[],
  config: SimulationConfig = DEFAULT_SIM_CONFIG
): Strategy | null {
  const { trades, performance } = simulateStrategy(candidate, signals, candles, config);
  
  // Check minimum requirements
  if (performance.trades < 30) return null;
  if (performance.profitFactor < 1.1) return null;
  if (performance.winRate < 0.40) return null;
  
  const strategyScore = calculateStrategyScore(performance);
  
  return {
    strategyId: candidate.strategyId,
    pattern: candidate.pattern,
    state: candidate.state,
    liquidity: candidate.liquidity,
    scenario: candidate.scenario,
    regime: candidate.regime,
    entryRule: candidate.entryRule,
    exitRule: candidate.exitRule,
    stopATR: candidate.stopATR,
    targetATR: candidate.targetATR,
    riskReward: candidate.riskReward,
    performance,
    strategyScore,
    status: strategyScore > 0.5 ? 'ACTIVE' : 'CANDIDATE',
    createdAt: candidate.createdAt,
    updatedAt: new Date()
  };
}
