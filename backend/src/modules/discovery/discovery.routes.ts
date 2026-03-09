/**
 * Phase 9 — Strategy Discovery Engine: Routes
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { Db } from 'mongodb';
import { getDiscoveryService } from './discovery.service.js';

interface DiscoveryRouteOptions {
  db: Db;
}

export async function registerDiscoveryRoutes(
  app: FastifyInstance,
  options: DiscoveryRouteOptions
): Promise<void> {
  const { db } = options;
  const service = getDiscoveryService(db);
  
  /**
   * POST /api/discovery/run
   */
  app.post('/run', async (
    request: FastifyRequest<{
      Body: { symbols?: string[]; timeframes?: string[]; useMockData?: boolean }
    }>
  ) => {
    const { symbols, timeframes, useMockData = true } = request.body || {};
    const result = await service.runDiscovery({ symbols, timeframes, useMockData });
    return result;
  });
  
  /**
   * GET /api/discovery/status
   */
  app.get('/status', async () => {
    const status = await service.getStatus();
    const health = service.health();
    return { ...status, version: health.version };
  });
  
  /**
   * GET /api/discovery/strategies
   */
  app.get('/strategies', async (
    request: FastifyRequest<{ Querystring: { status?: string } }>
  ) => {
    const { status } = request.query;
    const strategies = await service.getStrategies(status);
    
    return {
      strategies,
      total: strategies.length,
      approved: strategies.filter(s => s.status === 'APPROVED').length,
      testing: strategies.filter(s => s.status === 'TESTING').length,
      candidates: strategies.filter(s => s.status === 'CANDIDATE').length
    };
  });
  
  /**
   * GET /api/discovery/strategies/:id
   */
  app.get('/strategies/:id', async (
    request: FastifyRequest<{ Params: { id: string } }>
  ) => {
    const strategy = await service.getStrategy(request.params.id);
    if (!strategy) {
      return { error: 'Strategy not found' };
    }
    return strategy;
  });
  
  /**
   * POST /api/discovery/strategies/:id/approve
   */
  app.post('/strategies/:id/approve', async (
    request: FastifyRequest<{ Params: { id: string } }>
  ) => {
    const success = await service.approveStrategy(request.params.id);
    return { success, message: success ? 'Strategy approved' : 'Strategy not found' };
  });
  
  /**
   * POST /api/discovery/strategies/:id/reject
   */
  app.post('/strategies/:id/reject', async (
    request: FastifyRequest<{ Params: { id: string } }>
  ) => {
    const success = await service.rejectStrategy(request.params.id);
    return { success, message: success ? 'Strategy rejected' : 'Strategy not found' };
  });
  
  /**
   * GET /api/discovery/combinations
   */
  app.get('/combinations', async (
    request: FastifyRequest<{ Querystring: { limit?: string } }>
  ) => {
    const limit = parseInt(request.query.limit || '10', 10);
    const combinations = await service.getTopCombinations(limit);
    return { combinations, count: combinations.length };
  });
  
  /**
   * GET /api/discovery/clusters
   */
  app.get('/clusters', async () => {
    const clusters = await service.getClusters();
    return { clusters, count: clusters.length };
  });
  
  /**
   * GET /api/discovery/features
   */
  app.get('/features', async () => {
    const analysis = await service.getFeatureAnalysis();
    
    // Sort by edge
    const sorted = Object.entries(analysis)
      .map(([feature, stats]) => ({ feature, ...stats }))
      .sort((a, b) => b.edge - a.edge);
    
    return { features: sorted };
  });
  
  /**
   * GET /api/discovery/health
   */
  app.get('/health', async () => {
    const health = service.health();
    return {
      ...health,
      status: 'ok',
      timestamp: new Date().toISOString()
    };
  });
}

export async function initDiscoveryIndexes(db: Db): Promise<void> {
  try {
    await db.collection('discovery_strategies').createIndex(
      { status: 1, confidence: -1 },
      { background: true }
    );
    await db.collection('discovery_combinations').createIndex(
      { edge: -1 },
      { background: true }
    );
    console.log('[Discovery Engine] Indexes initialized');
  } catch (error) {
    console.error('[Discovery Engine] Failed to create indexes:', error);
  }
}
