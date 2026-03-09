/**
 * Liquidity Engine - API Routes
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { LiquidityService } from './liquidity.service.js';
import { DEFAULT_LIQUIDITY_CONFIG } from './liquidity.types.js';

export async function registerLiquidityRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const service = new LiquidityService(db);

  /**
   * GET /analyze - Full liquidity analysis
   */
  app.get('/analyze', async (
    request: FastifyRequest<{
      Querystring: {
        asset?: string;
        tf?: string;
        lookback?: string;
      };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const lookback = parseInt(request.query.lookback || '200', 10);

    const analysis = await service.analyze(asset, timeframe, lookback);

    return {
      ok: true,
      asset,
      timeframe,
      ...analysis,
    };
  });

  /**
   * GET /zones - Just the liquidity zones
   */
  app.get('/zones', async (
    request: FastifyRequest<{
      Querystring: {
        asset?: string;
        tf?: string;
        lookback?: string;
      };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const lookback = parseInt(request.query.lookback || '200', 10);

    const analysis = await service.analyze(asset, timeframe, lookback);

    return {
      ok: true,
      asset,
      timeframe,
      zones: analysis.zones,
      nearestResistance: analysis.nearestResistance,
      nearestSupport: analysis.nearestSupport,
    };
  });

  /**
   * GET /sweeps - Recent sweep events
   */
  app.get('/sweeps', async (
    request: FastifyRequest<{
      Querystring: {
        asset?: string;
        tf?: string;
        lookback?: string;
      };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const lookback = parseInt(request.query.lookback || '200', 10);

    const analysis = await service.analyze(asset, timeframe, lookback);

    return {
      ok: true,
      asset,
      timeframe,
      sweeps: analysis.sweeps,
      metrics: {
        recentSweepUp: analysis.metrics.recentSweepUp,
        recentSweepDown: analysis.metrics.recentSweepDown,
        liquidityBias: analysis.metrics.liquidityBias,
      },
    };
  });

  /**
   * POST /boost - Get liquidity boost for a pattern
   */
  app.post('/boost', async (
    request: FastifyRequest<{
      Body: {
        asset?: string;
        timeframe?: string;
        direction?: 'BULLISH' | 'BEARISH';
      };
    }>
  ) => {
    const body = request.body || {};
    const asset = body.asset || 'BTCUSDT';
    const timeframe = body.timeframe || '1d';
    const direction = body.direction || 'BULLISH';

    const result = await service.getLiquidityBoost(asset, timeframe, direction);

    return {
      ok: true,
      asset,
      timeframe,
      direction,
      boost: result.boost,
      reason: result.reason,
      metrics: result.analysis.metrics,
    };
  });

  /**
   * GET /config - Default configuration
   */
  app.get('/config', async () => {
    return {
      ok: true,
      config: DEFAULT_LIQUIDITY_CONFIG,
    };
  });

  console.log('[Liquidity] Routes registered: /analyze, /zones, /sweeps, /boost, /config');
}
