/**
 * D1 — Structure-Aware Scoring Routes
 * 
 * API for testing and using structure-aware scoring
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { 
  StructureAwareScoringService, 
  DEFAULT_STRUCTURE_CONFIG,
  computeContextScore,
  computeMarketStateScore,
  computeLiquidityScore,
} from './structure_scoring.js';

export async function registerStructureScoringRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const service = new StructureAwareScoringService(db);

  /**
   * POST /structure_score/compute - Compute full structure-aware boost
   */
  app.post('/structure_score/compute', async (
    request: FastifyRequest<{
      Body: {
        asset?: string;
        timeframe?: string;
        patternType?: string;
        direction?: 'LONG' | 'SHORT';
        patternQuality?: number;
        mlScore?: number;
      };
    }>
  ) => {
    const body = request.body || {};
    const asset = body.asset || 'BTCUSDT';
    const timeframe = body.timeframe || '1d';
    const patternType = body.patternType || 'BULL_FLAG';
    const direction = body.direction || 'LONG';
    const patternQuality = body.patternQuality ?? 0.7;
    const mlScore = body.mlScore ?? 0.5;

    const result = await service.computeBoost(
      asset,
      timeframe,
      patternType,
      direction,
      patternQuality,
      mlScore
    );

    return {
      ok: true,
      asset,
      timeframe,
      patternType,
      direction,
      ...result,
    };
  });

  /**
   * GET /structure_score/config - Get current config
   */
  app.get('/structure_score/config', async () => {
    return {
      ok: true,
      config: service.getConfig(),
      defaults: DEFAULT_STRUCTURE_CONFIG,
    };
  });

  /**
   * PATCH /structure_score/config - Update config
   */
  app.patch('/structure_score/config', async (
    request: FastifyRequest<{
      Body: {
        weights?: Partial<typeof DEFAULT_STRUCTURE_CONFIG.weights>;
        boostClamp?: Partial<typeof DEFAULT_STRUCTURE_CONFIG.boostClamp>;
      };
    }>
  ) => {
    const body = request.body || {};
    service.updateConfig(body);
    return {
      ok: true,
      config: service.getConfig(),
    };
  });

  /**
   * GET /structure_score/test - Quick test with default params
   */
  app.get('/structure_score/test', async (
    request: FastifyRequest<{
      Querystring: {
        asset?: string;
        tf?: string;
        direction?: string;
      };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const direction = (request.query.direction || 'LONG') as 'LONG' | 'SHORT';

    // Test various pattern types
    const patterns = ['BULL_FLAG', 'ASC_TRIANGLE', 'DOUBLE_BOTTOM'];
    const results = [];

    for (const patternType of patterns) {
      const result = await service.computeBoost(
        asset,
        timeframe,
        patternType,
        direction,
        0.7,
        0.5
      );
      results.push({
        pattern: patternType,
        structureBoost: result.structureBoost,
        context: result.contextScore.overallScore,
        marketState: result.marketStateScore.overallScore,
        liquidity: result.liquidityScore.overallScore,
      });
    }

    return {
      ok: true,
      asset,
      timeframe,
      direction,
      results,
    };
  });

  /**
   * GET /structure_score/breakdown - Detailed breakdown for single pattern
   */
  app.get('/structure_score/breakdown', async (
    request: FastifyRequest<{
      Querystring: {
        asset?: string;
        tf?: string;
        pattern?: string;
        direction?: string;
      };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const patternType = request.query.pattern || 'BULL_FLAG';
    const direction = (request.query.direction || 'LONG') as 'LONG' | 'SHORT';

    const result = await service.computeBoost(
      asset,
      timeframe,
      patternType,
      direction,
      0.7,
      0.5
    );

    return {
      ok: true,
      asset,
      timeframe,
      patternType,
      direction,
      structureBoost: result.structureBoost,
      scores: {
        context: result.contextScore,
        marketState: result.marketStateScore,
        liquidity: result.liquidityScore,
        patternQuality: result.patternQualityScore,
        ml: result.mlScore,
      },
      breakdown: result.breakdown,
      interpretation: {
        context: result.contextScore.overallScore > 0.6 ? 'supportive' : 
                 result.contextScore.overallScore < 0.4 ? 'unfavorable' : 'neutral',
        marketState: result.marketStateScore.overallScore > 0.6 ? 'aligned' :
                    result.marketStateScore.overallScore < 0.4 ? 'misaligned' : 'neutral',
        liquidity: result.liquidityScore.overallScore > 0.6 ? 'favorable' :
                  result.liquidityScore.overallScore < 0.4 ? 'caution' : 'neutral',
        overall: result.structureBoost > 1.1 ? 'STRONG' :
                result.structureBoost < 0.9 ? 'WEAK' : 'NEUTRAL',
      },
    };
  });

  console.log('[StructureScoring] Routes registered: /structure_score/compute, /config, /test, /breakdown');
}
