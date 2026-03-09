/**
 * P1.4 — MetaBrain v2.3 Regime Learning Routes
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { Db } from 'mongodb';
import { AnalysisModule, ALL_MODULES } from '../metabrain_learning/module_attribution.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import { RegimeModuleWeight, ALL_REGIMES } from './regime.learning.types.js';
import {
  computeRegimeModuleWeight,
  buildRegimeWeightMap,
  getDefaultRegimeWeights
} from './regime.learning.js';
import {
  saveRegimeWeights,
  getRegimeWeights,
  getAllRegimeWeights,
  getRegimeWeightMaps,
  resetAllRegimeWeights
} from './regime.learning.storage.js';
import { getRegimeWeightsForExplain, getRegimeLearningState } from './regime.learning.integration.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerRegimeLearningRoutes(
  fastify: FastifyInstance,
  db: Db
): Promise<void> {
  /**
   * GET /api/ta/metabrain/regime/weights
   * Get regime weights
   */
  fastify.get('/api/ta/metabrain/regime/weights', async (
    request: FastifyRequest<{ Querystring: { regime?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { regime } = request.query;
      
      if (regime) {
        if (!ALL_REGIMES.includes(regime as MarketRegime)) {
          return reply.code(400).send({
            success: false,
            error: `Unknown regime: ${regime}`
          });
        }
        
        const weights = await getRegimeWeights(regime as MarketRegime);
        const state = await getRegimeLearningState(regime as MarketRegime);
        
        return {
          success: true,
          data: {
            regime,
            weights,
            summary: {
              avgConfidence: state.avgConfidence,
              totalSamples: weights.reduce((sum, w) => sum + w.sampleSize, 0),
              modulesWithData: state.modulesWithData
            }
          }
        };
      }
      
      // Return all regime weight maps
      const maps = await getRegimeWeightMaps();
      
      return {
        success: true,
        data: {
          regimes: maps,
          totalRegimes: maps.length
        }
      };
    } catch (err: any) {
      console.error('[RegimeLearning] Error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * POST /api/ta/metabrain/regime/rebuild
   * Rebuild regime weights from attribution data
   */
  fastify.post('/api/ta/metabrain/regime/rebuild', async (
    request: FastifyRequest<{ Body: { regime?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { regime } = request.body ?? {};
      
      // For now, initialize with default weights if no attribution data
      // In production, this would pull from ta_module_attribution by regime
      const regimesToProcess = regime 
        ? [regime as MarketRegime]
        : ALL_REGIMES;
      
      let totalUpdated = 0;
      
      for (const r of regimesToProcess) {
        const weights = getDefaultRegimeWeights(r);
        await saveRegimeWeights(weights);
        totalUpdated += weights.length;
      }
      
      return {
        success: true,
        data: {
          regimesProcessed: regimesToProcess.length,
          weightsUpdated: totalUpdated,
          rebuiltAt: new Date()
        }
      };
    } catch (err: any) {
      console.error('[RegimeLearning] Rebuild error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/metabrain/regime/weights/:module
   * Get weights for specific module across regimes
   */
  fastify.get('/api/ta/metabrain/regime/weights/:module', async (
    request: FastifyRequest<{ Params: { module: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { module } = request.params;
      
      if (!ALL_MODULES.includes(module as AnalysisModule)) {
        return reply.code(400).send({
          success: false,
          error: `Unknown module: ${module}`
        });
      }
      
      const allWeights = await getAllRegimeWeights();
      const moduleWeights = allWeights.filter(w => w.module === module);
      
      // Build comparison across regimes
      const comparison: Record<string, number> = {};
      for (const regime of ALL_REGIMES) {
        const w = moduleWeights.find(mw => mw.regime === regime);
        comparison[regime] = w?.weight ?? 1.0;
      }
      
      return {
        success: true,
        data: {
          module,
          weights: moduleWeights,
          comparison
        }
      };
    } catch (err: any) {
      console.error('[RegimeLearning] Module weights error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/metabrain/regime/explain
   * Get regime weights for explain API
   */
  fastify.get('/api/ta/metabrain/regime/explain', async (
    request: FastifyRequest<{ Querystring: { regime?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { regime } = request.query;
      
      if (!regime || !ALL_REGIMES.includes(regime as MarketRegime)) {
        return reply.code(400).send({
          success: false,
          error: 'Missing or invalid regime parameter'
        });
      }
      
      const weights = await getRegimeWeightsForExplain(regime as MarketRegime);
      
      return {
        success: true,
        data: {
          regime,
          regimeWeights: weights
        }
      };
    } catch (err: any) {
      console.error('[RegimeLearning] Explain error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * POST /api/ta/metabrain/regime/reset
   * Reset all regime weights
   */
  fastify.post('/api/ta/metabrain/regime/reset', async (
    request: FastifyRequest,
    reply: FastifyReply
  ) => {
    try {
      const deleted = await resetAllRegimeWeights();
      
      return {
        success: true,
        data: {
          weightsDeleted: deleted,
          resetAt: new Date()
        }
      };
    } catch (err: any) {
      console.error('[RegimeLearning] Reset error:', err.message);
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  console.log('[P1.4 Regime Learning Routes] Registered:');
  console.log('  - GET  /api/ta/metabrain/regime/weights');
  console.log('  - GET  /api/ta/metabrain/regime/weights?regime=...');
  console.log('  - POST /api/ta/metabrain/regime/rebuild');
  console.log('  - GET  /api/ta/metabrain/regime/weights/:module');
  console.log('  - GET  /api/ta/metabrain/regime/explain?regime=...');
  console.log('  - POST /api/ta/metabrain/regime/reset');
}
