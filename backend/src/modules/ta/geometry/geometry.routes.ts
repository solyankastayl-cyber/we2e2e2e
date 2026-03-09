/**
 * P1.2 — Geometry API Routes (COMMIT 7)
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';
import { 
  computeGeometryForScenario, 
  computeGeometryBoost,
  extractGeometryFeatures 
} from './geometry.engine.js';
import { GeometryInput, getGeometryFamily } from './geometry.types.js';

export async function registerGeometryRoutes(
  app: FastifyInstance,
  opts: { db: Db }
): Promise<void> {
  
  // GET /geometry/status
  app.get('/geometry/status', async () => {
    return {
      ok: true,
      version: '1.2.0',
      families: ['TRIANGLE', 'CHANNEL', 'FLAG', 'REVERSAL_CLASSIC', 'HARMONIC'],
      featuresCount: 25,
    };
  });

  // POST /geometry/compute
  app.post('/geometry/compute', async (req, reply) => {
    const input = req.body as GeometryInput;
    
    if (!input.patternType || !input.timeframe) {
      return reply.code(400).send({ error: 'patternType and timeframe required' });
    }

    // Set defaults
    const fullInput: GeometryInput = {
      ...input,
      pivotHighs: input.pivotHighs || [],
      pivotLows: input.pivotLows || [],
      pivotHighIdxs: input.pivotHighIdxs || [],
      pivotLowIdxs: input.pivotLowIdxs || [],
      atr: input.atr || 1,
      price: input.price || 0,
      startIdx: input.startIdx || 0,
      endIdx: input.endIdx || 100,
    };

    const pack = computeGeometryForScenario(fullInput);
    const boost = computeGeometryBoost(pack);
    const features = extractGeometryFeatures(pack);

    return {
      geometry: pack,
      boost,
      features,
    };
  });

  // POST /geometry/test
  app.post('/geometry/test', async (req, reply) => {
    const { scenarioId, runId } = req.body as { scenarioId?: string; runId?: string };

    if (!scenarioId) {
      return reply.code(400).send({ error: 'scenarioId required' });
    }

    // Try to fetch scenario from DB
    const scenario = await opts.db.collection('ta_scenarios').findOne({
      $or: [{ scenarioId }, { _id: scenarioId }]
    });

    if (!scenario) {
      return reply.code(404).send({ error: 'Scenario not found' });
    }

    // Build geometry input from scenario
    const input: GeometryInput = {
      patternType: scenario.patternType || scenario.type || 'UNKNOWN',
      timeframe: scenario.timeframe || '1d',
      direction: scenario.direction || 'BOTH',
      pivotHighs: scenario.pivotHighs || [],
      pivotLows: scenario.pivotLows || [],
      pivotHighIdxs: scenario.pivotHighIdxs || [],
      pivotLowIdxs: scenario.pivotLowIdxs || [],
      atr: scenario.atr || 1,
      price: scenario.price || scenario.entry || 0,
      startIdx: scenario.startIdx || 0,
      endIdx: scenario.endIdx || 100,
      lineHigh: scenario.lineHigh,
      lineLow: scenario.lineLow,
      poleStart: scenario.poleStart,
      poleEnd: scenario.poleEnd,
      pointX: scenario.pointX,
      pointA: scenario.pointA,
      pointB: scenario.pointB,
      pointC: scenario.pointC,
      pointD: scenario.pointD,
    };

    const pack = computeGeometryForScenario(input);
    const boost = computeGeometryBoost(pack);
    const features = extractGeometryFeatures(pack);

    return {
      scenarioId,
      geometry: pack,
      boost,
      features,
    };
  });

  // GET /geometry/family/:type
  app.get('/geometry/family/:type', async (req, reply) => {
    const { type } = req.params as { type: string };
    const family = getGeometryFamily(type);
    
    return {
      patternType: type,
      family,
      description: getFamilyDescription(family),
    };
  });
}

function getFamilyDescription(family: string): string {
  switch (family) {
    case 'TRIANGLE': return 'Converging trendlines (ascending, descending, symmetric triangles, wedges)';
    case 'CHANNEL': return 'Parallel support/resistance (ascending, descending, horizontal channels)';
    case 'FLAG': return 'Pole + consolidation (bull/bear flags, pennants)';
    case 'REVERSAL_CLASSIC': return 'Classic reversal patterns (H&S, double/triple top/bottom)';
    case 'HARMONIC': return 'Fibonacci-based patterns (Gartley, Bat, Butterfly, ABCD)';
    default: return 'Unknown pattern family';
  }
}
