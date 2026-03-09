/**
 * Phase 7 — Edge Intelligence API Routes
 * 
 * REST API for edge analysis and attribution
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  EdgeIntelligenceConfig,
  DEFAULT_EDGE_CONFIG,
  EdgeIntelligenceResult
} from './edge_intel.types.js';
import { tradeToEdgeRecord, filterRecords, extractEdgeDataBatch } from './edge_intel.extractor.js';
import { 
  aggregateByDimension, 
  aggregateAllDimensions, 
  getTopPerformers, 
  getWorstPerformers,
  calcProfitFactor,
  calcWinRate,
  calcAvgR
} from './edge_intel.aggregator.js';
import { findBestCombinations, calculateEdgeMultiplier } from './edge_intel.attribution.js';
import {
  saveEdgeRecords,
  saveEdgeStats,
  saveEdgeAttributions,
  getEdgeRecords,
  getEdgeStatsByDimension,
  getTopAttributions,
  getGlobalBaseline
} from './edge_intel.storage.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerEdgeIntelligenceRoutes(fastify: FastifyInstance): Promise<void> {
  
  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/edge/patterns - Edge by patterns
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/edge/patterns', async (request: FastifyRequest, reply: FastifyReply) => {
    const { limit = '20' } = request.query as Record<string, string>;
    
    try {
      const stats = await getEdgeStatsByDimension('PATTERN');
      
      return {
        dimension: 'PATTERN',
        count: stats.length,
        stats: stats.slice(0, parseInt(limit)).map(s => ({
          pattern: s.key,
          sampleSize: s.sampleSize,
          winRate: Math.round(s.winRate * 100) / 100,
          avgR: Math.round(s.avgR * 100) / 100,
          profitFactor: Math.round(s.profitFactor * 100) / 100,
          edgeScore: Math.round(s.edgeScore * 1000) / 1000,
          confidence: Math.round(s.confidence * 100) / 100
        }))
      };
    } catch (error) {
      console.error('[EdgeIntelRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to fetch edge by patterns' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/edge/states - Edge by states
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/edge/states', async (request: FastifyRequest, reply: FastifyReply) => {
    const { limit = '20' } = request.query as Record<string, string>;
    
    try {
      const stats = await getEdgeStatsByDimension('STATE');
      
      return {
        dimension: 'STATE',
        count: stats.length,
        stats: stats.slice(0, parseInt(limit)).map(s => ({
          state: s.key,
          sampleSize: s.sampleSize,
          winRate: Math.round(s.winRate * 100) / 100,
          avgR: Math.round(s.avgR * 100) / 100,
          profitFactor: Math.round(s.profitFactor * 100) / 100,
          edgeScore: Math.round(s.edgeScore * 1000) / 1000
        }))
      };
    } catch (error) {
      console.error('[EdgeIntelRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to fetch edge by states' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/edge/scenarios - Edge by scenarios
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/edge/scenarios', async (request: FastifyRequest, reply: FastifyReply) => {
    const { limit = '20' } = request.query as Record<string, string>;
    
    try {
      const stats = await getEdgeStatsByDimension('SCENARIO');
      
      return {
        dimension: 'SCENARIO',
        count: stats.length,
        stats: stats.slice(0, parseInt(limit)).map(s => ({
          scenario: s.key,
          sampleSize: s.sampleSize,
          winRate: Math.round(s.winRate * 100) / 100,
          avgR: Math.round(s.avgR * 100) / 100,
          profitFactor: Math.round(s.profitFactor * 100) / 100,
          edgeScore: Math.round(s.edgeScore * 1000) / 1000
        }))
      };
    } catch (error) {
      console.error('[EdgeIntelRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to fetch edge by scenarios' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/edge/attribution - Edge attribution analysis
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/edge/attribution', async (request: FastifyRequest, reply: FastifyReply) => {
    const { limit = '20' } = request.query as Record<string, string>;
    
    try {
      const attributions = await getTopAttributions(parseInt(limit));
      
      return {
        count: attributions.length,
        attributions: attributions.map(a => ({
          attributionId: a.attributionId,
          dimensions: a.dimensions,
          combinedPF: Math.round(a.combinedPF * 100) / 100,
          synergy: Math.round(a.synergy * 100) / 100,
          sampleSize: a.sampleSize,
          confidence: Math.round(a.confidence * 100) / 100,
          individualEdges: a.individualEdges.map(e => ({
            dimension: e.dimension,
            value: e.value,
            pfAlone: Math.round(e.pfAlone * 100) / 100,
            contributionPct: Math.round(e.contributionPct)
          }))
        }))
      };
    } catch (error) {
      console.error('[EdgeIntelRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to fetch edge attribution' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/edge/baseline - Global baseline stats
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/edge/baseline', async (request: FastifyRequest, reply: FastifyReply) => {
    const { days = '180' } = request.query as Record<string, string>;
    
    try {
      const baseline = await getGlobalBaseline(parseInt(days));
      
      return {
        winRate: Math.round(baseline.winRate * 100) / 100,
        avgR: Math.round(baseline.avgR * 100) / 100,
        profitFactor: Math.round(baseline.profitFactor * 100) / 100,
        totalTrades: baseline.totalTrades,
        dataWindowDays: parseInt(days)
      };
    } catch (error) {
      console.error('[EdgeIntelRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to fetch baseline' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/edge/record - Record a trade for edge analysis
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/edge/record', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    
    if (!body.asset || body.pnlR === undefined) {
      return reply.status(400).send({ error: 'asset and pnlR are required' });
    }
    
    try {
      const record = tradeToEdgeRecord({
        asset: body.asset,
        timeframe: body.timeframe || '1d',
        entryTime: body.entryTime ? new Date(body.entryTime) : new Date(),
        exitTime: body.exitTime ? new Date(body.exitTime) : undefined,
        pattern: body.pattern,
        patternFamily: body.patternFamily,
        decisionPack: body.decisionPack,
        marketState: body.marketState,
        physicsState: body.physicsState,
        liquidityContext: body.liquidityContext,
        fractalMatch: body.fractalMatch,
        scenarioId: body.scenarioId,
        energyScore: body.energyScore,
        pnlR: body.pnlR
      });
      
      await saveEdgeRecords([record]);
      
      return { success: true, tradeId: record.tradeId };
    } catch (error) {
      console.error('[EdgeIntelRoutes] Error recording trade:', error);
      return reply.status(500).send({ error: 'Failed to record trade' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/edge/analyze - Run full edge analysis
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/edge/analyze', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    const { asset, timeframe, days = 180 } = body;
    
    try {
      const dateFrom = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
      
      // Get records
      const records = await getEdgeRecords({
        asset,
        timeframe,
        dateFrom
      });
      
      if (records.length < DEFAULT_EDGE_CONFIG.minSampleSize) {
        return {
          error: 'Insufficient data',
          recordCount: records.length,
          minRequired: DEFAULT_EDGE_CONFIG.minSampleSize
        };
      }
      
      // Get global baseline
      const baseline = await getGlobalBaseline(days);
      
      // Aggregate all dimensions
      const allStats = aggregateAllDimensions(
        records.map(r => ({
          tradeId: r.tradeId,
          asset: r.asset,
          timeframe: r.timeframe,
          entryTime: r.entryTime,
          exitTime: r.exitTime,
          pattern: r.pattern,
          patternFamily: r.patternFamily,
          fractal: r.fractal,
          scenario: r.scenario,
          state: r.state,
          liquidity: r.liquidity,
          marketState: r.marketState,
          physicsState: r.physicsState,
          resultR: r.resultR,
          outcome: r.outcome as 'WIN' | 'LOSS' | 'BREAKEVEN',
          entryScore: r.entryScore,
          entryConfidence: r.entryConfidence,
          energyScore: r.energyScore,
          graphBoost: r.graphBoost,
          stateBoost: r.stateBoost
        })),
        baseline,
        DEFAULT_EDGE_CONFIG
      );
      
      // Get top/worst performers
      const topEdges = getTopPerformers(allStats, 10);
      const worstEdges = getWorstPerformers(allStats, 10);
      
      // Find attributions
      const attributions = findBestCombinations(
        records.map(r => ({
          tradeId: r.tradeId,
          asset: r.asset,
          timeframe: r.timeframe,
          entryTime: r.entryTime,
          exitTime: r.exitTime,
          pattern: r.pattern,
          patternFamily: r.patternFamily,
          fractal: r.fractal,
          scenario: r.scenario,
          state: r.state,
          liquidity: r.liquidity,
          marketState: r.marketState,
          physicsState: r.physicsState,
          resultR: r.resultR,
          outcome: r.outcome as 'WIN' | 'LOSS' | 'BREAKEVEN',
          entryScore: r.entryScore,
          entryConfidence: r.entryConfidence,
          energyScore: r.energyScore,
          graphBoost: r.graphBoost,
          stateBoost: r.stateBoost
        })),
        DEFAULT_EDGE_CONFIG
      );
      
      // Save stats
      for (const stats of allStats.values()) {
        await saveEdgeStats(stats);
      }
      await saveEdgeAttributions(attributions);
      
      // Build result
      const result: EdgeIntelligenceResult = {
        asset,
        timeframe,
        globalBaseline: baseline,
        byPattern: allStats.get('PATTERN') || [],
        byState: allStats.get('STATE') || [],
        byFractal: allStats.get('FRACTAL') || [],
        byScenario: allStats.get('SCENARIO') || [],
        byLiquidity: allStats.get('LIQUIDITY') || [],
        topEdges,
        worstEdges,
        topAttributions: attributions.slice(0, 10),
        recommendations: generateRecommendations(topEdges, worstEdges),
        calculatedAt: new Date(),
        dataWindow: {
          from: dateFrom,
          to: new Date()
        }
      };
      
      return result;
    } catch (error) {
      console.error('[EdgeIntelRoutes] Analysis error:', error);
      return reply.status(500).send({ error: 'Edge analysis failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/edge/multiplier - Get edge multiplier for decision
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/edge/multiplier', async (request: FastifyRequest, reply: FastifyReply) => {
    const { pattern, state, scenario, liquidity } = request.query as Record<string, string>;
    
    if (!pattern || !state) {
      return reply.status(400).send({ error: 'pattern and state are required' });
    }
    
    try {
      const attributions = await getTopAttributions(50);
      
      const multiplier = calculateEdgeMultiplier(
        pattern,
        state,
        scenario,
        liquidity,
        attributions.map(a => ({
          attributionId: a.attributionId,
          dimensions: a.dimensions.map(d => ({
            dimension: d.dimension as any,
            value: d.value
          })),
          individualEdges: a.individualEdges.map(e => ({
            dimension: e.dimension as any,
            value: e.value,
            pfAlone: e.pfAlone,
            contributionPct: e.contributionPct
          })),
          combinedPF: a.combinedPF,
          synergy: a.synergy,
          sampleSize: a.sampleSize,
          confidence: a.confidence,
          calculatedAt: a.calculatedAt
        }))
      );
      
      return {
        pattern,
        state,
        scenario: scenario || null,
        liquidity: liquidity || null,
        multiplier: Math.round(multiplier.multiplier * 1000) / 1000,
        confidence: Math.round(multiplier.confidence * 100) / 100,
        basedOn: multiplier.basedOn
      };
    } catch (error) {
      console.error('[EdgeIntelRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to calculate multiplier' });
    }
  });
}

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function generateRecommendations(
  topEdges: any[],
  worstEdges: any[]
): Array<{ tradeDimension: string; tradeValue: string; reason: string; edgeBoost: number }> {
  const recommendations: Array<{ tradeDimension: string; tradeValue: string; reason: string; edgeBoost: number }> = [];
  
  // Recommendations from top edges
  for (const edge of topEdges.slice(0, 3)) {
    if (edge.edgeScore > 0.2 && edge.confidence > 0.5) {
      recommendations.push({
        tradeDimension: edge.dimension,
        tradeValue: edge.key,
        reason: `High edge: PF ${edge.profitFactor.toFixed(2)}, WR ${(edge.winRate * 100).toFixed(0)}%`,
        edgeBoost: 1 + edge.edgeScore * 0.3
      });
    }
  }
  
  // Warnings from worst edges
  for (const edge of worstEdges.slice(0, 2)) {
    if (edge.edgeScore < -0.2 && edge.confidence > 0.5) {
      recommendations.push({
        tradeDimension: edge.dimension,
        tradeValue: edge.key,
        reason: `Avoid: PF ${edge.profitFactor.toFixed(2)}, negative edge`,
        edgeBoost: 1 + edge.edgeScore * 0.3  // Will be < 1
      });
    }
  }
  
  return recommendations;
}

export default registerEdgeIntelligenceRoutes;
