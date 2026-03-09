/**
 * Phase 8 — Strategy Builder API Routes
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  StrategyCandidate,
  Strategy,
  DEFAULT_GENERATOR_CONFIG
} from './strategy.types.js';
import { generateStrategyCandidates, EdgeDimensionData } from './strategy.generator.js';
import { evaluateCandidate, TradeSignal, Candle, DEFAULT_SIM_CONFIG } from './strategy.simulator.js';
import {
  saveStrategies,
  getActiveStrategies,
  getTopStrategies,
  getStrategiesByPattern,
  getStrategiesByRegime,
  findMatchingStrategies,
  updateStrategyStatus,
  getStrategyStats
} from './strategy.storage.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerStrategyRoutes(fastify: FastifyInstance): Promise<void> {

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/strategies - Get all strategies
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/strategies', async (request: FastifyRequest, reply: FastifyReply) => {
    const { limit = '20', regime, pattern, minScore } = request.query as Record<string, string>;
    
    try {
      const strategies = await getTopStrategies(parseInt(limit), {
        regime: regime || undefined,
        minScore: minScore ? parseFloat(minScore) : undefined
      });
      
      return {
        count: strategies.length,
        strategies: strategies.map(s => ({
          strategyId: s.strategyId,
          pattern: s.pattern,
          state: s.state,
          liquidity: s.liquidity,
          regime: s.regime,
          entryRule: s.entryRule,
          exitRule: s.exitRule,
          riskReward: Math.round(s.riskReward * 100) / 100,
          performance: {
            trades: s.performance.trades,
            winRate: Math.round(s.performance.winRate * 100) / 100,
            profitFactor: Math.round(s.performance.profitFactor * 100) / 100,
            sharpe: Math.round(s.performance.sharpe * 100) / 100,
            maxDD: Math.round(s.performance.maxDD * 100) / 100
          },
          strategyScore: Math.round(s.strategyScore * 1000) / 1000,
          status: s.status
        }))
      };
    } catch (error) {
      console.error('[StrategyRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to fetch strategies' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/strategies/active - Get active strategies only
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/strategies/active', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const strategies = await getActiveStrategies();
      
      return {
        count: strategies.length,
        strategies
      };
    } catch (error) {
      console.error('[StrategyRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to fetch active strategies' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/strategies/top - Get top ranked strategies
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/strategies/top', async (request: FastifyRequest, reply: FastifyReply) => {
    const { limit = '10', regime } = request.query as Record<string, string>;
    
    try {
      const strategies = regime 
        ? await getStrategiesByRegime(regime)
        : await getTopStrategies(parseInt(limit));
      
      return {
        count: strategies.length,
        strategies: strategies.slice(0, parseInt(limit)).map(s => ({
          strategyId: s.strategyId,
          pattern: s.pattern,
          state: s.state,
          liquidity: s.liquidity,
          regime: s.regime,
          profitFactor: Math.round(s.performance.profitFactor * 100) / 100,
          winRate: Math.round(s.performance.winRate * 100) / 100,
          trades: s.performance.trades,
          strategyScore: Math.round(s.strategyScore * 1000) / 1000
        }))
      };
    } catch (error) {
      console.error('[StrategyRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to fetch top strategies' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/strategies/match - Find matching strategies
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/strategies/match', async (request: FastifyRequest, reply: FastifyReply) => {
    const { pattern, state, liquidity, regime } = request.query as Record<string, string>;
    
    if (!pattern) {
      return reply.status(400).send({ error: 'pattern is required' });
    }
    
    try {
      const matches = await findMatchingStrategies(
        pattern,
        state || 'COMPRESSION',
        liquidity || 'NEUTRAL',
        regime
      );
      
      return {
        pattern,
        state: state || 'COMPRESSION',
        liquidity: liquidity || 'NEUTRAL',
        regime: regime || null,
        matchCount: matches.length,
        matches: matches.map(m => ({
          strategyId: m.strategy.strategyId,
          matchScore: Math.round(m.matchScore * 100) / 100,
          dimensions: m.dimensions,
          profitFactor: Math.round(m.strategy.performance.profitFactor * 100) / 100,
          winRate: Math.round(m.strategy.performance.winRate * 100) / 100,
          entryRule: m.strategy.entryRule,
          exitRule: m.strategy.exitRule,
          stopATR: m.strategy.stopATR,
          targetATR: m.strategy.targetATR
        }))
      };
    } catch (error) {
      console.error('[StrategyRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to find matching strategies' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/strategies/generate - Generate new strategies
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/strategies/generate', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    
    // Expect edge data from Edge Intelligence
    const topPatterns: EdgeDimensionData[] = body.topPatterns || [];
    const topStates: EdgeDimensionData[] = body.topStates || [];
    const topLiquidity: EdgeDimensionData[] = body.topLiquidity || [];
    
    if (topPatterns.length === 0) {
      // Use mock data for testing
      const mockPatterns: EdgeDimensionData[] = [
        { key: 'TRIANGLE_ASC', edgeScore: 0.35, profitFactor: 1.42, sampleSize: 150 },
        { key: 'DOUBLE_BOTTOM', edgeScore: 0.28, profitFactor: 1.35, sampleSize: 120 },
        { key: 'FLAG_BULL', edgeScore: 0.25, profitFactor: 1.30, sampleSize: 100 },
        { key: 'HNS', edgeScore: 0.22, profitFactor: 1.28, sampleSize: 90 },
        { key: 'LIQUIDITY_SWEEP_LOW', edgeScore: 0.20, profitFactor: 1.25, sampleSize: 85 }
      ];
      const mockStates: EdgeDimensionData[] = [
        { key: 'COMPRESSION', edgeScore: 0.30, profitFactor: 1.38, sampleSize: 200 },
        { key: 'BREAKOUT', edgeScore: 0.25, profitFactor: 1.32, sampleSize: 180 },
        { key: 'RETEST', edgeScore: 0.20, profitFactor: 1.25, sampleSize: 120 }
      ];
      const mockLiquidity: EdgeDimensionData[] = [
        { key: 'SWEEP_DOWN', edgeScore: 0.28, profitFactor: 1.35, sampleSize: 100 },
        { key: 'NEUTRAL', edgeScore: 0.15, profitFactor: 1.18, sampleSize: 300 }
      ];
      
      const candidates = generateStrategyCandidates(mockPatterns, mockStates, mockLiquidity, DEFAULT_GENERATOR_CONFIG);
      
      return {
        generated: candidates.length,
        source: 'mock_edge_data',
        candidates: candidates.slice(0, 20).map(c => ({
          strategyId: c.strategyId,
          pattern: c.pattern,
          state: c.state,
          liquidity: c.liquidity,
          entryRule: c.entryRule,
          exitRule: c.exitRule,
          stopATR: c.stopATR,
          targetATR: c.targetATR,
          riskReward: Math.round(c.riskReward * 100) / 100
        }))
      };
    }
    
    try {
      const candidates = generateStrategyCandidates(topPatterns, topStates, topLiquidity, DEFAULT_GENERATOR_CONFIG);
      
      return {
        generated: candidates.length,
        source: 'edge_intelligence',
        candidates: candidates.slice(0, 20).map(c => ({
          strategyId: c.strategyId,
          pattern: c.pattern,
          state: c.state,
          liquidity: c.liquidity,
          entryRule: c.entryRule,
          exitRule: c.exitRule,
          stopATR: c.stopATR,
          targetATR: c.targetATR,
          riskReward: Math.round(c.riskReward * 100) / 100
        }))
      };
    } catch (error) {
      console.error('[StrategyRoutes] Generation error:', error);
      return reply.status(500).send({ error: 'Strategy generation failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/strategies/evaluate - Evaluate candidate
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/strategies/evaluate', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    
    const candidate: StrategyCandidate = body.candidate;
    const signals: TradeSignal[] = body.signals || [];
    const candles: Candle[] = body.candles || [];
    
    if (!candidate) {
      return reply.status(400).send({ error: 'candidate is required' });
    }
    
    if (signals.length === 0 || candles.length === 0) {
      // Return mock evaluation
      return {
        strategyId: candidate.strategyId,
        evaluated: false,
        reason: 'No signals or candles provided for backtest',
        mockPerformance: {
          trades: 0,
          winRate: 0,
          profitFactor: 1,
          strategyScore: 0
        }
      };
    }
    
    try {
      const strategy = evaluateCandidate(candidate, signals, candles, DEFAULT_SIM_CONFIG);
      
      if (!strategy) {
        return {
          strategyId: candidate.strategyId,
          evaluated: true,
          passed: false,
          reason: 'Did not meet minimum requirements (trades >= 30, PF >= 1.1, WR >= 40%)'
        };
      }
      
      // Save if passed
      await saveStrategies([strategy]);
      
      return {
        strategyId: strategy.strategyId,
        evaluated: true,
        passed: true,
        strategy: {
          pattern: strategy.pattern,
          state: strategy.state,
          liquidity: strategy.liquidity,
          performance: strategy.performance,
          strategyScore: Math.round(strategy.strategyScore * 1000) / 1000,
          status: strategy.status
        }
      };
    } catch (error) {
      console.error('[StrategyRoutes] Evaluation error:', error);
      return reply.status(500).send({ error: 'Strategy evaluation failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // PATCH /api/ta/strategies/:id/status - Update strategy status
  // ─────────────────────────────────────────────────────────────
  fastify.patch('/api/ta/strategies/:id/status', async (request: FastifyRequest, reply: FastifyReply) => {
    const { id } = request.params as { id: string };
    const { status } = request.body as { status: string };
    
    if (!['CANDIDATE', 'ACTIVE', 'PAUSED', 'RETIRED'].includes(status)) {
      return reply.status(400).send({ error: 'Invalid status' });
    }
    
    try {
      await updateStrategyStatus(id, status as any);
      return { success: true, strategyId: id, newStatus: status };
    } catch (error) {
      console.error('[StrategyRoutes] Status update error:', error);
      return reply.status(500).send({ error: 'Failed to update strategy status' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/strategies/stats - Strategy statistics
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/strategies/stats', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const stats = await getStrategyStats();
      
      return {
        total: stats.total,
        byStatus: stats.byStatus,
        byPattern: stats.byPattern,
        avgScore: Math.round(stats.avgScore * 1000) / 1000,
        avgProfitFactor: Math.round(stats.avgPF * 100) / 100
      };
    } catch (error) {
      console.error('[StrategyRoutes] Stats error:', error);
      return reply.status(500).send({ error: 'Failed to fetch strategy stats' });
    }
  });
}

export default registerStrategyRoutes;
