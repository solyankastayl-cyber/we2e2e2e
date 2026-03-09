/**
 * D2 — Fractal Engine Routes
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { FractalService } from './fractal.service.js';
import { DEFAULT_FRACTAL_CONFIG } from './fractal.types.js';

export async function registerFractalRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const service = new FractalService(db);
  await service.ensureIndexes();

  /**
   * POST /extract - Extract signature for current market
   */
  app.post('/extract', async (
    request: FastifyRequest<{
      Body: { asset?: string; timeframe?: string };
    }>
  ) => {
    const body = request.body || {};
    const asset = body.asset || 'BTCUSDT';
    const timeframe = body.timeframe || '1d';

    const signature = await service.extractSignature(asset, timeframe);

    return {
      ok: signature !== null,
      asset,
      timeframe,
      signature: signature ? {
        id: signature.id,
        vectorLength: signature.vectorLength,
        volatility: signature.volatility,
        trendBias: signature.trendBias,
        compression: signature.compression,
        impulseStrength: signature.impulseStrength,
      } : null,
    };
  });

  /**
   * POST /build - Build historical signatures
   */
  app.post('/build', async (
    request: FastifyRequest<{
      Body: { asset?: string; timeframe?: string; maxSignatures?: number };
    }>
  ) => {
    const body = request.body || {};
    const asset = body.asset || 'BTCUSDT';
    const timeframe = body.timeframe || '1d';
    const maxSignatures = body.maxSignatures || 500;

    const count = await service.buildHistoricalSignatures(asset, timeframe, maxSignatures);

    return {
      ok: true,
      asset,
      timeframe,
      signaturesBuilt: count,
    };
  });

  /**
   * POST /discovery/rebuild - Rebuild clusters and discover patterns
   */
  app.post('/discovery/rebuild', async () => {
    const result = await service.rebuildDiscovery();
    return {
      ok: true,
      ...result,
    };
  });

  /**
   * GET /match - Match current market to discovered fractals
   */
  app.get('/match', async (
    request: FastifyRequest<{
      Querystring: { asset?: string; tf?: string; topN?: string };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const topN = parseInt(request.query.topN || '5', 10);

    const matches = await service.matchCurrent(asset, timeframe, topN);

    return {
      ok: true,
      asset,
      timeframe,
      matchCount: matches.length,
      matches,
    };
  });

  /**
   * GET /boost - Get fractal boost for decision engine
   */
  app.get('/boost', async (
    request: FastifyRequest<{
      Querystring: { asset?: string; tf?: string; direction?: string };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const direction = (request.query.direction || 'BULL') as 'BULL' | 'BEAR';

    const result = await service.getFractalBoost(asset, timeframe, direction);

    return {
      ok: true,
      asset,
      timeframe,
      direction,
      boost: result.boost,
      matches: result.matches,
    };
  });

  /**
   * GET /clusters - Get all clusters
   */
  app.get('/clusters', async () => {
    const clusters = await service.getClusters();
    return {
      ok: true,
      count: clusters.length,
      clusters: clusters.map(c => ({
        clusterId: c.clusterId,
        size: c.size,
        avgTrendBias: c.avgTrendBias,
        avgVolatility: c.avgVolatility,
        avgCompression: c.avgCompression,
      })),
    };
  });

  /**
   * GET /discovered - Get discovered fractal patterns
   */
  app.get('/discovered', async () => {
    const patterns = await service.getDiscoveredPatterns();
    return {
      ok: true,
      count: patterns.length,
      patterns,
    };
  });

  /**
   * GET /stats - Get fractal engine statistics
   */
  app.get('/stats', async () => {
    const stats = await service.getStats();
    return {
      ok: true,
      ...stats,
    };
  });

  /**
   * GET /config - Get configuration
   */
  app.get('/config', async () => {
    return {
      ok: true,
      config: DEFAULT_FRACTAL_CONFIG,
    };
  });

  console.log('[FractalEngine] Routes: /extract, /build, /discovery/rebuild, /match, /boost, /clusters, /discovered, /stats');
}
