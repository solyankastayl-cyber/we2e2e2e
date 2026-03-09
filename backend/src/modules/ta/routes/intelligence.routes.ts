/**
 * Intelligence Routes (P4.1)
 * 
 * API endpoints for IntelligencePack
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { getIntelligenceEngine } from '../services/intelligence/intelligence.engine.js';
import { getIntelligenceStorage } from '../services/intelligence/intelligence.storage.js';
import { getIntelligenceHealthChecker } from '../services/intelligence/intelligence.health.js';

interface RouteOptions {
  db: Db;
}

export async function registerIntelligenceRoutes(
  app: FastifyInstance,
  options: RouteOptions
): Promise<void> {
  const { db } = options;
  
  const engine = getIntelligenceEngine(db);
  const storage = getIntelligenceStorage(db);
  const healthChecker = getIntelligenceHealthChecker(db);
  
  // Ensure indexes
  await storage.ensureIndexes();
  
  /**
   * GET /api/ta/intelligence
   * 
   * Main endpoint - compute and return IntelligencePack
   */
  app.get('/intelligence', async (
    request: FastifyRequest<{
      Querystring: {
        asset: string;
        tf: string;
        provider?: string;
        asOfTs?: string;
      };
    }>
  ) => {
    const { asset, tf, provider, asOfTs } = request.query;
    
    if (!asset || !tf) {
      return { ok: false, error: 'Missing required: asset, tf' };
    }
    
    try {
      const pack = await engine.compute({
        asset,
        timeframe: tf,
        provider: provider as any,
        asOfTs: asOfTs ? parseInt(asOfTs) : undefined
      });
      
      return {
        ok: true,
        ...pack
      };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  
  /**
   * GET /api/ta/intelligence/latest
   * 
   * Get latest stored pack for asset/tf
   */
  app.get('/intelligence/latest', async (
    request: FastifyRequest<{
      Querystring: {
        asset: string;
        tf: string;
      };
    }>
  ) => {
    const { asset, tf } = request.query;
    
    if (!asset || !tf) {
      return { ok: false, error: 'Missing required: asset, tf' };
    }
    
    const pack = await storage.getLatest(asset, tf);
    
    if (!pack) {
      return { ok: false, error: 'No intelligence pack found' };
    }
    
    return { ok: true, ...pack };
  });
  
  /**
   * GET /api/ta/intelligence/run/:runId
   * 
   * Get specific run by ID
   */
  app.get('/intelligence/run/:runId', async (
    request: FastifyRequest<{
      Params: { runId: string };
    }>
  ) => {
    const { runId } = request.params;
    
    const pack = await storage.getByRunId(runId);
    
    if (!pack) {
      return { ok: false, error: 'Run not found' };
    }
    
    return { ok: true, ...pack };
  });
  
  /**
   * GET /api/ta/intelligence/history
   * 
   * Get history for asset/tf
   */
  app.get('/intelligence/history', async (
    request: FastifyRequest<{
      Querystring: {
        asset: string;
        tf: string;
        limit?: string;
      };
    }>
  ) => {
    const { asset, tf, limit } = request.query;
    
    if (!asset || !tf) {
      return { ok: false, error: 'Missing required: asset, tf' };
    }
    
    const history = await storage.getHistory(
      asset,
      tf,
      limit ? parseInt(limit) : 50
    );
    
    return {
      ok: true,
      count: history.length,
      history
    };
  });
  
  /**
   * GET /api/ta/intelligence/opportunities
   * 
   * Get top opportunities by EV
   */
  app.get('/intelligence/opportunities', async (
    request: FastifyRequest<{
      Querystring: { limit?: string };
    }>
  ) => {
    const limit = request.query.limit ? parseInt(request.query.limit) : 10;
    
    const opportunities = await storage.getTopOpportunities(limit);
    
    return {
      ok: true,
      count: opportunities.length,
      opportunities
    };
  });
  
  /**
   * GET /api/ta/intelligence/stats
   * 
   * Get storage statistics
   */
  app.get('/intelligence/stats', async () => {
    const stats = await storage.getStats();
    return { ok: true, ...stats };
  });
  
  /**
   * GET /api/ta/intelligence/health
   * 
   * Health check
   */
  app.get('/intelligence/health', async () => {
    const health = await healthChecker.check();
    return { ok: health.status === 'OK', ...health };
  });
  
  console.log('[Intelligence] Routes registered:');
  console.log('  - GET  /intelligence');
  console.log('  - GET  /intelligence/latest');
  console.log('  - GET  /intelligence/run/:runId');
  console.log('  - GET  /intelligence/history');
  console.log('  - GET  /intelligence/opportunities');
  console.log('  - GET  /intelligence/stats');
  console.log('  - GET  /intelligence/health');
}
