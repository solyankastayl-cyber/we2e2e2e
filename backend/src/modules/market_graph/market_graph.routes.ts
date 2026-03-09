/**
 * G1 + G2 + G3 — Market Graph API Routes
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { MarketGraphService } from './market_graph.service.js';
import { MarketEventType } from './market_graph.types.js';

export async function registerMarketGraphRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const service = new MarketGraphService(db);
  await service.ensureIndexes();

  /**
   * POST /rebuild - Rebuild event graph for asset/timeframe
   */
  app.post('/rebuild', async (
    request: FastifyRequest<{
      Body: {
        asset?: string;
        timeframe?: string;
        startTs?: number;
        endTs?: number;
      };
    }>
  ) => {
    const body = request.body || {};
    const asset = body.asset || 'BTCUSDT';
    const timeframe = body.timeframe || '1d';

    const result = await service.rebuild(asset, timeframe, body.startTs, body.endTs);

    return {
      ok: true,
      asset,
      timeframe,
      ...result,
    };
  });

  /**
   * GET /events - Get market events
   */
  app.get('/events', async (
    request: FastifyRequest<{
      Querystring: {
        asset?: string;
        tf?: string;
        limit?: string;
      };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const limit = parseInt(request.query.limit || '100', 10);

    const events = await service.getEvents(asset, timeframe, limit);

    return {
      ok: true,
      asset,
      timeframe,
      count: events.length,
      events,
    };
  });

  /**
   * GET /transitions - Get event transitions
   */
  app.get('/transitions', async (
    request: FastifyRequest<{
      Querystring: {
        limit?: string;
        from?: string;
      };
    }>
  ) => {
    const limit = parseInt(request.query.limit || '50', 10);
    
    if (request.query.from) {
      const from = request.query.from as MarketEventType;
      const transitions = await service.getTransitionsFrom(from);
      return {
        ok: true,
        from,
        count: transitions.length,
        transitions,
      };
    }

    const transitions = await service.getTransitions(limit);

    return {
      ok: true,
      count: transitions.length,
      transitions,
    };
  });

  /**
   * GET /stats - Get graph statistics
   */
  app.get('/stats', async () => {
    const stats = await service.getStats();
    return {
      ok: true,
      ...stats,
    };
  });

  /**
   * GET /score - Compute graph boost score
   */
  app.get('/score', async (
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
    const pattern = request.query.pattern;
    const direction = request.query.direction as 'BULL' | 'BEAR' | undefined;

    const result = await service.computeBoost(asset, timeframe, pattern, direction);

    return {
      ok: true,
      asset,
      timeframe,
      score: result.score,
      confidence: result.confidence,
      boost: result.boost,
      chainLength: result.currentChain.length,
      predictedNext: result.predictedNext,
      bestPath: result.bestPath,
    };
  });

  /**
   * GET /forecast - Forecast next market events
   */
  app.get('/forecast', async (
    request: FastifyRequest<{
      Querystring: {
        asset?: string;
        tf?: string;
        topN?: string;
      };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const topN = parseInt(request.query.topN || '5', 10);

    const result = await service.forecast(asset, timeframe, topN);

    return {
      ok: true,
      asset,
      timeframe,
      chainLength: result.currentChain.length,
      currentEvents: result.currentChain.map(e => ({
        type: e.type,
        pattern: e.patternType,
        direction: e.direction,
      })),
      predictedNext: result.predictedNext,
      bestPath: result.bestPath,
      pathProbability: result.pathProbability,
    };
  });

  console.log('[MarketGraph] Routes registered: /rebuild, /events, /transitions, /stats, /score, /forecast');
}
