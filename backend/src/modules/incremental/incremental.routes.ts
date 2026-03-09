/**
 * Phase 7.5 — Incremental Engine: Routes
 * 
 * API endpoints for incremental computation
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { Db } from 'mongodb';
import { getIncrementalEngine } from './incremental.engine.js';
import { NodeId } from './incremental.types.js';

interface IncrementalRouteOptions {
  db: Db;
}

/**
 * Register Incremental Engine routes
 */
export async function registerIncrementalRoutes(
  app: FastifyInstance,
  options: IncrementalRouteOptions
): Promise<void> {
  const { db } = options;
  const engine = getIncrementalEngine();
  
  // Collection for storing computation history
  const computeHistoryCol = db.collection('incremental_history');
  
  /**
   * GET /api/incremental/status
   * 
   * Get engine status and statistics
   */
  app.get('/status', async () => {
    const stats = engine.getStats();
    const graphInfo = engine.getGraphInfo();
    const health = engine.health();
    
    return {
      enabled: health.enabled,
      version: health.version,
      graph: {
        nodeCount: graphInfo.nodeCount,
        edges: graphInfo.edges,
        computationOrder: graphInfo.computationOrder
      },
      stats,
      lastUpdate: Date.now()
    };
  });
  
  /**
   * POST /api/incremental/compute
   * 
   * Trigger incremental computation
   */
  app.post('/compute', async (
    request: FastifyRequest<{
      Body: {
        symbol?: string;
        timeframe?: string;
        trigger?: string;
        forceFullRecompute?: boolean;
      }
    }>,
    reply: FastifyReply
  ) => {
    const { 
      symbol = 'BTCUSDT', 
      timeframe = '4h',
      trigger = 'candles',
      forceFullRecompute = false
    } = request.body || {};
    
    try {
      const update = await engine.triggerUpdate(
        symbol,
        timeframe,
        trigger as NodeId,
        forceFullRecompute
      );
      
      // Store in history
      await computeHistoryCol.insertOne({
        ...update,
        symbol,
        timeframe,
        storedAt: new Date()
      }).catch(() => {});
      
      return {
        symbol,
        timeframe,
        mode: forceFullRecompute ? 'full' : 'incremental',
        nodesComputed: update.nodesComputed,
        nodesSkipped: update.nodesSkipped,
        totalDuration: update.totalDuration,
        savedDuration: update.savedDuration,
        savingsPercent: update.savedDuration > 0 
          ? Math.round((update.savedDuration / (update.totalDuration + update.savedDuration)) * 100)
          : 0,
        timestamp: update.timestamp
      };
    } catch (error) {
      request.log.error(error, 'Incremental compute error');
      return reply.status(500).send({
        error: 'Computation failed',
        details: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });
  
  /**
   * GET /api/incremental/context
   * 
   * Get current computation context
   */
  app.get('/context', async (
    request: FastifyRequest<{
      Querystring: { symbol?: string; tf?: string }
    }>
  ) => {
    const { symbol = 'BTCUSDT', tf = '4h' } = request.query;
    
    const ctx = engine.getContext(symbol, tf);
    
    if (!ctx) {
      return {
        symbol,
        timeframe: tf,
        context: null,
        message: 'No context available. Run /compute first.'
      };
    }
    
    // Extract summary (avoid returning full cached data)
    const summary: Record<string, any> = {};
    for (const [key, value] of Object.entries(ctx)) {
      if (typeof value === 'object' && value !== null) {
        summary[key] = {
          computed: true,
          timestamp: value.timestamp || null
        };
      }
    }
    
    return {
      symbol,
      timeframe: tf,
      nodesSummary: summary
    };
  });
  
  /**
   * GET /api/incremental/node/:nodeId
   * 
   * Get cached result for specific node
   */
  app.get('/node/:nodeId', async (
    request: FastifyRequest<{
      Params: { nodeId: string };
      Querystring: { symbol?: string; tf?: string }
    }>
  ) => {
    const { nodeId } = request.params;
    const { symbol = 'BTCUSDT', tf = '4h' } = request.query;
    
    const result = engine.getCachedResult(symbol, tf, nodeId as NodeId);
    
    return {
      symbol,
      timeframe: tf,
      nodeId,
      cached: result !== null,
      result: result || null
    };
  });
  
  /**
   * GET /api/incremental/graph
   * 
   * Get dependency graph visualization
   */
  app.get('/graph', async () => {
    const graphInfo = engine.getGraphInfo();
    
    // Build adjacency list
    const adjacencyList: Record<string, string[]> = {};
    
    // Get raw graph data
    const rawGraph = (engine as any).graph;
    
    if (rawGraph && rawGraph.nodes) {
      for (const [nodeId, node] of rawGraph.nodes.entries()) {
        adjacencyList[nodeId] = node.dependsOn || [];
      }
    }
    
    return {
      nodeCount: graphInfo.nodeCount,
      edgeCount: graphInfo.edges,
      computationOrder: graphInfo.computationOrder,
      adjacencyList
    };
  });
  
  /**
   * GET /api/incremental/stats
   * 
   * Get detailed statistics
   */
  app.get('/stats', async () => {
    const stats = engine.getStats();
    
    return {
      computations: {
        total: stats.totalComputations,
        incremental: stats.incrementalComputations,
        full: stats.fullComputations,
        incrementalRatio: stats.totalComputations > 0 
          ? stats.incrementalComputations / stats.totalComputations 
          : 0
      },
      performance: {
        totalTimeSaved: stats.totalTimeSaved,
        avgTimeSavedPerUpdate: Math.round(stats.avgTimeSavedPerUpdate),
        avgIncrementalDuration: Math.round(stats.avgIncrementalDuration),
        avgFullDuration: Math.round(stats.avgFullDuration),
        speedupFactor: stats.avgFullDuration > 0 
          ? stats.avgFullDuration / (stats.avgIncrementalDuration || 1)
          : 0
      },
      cache: {
        hits: stats.cacheHits,
        misses: stats.cacheMisses,
        hitRate: Math.round(stats.cacheHitRate * 100)
      },
      nodeStats: {
        computeCounts: stats.nodeComputeCounts,
        avgDurations: stats.nodeAvgDurations
      }
    };
  });
  
  /**
   * POST /api/incremental/reset
   * 
   * Reset engine state
   */
  app.post('/reset', async () => {
    engine.reset();
    
    return {
      success: true,
      message: 'Incremental engine reset',
      timestamp: new Date().toISOString()
    };
  });
  
  /**
   * GET /api/incremental/health
   * 
   * Health check
   */
  app.get('/health', async () => {
    const health = engine.health();
    
    return {
      ...health,
      status: 'ok',
      timestamp: new Date().toISOString()
    };
  });
  
  /**
   * GET /api/incremental/history
   * 
   * Get computation history
   */
  app.get('/history', async (
    request: FastifyRequest<{
      Querystring: { symbol?: string; tf?: string; limit?: string }
    }>
  ) => {
    const { symbol = 'BTCUSDT', tf = '4h', limit = '20' } = request.query;
    const limitNum = Math.min(100, parseInt(limit, 10) || 20);
    
    try {
      const history = await computeHistoryCol
        .find({ symbol, timeframe: tf })
        .sort({ timestamp: -1 })
        .limit(limitNum)
        .project({ _id: 0 })
        .toArray();
      
      return {
        symbol,
        timeframe: tf,
        count: history.length,
        history
      };
    } catch (error) {
      return {
        symbol,
        timeframe: tf,
        count: 0,
        history: []
      };
    }
  });
}

/**
 * Initialize Incremental Engine indexes
 */
export async function initIncrementalIndexes(db: Db): Promise<void> {
  try {
    await db.collection('incremental_history').createIndex(
      { symbol: 1, timeframe: 1, timestamp: -1 },
      { background: true }
    );
    await db.collection('incremental_history').createIndex(
      { storedAt: -1 },
      { background: true, expireAfterSeconds: 86400 }  // 24h TTL
    );
    console.log('[Incremental Engine] Indexes initialized');
  } catch (error) {
    console.error('[Incremental Engine] Failed to create indexes:', error);
  }
}
