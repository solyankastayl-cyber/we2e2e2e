/**
 * Phase 5.1 B1.9 — Trade Simulation Engine
 * 
 * Simulates trade execution without lookahead bias.
 * Core rules:
 * - NO lookahead: execution starts from candle AFTER signal
 * - CONSERVATIVE intrabar policy: if stop and target can both trigger in same bar, assume STOP
 * - Proper MFE/MAE calculation
 */

import {
  TradePlan,
  TradeResult,
  TradeStatus,
  Candle,
  TradeSimulationConfig,
  IntrabarPolicy,
  DEFAULT_BACKTEST_CONFIG,
} from './domain/types.js';

// ═══════════════════════════════════════════════════════════════
// Core Simulation Function
// ═══════════════════════════════════════════════════════════════

export function simulateTrade(
  plan: TradePlan,
  forwardCandles: Candle[],
  config: Partial<TradeSimulationConfig> = {}
): TradeResult {
  const opts: TradeSimulationConfig = {
    intrabarPolicy: config.intrabarPolicy || DEFAULT_BACKTEST_CONFIG.intrabarPolicy,
    feesBps: config.feesBps ?? DEFAULT_BACKTEST_CONFIG.feesBps,
    slippageBps: config.slippageBps ?? DEFAULT_BACKTEST_CONFIG.slippageBps,
  };

  const isLong = plan.bias === 'LONG';
  
  // Calculate Risk (R)
  const risk = isLong 
    ? plan.entryPrice - plan.stopPrice 
    : plan.stopPrice - plan.entryPrice;
  
  // Invalid plan - risk must be positive
  if (risk <= 0 || !Number.isFinite(risk)) {
    return createNoEntryResult(plan, 'invalid_risk');
  }
  
  // No candles to simulate
  if (!forwardCandles || forwardCandles.length === 0) {
    return createNoEntryResult(plan, 'no_candles');
  }

  // ═══════════════════════════════════════════════════════════════
  // State A: WAIT_ENTRY - Find entry trigger
  // ═══════════════════════════════════════════════════════════════
  
  let entryBarIndex = -1;
  let actualEntryPrice = plan.entryPrice;
  
  for (let i = 0; i < Math.min(forwardCandles.length, plan.timeoutBars); i++) {
    const candle = forwardCandles[i];
    
    // Check for gap through entry
    if (isLong) {
      // LONG: entry triggers when high >= entryPrice
      if (candle.open >= plan.entryPrice) {
        // Gap up through entry - execute at open with slippage
        entryBarIndex = i;
        actualEntryPrice = candle.open * (1 + opts.slippageBps / 10000);
        break;
      } else if (candle.high >= plan.entryPrice) {
        entryBarIndex = i;
        actualEntryPrice = plan.entryPrice * (1 + opts.slippageBps / 10000);
        break;
      }
    } else {
      // SHORT: entry triggers when low <= entryPrice
      if (candle.open <= plan.entryPrice) {
        // Gap down through entry - execute at open with slippage
        entryBarIndex = i;
        actualEntryPrice = candle.open * (1 - opts.slippageBps / 10000);
        break;
      } else if (candle.low <= plan.entryPrice) {
        entryBarIndex = i;
        actualEntryPrice = plan.entryPrice * (1 - opts.slippageBps / 10000);
        break;
      }
    }
  }
  
  // NO_ENTRY - price never reached entry
  if (entryBarIndex === -1) {
    return createNoEntryResult(plan, 'entry_not_triggered', forwardCandles.length);
  }

  // ═══════════════════════════════════════════════════════════════
  // State B: IN_TRADE - Simulate until exit
  // ═══════════════════════════════════════════════════════════════
  
  let mfe = 0;  // Max Favorable Excursion (absolute)
  let mae = 0;  // Max Adverse Excursion (absolute)
  let exitBarIndex = entryBarIndex;
  let exitPrice = actualEntryPrice;
  let status: TradeStatus = 'TIMEOUT';
  let exitReason = 'timeout';
  
  // Recalculate risk with actual entry
  const actualRisk = isLong 
    ? actualEntryPrice - plan.stopPrice 
    : plan.stopPrice - actualEntryPrice;
  
  // Process candles from entry bar onwards
  for (let i = entryBarIndex; i < Math.min(forwardCandles.length, entryBarIndex + plan.timeoutBars); i++) {
    const candle = forwardCandles[i];
    const { high, low, close, open, openTime } = candle;
    
    // Calculate MFE/MAE for this bar
    if (isLong) {
      const favorable = high - actualEntryPrice;
      const adverse = actualEntryPrice - low;
      if (favorable > mfe) mfe = favorable;
      if (adverse > mae) mae = adverse;
    } else {
      const favorable = actualEntryPrice - low;
      const adverse = high - actualEntryPrice;
      if (favorable > mfe) mfe = favorable;
      if (adverse > mae) mae = adverse;
    }
    
    // Check for GAP through stop (open already below/above stop)
    if (isLong && open <= plan.stopPrice) {
      exitBarIndex = i;
      exitPrice = open;  // Gap slippage
      status = 'LOSS';
      exitReason = 'gap_through_stop';
      break;
    } else if (!isLong && open >= plan.stopPrice) {
      exitBarIndex = i;
      exitPrice = open;  // Gap slippage
      status = 'LOSS';
      exitReason = 'gap_through_stop';
      break;
    }
    
    // Check for GAP through target (open already at/beyond target)
    if (isLong && open >= plan.target1) {
      exitBarIndex = i;
      exitPrice = plan.target2 && open >= plan.target2 ? plan.target2 : open;
      status = plan.target2 && open >= plan.target2 ? 'WIN_T2' : 'WIN_T1';
      exitReason = 'gap_through_target';
      break;
    } else if (!isLong && open <= plan.target1) {
      exitBarIndex = i;
      exitPrice = plan.target2 && open <= plan.target2 ? plan.target2 : open;
      status = plan.target2 && open <= plan.target2 ? 'WIN_T2' : 'WIN_T1';
      exitReason = 'gap_through_target';
      break;
    }
    
    // Normal bar processing with intrabar policy
    const exitResult = processIntrabar(
      isLong,
      candle,
      plan,
      opts.intrabarPolicy
    );
    
    if (exitResult) {
      exitBarIndex = i;
      exitPrice = exitResult.price;
      status = exitResult.status;
      exitReason = exitResult.reason;
      break;
    }
    
    // No exit - continue to next bar
    exitBarIndex = i;
    exitPrice = close;
  }
  
  // Calculate R metrics
  const realizedMove = isLong 
    ? exitPrice - actualEntryPrice 
    : actualEntryPrice - exitPrice;
  
  // Apply fees
  const totalFeesBps = opts.feesBps * 2;  // Entry + Exit
  const feeCost = actualEntryPrice * (totalFeesBps / 10000);
  const netMove = realizedMove - (isLong ? feeCost : -feeCost);
  
  const rMultiple = actualRisk > 0 ? netMove / actualRisk : 0;
  const mfeR = actualRisk > 0 ? mfe / actualRisk : 0;
  const maeR = actualRisk > 0 ? mae / actualRisk : 0;
  
  return {
    status,
    entryTs: forwardCandles[entryBarIndex]?.openTime,
    exitTs: forwardCandles[exitBarIndex]?.openTime,
    entryPrice: actualEntryPrice,
    exitPrice,
    stopPrice: plan.stopPrice,
    target1: plan.target1,
    target2: plan.target2,
    rMultiple,
    mfeR,
    maeR,
    barsToEntry: entryBarIndex,
    barsToExit: exitBarIndex - entryBarIndex,
    debug: {
      entryBarIndex,
      exitBarIndex,
      reason: exitReason,
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// Intrabar Processing (CONSERVATIVE policy)
// ═══════════════════════════════════════════════════════════════

interface IntrabarExit {
  status: TradeStatus;
  price: number;
  reason: string;
}

function processIntrabar(
  isLong: boolean,
  candle: Candle,
  plan: TradePlan,
  policy: IntrabarPolicy
): IntrabarExit | null {
  const { high, low } = candle;
  
  // Determine what could have been hit
  const stopHit = isLong ? low <= plan.stopPrice : high >= plan.stopPrice;
  const t1Hit = isLong ? high >= plan.target1 : low <= plan.target1;
  const t2Hit = plan.target2 
    ? (isLong ? high >= plan.target2 : low <= plan.target2)
    : false;
  
  // CONSERVATIVE: If both stop and target could trigger, assume STOP
  if (policy === 'CONSERVATIVE') {
    if (stopHit && (t1Hit || t2Hit)) {
      // Both possible - assume stop hit first (conservative)
      return {
        status: 'LOSS',
        price: plan.stopPrice,
        reason: 'stop_and_target_same_bar_conservative',
      };
    }
  }
  
  // Stop hit
  if (stopHit) {
    return {
      status: 'LOSS',
      price: plan.stopPrice,
      reason: 'stop_hit',
    };
  }
  
  // Target2 hit (check before T1 if both exist)
  if (t2Hit) {
    return {
      status: 'WIN_T2',
      price: plan.target2!,
      reason: 'target2_hit',
    };
  }
  
  // Target1 hit
  if (t1Hit) {
    return {
      status: 'WIN_T1',
      price: plan.target1,
      reason: 'target1_hit',
    };
  }
  
  return null;  // No exit this bar
}

// ═══════════════════════════════════════════════════════════════
// Helper: Create NO_ENTRY result
// ═══════════════════════════════════════════════════════════════

function createNoEntryResult(
  plan: TradePlan,
  reason: string,
  barsChecked: number = 0
): TradeResult {
  return {
    status: 'NO_ENTRY',
    stopPrice: plan.stopPrice,
    target1: plan.target1,
    target2: plan.target2,
    rMultiple: 0,
    mfeR: 0,
    maeR: 0,
    barsToEntry: barsChecked,
    barsToExit: 0,
    debug: {
      entryBarIndex: -1,
      exitBarIndex: -1,
      reason,
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// Map TradeStatus to BacktestExitType
// ═══════════════════════════════════════════════════════════════

export function tradeStatusToExitType(status: TradeStatus): string {
  const map: Record<TradeStatus, string> = {
    'NO_ENTRY': 'NO_ENTRY',
    'LOSS': 'STOP',
    'WIN_T1': 'T1',
    'WIN_T2': 'T2',
    'TIMEOUT': 'TIMEOUT',
    'PARTIAL': 'PARTIAL',
  };
  return map[status] || 'TIMEOUT';
}
