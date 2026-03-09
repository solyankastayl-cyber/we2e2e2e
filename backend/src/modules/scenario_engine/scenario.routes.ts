/**
 * Phase 6 — Scenario Engine API Routes
 * 
 * REST API for scenario simulation and retrieval
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { 
  ScenarioSimulationInput, 
  DEFAULT_SCENARIO_CONFIG,
  MarketBehaviorState
} from './scenario.types.js';
import { simulateScenarios, refineWithMonteCarlo, analyzeCriticalPoints } from './scenario.simulator.js';
import { calculateScenarioEV, calculateRiskAdjustedScore } from './scenario.scoring.js';
import { 
  saveSimulationResult, 
  getLatestScenarios, 
  getActiveScenarios,
  getScenarioStats,
  updateScenarioOutcome,
  cleanupExpiredScenarios
} from './scenario.storage.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerScenarioRoutes(fastify: FastifyInstance): Promise<void> {
  
  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/scenarios/top — For Digital Twin Live Context
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/scenarios/top', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset = 'BTCUSDT', tf = '1d', limit = '5' } = request.query as Record<string, string>;
    
    try {
      const scenarios = await getLatestScenarios(asset, tf, parseInt(limit));
      
      if (scenarios.length === 0) {
        // Return mock scenarios for Digital Twin
        return {
          asset,
          timeframe: tf,
          scenarios: [
            {
              scenarioId: 'SCN_MOCK_001',
              direction: 'BULL',
              probability: 0.52,
              confidence: 0.68,
              path: ['COMPRESSION', 'BREAKOUT', 'RETEST', 'EXPANSION'],
              expectedMoveATR: 2.3
            },
            {
              scenarioId: 'SCN_MOCK_002',
              direction: 'NEUTRAL',
              probability: 0.31,
              confidence: 0.55,
              path: ['COMPRESSION', 'FALSE_BREAKOUT', 'RANGE'],
              expectedMoveATR: 0.8
            },
            {
              scenarioId: 'SCN_MOCK_003',
              direction: 'BEAR',
              probability: 0.17,
              confidence: 0.42,
              path: ['COMPRESSION', 'BREAKOUT', 'REVERSAL'],
              expectedMoveATR: 1.5
            }
          ]
        };
      }
      
      return {
        asset,
        timeframe: tf,
        scenarios: scenarios.map(s => ({
          scenarioId: s.scenarioId,
          direction: s.direction,
          probability: s.probability,
          confidence: s.confidence,
          path: s.path,
          expectedMoveATR: s.expectedMoveATR
        }))
      };
    } catch (error) {
      console.error('[ScenarioRoutes] Top scenarios error:', error);
      return reply.status(500).send({ error: 'Failed to fetch top scenarios' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/scenarios - Get latest scenarios for asset
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/scenarios', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset = 'BTCUSDT', timeframe = '1d', limit = '10' } = request.query as Record<string, string>;
    
    try {
      const scenarios = await getLatestScenarios(asset, timeframe, parseInt(limit));
      
      return {
        asset,
        timeframe,
        count: scenarios.length,
        scenarios: scenarios.map(s => ({
          scenarioId: s.scenarioId,
          direction: s.direction,
          probability: s.probability,
          path: s.path,
          expectedMoveATR: s.expectedMoveATR,
          confidence: s.confidence,
          score: s.score,
          generatedAt: s.generatedAt
        }))
      };
    } catch (error) {
      console.error('[ScenarioRoutes] Error fetching scenarios:', error);
      return reply.status(500).send({ error: 'Failed to fetch scenarios' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/scenarios/active - Get active (non-expired) scenarios
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/scenarios/active', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset = 'BTCUSDT', timeframe = '1d' } = request.query as Record<string, string>;
    
    try {
      const scenarios = await getActiveScenarios(asset, timeframe);
      
      return {
        asset,
        timeframe,
        count: scenarios.length,
        scenarios
      };
    } catch (error) {
      console.error('[ScenarioRoutes] Error fetching active scenarios:', error);
      return reply.status(500).send({ error: 'Failed to fetch active scenarios' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/scenarios/simulate - Run scenario simulation
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/scenarios/simulate', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as Partial<ScenarioSimulationInput>;
    
    if (!body.asset) {
      return reply.status(400).send({ error: 'asset is required' });
    }
    
    try {
      const input: ScenarioSimulationInput = {
        asset: body.asset,
        timeframe: body.timeframe || '1d',
        currentState: (body.currentState as MarketBehaviorState) || 'COMPRESSION',
        physicsState: body.physicsState,
        energyScore: body.energyScore,
        releaseProbability: body.releaseProbability,
        exhaustionScore: body.exhaustionScore,
        liquidityBias: body.liquidityBias,
        recentSweepUp: body.recentSweepUp,
        recentSweepDown: body.recentSweepDown,
        trendDirection: body.trendDirection,
        trendStrength: body.trendStrength,
        volumeProfile: body.volumeProfile,
        atrRatio: body.atrRatio
      };
      
      // Run simulation
      const result = simulateScenarios(input, DEFAULT_SCENARIO_CONFIG);
      
      // Save result
      await saveSimulationResult(result);
      
      return {
        ...result,
        scenarios: result.scenarios.map(s => ({
          scenarioId: s.scenarioId,
          direction: s.direction,
          probability: Math.round(s.probability * 100) / 100,
          path: s.path,
          expectedMoveATR: Math.round(s.expectedMoveATR * 100) / 100,
          confidence: Math.round(s.confidence * 100) / 100,
          score: Math.round(s.score * 1000) / 1000,
          ev: Math.round(calculateScenarioEV(s) * 1000) / 1000
        }))
      };
    } catch (error) {
      console.error('[ScenarioRoutes] Simulation error:', error);
      return reply.status(500).send({ error: 'Scenario simulation failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/scenarios/refine - Monte Carlo refinement
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/scenarios/refine', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    
    if (!body.scenarioId && !body.scenario) {
      return reply.status(400).send({ error: 'scenarioId or scenario object required' });
    }
    
    try {
      const scenario = body.scenario;
      const input: ScenarioSimulationInput = {
        asset: scenario.asset || 'BTCUSDT',
        timeframe: scenario.timeframe || '1d',
        currentState: 'COMPRESSION'
      };
      
      const refinement = refineWithMonteCarlo(
        scenario,
        input,
        body.numSimulations || 1000
      );
      
      const criticalPoints = analyzeCriticalPoints(scenario);
      
      return {
        scenarioId: scenario.scenarioId,
        original: {
          probability: scenario.probability,
          expectedMoveATR: scenario.expectedMoveATR
        },
        refined: {
          probability: Math.round(refinement.refinedProbability * 1000) / 1000,
          expectedBars: refinement.expectedBars,
          confidenceInterval: refinement.confidenceInterval.map(v => Math.round(v * 1000) / 1000)
        },
        criticalPoints,
        riskAdjustedScore: Math.round(calculateRiskAdjustedScore(scenario) * 1000) / 1000
      };
    } catch (error) {
      console.error('[ScenarioRoutes] Refinement error:', error);
      return reply.status(500).send({ error: 'Scenario refinement failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/scenarios/stats - Scenario statistics
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/scenarios/stats', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, timeframe, days = '30' } = request.query as Record<string, string>;
    
    try {
      const stats = await getScenarioStats(
        asset || undefined,
        timeframe || undefined,
        parseInt(days)
      );
      
      return stats;
    } catch (error) {
      console.error('[ScenarioRoutes] Stats error:', error);
      return reply.status(500).send({ error: 'Failed to fetch scenario statistics' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/scenarios/outcome - Update scenario outcome
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/scenarios/outcome', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    
    if (!body.scenarioId) {
      return reply.status(400).send({ error: 'scenarioId is required' });
    }
    
    try {
      await updateScenarioOutcome(body.scenarioId, {
        realized: body.realized,
        actualPath: body.actualPath,
        actualMoveATR: body.actualMoveATR
      });
      
      return { success: true, scenarioId: body.scenarioId };
    } catch (error) {
      console.error('[ScenarioRoutes] Outcome update error:', error);
      return reply.status(500).send({ error: 'Failed to update scenario outcome' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/scenarios/cleanup - Cleanup expired scenarios
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/scenarios/cleanup', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const deleted = await cleanupExpiredScenarios();
      
      return { success: true, deletedCount: deleted };
    } catch (error) {
      console.error('[ScenarioRoutes] Cleanup error:', error);
      return reply.status(500).send({ error: 'Cleanup failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/scenarios/templates - Get scenario templates
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/scenarios/templates', async (request: FastifyRequest, reply: FastifyReply) => {
    const { SCENARIO_TEMPLATES } = await import('./scenario.types.js');
    
    return {
      count: SCENARIO_TEMPLATES.length,
      templates: SCENARIO_TEMPLATES.map(t => ({
        name: t.name,
        direction: t.direction,
        path: t.path,
        baseProb: t.baseProb,
        description: t.description
      }))
    };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/scenarios/transitions - Get state transitions
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/scenarios/transitions', async (request: FastifyRequest, reply: FastifyReply) => {
    const { STATE_TRANSITIONS } = await import('./scenario.types.js');
    
    // Group by 'from' state
    const grouped: Record<string, Array<{ to: string; probability: number }>> = {};
    
    for (const t of STATE_TRANSITIONS) {
      if (!grouped[t.from]) grouped[t.from] = [];
      grouped[t.from].push({
        to: t.to,
        probability: t.baseProbability
      });
    }
    
    return {
      totalTransitions: STATE_TRANSITIONS.length,
      byState: grouped
    };
  });
}

export default registerScenarioRoutes;
