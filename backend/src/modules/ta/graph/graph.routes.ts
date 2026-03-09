/**
 * Phase 8.6 — Graph API Routes
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';
import {
  createGraphStorage,
  createGraphIndexes,
} from './graph.storage.js';
import { buildGraph, patternsToEvents } from './graph.builder.js';
import { buildGraphV2, getGraphStats } from './graph.builder_v2.js';
import { createGraphBoostService } from './graph.service.js';
import { 
  applyGraphBoostToScenarios, 
  createDecisionPackWithBoost,
  extractGraphFeatures,
  calculateBoostedEV 
} from './graph.integration.js';
import { DEFAULT_GRAPH_PARAMS, DEFAULT_GRAPH_CONFIG, BoostParams } from './graph.types.js';

export async function registerGraphRoutes(
  app: FastifyInstance,
  opts: { db: Db }
): Promise<void> {
  // Create indexes
  await createGraphIndexes(opts.db);

  const storage = createGraphStorage(opts.db);
  const boostService = createGraphBoostService(opts.db);

  // GET /graph/status
  app.get('/graph/status', async () => {
    const stats = await getGraphStats(opts.db);
    return stats;
  });

  // GET /graph/runs
  app.get('/graph/runs', async (req) => {
    const { limit } = req.query as { limit?: string };
    const runs = await storage.getRuns(limit ? parseInt(limit, 10) : 20);
    return { runs };
  });

  // POST /graph/rebuild - Full graph rebuild from ta_patterns
  app.post('/graph/rebuild', async (req, reply) => {
    const { 
      assets, 
      timeframes, 
      windowBars,
      minEdgeCount,
      liftMin 
    } = req.body as {
      assets?: string[];
      timeframes?: string[];
      windowBars?: number[];
      minEdgeCount?: number;
      liftMin?: number;
    };

    const params = {
      ...DEFAULT_GRAPH_PARAMS,
      ...(assets && { assets }),
      ...(timeframes && { timeframes }),
      ...(windowBars && { windowBars }),
      ...(minEdgeCount && { minEdgeCount }),
      ...(liftMin && { liftMin }),
    };

    try {
      const result = await buildGraphV2(opts.db, params);
      return { ok: true, ...result };
    } catch (err: any) {
      return reply.code(500).send({ error: err.message });
    }
  });

  // POST /graph/boost - Compute boost for a pattern
  app.post('/graph/boost', async (req, reply) => {
    const params = req.body as BoostParams;

    if (!params.patternType || !params.direction || !params.timeframe) {
      return reply.code(400).send({ error: 'patternType, direction, timeframe required' });
    }

    const result = await boostService.computeBoost(params);
    return result;
  });

  // POST /graph/boost/scenarios - Apply boost to multiple scenarios
  app.post('/graph/boost/scenarios', async (req, reply) => {
    const { scenarios } = req.body as {
      scenarios: Array<{
        scenarioId: string;
        patternType: string;
        direction: string;
        timeframe: string;
        score: number;
        recentPatterns?: Array<{ type: string; direction: string; barsAgo: number }>;
      }>;
    };

    if (!scenarios?.length) {
      return reply.code(400).send({ error: 'scenarios array required' });
    }

    const boosted = await applyGraphBoostToScenarios(opts.db, scenarios);
    return { scenarios: boosted };
  });

  // POST /graph/decision_pack - Create full decision pack with boost
  app.post('/graph/decision_pack', async (req, reply) => {
    const { asset, timeframe, scenarios } = req.body as {
      asset: string;
      timeframe: string;
      scenarios: Array<{
        scenarioId: string;
        patternType: string;
        direction: string;
        score: number;
        recentPatterns?: Array<{ type: string; direction: string; barsAgo: number }>;
      }>;
    };

    if (!asset || !timeframe || !scenarios?.length) {
      return reply.code(400).send({ error: 'asset, timeframe, scenarios required' });
    }

    const pack = await createDecisionPackWithBoost(opts.db, asset, timeframe, scenarios);
    return pack;
  });

  // POST /graph/ev - Calculate boosted expected value
  app.post('/graph/ev', async (req, reply) => {
    const { baseWinProbability, graphBoostFactor, riskRewardRatio } = req.body as {
      baseWinProbability: number;
      graphBoostFactor: number;
      riskRewardRatio: number;
    };

    if (baseWinProbability === undefined || graphBoostFactor === undefined || riskRewardRatio === undefined) {
      return reply.code(400).send({ error: 'baseWinProbability, graphBoostFactor, riskRewardRatio required' });
    }

    const ev = calculateBoostedEV(baseWinProbability, graphBoostFactor, riskRewardRatio);
    return ev;
  });

  // GET /graph/node/:type
  app.get('/graph/node/:type', async (req, reply) => {
    const { type } = req.params as { type: string };
    const { tf } = req.query as { tf?: string };

    const info = await boostService.getNodeInfo(type, tf || '1d');
    if (!info) {
      return reply.code(404).send({ error: 'Node not found' });
    }
    return info;
  });

  // GET /graph/transitions/:type
  app.get('/graph/transitions/:type', async (req, reply) => {
    const { type } = req.params as { type: string };
    const { tf, limit } = req.query as { tf?: string; limit?: string };

    const transitions = await boostService.getTopTransitions(
      type, 
      tf || '1d',
      limit ? parseInt(limit, 10) : 10
    );
    return { transitions };
  });

  // GET /graph/edges
  app.get('/graph/edges', async (req) => {
    const { tf, limit } = req.query as { tf?: string; limit?: string };
    const edges = await storage.getTopEdgesByLift(
      tf || '1d',
      limit ? parseInt(limit, 10) : 50
    );
    return { edges, count: edges.length };
  });

  // GET /graph/nodes
  app.get('/graph/nodes', async (req) => {
    const { tf, family } = req.query as { tf?: string; family?: string };
    
    if (family) {
      const nodes = await storage.getNodesByFamily(family, tf || '1d');
      return { nodes, count: nodes.length };
    }
    
    const nodes = await storage.getNodesByTf(tf || '1d');
    return { nodes, count: nodes.length };
  });

  // DELETE /graph/clear
  app.delete('/graph/clear', async (req) => {
    const { tf } = req.query as { tf?: string };
    await storage.clearGraph(tf);
    return { ok: true, message: `Graph cleared${tf ? ` for ${tf}` : ''}` };
  });
}
