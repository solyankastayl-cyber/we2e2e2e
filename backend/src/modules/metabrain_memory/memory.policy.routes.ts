/**
 * P1.3 — MM3 Memory Policy Routes
 * 
 * API endpoints for memory-conditioned policies
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { Db } from 'mongodb';
import {
  MemoryContext,
  MemoryPolicy,
  MemoryStrength,
  MemoryPolicyRecord
} from './memory.policy.types.js';
import {
  computeMemoryPolicy,
  classifyMemoryStrength,
  getNeutralMemoryPolicy,
  createMemoryContext
} from './memory.policies.js';
import {
  saveMemoryPolicy,
  getLatestMemoryPolicy,
  getMemoryPolicyHistory,
  countPoliciesByStrength,
  cleanOldPolicies
} from './memory.policy.storage.js';
import {
  fetchMemoryContext,
  getMemoryPolicyForMetaBrain,
  getMemoryPolicyForExplain
} from './memory.policy.integration.js';
import { ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerMemoryPolicyRoutes(
  fastify: FastifyInstance,
  db: Db
): Promise<void> {
  /**
   * GET /api/ta/metabrain/memory/policy
   * Get current memory policy for asset
   */
  fastify.get('/api/ta/metabrain/memory/policy', async (
    request: FastifyRequest<{ Querystring: { asset?: string; tf?: string; direction?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { asset, tf, direction } = request.query;
      
      if (!asset || !tf) {
        return reply.code(400).send({
          success: false,
          error: 'Missing required parameters: asset, tf'
        });
      }
      
      // Fetch memory context
      const context = await fetchMemoryContext(asset, tf);
      
      if (!context) {
        return {
          success: true,
          data: {
            context: null,
            policy: getNeutralMemoryPolicy(),
            strength: 'NONE' as MemoryStrength
          }
        };
      }
      
      // Compute policy
      const signalDirection = direction as ScenarioDirection | undefined;
      const strength = classifyMemoryStrength(context);
      const policy = computeMemoryPolicy(context, signalDirection);
      
      return {
        success: true,
        data: {
          context,
          policy,
          strength
        }
      };
    } catch (err: any) {
      console.error('[MemoryPolicy] Error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * POST /api/ta/metabrain/memory/recompute
   * Recompute and save memory policy
   */
  fastify.post('/api/ta/metabrain/memory/recompute', async (
    request: FastifyRequest<{ Body: { asset?: string; tf?: string; direction?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { asset, tf, direction } = request.body ?? {};
      
      if (!asset || !tf) {
        return reply.code(400).send({
          success: false,
          error: 'Missing required fields: asset, tf'
        });
      }
      
      // Fetch memory context
      const context = await fetchMemoryContext(asset, tf);
      
      if (!context) {
        return {
          success: true,
          data: {
            message: 'No memory context available',
            policy: getNeutralMemoryPolicy()
          }
        };
      }
      
      // Compute policy
      const signalDirection = direction as ScenarioDirection | undefined;
      const strength = classifyMemoryStrength(context);
      const policy = computeMemoryPolicy(context, signalDirection);
      
      // Save policy
      const record: MemoryPolicyRecord = {
        asset,
        timeframe: tf,
        ts: Date.now(),
        context,
        policy,
        strength,
        createdAt: new Date()
      };
      
      await saveMemoryPolicy(record);
      
      return {
        success: true,
        data: {
          asset,
          timeframe: tf,
          policy,
          strength,
          recomputedAt: new Date()
        }
      };
    } catch (err: any) {
      console.error('[MemoryPolicy] Recompute error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/metabrain/memory/history
   * Get memory policy history
   */
  fastify.get('/api/ta/metabrain/memory/history', async (
    request: FastifyRequest<{ Querystring: { asset?: string; tf?: string; limit?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { asset, tf, limit } = request.query;
      
      if (!asset || !tf) {
        return reply.code(400).send({
          success: false,
          error: 'Missing required parameters: asset, tf'
        });
      }
      
      const limitNum = limit ? parseInt(limit, 10) : 50;
      const history = await getMemoryPolicyHistory(asset, tf, limitNum);
      
      return {
        success: true,
        data: {
          history,
          count: history.length
        }
      };
    } catch (err: any) {
      console.error('[MemoryPolicy] History error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/metabrain/memory/stats
   * Get memory policy statistics
   */
  fastify.get('/api/ta/metabrain/memory/stats', async (
    request: FastifyRequest,
    reply: FastifyReply
  ) => {
    try {
      const counts = await countPoliciesByStrength();
      const total = Object.values(counts).reduce((a, b) => a + b, 0);
      
      return {
        success: true,
        data: {
          totalPolicies: total,
          byStrength: counts,
          strongRate: total > 0 ? counts.STRONG / total : 0,
          moderateRate: total > 0 ? counts.MODERATE / total : 0,
          weakRate: total > 0 ? counts.WEAK / total : 0
        }
      };
    } catch (err: any) {
      console.error('[MemoryPolicy] Stats error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * POST /api/ta/metabrain/memory/cleanup
   * Clean old policies
   */
  fastify.post('/api/ta/metabrain/memory/cleanup', async (
    request: FastifyRequest<{ Body: { daysToKeep?: number } }>,
    reply: FastifyReply
  ) => {
    try {
      const { daysToKeep = 30 } = request.body ?? {};
      
      const deleted = await cleanOldPolicies(daysToKeep);
      
      return {
        success: true,
        data: {
          deletedPolicies: deleted,
          cleanedAt: new Date()
        }
      };
    } catch (err: any) {
      console.error('[MemoryPolicy] Cleanup error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/metabrain/memory/explain
   * Get memory policy for explain API
   */
  fastify.get('/api/ta/metabrain/memory/explain', async (
    request: FastifyRequest<{ Querystring: { asset?: string; tf?: string; direction?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { asset, tf, direction } = request.query;
      
      if (!asset || !tf) {
        return reply.code(400).send({
          success: false,
          error: 'Missing required parameters: asset, tf'
        });
      }
      
      const signalDirection = direction as ScenarioDirection | undefined;
      const explainData = await getMemoryPolicyForExplain(asset, tf, signalDirection);
      
      return {
        success: true,
        data: explainData
      };
    } catch (err: any) {
      console.error('[MemoryPolicy] Explain error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  console.log('[MM3 Memory Policy Routes] Registered:');
  console.log('  - GET  /api/ta/metabrain/memory/policy?asset=...&tf=...');
  console.log('  - POST /api/ta/metabrain/memory/recompute');
  console.log('  - GET  /api/ta/metabrain/memory/history?asset=...&tf=...');
  console.log('  - GET  /api/ta/metabrain/memory/stats');
  console.log('  - POST /api/ta/metabrain/memory/cleanup');
  console.log('  - GET  /api/ta/metabrain/memory/explain?asset=...&tf=...');
}
