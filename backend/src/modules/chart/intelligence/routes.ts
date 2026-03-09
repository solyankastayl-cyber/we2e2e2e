/**
 * Chart Intelligence Routes
 * ==========================
 * 
 * Endpoints:
 *   GET /api/chart/candles     — OHLCV data
 *   GET /api/chart/prediction  — Forecast path
 *   GET /api/chart/levels      — Support / Resistance / Liquidity
 *   GET /api/chart/scenarios   — Probable market scenarios
 *   GET /api/chart/objects     — Graphical objects for frontend
 *   GET /api/chart/regime      — Current market regime
 *   GET /api/chart/system      — MetaBrain state
 *   GET /api/chart/state       — Aggregated full state (1 request)
 */

import { FastifyInstance } from 'fastify';
import { getCandles } from './candles.service.js';
import { getPrediction } from './prediction.service.js';
import { getLevels } from './levels.service.js';
import { getScenarios } from './scenarios.service.js';
import { buildChartObjects } from './objects.builder.js';
import { getRegime } from './regime.service.js';
import { getSystemState } from './system.service.js';
import { getChartState } from './state.service.js';

interface ChartQuery {
  symbol?: string;
  interval?: string;
  limit?: string;
  horizon?: string;
}

export async function registerChartIntelligenceRoutes(app: FastifyInstance): Promise<void> {

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/candles
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: ChartQuery }>('/api/chart/candles', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';
    const interval = request.query.interval || '1d';
    const limit = parseInt(request.query.limit || '500', 10);

    try {
      const data = await getCandles(symbol, interval, limit);
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/prediction
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: ChartQuery }>('/api/chart/prediction', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';
    const horizon = request.query.horizon || '90d';

    try {
      const data = await getPrediction(symbol, horizon);
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/levels
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: ChartQuery }>('/api/chart/levels', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';

    try {
      const data = await getLevels(symbol);
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/scenarios
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: ChartQuery }>('/api/chart/scenarios', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';

    try {
      const data = await getScenarios(symbol);
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/objects
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: ChartQuery }>('/api/chart/objects', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';

    try {
      // Get candles and levels for building objects
      const [candlesRes, levels, scenariosRes] = await Promise.all([
        getCandles(symbol, '1d', 100),
        getLevels(symbol),
        getScenarios(symbol),
      ]);

      const data = await buildChartObjects(
        symbol,
        candlesRes.candles,
        levels,
        scenariosRes.scenarios
      );
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/regime
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: ChartQuery }>('/api/chart/regime', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';

    try {
      const data = await getRegime(symbol);
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/system
  // ─────────────────────────────────────────────────────────────
  app.get('/api/chart/system', async (_request, reply) => {
    try {
      const data = await getSystemState();
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/state — MAIN AGGREGATED ENDPOINT
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: ChartQuery }>('/api/chart/state', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';
    const interval = request.query.interval || '1d';
    const limit = parseInt(request.query.limit || '500', 10);
    const horizon = request.query.horizon || '90d';

    try {
      const data = await getChartState(symbol, interval, limit, horizon);
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  console.log('[Chart Intelligence] Routes registered: /api/chart/*');
}
