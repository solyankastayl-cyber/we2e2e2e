/**
 * Phase 7 — Market Structure AI: Routes
 * 
 * API endpoints for structure analysis
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { Db } from 'mongodb';
import { getStructureAIService } from './structure.service.js';

interface StructureRouteOptions {
  db: Db;
}

/**
 * Register Structure AI routes
 */
export async function registerStructureRoutes(
  app: FastifyInstance,
  options: StructureRouteOptions
): Promise<void> {
  const { db } = options;
  const structureService = getStructureAIService(db);
  
  /**
   * GET /api/structure/state
   * 
   * Get full structure state
   */
  app.get('/state', async (
    request: FastifyRequest<{ Querystring: { symbol?: string; tf?: string } }>,
    reply: FastifyReply
  ) => {
    const { symbol = 'BTCUSDT', tf = '4h' } = request.query;
    
    try {
      const state = await structureService.analyze(symbol, tf);
      
      return {
        symbol: state.symbol,
        timeframe: state.timeframe,
        structure: state.structure,
        structureConfidence: state.structureConfidence,
        events: state.currentEvents.map(e => e.type),
        expectedNext: state.expectedNext,
        probability: state.expectedProbability,
        bias: state.bias,
        momentum: state.momentum,
        narrative: state.narrative,
        computedAt: state.computedAt
      };
    } catch (error) {
      request.log.error(error, 'Structure state error');
      return reply.status(500).send({
        error: 'Failed to analyze structure',
        details: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });
  
  /**
   * GET /api/structure/events
   * 
   * Get detected market events
   */
  app.get('/events', async (
    request: FastifyRequest<{ Querystring: { symbol?: string; tf?: string } }>,
    reply: FastifyReply
  ) => {
    const { symbol = 'BTCUSDT', tf = '4h' } = request.query;
    
    try {
      const events = await structureService.getEvents(symbol, tf);
      
      return {
        symbol,
        timeframe: tf,
        events,
        count: events.length,
        timestamp: Date.now()
      };
    } catch (error) {
      request.log.error(error, 'Structure events error');
      return reply.status(500).send({
        error: 'Failed to get structure events'
      });
    }
  });
  
  /**
   * GET /api/structure/narrative
   * 
   * Get human-readable narrative
   */
  app.get('/narrative', async (
    request: FastifyRequest<{ Querystring: { symbol?: string; tf?: string } }>,
    reply: FastifyReply
  ) => {
    const { symbol = 'BTCUSDT', tf = '4h' } = request.query;
    
    try {
      const state = await structureService.analyze(symbol, tf);
      
      return {
        symbol,
        timeframe: tf,
        narrative: state.narrative,
        events: state.currentEvents.map(e => e.type),
        expectedNext: state.expectedNext,
        confidence: state.structureConfidence
      };
    } catch (error) {
      request.log.error(error, 'Structure narrative error');
      return reply.status(500).send({
        error: 'Failed to get narrative'
      });
    }
  });
  
  /**
   * GET /api/structure/chain
   * 
   * Get active event chain
   */
  app.get('/chain', async (
    request: FastifyRequest<{ Querystring: { symbol?: string; tf?: string } }>,
    reply: FastifyReply
  ) => {
    const { symbol = 'BTCUSDT', tf = '4h' } = request.query;
    
    try {
      const state = await structureService.analyze(symbol, tf);
      
      if (!state.activeChain) {
        return {
          symbol,
          timeframe: tf,
          chain: null,
          message: 'No active event chain detected'
        };
      }
      
      return {
        symbol,
        timeframe: tf,
        chain: {
          id: state.activeChain.id,
          events: state.activeChain.events,
          completed: state.activeChain.completed,
          expected: state.activeChain.expected,
          progress: state.activeChain.completed.length / state.activeChain.events.length,
          probability: state.activeChain.probability,
          direction: state.activeChain.direction
        }
      };
    } catch (error) {
      request.log.error(error, 'Structure chain error');
      return reply.status(500).send({
        error: 'Failed to get event chain'
      });
    }
  });
  
  /**
   * GET /api/structure/health
   * 
   * Health check
   */
  app.get('/health', async () => {
    const health = structureService.health();
    return {
      ...health,
      status: 'ok',
      timestamp: new Date().toISOString()
    };
  });
  
  /**
   * GET /api/structure/history
   * 
   * Get recent structure analysis history
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
      const history = await db.collection('structure_states')
        .find({ symbol, timeframe: tf })
        .sort({ computedAt: -1 })
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
      request.log.error(error, 'Structure history error');
      return reply.status(500).send({
        error: 'Failed to get structure history'
      });
    }
  });
}

/**
 * Initialize Structure AI indexes
 */
export async function initStructureIndexes(db: Db): Promise<void> {
  try {
    await db.collection('structure_states').createIndex(
      { symbol: 1, timeframe: 1 },
      { background: true }
    );
    await db.collection('structure_states').createIndex(
      { computedAt: -1 },
      { background: true, expireAfterSeconds: 86400 }
    );
    await db.collection('structure_events').createIndex(
      { symbol: 1, timeframe: 1, timestamp: -1 },
      { background: true }
    );
    await db.collection('structure_events').createIndex(
      { storedAt: -1 },
      { background: true, expireAfterSeconds: 172800 }  // 48h TTL
    );
    console.log('[Structure AI] Indexes initialized');
  } catch (error) {
    console.error('[Structure AI] Failed to create indexes:', error);
  }
}
