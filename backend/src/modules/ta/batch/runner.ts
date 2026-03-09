/**
 * Phase 7: Batch Task Runner
 * 
 * Executes single batch task: replay simulation for date range.
 * Uses existing SimRunner with dataset v2 auto-writer.
 * Phase 7.5+: Uses real candles from MongoDB when available.
 */

import { v4 as uuid } from 'uuid';
import {
  BatchTask,
  BatchRun,
} from './domain.js';
import * as storage from './storage.js';
import { logger } from '../infra/logger.js';
import { getMongoDb } from '../../../db/mongoose.js';

// Import simulation components
import {
  DEFAULT_SIM_CONFIG,
  SimConfig,
} from '../simulator/config.js';
import {
  SimCandle,
  SimPosition,
} from '../simulator/domain.js';
import {
  createEntryOrder,
  tryFillOrder,
  createPosition,
  updatePositionOnCandle,
} from '../simulator/execution.js';
import {
  onPositionClose,
  storeScenarioContext,
} from '../simulator/dataset_hook.js';

// ═══════════════════════════════════════════════════════════════
// WORKER ID
// ═══════════════════════════════════════════════════════════════

const WORKER_ID = `worker_${process.pid}_${uuid().slice(0, 8)}`;

// ═══════════════════════════════════════════════════════════════
// REAL CANDLE LOADING (MongoDB)
// ═══════════════════════════════════════════════════════════════

async function loadRealCandles(
  symbol: string,
  tf: string,
  startTs: number,
  endTs: number,
  warmupBars: number
): Promise<SimCandle[] | null> {
  try {
    const db = getMongoDb();
    const col = db.collection('candles_binance');
    
    // Convert tf to Binance interval format (lowercase)
    const interval = tf.toLowerCase();
    
    // Calculate warmup start time
    const tfMs = getTfMs(tf);
    const warmupStart = startTs - (warmupBars * tfMs);
    
    // Normalize symbol to uppercase
    const symbolUpper = symbol.toUpperCase();
    
    console.log(`[Batch] Querying candles: symbol=${symbolUpper}, interval=${interval}, warmupStart=${warmupStart}, endTs=${endTs}`);
    
    // Query candles
    const docs = await col
      .find({
        symbol: symbolUpper,
        interval: interval,
        openTime: { $gte: warmupStart, $lte: endTs },
      })
      .sort({ openTime: 1 })
      .toArray();
    
    if (docs.length < warmupBars + 10) {
      // Not enough data, return null to use mock
      console.log(`[Batch] Real candles: only ${docs.length} found for ${symbolUpper} ${interval}, need ${warmupBars + 10}+. Using mock.`);
      return null;
    }
    
    // Convert to SimCandle format
    const candles: SimCandle[] = docs.map((d: any) => ({
      ts: Math.floor(d.openTime / 1000), // Unix seconds
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
      volume: d.volume || 0,
    }));
    
    console.log(`[Batch] Loaded ${candles.length} real candles for ${symbolUpper} ${interval}`);
    return candles;
  } catch (err) {
    console.log(`[Batch] Failed to load real candles: ${(err as Error).message}`);
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
// CANDLE GENERATION (Mock/Deterministic)
// ═══════════════════════════════════════════════════════════════

function mulberry32(seed: number): () => number {
  return () => {
    let t = seed += 0x6D2B79F5;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function generateCandles(
  symbol: string,
  tf: string,
  startTs: number,
  endTs: number,
  warmupBars: number,
  seed: number
): SimCandle[] {
  const candles: SimCandle[] = [];
  const rng = mulberry32(seed + hashCode(symbol + tf));
  
  // TF in ms
  const tfMs = getTfMs(tf);
  
  // Start from warmup
  const warmupStart = startTs - (warmupBars * tfMs);
  
  // Base price depends on symbol
  let price = getBasePrice(symbol);
  const volatility = getVolatility(symbol);
  
  let ts = warmupStart;
  while (ts <= endTs) {
    // Random walk with drift
    const change = (rng() - 0.48) * volatility * price;
    price = Math.max(price * 0.5, price + change);
    
    const range = price * volatility * (0.5 + rng());
    const open = price;
    const close = price + (rng() - 0.5) * range;
    const high = Math.max(open, close) + rng() * range * 0.5;
    const low = Math.min(open, close) - rng() * range * 0.5;
    
    candles.push({
      ts: Math.floor(ts / 1000), // Unix seconds
      open,
      high,
      low,
      close,
      volume: 1000000 * (0.5 + rng()),
    });
    
    price = close;
    ts += tfMs;
  }
  
  return candles;
}

function hashCode(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function getTfMs(tf: string): number {
  const tfLower = tf.toLowerCase();
  switch (tfLower) {
    case '1m': return 60 * 1000;
    case '5m': return 5 * 60 * 1000;
    case '15m': return 15 * 60 * 1000;
    case '1h': return 60 * 60 * 1000;
    case '4h': return 4 * 60 * 60 * 1000;
    case '1d': return 24 * 60 * 60 * 1000;
    case '1w': return 7 * 24 * 60 * 60 * 1000;
    default: return 24 * 60 * 60 * 1000;
  }
}

function getBasePrice(symbol: string): number {
  const s = symbol.toUpperCase();
  if (s.includes('BTC')) return 30000 + Math.random() * 20000;
  if (s.includes('ETH')) return 2000 + Math.random() * 1000;
  if (s.includes('SOL')) return 50 + Math.random() * 100;
  if (s.includes('BNB')) return 300 + Math.random() * 200;
  if (s.includes('XRP')) return 0.5 + Math.random() * 0.5;
  if (s.includes('SPX') || s.includes('SP500')) return 4000 + Math.random() * 1000;
  if (s.includes('NQ') || s.includes('NASDAQ')) return 14000 + Math.random() * 2000;
  if (s.includes('GOLD') || s.includes('XAU')) return 1800 + Math.random() * 200;
  return 100 + Math.random() * 100;
}

function getVolatility(symbol: string): number {
  const s = symbol.toUpperCase();
  if (s.includes('BTC')) return 0.03;
  if (s.includes('ETH')) return 0.04;
  if (s.includes('SOL')) return 0.05;
  if (s.includes('XRP')) return 0.04;
  if (s.includes('SPX')) return 0.01;
  if (s.includes('NQ')) return 0.015;
  if (s.includes('GOLD')) return 0.008;
  return 0.02;
}

// ═══════════════════════════════════════════════════════════════
// PATTERN FAMILY HELPER
// ═══════════════════════════════════════════════════════════════

function getPatternFamily(patternType: string): string {
  const type = patternType.toUpperCase();
  if (type.includes('TRIANGLE')) return 'TRIANGLE';
  if (type.includes('CHANNEL')) return 'CHANNEL';
  if (type.includes('FLAG') || type.includes('PENNANT')) return 'FLAG';
  if (type.includes('HEAD') || type.includes('SHOULDER') || type.includes('HNS')) return 'HNS';
  if (type.includes('HARMONIC') || type.includes('GARTLEY') || type.includes('BAT') || type.includes('BUTTERFLY')) return 'HARMONIC';
  if (type.includes('BREAK') || type.includes('BOS')) return 'BREAKOUT';
  if (type.includes('DOUBLE') || type.includes('TRIPLE')) return 'REVERSAL';
  if (type.includes('CUP') || type.includes('HANDLE')) return 'CONTINUATION';
  return 'OTHER';
}

// ═══════════════════════════════════════════════════════════════
// INDICATOR CALCULATION
// ═══════════════════════════════════════════════════════════════

interface IndicatorSet {
  rsi: number;
  rsiSlope: number;
  atr: number;
  atrPct: number;
  sma20: number;
  sma50: number;
  macd: number;
  macdSignal: number;
  macdHist: number;
  volatilityRegime: number;
  trendDirection: number;
  trendStrength: number;
}

function computeIndicators(candles: SimCandle[], nowIdx: number): IndicatorSet {
  const defaultResult: IndicatorSet = {
    rsi: 50,
    rsiSlope: 0,
    atr: 0,
    atrPct: 0,
    sma20: 0,
    sma50: 0,
    macd: 0,
    macdSignal: 0,
    macdHist: 0,
    volatilityRegime: 1,
    trendDirection: 0,
    trendStrength: 0,
  };
  
  if (nowIdx < 50) return defaultResult;
  
  const closes = candles.slice(0, nowIdx + 1).map(c => c.close);
  const highs = candles.slice(0, nowIdx + 1).map(c => c.high);
  const lows = candles.slice(0, nowIdx + 1).map(c => c.low);
  
  // RSI (14 period)
  const rsiPeriod = 14;
  let gains = 0, losses = 0;
  for (let i = Math.max(1, closes.length - rsiPeriod); i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) gains += diff;
    else losses -= diff;
  }
  const rs = gains / Math.max(losses, 0.001);
  const rsi = 100 - (100 / (1 + rs));
  
  // RSI slope (compare to 5 bars ago)
  let rsiPrev = 50;
  if (closes.length > rsiPeriod + 5) {
    let gainsP = 0, lossesP = 0;
    for (let i = Math.max(1, closes.length - rsiPeriod - 5); i < closes.length - 5; i++) {
      const diff = closes[i] - closes[i - 1];
      if (diff > 0) gainsP += diff;
      else lossesP -= diff;
    }
    const rsP = gainsP / Math.max(lossesP, 0.001);
    rsiPrev = 100 - (100 / (1 + rsP));
  }
  const rsiSlope = (rsi - rsiPrev) / 5;
  
  // ATR (14 period)
  let atrSum = 0;
  for (let i = Math.max(0, nowIdx - 14); i <= nowIdx; i++) {
    const tr = Math.max(
      highs[i] - lows[i],
      Math.abs(highs[i] - (i > 0 ? closes[i - 1] : closes[i])),
      Math.abs(lows[i] - (i > 0 ? closes[i - 1] : closes[i]))
    );
    atrSum += tr;
  }
  const atr = atrSum / Math.min(14, nowIdx + 1);
  const atrPct = atr / closes[closes.length - 1];
  
  // SMAs
  const sma20 = closes.slice(-20).reduce((a, b) => a + b, 0) / Math.min(20, closes.length);
  const sma50 = closes.slice(-50).reduce((a, b) => a + b, 0) / Math.min(50, closes.length);
  
  // MACD (12, 26, 9)
  const ema12 = closes.slice(-12).reduce((a, b) => a + b, 0) / Math.min(12, closes.length);
  const ema26 = closes.slice(-26).reduce((a, b) => a + b, 0) / Math.min(26, closes.length);
  const macd = ema12 - ema26;
  const macdSignal = macd * 0.9; // simplified
  const macdHist = macd - macdSignal;
  
  // Volatility regime (0=LOW, 1=NORMAL, 2=HIGH, 3=EXTREME)
  let volatilityRegime = 1;
  if (atrPct < 0.01) volatilityRegime = 0;
  else if (atrPct < 0.025) volatilityRegime = 1;
  else if (atrPct < 0.05) volatilityRegime = 2;
  else volatilityRegime = 3;
  
  // Trend direction and strength
  const trendDirection = sma20 > sma50 ? 1 : sma20 < sma50 ? -1 : 0;
  const trendStrength = Math.min(1, Math.abs(sma20 - sma50) / atr);
  
  return {
    rsi,
    rsiSlope,
    atr,
    atrPct,
    sma20,
    sma50,
    macd,
    macdSignal,
    macdHist,
    volatilityRegime,
    trendDirection,
    trendStrength,
  };
}

// ═══════════════════════════════════════════════════════════════
// SIMPLE DECISION MAKER (Pattern Detection Stub)
// ═══════════════════════════════════════════════════════════════

interface SimpleDecision {
  shouldTrade: boolean;
  side: 'LONG' | 'SHORT';
  entry: number;
  stop: number;
  target1: number;
  patternType: string;
  confidence: number;
}

function makeDecision(candles: SimCandle[], nowIdx: number): SimpleDecision | null {
  if (nowIdx < 20) return null;
  
  const window = candles.slice(nowIdx - 20, nowIdx + 1);
  const closes = window.map(c => c.close);
  const highs = window.map(c => c.high);
  const lows = window.map(c => c.low);
  
  const now = candles[nowIdx];
  const sma20 = closes.reduce((a, b) => a + b, 0) / closes.length;
  
  // Calculate RSI-like momentum
  let gains = 0, losses = 0;
  for (let i = 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) gains += diff;
    else losses -= diff;
  }
  const rs = gains / Math.max(losses, 0.001);
  const rsi = 100 - (100 / (1 + rs));
  
  // ATR for stops
  let atrSum = 0;
  for (const c of window) {
    atrSum += c.high - c.low;
  }
  const atr = atrSum / window.length;
  
  // Simple pattern detection
  const recentHigh = Math.max(...highs.slice(-5));
  const recentLow = Math.min(...lows.slice(-5));
  const rangePos = (now.close - recentLow) / (recentHigh - recentLow + 0.001);
  
  // Decision logic: trade more frequently for data generation
  let decision: SimpleDecision | null = null;
  
  // Use simple hash to decide if we trade on this bar (every ~5 bars for more data)
  const barHash = (nowIdx * 7 + Math.floor(now.close * 100)) % 5;
  
  if (barHash === 0) {
    // Decide direction based on trend
    const side: 'LONG' | 'SHORT' = now.close > sma20 ? 'LONG' : 'SHORT';
    
    decision = {
      shouldTrade: true,
      side,
      entry: now.close,
      stop: side === 'LONG' ? now.close - atr * 1.5 : now.close + atr * 1.5,
      target1: side === 'LONG' ? now.close + atr * 2.5 : now.close - atr * 2.5,
      patternType: 'momentum_pattern',
      confidence: 0.6,
    };
    
    // Add variety to pattern types
    const patterns = [
      'triangle_breakout', 'flag_continuation', 'channel_bounce', 
      'double_bottom', 'support_test', 'resistance_reject',
      'momentum_reversal', 'trend_continuation', 'range_breakout'
    ];
    decision.patternType = patterns[nowIdx % patterns.length];
  }
  
  return decision;
}

// ═══════════════════════════════════════════════════════════════
// TASK RUNNER
// ═══════════════════════════════════════════════════════════════

export interface TaskResult {
  success: boolean;
  rowsWritten: number;
  tradesClosed: number;
  error?: string;
}

export async function runTask(task: BatchTask, seed: number): Promise<TaskResult> {
  const startTime = Date.now();
  
  try {
    // Try to load real candles first (Phase 7.5+)
    let candles = await loadRealCandles(
      task.symbol,
      task.tf,
      task.startTs,
      task.endTs,
      task.warmupBars
    );
    
    let dataSource = 'real';
    
    // Fallback to mock if no real data
    if (!candles || candles.length < task.warmupBars + 10) {
      candles = generateCandles(
        task.symbol,
        task.tf,
        task.startTs,
        task.endTs,
        task.warmupBars,
        seed
      );
      dataSource = 'mock';
    }
    
    console.log(`[Batch] Task ${task.taskId.slice(0,8)}: ${candles.length} candles (${dataSource}), warmup=${task.warmupBars}`);
    
    if (candles.length < task.warmupBars + 10) {
      return { success: false, rowsWritten: 0, tradesClosed: 0, error: `Not enough candles: ${candles.length}` };
    }
    
    const config: SimConfig = {
      ...DEFAULT_SIM_CONFIG,
      tradeTimeoutBars: task.horizonBars,
    };
    
    let openPosition: SimPosition | null = null;
    let openOrder: any = null;
    let rowsWritten = 0;
    let tradesClosed = 0;
    let decisionsAttempted = 0;
    let decisionsAccepted = 0;
    
    const runId = `batch_${task.runId}_${task.taskId}`;
    
    // Walk through candles
    const startIdx = task.warmupBars;
    const endIdx = candles.length;
    console.log(`[Batch] Task ${task.taskId.slice(0,8)}: Walking bars ${startIdx} to ${endIdx-1}`);
    
    for (let i = startIdx; i < endIdx; i++) {
      const nowCandle = candles[i];
      const nowTs = nowCandle.ts;
      
      // Update existing position
      if (openPosition && openPosition.status === 'OPEN') {
        const updateResult = updatePositionOnCandle(openPosition, nowCandle, config);
        openPosition = updateResult.position;
        
        if (updateResult.closed) {
          // Write to dataset via hook
          try {
            console.log(`[Batch] Trade closed: ${openPosition.side} R=${openPosition.rMultiple?.toFixed(2)} reason=${openPosition.exitReason}`);
            await onPositionClose({
              position: openPosition,
              runId,
            });
            rowsWritten++;
            tradesClosed++;
          } catch (e) {
            console.log(`[Batch] Hook error: ${(e as Error).message}`);
            // Continue even if hook fails
          }
          openPosition = null;
        }
      }
      
      // Try to fill pending order
      if (openOrder && openOrder.status === 'OPEN') {
        const fillResult = tryFillOrder(openOrder, nowCandle, config);
        openOrder = fillResult.order;
        
        if (fillResult.filled && openOrder.status === 'FILLED') {
          openPosition = createPosition(
            runId,
            {
              scenarioId: openOrder.scenarioId,
              symbol: task.symbol,
              tf: task.tf,
              side: openOrder.side,
              risk: {
                entryPrice: openOrder.filledPrice,
                stopPrice: openOrder.meta?.stop,
                target1Price: openOrder.meta?.target1,
              },
            },
            openOrder,
            config
          );
          openOrder = null;
        }
      }
      
      // No position and no order - try to open new trade
      if (!openPosition && !openOrder) {
        decisionsAttempted++;
        const decision = makeDecision(candles, i);
        
        if (decision && decision.shouldTrade) {
          decisionsAccepted++;
          console.log(`[Batch] Decision at bar ${i}: ${decision.side} ${decision.patternType}`);
          const scenarioId = `scenario_${nowTs}_${Math.random().toString(36).slice(2, 8)}`;
          
          openOrder = createEntryOrder(
            runId,
            `step_${nowTs}`,
            nowTs,
            {
              scenarioId,
              symbol: task.symbol,
              tf: task.tf,
              side: decision.side,
              risk: {
                entryType: 'MARKET',
                entryPrice: decision.entry,
                stopPrice: decision.stop,
                target1Price: decision.target1,
                entryTimeoutBars: 5,
                tradeTimeoutBars: task.horizonBars,
              },
            }
          );
          
          // Store extra info for dataset
          openOrder.meta = {
            ...openOrder.meta,
            stop: decision.stop,
            target1: decision.target1,
            patternType: decision.patternType,
          };
          
          // MARKET orders fill immediately
          const fillResult2 = tryFillOrder(openOrder, nowCandle, config);
          openOrder = fillResult2.order;
          
          if (fillResult2.filled && openOrder.status === 'FILLED') {
            console.log(`[Batch] Position opened: ${decision.side} entry=${openOrder.filledPrice?.toFixed(2)} stop=${decision.stop?.toFixed(2)}`);
            
            // Compute indicators for context
            const indicators = computeIndicators(candles, i);
            
            openPosition = createPosition(
              runId,
              {
                scenarioId,
                symbol: task.symbol,
                tf: task.tf,
                side: decision.side,
                risk: {
                  entryPrice: openOrder.filledPrice,
                  stopPrice: decision.stop,
                  target1Price: decision.target1,
                },
              },
              openOrder,
              config
            );
            
            // Store context for dataset hook
            storeScenarioContext(scenarioId, {
              scenario: {
                id: scenarioId,
                symbol: task.symbol,
                tf: task.tf,
                direction: decision.side === 'LONG' ? 'BULL' : 'BEAR',
                patterns: [],
                risk: {
                  entryPrice: openOrder.filledPrice || decision.entry,
                  stopPrice: decision.stop,
                  target1Price: decision.target1,
                },
              } as any,
              patterns: [{
                type: decision.patternType,
                family: getPatternFamily(decision.patternType),
                score: decision.confidence,
                geometry: {},
              }],
              riskPack: {
                entry: openOrder.filledPrice || decision.entry,
                stop: decision.stop,
                target1: decision.target1,
              },
              regime: indicators.trendDirection > 0 ? 'TREND_UP' : indicators.trendDirection < 0 ? 'TREND_DOWN' : 'RANGE',
              vol: {
                atr: indicators.atr,
                atrPct: indicators.atrPct,
                regime: indicators.volatilityRegime,
              },
              confluence: {},
              reliability: {
                prior: decision.confidence,
                priorRegime: decision.confidence * 0.9,
                decay: 0.95,
                clusterDensity: 0.3,
                similarPatterns: 5,
                behaviourProb: decision.confidence,
              },
              candles: candles.slice(Math.max(0, i - 100), i + 1),
              nowTs,
              indicators: {
                rsi: indicators.rsi,
                rsiSlope: indicators.rsiSlope,
                macd: indicators.macd,
                macdSignal: indicators.macdSignal,
                macdHist: indicators.macdHist,
                atr: indicators.atr,
                atrPct: indicators.atrPct,
                sma20: indicators.sma20,
                sma50: indicators.sma50,
              },
              structure: {
                regime: indicators.trendDirection > 0 ? 'TREND_UP' : indicators.trendDirection < 0 ? 'TREND_DOWN' : 'RANGE',
                trendDirection: indicators.trendDirection,
                trendStrength: indicators.trendStrength,
              },
            });
            
            openOrder = null;
          }
        }
      }
      
      // Renew lease periodically
      if (i % 100 === 0) {
        await storage.renewTaskLease(task.taskId, WORKER_ID);
      }
    }
    
    // Close any remaining position at end
    if (openPosition && openPosition.status === 'OPEN') {
      const lastCandle = candles[candles.length - 1];
      openPosition.status = 'CLOSED';
      openPosition.exitTs = lastCandle.ts;
      openPosition.exitPrice = lastCandle.close;
      openPosition.exitReason = 'TIMEOUT';
      
      const stopDist = Math.abs(openPosition.entryPrice - openPosition.stopPrice);
      const pnl = openPosition.side === 'LONG'
        ? lastCandle.close - openPosition.entryPrice
        : openPosition.entryPrice - lastCandle.close;
      openPosition.rMultiple = stopDist > 0 ? pnl / stopDist : 0;
      
      try {
        await onPositionClose({ position: openPosition, runId });
        rowsWritten++;
        tradesClosed++;
      } catch (e) {}
    }
    
    const duration = Date.now() - startTime;
    logger.info({
      phase: 'batch_runner',
      taskId: task.taskId,
      symbol: task.symbol,
      tf: task.tf,
      rowsWritten,
      tradesClosed,
      durationMs: duration,
    }, 'Task completed');
    
    return { success: true, rowsWritten, tradesClosed };
    
  } catch (error) {
    return {
      success: false,
      rowsWritten: 0,
      tradesClosed: 0,
      error: (error as Error).message,
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// BATCH WORKER
// ═══════════════════════════════════════════════════════════════

let workerRunning = false;

export async function startWorker(runId: string, seed: number): Promise<void> {
  if (workerRunning) return;
  workerRunning = true;
  
  logger.info({ phase: 'batch_worker', runId, workerId: WORKER_ID }, 'Worker started');
  
  while (workerRunning) {
    const task = await storage.claimNextTask(runId, WORKER_ID);
    
    if (!task) {
      // No more tasks, check if run is complete
      const stats = await storage.getTaskStats(runId);
      
      if (stats.pending === 0 && stats.running === 0) {
        // All done
        await storage.updateRunStatus(runId, 'DONE');
        await storage.updateRunProgress(runId, {
          doneTasks: stats.done,
          failedTasks: stats.failed,
          rowsWritten: stats.rowsWritten,
          tradesClosed: stats.tradesClosed,
        });
        break;
      }
      
      // Wait for other workers
      await new Promise(r => setTimeout(r, 5000));
      continue;
    }
    
    // Run the task
    const result = await runTask(task, seed);
    
    // Update task status
    await storage.completeTask(
      task.taskId,
      result.success,
      { rowsWritten: result.rowsWritten, tradesClosed: result.tradesClosed },
      result.error
    );
    
    // Update run progress
    const stats = await storage.getTaskStats(runId);
    await storage.updateRunProgress(runId, {
      doneTasks: stats.done,
      failedTasks: stats.failed,
      rowsWritten: stats.rowsWritten,
      tradesClosed: stats.tradesClosed,
    });
  }
  
  workerRunning = false;
  logger.info({ phase: 'batch_worker', runId }, 'Worker stopped');
}

export function stopWorker(): void {
  workerRunning = false;
}

export function isWorkerRunning(): boolean {
  return workerRunning;
}
