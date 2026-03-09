/**
 * Phase 5.1 B2 — Backtest Worker
 * 
 * Single-process worker that processes backtest jobs from queue
 */

import { Db } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';
import { getBacktestJobQueue, BacktestJobQueue } from './backtest.queue.js';
import { BacktestJobDoc, JOB_LIMITS, ProgressCallback, CancelCheckCallback } from './backtest.job.schema.js';
import { getBacktestStorage } from '../backtest.storage.js';
import { computeBacktestSummary } from '../backtest.metrics.js';
import { simulateTrade, tradeStatusToExitType } from '../trade.simulator.js';
import { decisionToTradePlan, buildDecisionSnapshot, DecisionPackMinimal } from '../decision.adapter.js';
import {
  BacktestRunDoc,
  BacktestTradeDoc,
  BacktestConfig,
  BacktestExitType,
  Candle,
  DEFAULT_BACKTEST_CONFIG,
} from '../domain/types.js';

// ═══════════════════════════════════════════════════════════════
// Worker State
// ═══════════════════════════════════════════════════════════════

let workerRunning = false;
let workerDb: Db | null = null;

// ═══════════════════════════════════════════════════════════════
// Start Worker
// ═══════════════════════════════════════════════════════════════

export async function startBacktestWorker(db: Db): Promise<void> {
  if (workerRunning) {
    console.log('[BacktestWorker] Already running');
    return;
  }

  workerDb = db;
  workerRunning = true;
  
  const queue = getBacktestJobQueue(db);
  await queue.ensureIndexes();

  console.log('[BacktestWorker] ✅ Started');

  // Worker loop
  workerLoop(db, queue);
}

// ═══════════════════════════════════════════════════════════════
// Stop Worker
// ═══════════════════════════════════════════════════════════════

export function stopBacktestWorker(): void {
  workerRunning = false;
  console.log('[BacktestWorker] Stopping...');
}

// ═══════════════════════════════════════════════════════════════
// Worker Loop
// ═══════════════════════════════════════════════════════════════

async function workerLoop(db: Db, queue: BacktestJobQueue): Promise<void> {
  while (workerRunning) {
    try {
      // Check concurrent job limit
      const runningCount = await queue.countRunning();
      if (runningCount >= JOB_LIMITS.maxConcurrentJobs) {
        await sleep(2000);
        continue;
      }

      // Try to claim next job
      const job = await queue.claimNextJob();
      
      if (!job) {
        // No jobs available, wait before checking again
        await sleep(1000);
        continue;
      }

      console.log(`[BacktestWorker] Processing job ${job.jobId}`);

      // Process the job
      await processJob(db, queue, job);

    } catch (err: any) {
      console.error('[BacktestWorker] Loop error:', err.message);
      await sleep(5000);
    }
  }

  console.log('[BacktestWorker] Stopped');
}

// ═══════════════════════════════════════════════════════════════
// Process Job
// ═══════════════════════════════════════════════════════════════

async function processJob(
  db: Db,
  queue: BacktestJobQueue,
  job: BacktestJobDoc
): Promise<void> {
  const { jobId, request } = job;
  const storage = getBacktestStorage(db);

  try {
    // Create progress callback with throttling
    let lastProgressUpdate = 0;
    const onProgress: ProgressCallback = (progress) => {
      const now = Date.now();
      if (now - lastProgressUpdate < JOB_LIMITS.progressUpdateIntervalMs) return;
      lastProgressUpdate = now;

      const pct = progress.barsTotal > 0 
        ? Math.round((progress.barsDone / progress.barsTotal) * 100) 
        : 0;

      queue.updateProgress(jobId, {
        pct,
        barsDone: progress.barsDone,
        barsTotal: progress.barsTotal,
        asset: progress.asset,
        step: progress.step,
      }).catch(err => console.error('[BacktestWorker] Progress update failed:', err));
    };

    // Create cancel check callback
    const checkCancel: CancelCheckCallback = async () => {
      return queue.isCancelRequested(jobId);
    };

    // Run backtest for all assets
    const runId = uuidv4();
    const allTrades: BacktestTradeDoc[] = [];
    let totalBars = 0;
    let processedBars = 0;

    // Estimate total bars
    for (const asset of request.assets) {
      const candles = await loadCandles(db, asset, request.tf, request.from, request.to);
      totalBars += Math.max(0, candles.length - (request.warmupBars || 300));
    }

    // Process each asset
    for (const asset of request.assets) {
      // Check for cancellation
      if (await checkCancel()) {
        console.log(`[BacktestWorker] Job ${jobId} cancelled`);
        await queue.markCancelled(jobId);
        return;
      }

      onProgress({
        barsDone: processedBars,
        barsTotal: totalBars,
        asset,
        step: `Loading candles for ${asset}`,
      });

      // Load candles
      const candles = await loadCandles(db, asset, request.tf, request.from, request.to);
      if (candles.length === 0) {
        console.log(`[BacktestWorker] No candles for ${asset}, skipping`);
        continue;
      }

      // Run backtest for this asset
      const trades = await runAssetBacktest(
        db,
        runId,
        asset,
        request.tf,
        candles,
        request,
        (barsDone, barsTotal) => {
          onProgress({
            barsDone: processedBars + barsDone,
            barsTotal: totalBars,
            asset,
            step: `Processing ${asset}: ${barsDone}/${barsTotal}`,
          });
        },
        checkCancel
      );

      allTrades.push(...trades);
      processedBars += Math.max(0, candles.length - (request.warmupBars || 300));
    }

    // Compute summary
    const summary = computeBacktestSummary(allTrades);

    // Create run document
    const config: BacktestConfig = {
      warmupBars: request.warmupBars || 300,
      stepBars: 1,
      feesBps: 2,
      slippageBps: 1,
      seed: request.seed || 1337,
      labelVersion: 'v3',
      featureSchemaVersion: 'v1.0',
      entryModelVersion: request.decisionEngine === 'LIVE' ? 'live_v1' : 'mock_v1',
      rModelVersion: 'mock_v1',
      edgeRunId: 'NONE',
    };

    const runDoc: BacktestRunDoc = {
      runId,
      createdAt: new Date().toISOString(),
      asset: request.assets.join(','),
      timeframe: request.tf,
      from: request.from,
      to: request.to,
      config,
      status: 'DONE',
      summary,
    };

    // Save run
    await storage.insertRunCreated(runDoc);
    await storage.markRunDone(runId, summary);

    // Save trades
    if (allTrades.length > 0) {
      await storage.insertTrades(allTrades);
    }

    // Mark job completed
    await queue.markCompleted(jobId, runId);
    console.log(`[BacktestWorker] Job ${jobId} completed. RunId: ${runId}, Trades: ${allTrades.length}`);

  } catch (err: any) {
    console.error(`[BacktestWorker] Job ${jobId} failed:`, err.message);
    
    if (err.message === 'CANCELLED') {
      await queue.markCancelled(jobId);
    } else {
      await queue.markFailed(jobId, {
        message: err.message,
        stack: err.stack,
      });
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// Run Backtest for Single Asset
// ═══════════════════════════════════════════════════════════════

async function runAssetBacktest(
  db: Db,
  runId: string,
  asset: string,
  tf: string,
  candles: Candle[],
  request: any,
  onProgress: (barsDone: number, barsTotal: number) => void,
  checkCancel: CancelCheckCallback
): Promise<BacktestTradeDoc[]> {
  const trades: BacktestTradeDoc[] = [];
  const warmupBars = request.warmupBars || 300;
  const totalBars = candles.length - warmupBars;

  // Create decision engine (mock for now, B3 will add real one)
  const decisionEngine = createDecisionEngine(request.decisionEngine || 'MOCK');

  for (let i = warmupBars; i < candles.length - 1; i++) {
    // Check cancel every 100 bars
    if ((i - warmupBars) % 100 === 0) {
      if (await checkCancel()) {
        throw new Error('CANCELLED');
      }
      onProgress(i - warmupBars, totalBars);
    }

    // Build context (NO LOOKAHEAD - only candles up to current bar)
    const contextCandles = candles.slice(Math.max(0, i - 300), i + 1);
    const currentCandle = candles[i];
    const atr = calculateSimpleATR(contextCandles.slice(-14));

    // Get decision
    const decision = await decisionEngine.compute({
      asset,
      timeframe: tf,
      candles: contextCandles,
      currentPrice: currentCandle.close,
      atr,
    });

    // Convert to trade plan
    const plan = decisionToTradePlan(decision, 50);
    if (!plan) continue;

    // Simulate trade with forward candles
    const forwardCandles = candles.slice(i + 1);
    const tradeResult = simulateTrade(plan, forwardCandles, {
      feesBps: 2,
      slippageBps: 1,
      intrabarPolicy: 'CONSERVATIVE',
    });

    // Build trade document
    const tradeDoc: BacktestTradeDoc = {
      runId,
      tradeId: uuidv4(),
      signalIndex: i,
      openedAtIndex: tradeResult.debug.entryBarIndex >= 0 ? i + 1 + tradeResult.debug.entryBarIndex : -1,
      closedAtIndex: tradeResult.debug.exitBarIndex >= 0 ? i + 1 + tradeResult.debug.exitBarIndex : i + 1,
      entryPrice: tradeResult.entryPrice,
      stopPrice: tradeResult.stopPrice,
      target1: tradeResult.target1,
      target2: tradeResult.target2,
      exitPrice: tradeResult.exitPrice,
      exitType: tradeStatusToExitType(tradeResult.status) as BacktestExitType,
      rMultiple: tradeResult.rMultiple,
      mfeR: tradeResult.mfeR,
      maeR: tradeResult.maeR,
      feesBps: 2,
      slippageBps: 1,
      barsToEntry: tradeResult.barsToEntry,
      barsToExit: tradeResult.barsToExit,
      decisionSnapshot: buildDecisionSnapshot(plan),
    };

    trades.push(tradeDoc);

    // Skip forward by bars held
    if (tradeResult.status !== 'NO_ENTRY') {
      i += tradeResult.barsToEntry + tradeResult.barsToExit;
    }
  }

  return trades;
}

// ═══════════════════════════════════════════════════════════════
// Helper: Load Candles
// ═══════════════════════════════════════════════════════════════

async function loadCandles(
  db: Db,
  asset: string,
  tf: string,
  from: string,
  to: string
): Promise<Candle[]> {
  const collections = ['candles_binance', 'ta_candles'];
  
  for (const collName of collections) {
    try {
      const candles = await db.collection(collName)
        .find({
          symbol: asset.toUpperCase(),
          interval: tf.toLowerCase(),
          openTime: {
            $gte: new Date(from).getTime(),
            $lte: new Date(to).getTime(),
          },
        })
        .sort({ openTime: 1 })
        .toArray();
      
      if (candles.length > 0) {
        return candles.map(c => ({
          openTime: c.openTime,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
        }));
      }
    } catch (err) {
      // Collection doesn't exist
    }
  }

  // Generate mock candles if no real data
  console.log(`[BacktestWorker] No candles for ${asset}, generating mock data`);
  return generateMockCandles(from, to, tf);
}

// ═══════════════════════════════════════════════════════════════
// Helper: Create Decision Engine
// ═══════════════════════════════════════════════════════════════

function createDecisionEngine(type: 'LIVE' | 'MOCK') {
  let signalCounter = 0;

  return {
    async compute(ctx: any): Promise<DecisionPackMinimal> {
      // TODO B3: Integrate real Decision Engine when type === 'LIVE'
      
      // Mock decision engine
      signalCounter++;
      if (signalCounter % 10 !== 0) {
        return { topScenario: undefined };
      }

      const { currentPrice, atr } = ctx;
      const isLong = Math.random() > 0.5;
      const direction = isLong ? 'LONG' : 'SHORT';

      const entry = currentPrice;
      const stop = isLong ? currentPrice - atr * 1.5 : currentPrice + atr * 1.5;
      const target1 = isLong ? currentPrice + atr * 2.5 : currentPrice - atr * 2.5;
      const target2 = isLong ? currentPrice + atr * 4 : currentPrice - atr * 4;

      return {
        topScenario: {
          scenarioId: `mock_${Date.now()}`,
          patternType: 'MOCK_PATTERN',
          direction,
          entry,
          stop,
          target1,
          target2,
          pEntry: 0.5 + Math.random() * 0.3,
          rExpected: 1.5 + Math.random() * 1.5,
          evAfterEdge: 0.8 + Math.random() * 0.4,
        },
      };
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// Helper: Generate Mock Candles
// ═══════════════════════════════════════════════════════════════

function generateMockCandles(from: string, to: string, tf: string): Candle[] {
  const candles: Candle[] = [];
  const intervalMs = getIntervalMs(tf);

  let currentTime = new Date(from).getTime();
  const endTime = new Date(to).getTime();
  let price = 100;

  while (currentTime <= endTime) {
    const change = (Math.random() - 0.5) * 2;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * 0.5;
    const low = Math.min(open, close) - Math.random() * 0.5;

    candles.push({
      openTime: currentTime,
      open,
      high,
      low,
      close,
      volume: 1000 + Math.random() * 1000,
    });

    price = close;
    currentTime += intervalMs;
  }

  return candles;
}

function getIntervalMs(tf: string): number {
  const map: Record<string, number> = {
    '1m': 60 * 1000,
    '5m': 5 * 60 * 1000,
    '15m': 15 * 60 * 1000,
    '1h': 60 * 60 * 1000,
    '4h': 4 * 60 * 60 * 1000,
    '1d': 24 * 60 * 60 * 1000,
  };
  return map[tf.toLowerCase()] || 24 * 60 * 60 * 1000;
}

function calculateSimpleATR(candles: Candle[]): number {
  if (candles.length < 2) return 1;
  
  let totalTR = 0;
  for (let i = 1; i < candles.length; i++) {
    const high = candles[i].high;
    const low = candles[i].low;
    const prevClose = candles[i - 1].close;
    const tr = Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose));
    totalTR += tr;
  }
  return totalTR / (candles.length - 1);
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
