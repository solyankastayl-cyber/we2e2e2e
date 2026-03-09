/**
 * P1.6.1, P1.9, P2.0 — Research API Routes
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { createBatchSimulationService, BatchConfig } from './batch_simulation.js';
import { createBacktestRunnerService, BacktestConfig } from './backtest_runner.js';
import { createQualityService } from '../quality/quality.service.js';
import { QualityRebuildConfig, Regime } from '../quality/quality.types.js';

interface RouteOptions {
  db: Db;
}

export async function registerResearchRoutes(
  app: FastifyInstance,
  options: RouteOptions
): Promise<void> {
  const { db } = options;
  
  const batchSimService = createBatchSimulationService(db);
  const backtestService = createBacktestRunnerService(db);
  const qualityService = createQualityService(db);
  
  // Initialize quality indexes
  await qualityService.init();
  
  // ═══════════════════════════════════════════════════════════════
  // BATCH SIMULATION (P1.6.1)
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * POST /api/ta/research/batch-simulate
   * 
   * Run batch simulation to fill dataset V4
   */
  app.post('/research/batch-simulate', async (
    request: FastifyRequest<{
      Body: {
        assets?: string[];
        timeframes?: string[];
        from?: string;
        to?: string;
        windowSize?: number;
        sync?: boolean;
      }
    }>
  ) => {
    const config: BatchConfig = {
      assets: request.body?.assets || ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT'],
      timeframes: request.body?.timeframes || ['1d', '4h', '1h'],
      from: request.body?.from || '2017-01-01',
      to: request.body?.to || '2024-12-31',
      windowSize: request.body?.windowSize || 300,
    };
    
    const sync = request.body?.sync ?? false;
    
    if (sync) {
      // Run synchronously and return results
      const result = await batchSimService.runBatchSimulation(config);
      return {
        ok: true,
        ...result,
      };
    } else {
      // Run async (don't await full completion)
      batchSimService.runBatchSimulation(config);
      
      // Return immediately
      return {
        ok: true,
        message: 'Batch simulation started',
        config,
      };
    }
  });
  
  /**
   * GET /api/ta/research/batch-simulate/stats
   * 
   * Get dataset V4 statistics
   */
  app.get('/research/batch-simulate/stats', async () => {
    const stats = await batchSimService.getDatasetStats();
    
    return {
      ok: true,
      stats,
    };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // BACKTEST (P1.9)
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * POST /api/ta/research/backtest/run
   * 
   * Run backtest
   */
  app.post('/research/backtest/run', async (
    request: FastifyRequest<{
      Body: {
        assets?: string[];
        timeframes?: string[];
        from?: string;
        to?: string;
      }
    }>
  ) => {
    const config: BacktestConfig = {
      assets: request.body?.assets || ['BTCUSDT', 'ETHUSDT'],
      timeframes: request.body?.timeframes || ['1d', '4h'],
      from: request.body?.from || '2019-01-01',
      to: request.body?.to || '2024-12-31',
    };
    
    const result = await backtestService.runBacktest(config);
    
    return {
      ok: true,
      ...result,
    };
  });
  
  /**
   * GET /api/ta/research/backtest/status
   * 
   * Get backtest status
   */
  app.get('/research/backtest/status', async (
    request: FastifyRequest<{
      Querystring: { runId: string }
    }>
  ) => {
    const { runId } = request.query;
    
    if (!runId) {
      return { ok: false, error: 'runId required' };
    }
    
    const status = await backtestService.getStatus(runId);
    
    return {
      ok: true,
      status,
    };
  });
  
  /**
   * GET /api/ta/research/backtest/report
   * 
   * Get backtest report
   */
  app.get('/research/backtest/report', async (
    request: FastifyRequest<{
      Querystring: { runId: string }
    }>
  ) => {
    const { runId } = request.query;
    
    if (!runId) {
      return { ok: false, error: 'runId required' };
    }
    
    const report = await backtestService.getReport(runId);
    
    return {
      ok: true,
      report,
    };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // QUALITY (P2.0)
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * GET /api/ta/quality/pattern
   * 
   * Get quality for a specific pattern
   */
  app.get('/quality/pattern', async (
    request: FastifyRequest<{
      Querystring: {
        type: string;
        asset: string;
        tf: string;
        regime: string;
      }
    }>
  ) => {
    const { type, asset, tf, regime } = request.query;
    
    if (!type || !asset || !tf || !regime) {
      return { ok: false, error: 'type, asset, tf, regime required' };
    }
    
    const quality = await qualityService.getPatternQuality({
      patternType: type,
      asset,
      tf,
      regime: regime as Regime,
    });
    
    return {
      ok: true,
      quality,
    };
  });
  
  /**
   * GET /api/ta/quality/top
   * 
   * Get top patterns by quality
   */
  app.get('/quality/top', async (
    request: FastifyRequest<{
      Querystring: {
        asset?: string;
        tf?: string;
        regime?: string;
        limit?: string;
      }
    }>
  ) => {
    const { asset, tf, regime, limit } = request.query;
    
    const patterns = await qualityService.getTopPatterns({
      asset,
      tf,
      regime: regime as Regime | undefined,
      limit: limit ? parseInt(limit) : 20,
    });
    
    return {
      ok: true,
      patterns,
    };
  });
  
  /**
   * POST /api/ta/quality/rebuild
   * 
   * Rebuild quality scores
   */
  app.post('/quality/rebuild', async (
    request: FastifyRequest<{
      Body: {
        assets?: string[];
        timeframes?: string[];
        regimes?: string[];
        halfLifeDays?: number;
        minN?: number;
      }
    }>
  ) => {
    const config: QualityRebuildConfig = {
      assets: request.body?.assets || ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT'],
      timeframes: request.body?.timeframes || ['1d', '4h', '1h'],
      regimes: (request.body?.regimes as Regime[]) || ['TREND_UP', 'TREND_DOWN', 'RANGE'],
      halfLifeDays: request.body?.halfLifeDays || 120,
      minN: request.body?.minN || 60,
    };
    
    const result = await qualityService.rebuildQuality(config);
    
    return {
      ok: true,
      ...result,
    };
  });
  
  /**
   * GET /api/ta/quality/multiplier
   * 
   * Get quality multiplier for a scenario
   */
  app.get('/quality/multiplier', async (
    request: FastifyRequest<{
      Querystring: {
        patterns: string;  // comma-separated
        asset: string;
        tf: string;
        regime: string;
      }
    }>
  ) => {
    const { patterns, asset, tf, regime } = request.query;
    
    if (!patterns || !asset || !tf || !regime) {
      return { ok: false, error: 'patterns, asset, tf, regime required' };
    }
    
    const patternTypes = patterns.split(',');
    
    const result = await qualityService.getScenarioMultiplier(
      patternTypes,
      asset,
      tf,
      regime as Regime
    );
    
    return {
      ok: true,
      ...result,
    };
  });
}
