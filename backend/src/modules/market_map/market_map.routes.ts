/**
 * Phase 2.5 — Market Map Routes
 * ===============================
 * 
 * Endpoints:
 *   GET /api/chart/market-map      — Main market map (probabilistic branches)
 *   GET /api/chart/heatmap         — Price probability heatmap
 *   GET /api/chart/timeline        — Event timeline
 *   GET /api/chart/scenario-paths  — Visual scenario paths
 *   GET /api/chart/market-tree     — Branch tree structure
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { getMarketMap, getBatchMarketMaps, detectCurrentState } from './market_map.service.js';
import { buildMarketTree } from './market_map.tree.js';
import { getHeatmap, getHeatmapInRange } from './market_map.heatmap.js';
import { getTimeline } from './market_map.timeline.js';
import { ScenarioPathsResponse, ScenarioPath, PathPoint } from './market_map.types.js';

// ═══════════════════════════════════════════════════════════════
// QUERY INTERFACES
// ═══════════════════════════════════════════════════════════════

interface MarketMapQuery {
  symbol?: string;
  timeframe?: string;
}

interface HeatmapQuery {
  symbol?: string;
  timeframe?: string;
  levels?: string;
  range?: string;
}

interface TimelineQuery {
  symbol?: string;
  timeframe?: string;
  events?: string;
}

interface TreeQuery {
  symbol?: string;
  timeframe?: string;
  depth?: string;
}

// ═══════════════════════════════════════════════════════════════
// BASE PRICES FOR PATH GENERATION
// ═══════════════════════════════════════════════════════════════

const BASE_PRICES: Record<string, number> = {
  BTCUSDT: 87000,
  ETHUSDT: 3200,
  SOLUSDT: 145,
  BNBUSDT: 620,
};

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerMarketMapRoutes(app: FastifyInstance): Promise<void> {

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/market-map — MAIN ENDPOINT
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: MarketMapQuery }>('/api/chart/market-map', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';
    const timeframe = request.query.timeframe || '1d';

    try {
      const data = await getMarketMap(symbol, timeframe);
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/heatmap — Price probability heatmap
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: HeatmapQuery }>('/api/chart/heatmap', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';
    const timeframe = request.query.timeframe || '1d';
    const numLevels = parseInt(request.query.levels || '10', 10);
    const rangePercent = parseFloat(request.query.range || '0.15');

    try {
      const data = await getHeatmap(symbol, timeframe, numLevels, rangePercent);
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/timeline — Event timeline
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: TimelineQuery }>('/api/chart/timeline', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';
    const timeframe = request.query.timeframe || '1d';
    const maxEvents = parseInt(request.query.events || '8', 10);

    try {
      const data = await getTimeline(symbol, timeframe, maxEvents);
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/scenario-paths — Visual scenario paths
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: MarketMapQuery }>('/api/chart/scenario-paths', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';
    const timeframe = request.query.timeframe || '1d';

    try {
      // Get market map to derive paths
      const marketMap = await getMarketMap(symbol, timeframe);
      
      // Convert branches to visual paths
      const paths: ScenarioPath[] = marketMap.branches.map((branch, idx) => {
        // Assign colors based on direction
        let color: string;
        switch (branch.direction) {
          case 'BULL':
            color = '#22c55e'; // green
            break;
          case 'BEAR':
            color = '#ef4444'; // red
            break;
          default:
            color = '#f59e0b'; // amber
        }
        
        return {
          id: `path_${idx}`,
          probability: branch.probability,
          direction: branch.direction,
          points: branch.path,
          label: `${branch.scenario} (${Math.round(branch.probability * 100)}%)`,
          color,
        };
      });

      const response: ScenarioPathsResponse = {
        symbol,
        timeframe,
        ts: Date.now(),
        currentPrice: marketMap.currentPrice,
        paths,
      };

      return reply.send({ ok: true, data: response });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/chart/market-tree — Branch tree structure
  // ─────────────────────────────────────────────────────────────
  app.get<{ Querystring: TreeQuery }>('/api/chart/market-tree', async (request, reply) => {
    const symbol = request.query.symbol || 'BTCUSDT';
    const timeframe = request.query.timeframe || '1d';
    const maxDepth = parseInt(request.query.depth || '3', 10);

    try {
      const currentState = detectCurrentState(symbol);
      const data = buildMarketTree(symbol, timeframe, currentState, maxDepth);
      return reply.send({ ok: true, data });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });

  console.log('[Market Map Routes] Registered:');
  console.log('  - GET /api/chart/market-map');
  console.log('  - GET /api/chart/heatmap');
  console.log('  - GET /api/chart/timeline');
  console.log('  - GET /api/chart/scenario-paths');
  console.log('  - GET /api/chart/market-tree');
}
