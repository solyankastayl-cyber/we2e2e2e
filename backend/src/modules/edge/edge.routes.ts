/**
 * Edge Attribution Routes (P5.0.8)
 * 
 * API endpoints for Edge Attribution Engine
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { EdgeDatasource, getEdgeDatasource } from './edge.datasource.js';
import { EdgeStorage, getEdgeStorage } from './edge.storage.js';
import { EdgeRebuildJob, getEdgeRebuildJob } from './edge.rebuild.job.js';
import type { 
  EdgeHealth, 
  EdgeRow, 
  EdgeRebuildRequest,
  EdgeDimension,
  EdgeAggregate,
} from './domain/types.js';

interface RouteContext {
  db: Db;
}

export async function registerEdgeRoutes(
  app: FastifyInstance,
  { db }: RouteContext
): Promise<void> {
  const datasource = getEdgeDatasource(db);
  const storage = getEdgeStorage(db);
  const rebuildJob = getEdgeRebuildJob(db);

  // Ensure indexes on startup
  storage.ensureIndexes().catch(err => {
    console.error('[Edge] Failed to ensure indexes:', err);
  });

  // ═══════════════════════════════════════════════════════════════
  // Health & Diagnostic Endpoints
  // ═══════════════════════════════════════════════════════════════

  /**
   * GET /health
   * Check edge data source readiness
   */
  app.get('/health', async (): Promise<{ ok: boolean; data: EdgeHealth }> => {
    const health = await datasource.checkHealth();
    return {
      ok: health.ok,
      data: health,
    };
  });

  /**
   * GET /sample
   * Load sample rows for debugging
   */
  app.get('/sample', async (request: FastifyRequest<{
    Querystring: { limit?: string }
  }>): Promise<{ ok: boolean; count: number; rows: EdgeRow[] }> => {
    const limit = Math.min(parseInt(request.query.limit || '20', 10), 100);
    const rows = await datasource.loadSample(limit);
    return {
      ok: true,
      count: rows.length,
      rows,
    };
  });

  /**
   * GET /count
   * Count total eligible rows
   */
  app.get('/count', async (request: FastifyRequest<{
    Querystring: {
      from?: string;
      to?: string;
      assets?: string;
      timeframes?: string;
    }
  }>): Promise<{ ok: boolean; count: number }> => {
    const { from, to, assets, timeframes } = request.query;
    
    const count = await datasource.countRows({
      from: from ? new Date(from) : undefined,
      to: to ? new Date(to) : undefined,
      assets: assets ? assets.split(',') : undefined,
      timeframes: timeframes ? timeframes.split(',') : undefined,
    });
    
    return {
      ok: true,
      count,
    };
  });

  /**
   * GET /rows
   * Load edge rows with pagination
   */
  app.get('/rows', async (request: FastifyRequest<{
    Querystring: {
      from?: string;
      to?: string;
      assets?: string;
      timeframes?: string;
      limit?: string;
      skip?: string;
    }
  }>): Promise<{ ok: boolean; count: number; rows: EdgeRow[] }> => {
    const { from, to, assets, timeframes, limit, skip } = request.query;
    
    const rows = await datasource.loadEdgeRows({
      from: from ? new Date(from) : undefined,
      to: to ? new Date(to) : undefined,
      assets: assets ? assets.split(',') : undefined,
      timeframes: timeframes ? timeframes.split(',') : undefined,
      limit: limit ? parseInt(limit, 10) : 1000,
      skip: skip ? parseInt(skip, 10) : 0,
    });
    
    return {
      ok: true,
      count: rows.length,
      rows,
    };
  });

  // ═══════════════════════════════════════════════════════════════
  // Dimensions Endpoint
  // ═══════════════════════════════════════════════════════════════

  /**
   * GET /dimensions
   * List available edge dimensions
   */
  app.get('/dimensions', async (): Promise<{ 
    ok: boolean; 
    dimensions: string[];
    description: Record<string, string>;
  }> => {
    return {
      ok: true,
      dimensions: [
        'pattern',
        'family',
        'regime',
        'geometry',
        'ml_bucket',
        'stability_bucket',
        'timeframe',
        'asset',
      ],
      description: {
        pattern: 'Individual pattern type (e.g., TRIANGLE_ASC)',
        family: 'Pattern family (e.g., TRIANGLES, HARMONICS)',
        regime: 'Market regime (TREND_UP, TREND_DOWN, RANGE)',
        geometry: 'Geometry quality bucket (maturity, fit error)',
        ml_bucket: 'ML confidence bucket (LOW, MED_LOW, MED_HIGH, HIGH)',
        stability_bucket: 'Stability multiplier bucket (LOW, MED, HIGH)',
        timeframe: 'Trading timeframe (1h, 4h, 1d)',
        asset: 'Trading asset (BTC, ETH, SPX)',
      },
    };
  });

  // ═══════════════════════════════════════════════════════════════
  // Rebuild Endpoints
  // ═══════════════════════════════════════════════════════════════

  /**
   * POST /rebuild
   * Trigger full edge statistics rebuild
   */
  app.post('/rebuild', async (request: FastifyRequest<{
    Body: EdgeRebuildRequest
  }>) => {
    const params = request.body || {};
    
    console.log('[Edge] Rebuild requested:', JSON.stringify(params));
    
    const result = await rebuildJob.run(params);
    
    return {
      ok: result.status === 'SUCCESS',
      data: result,
    };
  });

  /**
   * GET /rebuild/status
   * Get rebuild job status
   */
  app.get('/rebuild/status', async () => {
    const status = await rebuildJob.getStatus();
    return {
      ok: true,
      data: status,
    };
  });

  // ═══════════════════════════════════════════════════════════════
  // Stats Endpoints
  // ═══════════════════════════════════════════════════════════════

  /**
   * GET /latest
   * Get latest aggregated stats
   */
  app.get('/latest', async (request: FastifyRequest<{
    Querystring: { dimension?: string }
  }>) => {
    const dimension = request.query.dimension as EdgeDimension | undefined;
    const aggregates = await storage.getLatestAggregates(dimension);
    const latestRun = await storage.getLatestRun();
    
    return {
      ok: true,
      runId: latestRun?.runId,
      runAt: latestRun?.finishedAt,
      count: aggregates.length,
      aggregates,
    };
  });

  /**
   * GET /top
   * Get top performers by dimension
   */
  app.get('/top', async (request: FastifyRequest<{
    Querystring: { 
      dimension: string;
      limit?: string;
    }
  }>) => {
    const dimension = request.query.dimension as EdgeDimension;
    const limit = parseInt(request.query.limit || '10', 10);
    
    if (!dimension) {
      return {
        ok: false,
        error: 'dimension parameter required',
      };
    }
    
    const aggregates = await storage.getTopPerformers(dimension, limit);
    
    return {
      ok: true,
      dimension,
      count: aggregates.length,
      aggregates,
    };
  });

  /**
   * GET /worst
   * Get worst performers by dimension
   */
  app.get('/worst', async (request: FastifyRequest<{
    Querystring: { 
      dimension: string;
      limit?: string;
    }
  }>) => {
    const dimension = request.query.dimension as EdgeDimension;
    const limit = parseInt(request.query.limit || '10', 10);
    
    if (!dimension) {
      return {
        ok: false,
        error: 'dimension parameter required',
      };
    }
    
    const aggregates = await storage.getWorstPerformers(dimension, limit);
    
    return {
      ok: true,
      dimension,
      count: aggregates.length,
      aggregates,
    };
  });

  /**
   * GET /stat/:dimension/:key
   * Get specific stat by dimension and key
   */
  app.get('/stat/:dimension/:key', async (request: FastifyRequest<{
    Params: { dimension: string; key: string }
  }>) => {
    const { dimension, key } = request.params;
    
    const aggregate = await storage.getAggregate(
      dimension as EdgeDimension,
      key
    );
    
    if (!aggregate) {
      return {
        ok: false,
        error: 'Stat not found',
      };
    }
    
    return {
      ok: true,
      aggregate,
    };
  });

  /**
   * GET /run/:runId
   * Get specific run details
   */
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
    
    const aggregates = await storage.getAggregatesByRunId(runId);
    
    return {
      ok: true,
      run,
      aggregatesCount: aggregates.length,
    };
  });

  /**
   * GET /runs
   * List recent runs
   */
  app.get('/runs', async (request: FastifyRequest<{
    Querystring: { limit?: string }
  }>) => {
    const limit = parseInt(request.query.limit || '20', 10);
    const runs = await storage.listRuns(limit);
    
    return {
      ok: true,
      count: runs.length,
      runs,
    };
  });

  /**
   * GET /global
   * Get global baseline metrics
   */
  app.get('/global', async () => {
    const baseline = await storage.getLatestGlobalBaseline();
    const latestRun = await storage.getLatestRun();
    
    return {
      ok: baseline !== null,
      runId: latestRun?.runId,
      baseline,
    };
  });

  console.log('[Edge] Routes registered: /health, /sample, /count, /rows, /dimensions, /rebuild, /latest, /top, /worst, /stat/:dimension/:key, /run/:runId, /runs, /global');
}
