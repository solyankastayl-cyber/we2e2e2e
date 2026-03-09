/**
 * Phase 5.1 B1.5 + B3 — Backtest API Routes
 * 
 * B3: Real Decision Engine Integration
 * 
 * Endpoints:
 * - POST /api/ta/backtest/run
 * - GET /api/ta/backtest/run/:runId
 * - GET /api/ta/backtest/run/:runId/trades
 * - GET /api/ta/backtest/runs
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { BacktestRunRequest, Candle } from './domain/types.js';
import { runBacktest, CandleProvider, DecisionEngine, DecisionContext } from './backtest.runner.js';
import { getBacktestStorage, BacktestStorage } from './backtest.storage.js';
import { DecisionPackMinimal } from './decision.adapter.js';
import { computeCalibrationBuckets } from './backtest.metrics.js';
import { createRealDecisionProvider, createMockDecisionProvider } from './real_decision.provider.js';

// ═══════════════════════════════════════════════════════════════
// Route Context
// ═══════════════════════════════════════════════════════════════

interface RouteContext {
  db: Db;
}

// ═══════════════════════════════════════════════════════════════
// Candle Provider (fetches from DB or generates mock data)
// ═══════════════════════════════════════════════════════════════

function createCandleProvider(db: Db): CandleProvider {
  return {
    async getCandles(asset: string, timeframe: string, from: Date, to: Date): Promise<Candle[]> {
      // Try to fetch from ta_candles or candles_binance collection
      const collections = ['candles_binance', 'ta_candles'];
      
      for (const collName of collections) {
        try {
          const candles = await db.collection(collName)
            .find({
              symbol: asset.toUpperCase(),
              interval: timeframe.toLowerCase(),
              openTime: {
                $gte: from.getTime(),
                $lte: to.getTime(),
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
          // Collection doesn't exist, try next
        }
      }
      
      // No real data - generate mock candles for testing
      console.log('[Backtest] No candles found, generating mock data');
      return generateMockCandles(from, to, timeframe);
    },
  };
}

function generateMockCandles(from: Date, to: Date, timeframe: string): Candle[] {
  const candles: Candle[] = [];
  const intervalMs = getIntervalMs(timeframe);
  
  let currentTime = from.getTime();
  let price = 100;  // Starting price
  
  while (currentTime <= to.getTime()) {
    // Random walk
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

function getIntervalMs(timeframe: string): number {
  const map: Record<string, number> = {
    '1m': 60 * 1000,
    '5m': 5 * 60 * 1000,
    '15m': 15 * 60 * 1000,
    '1h': 60 * 60 * 1000,
    '4h': 4 * 60 * 60 * 1000,
    '1d': 24 * 60 * 60 * 1000,
  };
  return map[timeframe] || 24 * 60 * 60 * 1000;
}

// ═══════════════════════════════════════════════════════════════
// Routes
// ═══════════════════════════════════════════════════════════════

export async function registerBacktestRoutes(
  app: FastifyInstance,
  { db }: RouteContext
): Promise<void> {
  const storage = getBacktestStorage(db);
  
  // Ensure indexes on startup
  await storage.ensureIndexes();
  
  // ─────────────────────────────────────────────────────────────
  // POST /run - Start backtest
  // ─────────────────────────────────────────────────────────────
  app.post('/run', async (request: FastifyRequest<{
    Body: BacktestRunRequest & { useRealDecision?: boolean }
  }>) => {
    const body = request.body;
    
    // Validate required fields
    if (!body.asset || !body.timeframe || !body.from || !body.to) {
      return {
        ok: false,
        error: 'Missing required fields: asset, timeframe, from, to',
      };
    }
    
    // B3: Use real or mock decision engine
    const useReal = body.useRealDecision ?? true;  // Default to REAL
    
    console.log(`[Backtest] Starting backtest for ${body.asset} ${body.timeframe} (useRealDecision=${useReal})`);
    
    // Create providers
    const candleProvider = createCandleProvider(db);
    const decisionEngine = useReal 
      ? createRealDecisionProvider(db)
      : createMockDecisionProvider();
    
    // Run backtest (synchronous for B1)
    const result = await runBacktest(body, {
      db,
      candleProvider,
      decisionEngine,
    });
    
    return {
      ok: result.run.status === 'DONE',
      runId: result.run.runId,
      status: result.run.status,
      summary: result.run.summary,
      error: result.run.error,
      decisionEngine: useReal ? 'REAL' : 'MOCK',
    };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /run/:runId - Get run details
  // ─────────────────────────────────────────────────────────────
  app.get('/run/:runId', async (request: FastifyRequest<{
    Params: { runId: string }
  }>) => {
    const { runId } = request.params;
    
    const run = await storage.getRun(runId);
    
    if (!run) {
      return {
        ok: false,
        error: 'Run not found',
      };
    }
    
    return {
      ok: true,
      run,
    };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /run/:runId/trades - Get trades with pagination
  // ─────────────────────────────────────────────────────────────
  app.get('/run/:runId/trades', async (request: FastifyRequest<{
    Params: { runId: string };
    Querystring: { limit?: string; skip?: string };
  }>) => {
    const { runId } = request.params;
    const { limit, skip } = request.query;
    
    const run = await storage.getRun(runId);
    if (!run) {
      return {
        ok: false,
        error: 'Run not found',
      };
    }
    
    const trades = await storage.getTrades(
      runId,
      limit ? parseInt(limit, 10) : 200,
      skip ? parseInt(skip, 10) : 0
    );
    
    const total = await storage.countTrades(runId);
    
    return {
      ok: true,
      runId,
      total,
      count: trades.length,
      trades,
    };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /run/:runId/calibration - Get calibration buckets
  // ─────────────────────────────────────────────────────────────
  app.get('/run/:runId/calibration', async (request: FastifyRequest<{
    Params: { runId: string };
  }>) => {
    const { runId } = request.params;
    
    const run = await storage.getRun(runId);
    if (!run) {
      return {
        ok: false,
        error: 'Run not found',
      };
    }
    
    const trades = await storage.getTrades(runId, 10000, 0);
    const buckets = computeCalibrationBuckets(trades);
    
    return {
      ok: true,
      runId,
      buckets,
    };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /runs - List recent runs
  // ─────────────────────────────────────────────────────────────
  app.get('/runs', async (request: FastifyRequest<{
    Querystring: { limit?: string };
  }>) => {
    const { limit } = request.query;
    
    const runs = await storage.listRuns(
      limit ? parseInt(limit, 10) : 20
    );
    
    return {
      ok: true,
      count: runs.length,
      runs,
    };
  });

  // ─────────────────────────────────────────────────────────────
  // DELETE /run/:runId - Delete run and trades
  // ─────────────────────────────────────────────────────────────
  app.delete('/run/:runId', async (request: FastifyRequest<{
    Params: { runId: string };
  }>) => {
    const { runId } = request.params;
    
    await storage.deleteRun(runId);
    
    return {
      ok: true,
      deleted: runId,
    };
  });

  console.log('[Backtest] Routes registered: POST /run, GET /run/:runId, GET /run/:runId/trades, GET /runs');
}
