/**
 * Edge Admin Routes (P5.0.9)
 * 
 * Admin endpoints for Edge Multiplier configuration
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { 
  getEdgeMultiplierService, 
  EdgeMultiplierService,
  EdgeMultiplierConfig,
  readEdgeMultiplierConfig
} from './edge.multiplier.service.js';

interface RouteContext {
  db: Db;
}

interface FlagsPatchBody {
  EDGE_MULT_ENABLED?: boolean;
  EDGE_MIN_N?: number;
  EDGE_MAX_AGE_H?: number;
  EDGE_CLAMP_MIN?: number;
  EDGE_CLAMP_MAX?: number;
}

export async function registerEdgeAdminRoutes(
  app: FastifyInstance,
  { db }: RouteContext
): Promise<void> {
  const multiplierService = getEdgeMultiplierService(db);

  /**
   * GET /admin/flags
   * Get current edge multiplier flags
   */
  app.get('/admin/flags', async () => {
    const config = multiplierService.getConfig();
    
    return {
      ok: true,
      flags: {
        EDGE_MULT_ENABLED: config.enabled,
        EDGE_MIN_N: config.minN,
        EDGE_MAX_AGE_H: config.maxAgeH,
        EDGE_CLAMP_MIN: config.clampMin,
        EDGE_CLAMP_MAX: config.clampMax,
      },
      source: 'runtime',
      note: 'These are runtime values. ENV values are read at startup.'
    };
  });

  /**
   * POST /admin/flags
   * Update edge multiplier flags at runtime
   */
  app.post('/admin/flags', async (request: FastifyRequest<{
    Body: FlagsPatchBody
  }>) => {
    const body = request.body || {};
    
    const update: Partial<EdgeMultiplierConfig> = {};
    
    if (body.EDGE_MULT_ENABLED !== undefined) {
      update.enabled = body.EDGE_MULT_ENABLED;
    }
    if (body.EDGE_MIN_N !== undefined) {
      update.minN = body.EDGE_MIN_N;
    }
    if (body.EDGE_MAX_AGE_H !== undefined) {
      update.maxAgeH = body.EDGE_MAX_AGE_H;
    }
    if (body.EDGE_CLAMP_MIN !== undefined) {
      update.clampMin = body.EDGE_CLAMP_MIN;
    }
    if (body.EDGE_CLAMP_MAX !== undefined) {
      update.clampMax = body.EDGE_CLAMP_MAX;
    }

    const newConfig = multiplierService.updateConfig(update);

    return {
      ok: true,
      updated: update,
      currentFlags: {
        EDGE_MULT_ENABLED: newConfig.enabled,
        EDGE_MIN_N: newConfig.minN,
        EDGE_MAX_AGE_H: newConfig.maxAgeH,
        EDGE_CLAMP_MIN: newConfig.clampMin,
        EDGE_CLAMP_MAX: newConfig.clampMax,
      }
    };
  });

  /**
   * GET /admin/multiplier/test
   * Test edge multiplier for a pattern
   */
  app.get('/admin/multiplier/test', async (request: FastifyRequest<{
    Querystring: { 
      pattern: string;
      regime?: string;
    }
  }>) => {
    const { pattern, regime } = request.query;
    
    if (!pattern) {
      return {
        ok: false,
        error: 'pattern parameter required'
      };
    }

    const result = await multiplierService.getMultiplier(pattern, regime);

    return {
      ok: true,
      input: { pattern, regime },
      result
    };
  });

  /**
   * POST /admin/multiplier/batch
   * Test edge multiplier for multiple patterns
   */
  app.post('/admin/multiplier/batch', async (request: FastifyRequest<{
    Body: { patterns: string[]; weights?: number[] }
  }>) => {
    const { patterns, weights } = request.body || {};
    
    if (!patterns || patterns.length === 0) {
      return {
        ok: false,
        error: 'patterns array required'
      };
    }

    const combined = await multiplierService.getCombinedMultiplier(patterns, weights);
    const individual = await multiplierService.getMultipliers(patterns);

    return {
      ok: true,
      combined,
      individual: Object.fromEntries(individual)
    };
  });

  console.log('[Edge] Admin routes registered: /admin/flags, /admin/multiplier/test, /admin/multiplier/batch');
}
