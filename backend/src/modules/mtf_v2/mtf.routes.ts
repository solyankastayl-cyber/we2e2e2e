/**
 * Phase 6.5 — MTF Routes
 * 
 * API endpoints for Multi-Timeframe Confirmation Layer
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { Db } from 'mongodb';
import { getMTFService } from './mtf.service.js';
import { DEFAULT_MTF_CONFIG } from './mtf.types.js';

interface MTFRouteOptions {
  db: Db;
}

/**
 * Register MTF routes
 */
export async function registerMTFV2Routes(
  app: FastifyInstance,
  options: MTFRouteOptions
): Promise<void> {
  const { db } = options;
  const mtfService = getMTFService(db);
  
  /**
   * GET /api/mtf/state
   * 
   * Get MTF state for symbol and timeframe
   * 
   * Query params:
   * - symbol: string (e.g., BTCUSDT)
   * - tf: string (e.g., 4h)
   */
  app.get('/state', async (
    request: FastifyRequest<{ Querystring: { symbol?: string; tf?: string } }>,
    reply: FastifyReply
  ) => {
    const { symbol = 'BTCUSDT', tf = '4h' } = request.query;
    
    try {
      const state = await mtfService.getState(symbol, tf);
      return state;
    } catch (error) {
      request.log.error(error, 'MTF state error');
      return reply.status(500).send({
        error: 'Failed to compute MTF state',
        details: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });
  
  /**
   * GET /api/mtf/boost
   * 
   * Get MTF boost for specific direction
   * 
   * Query params:
   * - symbol: string
   * - tf: string
   * - direction: LONG | SHORT
   */
  app.get('/boost', async (
    request: FastifyRequest<{ 
      Querystring: { symbol?: string; tf?: string; direction?: string } 
    }>,
    reply: FastifyReply
  ) => {
    const { 
      symbol = 'BTCUSDT', 
      tf = '4h',
      direction = 'LONG'
    } = request.query;
    
    const dir = direction.toUpperCase() as 'LONG' | 'SHORT';
    if (dir !== 'LONG' && dir !== 'SHORT') {
      return reply.status(400).send({ error: 'direction must be LONG or SHORT' });
    }
    
    try {
      const result = await mtfService.getBoostForDirection(symbol, tf, dir);
      return {
        symbol,
        tf,
        direction: dir,
        ...result
      };
    } catch (error) {
      request.log.error(error, 'MTF boost error');
      return reply.status(500).send({
        error: 'Failed to compute MTF boost',
        details: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });
  
  /**
   * GET /api/mtf/explain
   * 
   * Get MTF explain block (for Decision API integration)
   */
  app.get('/explain', async (
    request: FastifyRequest<{ Querystring: { symbol?: string; tf?: string } }>,
    reply: FastifyReply
  ) => {
    const { symbol = 'BTCUSDT', tf = '4h' } = request.query;
    
    try {
      const explain = await mtfService.getExplain(symbol, tf);
      return explain;
    } catch (error) {
      request.log.error(error, 'MTF explain error');
      return reply.status(500).send({
        error: 'Failed to get MTF explain',
        details: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });
  
  /**
   * GET /api/mtf/config
   * 
   * Get current MTF configuration
   */
  app.get('/config', async () => {
    return {
      config: DEFAULT_MTF_CONFIG,
      version: 'phase6.5'
    };
  });
  
  /**
   * GET /api/mtf/health
   * 
   * Health check endpoint
   */
  app.get('/health', async () => {
    const health = mtfService.health();
    return {
      ...health,
      status: 'ok',
      timestamp: new Date().toISOString()
    };
  });
  
  /**
   * GET /api/mtf/history
   * 
   * Get recent MTF state history
   */
  app.get('/history', async (
    request: FastifyRequest<{ 
      Querystring: { symbol?: string; tf?: string; limit?: string } 
    }>,
    reply: FastifyReply
  ) => {
    const { symbol = 'BTCUSDT', tf = '4h', limit = '20' } = request.query;
    const limitNum = Math.min(100, parseInt(limit, 10) || 20);
    
    try {
      const history = await db.collection('mtf_states')
        .find({ symbol, anchorTf: tf })
        .sort({ computedAt: -1 })
        .limit(limitNum)
        .project({ _id: 0 })
        .toArray();
      
      return {
        symbol,
        tf,
        count: history.length,
        history
      };
    } catch (error) {
      request.log.error(error, 'MTF history error');
      return reply.status(500).send({
        error: 'Failed to get MTF history'
      });
    }
  });
}

/**
 * Initialize MTF indexes
 */
export async function initMTFV2Indexes(db: Db): Promise<void> {
  try {
    await db.collection('mtf_states').createIndex(
      { symbol: 1, anchorTf: 1 },
      { background: true }
    );
    await db.collection('mtf_states').createIndex(
      { computedAt: -1 },
      { background: true, expireAfterSeconds: 86400 }  // TTL 24h
    );
    console.log('[MTF V2] Indexes initialized');
  } catch (error) {
    console.error('[MTF V2] Failed to create indexes:', error);
  }
}
