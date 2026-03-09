/**
 * MetaBrain v2.1 — API Routes
 * 
 * Learning Layer endpoints
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { DEFAULT_LEARNING_CONFIG } from './module_attribution.types.js';
import {
  rebuildModuleAttribution,
  getCurrentWeights,
  getModuleWeight,
  getCurrentAttribution,
  forceRecompute,
  getLearningStatus
} from './module_controller.js';
import { getWeightHistory, getRecentWeightChanges } from './module_storage.js';
import { getWeightSummary } from './module_weights.engine.js';
import { registerGatingRoutes } from './learning.gating.routes.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerLearningRoutes(fastify: FastifyInstance): Promise<void> {

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/learning/status - Learning status
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/learning/status', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const status = await getLearningStatus();
      return status;
    } catch (error) {
      console.error('[LearningRoutes] Status error:', error);
      return reply.status(500).send({ error: 'Failed to get learning status' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/learning/weights - Current module weights
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/learning/weights', async (request: FastifyRequest, reply: FastifyReply) => {
    const { regime } = request.query as Record<string, string>;
    
    try {
      const weights = await getCurrentWeights(regime);
      const summary = getWeightSummary(weights);
      
      return {
        weights: weights.map(w => ({
          module: w.module,
          weight: w.weight,
          confidence: w.confidence,
          edgeScore: w.basedOnEdgeScore,
          sampleSize: w.basedOnSample
        })),
        summary,
        regime: regime || 'GLOBAL'
      };
    } catch (error) {
      console.error('[LearningRoutes] Weights error:', error);
      return reply.status(500).send({ error: 'Failed to get weights' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/learning/attribution - Current attribution
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/learning/attribution', async (request: FastifyRequest, reply: FastifyReply) => {
    const { regime } = request.query as Record<string, string>;
    
    try {
      const attribution = await getCurrentAttribution(regime);
      
      if (!attribution) {
        return {
          hasData: false,
          message: 'No attribution data. Run /rebuild to compute.',
          regime: regime || 'GLOBAL'
        };
      }
      
      return {
        hasData: true,
        attribution: {
          modules: attribution.modules.map(m => ({
            module: m.module,
            edgeScore: Math.round(m.edgeScore * 100) / 100,
            winRate: Math.round(m.winRate * 100) / 100,
            profitFactor: Math.round(m.profitFactor * 100) / 100,
            avgR: Math.round(m.avgR * 100) / 100,
            impact: m.impact,
            sampleSize: m.sampleSize,
            confidence: Math.round(m.confidence * 100) / 100
          })),
          topModules: attribution.topModules,
          weakModules: attribution.weakModules,
          baseline: attribution.baseline
        },
        calculatedAt: attribution.calculatedAt,
        regime: regime || 'GLOBAL'
      };
    } catch (error) {
      console.error('[LearningRoutes] Attribution error:', error);
      return reply.status(500).send({ error: 'Failed to get attribution' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/metabrain/learning/rebuild - Rebuild attribution
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/metabrain/learning/rebuild', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    
    const {
      asset,
      timeframe,
      regime,
      useSynthetic = true,
      dataWindowDays
    } = body || {};
    
    try {
      const config = { ...DEFAULT_LEARNING_CONFIG };
      if (dataWindowDays) config.dataWindowDays = dataWindowDays;
      
      const result = await rebuildModuleAttribution(config, {
        asset,
        timeframe,
        regime,
        useSynthetic
      });
      
      return {
        success: true,
        attribution: {
          topModules: result.attribution.topModules,
          weakModules: result.attribution.weakModules,
          moduleCount: result.attribution.modules.length,
          totalSamples: result.attribution.modules.reduce((sum, m) => sum + m.sampleSize, 0)
        },
        weights: result.weights.map(w => ({
          module: w.module,
          weight: w.weight,
          edgeScore: w.basedOnEdgeScore
        })),
        history: result.history.map(h => ({
          module: h.module,
          weight: h.weight,
          reason: h.reason
        })),
        regime: regime || 'GLOBAL'
      };
    } catch (error) {
      console.error('[LearningRoutes] Rebuild error:', error);
      return reply.status(500).send({ error: 'Rebuild failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/learning/weight/:module - Single module weight
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/learning/weight/:module', async (request: FastifyRequest, reply: FastifyReply) => {
    const { module } = request.params as Record<string, string>;
    const { regime } = request.query as Record<string, string>;
    
    try {
      const weight = await getModuleWeight(module as any, regime);
      const history = await getWeightHistory(module as any, 20);
      
      return {
        module,
        weight,
        regime: regime || 'GLOBAL',
        history: history.map(h => ({
          weight: h.weight,
          reason: h.reason,
          changedAt: h.changedAt
        }))
      };
    } catch (error) {
      console.error('[LearningRoutes] Weight error:', error);
      return reply.status(500).send({ error: 'Failed to get weight' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/learning/history - Weight change history
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/learning/history', async (request: FastifyRequest, reply: FastifyReply) => {
    const { days = '30', limit = '50' } = request.query as Record<string, string>;
    
    try {
      const changes = await getRecentWeightChanges(parseInt(days), parseInt(limit));
      
      return {
        count: changes.length,
        daysBack: parseInt(days),
        changes: changes.map(c => ({
          module: c.module,
          weight: c.weight,
          regime: c.regime,
          reason: c.reason,
          changedAt: c.changedAt
        }))
      };
    } catch (error) {
      console.error('[LearningRoutes] History error:', error);
      return reply.status(500).send({ error: 'Failed to get history' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/learning/config - Get config
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/learning/config', async (request: FastifyRequest, reply: FastifyReply) => {
    return {
      config: DEFAULT_LEARNING_CONFIG
    };
  });

  // ─────────────────────────────────────────────────────────────
  // P1.2: Module Gating Routes
  // ─────────────────────────────────────────────────────────────
  await registerGatingRoutes(fastify);
}

export default registerLearningRoutes;
