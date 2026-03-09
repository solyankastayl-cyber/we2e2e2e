/**
 * MetaBrain v3 — Routes
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { Db } from 'mongodb';
import { MarketRegime } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';
import { runMetaBrainV3, runMetaBrainV3WithContext, getNeutralDecision } from './metabrain_v3.optimizer.js';
import { buildMetaBrainV3Context, getDefaultContext } from './metabrain_v3.context.js';
import {
  saveMetaBrainV3State,
  getLatestMetaBrainV3State,
  getMetaBrainV3History,
  getMetaBrainV3Actions,
  cleanOldMetaBrainV3Data
} from './metabrain_v3.storage.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerMetaBrainV3Routes(
  fastify: FastifyInstance,
  db: Db
): Promise<void> {
  /**
   * GET /api/ta/metabrain/v3/state
   * Get current MetaBrain v3 state
   */
  fastify.get('/api/ta/metabrain/v3/state', async (
    request: FastifyRequest<{ Querystring: { asset?: string; tf?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { asset, tf } = request.query;
      
      const state = await getLatestMetaBrainV3State(asset, tf);
      
      if (!state) {
        return {
          success: true,
          data: {
            context: getDefaultContext(),
            decision: getNeutralDecision(),
            createdAt: new Date()
          }
        };
      }
      
      return {
        success: true,
        data: state
      };
    } catch (err: any) {
      console.error('[MetaBrainV3] State error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/metabrain/v3/decision
   * Get current decision
   */
  fastify.get('/api/ta/metabrain/v3/decision', async (
    request: FastifyRequest<{ Querystring: { asset?: string; tf?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { asset, tf } = request.query;
      
      const state = await getLatestMetaBrainV3State(asset, tf);
      
      return {
        success: true,
        data: state?.decision ?? getNeutralDecision()
      };
    } catch (err: any) {
      console.error('[MetaBrainV3] Decision error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * POST /api/ta/metabrain/v3/recompute
   * Recompute MetaBrain v3 decision
   */
  fastify.post('/api/ta/metabrain/v3/recompute', async (
    request: FastifyRequest<{ Body: { asset?: string; tf?: string; regime?: string; state?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { asset = 'BTCUSDT', tf = '1d', regime, state: marketState } = request.body ?? {};
      
      const result = await runMetaBrainV3(
        asset,
        tf,
        regime as MarketRegime | undefined,
        marketState as MarketStateNode | undefined
      );
      
      // Save state
      await saveMetaBrainV3State(result);
      
      return {
        success: true,
        data: result
      };
    } catch (err: any) {
      console.error('[MetaBrainV3] Recompute error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/metabrain/v3/history
   * Get MetaBrain v3 history
   */
  fastify.get('/api/ta/metabrain/v3/history', async (
    request: FastifyRequest<{ Querystring: { asset?: string; tf?: string; limit?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { asset, tf, limit } = request.query;
      const limitNum = limit ? parseInt(limit, 10) : 50;
      
      const states = await getMetaBrainV3History(limitNum, asset, tf);
      const actions = await getMetaBrainV3Actions(limitNum);
      
      return {
        success: true,
        data: {
          states,
          actions
        }
      };
    } catch (err: any) {
      console.error('[MetaBrainV3] History error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/metabrain/v3/context
   * Get current context (without decision)
   */
  fastify.get('/api/ta/metabrain/v3/context', async (
    request: FastifyRequest<{ Querystring: { asset?: string; tf?: string; regime?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { asset = 'BTCUSDT', tf = '1d', regime } = request.query;
      
      const context = await buildMetaBrainV3Context(
        asset,
        tf,
        regime as MarketRegime | undefined
      );
      
      return {
        success: true,
        data: context
      };
    } catch (err: any) {
      console.error('[MetaBrainV3] Context error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * POST /api/ta/metabrain/v3/cleanup
   * Clean old data
   */
  fastify.post('/api/ta/metabrain/v3/cleanup', async (
    request: FastifyRequest<{ Body: { daysToKeep?: number } }>,
    reply: FastifyReply
  ) => {
    try {
      const { daysToKeep = 30 } = request.body ?? {};
      
      const result = await cleanOldMetaBrainV3Data(daysToKeep);
      
      return {
        success: true,
        data: {
          ...result,
          cleanedAt: new Date()
        }
      };
    } catch (err: any) {
      console.error('[MetaBrainV3] Cleanup error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  console.log('[MetaBrain v3 Routes] Registered:');
  console.log('  - GET  /api/ta/metabrain/v3/state');
  console.log('  - GET  /api/ta/metabrain/v3/decision');
  console.log('  - POST /api/ta/metabrain/v3/recompute');
  console.log('  - GET  /api/ta/metabrain/v3/history');
  console.log('  - GET  /api/ta/metabrain/v3/context');
  console.log('  - POST /api/ta/metabrain/v3/cleanup');
}
