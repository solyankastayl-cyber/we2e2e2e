/**
 * Phase 5.1 B1.3 — Backtest Runner
 * 
 * Main backtest loop - walks through candles and executes decision pipeline.
 * NO lookahead: at candle i, decision is computed using only candles[0..i]
 */

import { v4 as uuidv4 } from 'uuid';
import { Db } from 'mongodb';
import {
  BacktestRunRequest,
  BacktestRunDoc,
  BacktestTradeDoc,
  BacktestConfig,
  BacktestExitType,
  TradePlan,
  Candle,
  DEFAULT_BACKTEST_CONFIG,
} from './domain/types.js';
import { simulateTrade, tradeStatusToExitType } from './trade.simulator.js';
import { decisionToTradePlan, buildDecisionSnapshot, DecisionPackMinimal } from './decision.adapter.js';
import { computeBacktestSummary } from './backtest.metrics.js';
import { getBacktestStorage, BacktestStorage } from './backtest.storage.js';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export interface BacktestDependencies {
  db: Db;
  candleProvider: CandleProvider;
  decisionEngine: DecisionEngine;
}

export interface CandleProvider {
  getCandles(asset: string, timeframe: string, from: Date, to: Date): Promise<Candle[]>;
}

export interface DecisionEngine {
  computeDecision(ctx: DecisionContext): Promise<DecisionPackMinimal>;
}

export interface DecisionContext {
  asset: string;
  timeframe: string;
  timestamp: Date;
  candles: Candle[];
  currentPrice: number;
  atr: number;
}

export interface BacktestResult {
  run: BacktestRunDoc;
  trades: BacktestTradeDoc[];
}

// ═══════════════════════════════════════════════════════════════
// Main Runner Function
// ═══════════════════════════════════════════════════════════════

export async function runBacktest(
  request: BacktestRunRequest,
  deps: BacktestDependencies
): Promise<BacktestResult> {
  const { db, candleProvider, decisionEngine } = deps;
  const storage = getBacktestStorage(db);
  
  // Generate run ID
  const runId = uuidv4();
  const createdAt = new Date().toISOString();
  
  // Build config with defaults
  const config: BacktestConfig = {
    warmupBars: request.warmupBars ?? DEFAULT_BACKTEST_CONFIG.warmupBars,
    stepBars: request.stepBars ?? DEFAULT_BACKTEST_CONFIG.stepBars,
    maxTrades: request.maxTrades,
    feesBps: request.feesBps ?? DEFAULT_BACKTEST_CONFIG.feesBps,
    slippageBps: request.slippageBps ?? DEFAULT_BACKTEST_CONFIG.slippageBps,
    seed: request.seed ?? DEFAULT_BACKTEST_CONFIG.seed,
    
    // Version info for determinism
    labelVersion: 'v3',
    featureSchemaVersion: 'v1.0',
    entryModelVersion: 'mock_v1',
    rModelVersion: 'mock_v1',
    edgeRunId: 'NONE',
  };
  
  // Create initial run document
  const runDoc: BacktestRunDoc = {
    runId,
    createdAt,
    asset: request.asset,
    timeframe: request.timeframe,
    from: request.from,
    to: request.to,
    config,
    status: 'CREATED',
  };
  
  // Save created run
  await storage.insertRunCreated(runDoc);
  
  try {
    // Mark as running
    await storage.markRunRunning(runId);
    
    // Fetch candles
    console.log(`[Backtest] Fetching candles for ${request.asset} ${request.timeframe}...`);
    const candles = await candleProvider.getCandles(
      request.asset,
      request.timeframe,
      new Date(request.from),
      new Date(request.to)
    );
    
    if (candles.length === 0) {
      throw new Error('No candles available for backtest period');
    }
    
    console.log(`[Backtest] Loaded ${candles.length} candles`);
    
    // Run backtest loop
    const trades = await executeBacktestLoop(
      runId,
      runDoc.asset,      // B3: Pass asset
      runDoc.timeframe,  // B3: Pass timeframe
      candles,
      config,
      decisionEngine
    );
    
    // Compute summary
    const summary = computeBacktestSummary(trades);
    
    // Save trades
    await storage.insertTrades(trades);
    
    // Mark as done
    await storage.markRunDone(runId, summary);
    
    // Return result
    const finalRun = await storage.getRun(runId);
    
    return {
      run: finalRun!,
      trades,
    };
    
  } catch (err: any) {
    console.error(`[Backtest] Error: ${err.message}`);
    await storage.markRunFailed(runId, err.message);
    
    return {
      run: {
        ...runDoc,
        status: 'FAILED',
        error: err.message,
      },
      trades: [],
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// Backtest Loop
// ═══════════════════════════════════════════════════════════════

async function executeBacktestLoop(
  runId: string,
  asset: string,      // B3: Added asset
  timeframe: string,  // B3: Added timeframe
  candles: Candle[],
  config: BacktestConfig,
  decisionEngine: DecisionEngine
): Promise<BacktestTradeDoc[]> {
  const trades: BacktestTradeDoc[] = [];
  let currentPosition: TradePlan | null = null;
  let positionOpenIndex: number = -1;
  
  const { warmupBars, stepBars, maxTrades, feesBps, slippageBps } = config;
  
  console.log(`[Backtest] Starting loop from bar ${warmupBars} to ${candles.length - 1}`);
  
  // Main loop - step through candles
  for (let i = warmupBars; i < candles.length - 1; i += stepBars) {
    // Check max trades limit
    if (maxTrades && trades.length >= maxTrades) {
      console.log(`[Backtest] Max trades limit reached (${maxTrades})`);
      break;
    }
    
    // Skip if position already open (B1: one position at a time)
    if (currentPosition !== null) {
      continue;
    }
    
    // Build context with candles up to current index (NO LOOKAHEAD)
    const contextCandles = candles.slice(0, i + 1);
    const currentCandle = candles[i];
    
    // Calculate simple ATR for context
    const atr = calculateSimpleATR(contextCandles.slice(-14));
    
    const ctx: DecisionContext = {
      asset,         // B3: Use actual asset
      timeframe,     // B3: Use actual timeframe
      timestamp: new Date(currentCandle.openTime),
      candles: contextCandles,
      currentPrice: currentCandle.close,
      atr,
    };
    
    // Get decision from engine
    let decision: DecisionPackMinimal;
    try {
      decision = await decisionEngine.computeDecision(ctx);
    } catch (err) {
      // Decision engine failed - skip this bar
      continue;
    }
    
    // Convert to trade plan
    const plan = decisionToTradePlan(decision, 50);
    
    // No trade signal
    if (!plan) {
      continue;
    }
    
    // Simulate trade with forward candles
    const forwardCandles = candles.slice(i + 1);  // Start AFTER signal candle
    
    const tradeResult = simulateTrade(plan, forwardCandles, {
      feesBps,
      slippageBps,
      intrabarPolicy: 'CONSERVATIVE',
    });
    
    // Build trade document
    const tradeDoc: BacktestTradeDoc = {
      runId,
      tradeId: uuidv4(),
      
      signalIndex: i,
      openedAtIndex: tradeResult.debug.entryBarIndex >= 0 
        ? i + 1 + tradeResult.debug.entryBarIndex 
        : -1,
      closedAtIndex: tradeResult.debug.exitBarIndex >= 0 
        ? i + 1 + tradeResult.debug.exitBarIndex 
        : i + 1,
      
      entryPrice: tradeResult.entryPrice,
      stopPrice: tradeResult.stopPrice,
      target1: tradeResult.target1,
      target2: tradeResult.target2,
      exitPrice: tradeResult.exitPrice,
      
      exitType: tradeStatusToExitType(tradeResult.status) as BacktestExitType,
      
      rMultiple: tradeResult.rMultiple,
      mfeR: tradeResult.mfeR,
      maeR: tradeResult.maeR,
      
      feesBps,
      slippageBps,
      
      barsToEntry: tradeResult.barsToEntry,
      barsToExit: tradeResult.barsToExit,
      
      decisionSnapshot: buildDecisionSnapshot(plan),
    };
    
    trades.push(tradeDoc);
    
    // Skip forward by bars held to avoid overlapping trades
    if (tradeResult.status !== 'NO_ENTRY') {
      i += tradeResult.barsToEntry + tradeResult.barsToExit;
    }
  }
  
  console.log(`[Backtest] Loop complete. Total trades: ${trades.length}`);
  
  return trades;
}

// ═══════════════════════════════════════════════════════════════
// Helper: Simple ATR calculation
// ═══════════════════════════════════════════════════════════════

function calculateSimpleATR(candles: Candle[]): number {
  if (candles.length < 2) return 0;
  
  let totalTR = 0;
  
  for (let i = 1; i < candles.length; i++) {
    const high = candles[i].high;
    const low = candles[i].low;
    const prevClose = candles[i - 1].close;
    
    const tr = Math.max(
      high - low,
      Math.abs(high - prevClose),
      Math.abs(low - prevClose)
    );
    
    totalTR += tr;
  }
  
  return totalTR / (candles.length - 1);
}
