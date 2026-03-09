/**
 * Phase 9.5 — Edge Validation: Routes
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { getEdgeValidationService } from './edge.service.js';
import { StrategyLifecycle } from './edge.types.js';

export async function registerEdgeValidationRoutes(
  app: FastifyInstance,
  options: { db: Db }
): Promise<void> {
  const service = getEdgeValidationService(options.db);
  
  /**
   * POST /api/edge/validate
   */
  app.post('/validate', async (
    request: FastifyRequest<{
      Body: {
        strategyId: string;
        strategyName: string;
        features: string[];
        metrics: { winRate: number; profitFactor: number; sharpe: number; maxDrawdown: number; trades: number };
        allStrategies?: { id: string; features: string[] }[];
      }
    }>
  ) => {
    const { strategyId, strategyName, features, metrics, allStrategies = [] } = request.body || {};
    
    const result = await service.validateStrategy(
      strategyId,
      strategyName,
      features,
      metrics,
      allStrategies
    );
    
    return result;
  });
  
  /**
   * POST /api/edge/validate-all
   */
  app.post('/validate-all', async (
    request: FastifyRequest<{
      Body: {
        strategies: {
          id: string;
          name: string;
          features: string[];
          metrics: { winRate: number; profitFactor: number; sharpe: number; maxDrawdown: number; trades: number };
        }[];
      }
    }>
  ) => {
    const { strategies = [] } = request.body || {};
    
    const results = await service.validateAllStrategies(strategies);
    
    return {
      validated: results.length,
      results: results.map(r => ({
        strategyId: r.strategyId,
        strategyName: r.strategyName,
        confidence: r.confidence.adjustedConfidence,
        status: r.recommendedStatus,
        reason: r.statusReason,
        riskFlags: r.confidence.riskFlags
      }))
    };
  });
  
  /**
   * GET /api/edge/validation/:id
   */
  app.get('/validation/:id', async (
    request: FastifyRequest<{ Params: { id: string } }>
  ) => {
    const validation = await service.getValidation(request.params.id);
    
    if (!validation) {
      return { error: 'Validation not found' };
    }
    
    return validation;
  });
  
  /**
   * POST /api/edge/lifecycle/:id
   */
  app.post('/lifecycle/:id', async (
    request: FastifyRequest<{
      Params: { id: string };
      Body: { status: StrategyLifecycle }
    }>
  ) => {
    const { status } = request.body || {};
    
    const success = await service.updateLifecycle(request.params.id, status);
    
    return { success, strategyId: request.params.id, newStatus: status };
  });
  
  /**
   * GET /api/edge/summary
   */
  app.get('/summary', async () => {
    return await service.getSummary();
  });
  
  /**
   * GET /api/edge/health
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

export async function initEdgeValidationIndexes(db: Db): Promise<void> {
  try {
    await db.collection('edge_validations').createIndex(
      { strategyId: 1 },
      { unique: true, background: true }
    );
    await db.collection('edge_validations').createIndex(
      { recommendedStatus: 1, 'confidence.adjustedConfidence': -1 },
      { background: true }
    );
    console.log('[Edge Validation] Indexes initialized');
  } catch (error) {
    console.error('[Edge Validation] Failed to create indexes:', error);
  }
}
