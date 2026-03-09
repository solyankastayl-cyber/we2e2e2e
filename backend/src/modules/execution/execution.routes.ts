/**
 * Phase 10 — Execution Intelligence API Routes
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  DEFAULT_RISK_LIMITS,
  DEFAULT_EXECUTION_CONFIG,
  Portfolio
} from './execution.types.js';
import { calculatePositionSize, calculateKellyPositionSize } from './execution.position.js';
import { calculateRiskStatus, shouldPauseTrading } from './execution.risk.js';
import { createPortfolio, addPosition, updatePositionPrices, closePosition, calculateAllocations, calculatePortfolioStats } from './execution.portfolio.js';
import { createExecutionPlan, validateExecutionPlan, SignalInput } from './execution.plan.js';
import {
  saveExecutionPlan,
  getExecutionPlans,
  getPendingPlans,
  updatePlanStatus,
  savePortfolio,
  getPortfolio,
  getDefaultPortfolio,
  getExecutionStats
} from './execution.storage.js';
import { getRiskMultiplier } from '../metabrain/metabrain.controller.js';

// In-memory portfolio for demo
let demoPortfolio: Portfolio | null = null;

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerExecutionRoutes(fastify: FastifyInstance): Promise<void> {

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/execution/status — For Digital Twin Live Context
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/execution/status', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      // Get portfolio stats
      let portfolio = demoPortfolio;
      if (!portfolio) {
        const stored = await getPortfolio('default');
        portfolio = stored || createPortfolio(100000);
      }
      
      const stats = calculatePortfolioStats(portfolio);
      
      return {
        portfolioExposure: stats.totalExposure,
        openPositions: portfolio.positions.length,
        portfolioStress: stats.drawdown > 0 ? Math.min(1, stats.drawdown / 0.2) : 0  // Normalize to 0-1
      };
    } catch (error) {
      console.error('[ExecutionRoutes] Status error:', error);
      return {
        portfolioExposure: 0,
        openPositions: 0,
        portfolioStress: 0
      };
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/execution/plan - Create execution plan
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/execution/plan', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as Partial<SignalInput> & { accountSize?: number; useMetaBrain?: boolean };
    
    if (!body.asset || !body.direction || body.entryPrice === undefined) {
      return reply.status(400).send({ 
        error: 'Required: asset, direction, entryPrice, atr, stopATR, target1ATR' 
      });
    }
    
    try {
      // Get or create portfolio
      const accountSize = body.accountSize || 100000;
      if (!demoPortfolio) {
        demoPortfolio = createPortfolio(accountSize);
      }
      
      // Get MetaBrain risk multiplier if enabled (default: true)
      const useMetaBrain = body.useMetaBrain !== false;
      const metaRiskMultiplier = useMetaBrain ? await getRiskMultiplier() : undefined;
      
      const signal: SignalInput = {
        asset: body.asset,
        timeframe: body.timeframe || '1d',
        currentPrice: body.currentPrice || body.entryPrice,
        atr: body.atr || body.entryPrice * 0.02,  // Default 2% ATR
        direction: body.direction as 'LONG' | 'SHORT',
        strategyId: body.strategyId || 'MANUAL',
        entryRule: body.entryRule || 'MARKET',
        entryPrice: body.entryPrice,
        stopATR: body.stopATR || 1.5,
        target1ATR: body.target1ATR || 3,
        target2ATR: body.target2ATR,
        confidence: body.confidence || 0.6,
        edgeScore: body.edgeScore || 0.5,
        regimeBoost: body.regimeBoost || 1.0,
        scenarioProbability: body.scenarioProbability || 0.5,
        metaRiskMultiplier,
        memoryRiskAdjustment: body.memoryRiskAdjustment,  // P0: Memory integration
        useTrailingStop: body.useTrailingStop
      };
      
      const result = createExecutionPlan(signal, demoPortfolio);
      
      if ('error' in result) {
        return reply.status(400).send(result);
      }
      
      // Validate
      const validation = validateExecutionPlan(result);
      if (!validation.valid) {
        return {
          plan: result,
          warnings: validation.issues
        };
      }
      
      // Save
      await saveExecutionPlan(result);
      
      return {
        plan: {
          planId: result.planId,
          asset: result.asset,
          direction: result.direction,
          strategyId: result.strategyId,
          entryPrice: result.entryPrice,
          stopPrice: Math.round(result.stopPrice * 100) / 100,
          target1Price: Math.round(result.target1Price * 100) / 100,
          positionSizePct: result.positionSizePct,
          riskPct: result.riskPct,
          riskAbsolute: Math.round(result.riskAbsolute * 100) / 100,
          signalQuality: result.signalQuality,
          status: result.status
        }
      };
    } catch (error) {
      console.error('[ExecutionRoutes] Plan error:', error);
      return reply.status(500).send({ error: 'Failed to create execution plan' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/execution/plans - Get execution plans
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/execution/plans', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, status, limit = '20' } = request.query as Record<string, string>;
    
    try {
      const plans = await getExecutionPlans({ asset, status }, parseInt(limit));
      
      return {
        count: plans.length,
        plans: plans.map(p => ({
          planId: p.planId,
          asset: p.asset,
          direction: p.direction,
          strategyId: p.strategyId,
          entryPrice: p.entryPrice,
          stopPrice: p.stopPrice,
          target1Price: p.target1Price,
          positionSizePct: p.positionSizePct,
          riskPct: p.riskPct,
          status: p.status,
          createdAt: p.createdAt
        }))
      };
    } catch (error) {
      console.error('[ExecutionRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to fetch plans' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/execution/position-size - Calculate position size
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/execution/position-size', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    
    const {
      accountSize = 100000,
      baseRiskPct = 0.5,
      asset = 'BTCUSDT',
      direction = 'LONG',
      entryPrice,
      stopPrice,
      atr,
      confidence = 0.6,
      edgeScore = 0.5,
      regimeBoost = 1.0,
      useMetaBrain = true,  // Auto-integrate MetaBrain multiplier
      memoryRiskAdjustment  // P0: From Memory Engine
    } = body;
    
    if (!entryPrice || !stopPrice) {
      return reply.status(400).send({ error: 'entryPrice and stopPrice are required' });
    }
    
    try {
      // Get MetaBrain risk multiplier if enabled
      const metaRiskMultiplier = useMetaBrain ? await getRiskMultiplier() : undefined;
      
      const result = calculatePositionSize({
        accountSize,
        baseRiskPct,
        asset,
        direction,
        entryPrice,
        stopPrice,
        atr: atr || Math.abs(entryPrice - stopPrice),
        confidence,
        edgeScore,
        regimeBoost,
        metaRiskMultiplier,
        memoryRiskAdjustment  // P0: Pass to position sizing
      });
      
      return result;
    } catch (error) {
      console.error('[ExecutionRoutes] Position size error:', error);
      return reply.status(500).send({ error: 'Position size calculation failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/execution/portfolio - Get portfolio
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/execution/portfolio', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      // Use demo portfolio or fetch from DB
      const portfolio = demoPortfolio || await getDefaultPortfolio();
      
      if (!portfolio) {
        // Create default
        demoPortfolio = createPortfolio(100000);
        return {
          portfolio: demoPortfolio,
          stats: calculatePortfolioStats(demoPortfolio)
        };
      }
      
      const stats = calculatePortfolioStats(portfolio as unknown as Portfolio);
      
      return {
        portfolio: {
          portfolioId: portfolio.portfolioId,
          accountSize: portfolio.accountSize,
          positions: portfolio.positions,
          totalRisk: Math.round(portfolio.totalRisk * 100) / 100,
          totalExposure: Math.round(portfolio.totalExposure * 100) / 100,
          unrealizedPnL: Math.round(portfolio.unrealizedPnL * 100) / 100,
          realizedPnL: Math.round(portfolio.realizedPnL * 100) / 100,
          winCount: portfolio.winCount,
          lossCount: portfolio.lossCount
        },
        stats
      };
    } catch (error) {
      console.error('[ExecutionRoutes] Portfolio error:', error);
      return reply.status(500).send({ error: 'Failed to fetch portfolio' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/execution/risk - Get risk status
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/execution/risk', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      if (!demoPortfolio) {
        demoPortfolio = createPortfolio(100000);
      }
      
      const riskStatus = calculateRiskStatus(demoPortfolio);
      const pauseCheck = shouldPauseTrading(
        riskStatus.currentDrawdown,
        DEFAULT_RISK_LIMITS.maxDrawdown,
        0  // Would need to track consecutive losses
      );
      
      return {
        ...riskStatus,
        tradingPaused: pauseCheck.pause,
        pauseReason: pauseCheck.reason,
        limits: DEFAULT_RISK_LIMITS
      };
    } catch (error) {
      console.error('[ExecutionRoutes] Risk error:', error);
      return reply.status(500).send({ error: 'Failed to fetch risk status' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/execution/allocations - Calculate allocations
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/execution/allocations', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    const { strategies = [], totalCapital = 100000 } = body;
    
    try {
      // Use mock strategies if none provided
      const strategyData = strategies.length > 0 ? strategies : [
        { strategyId: 'STR_001', strategyScore: 0.85, profitFactor: 1.42, trades: 150 },
        { strategyId: 'STR_002', strategyScore: 0.72, profitFactor: 1.35, trades: 120 },
        { strategyId: 'STR_003', strategyScore: 0.65, profitFactor: 1.28, trades: 100 }
      ];
      
      const allocations = calculateAllocations(strategyData, totalCapital);
      
      return allocations;
    } catch (error) {
      console.error('[ExecutionRoutes] Allocation error:', error);
      return reply.status(500).send({ error: 'Allocation calculation failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/execution/kelly - Kelly criterion sizing
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/execution/kelly', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    const { 
      accountSize = 100000, 
      winRate = 0.55, 
      avgWinR = 1.5, 
      avgLossR = 1.0,
      entryPrice = 100,
      stopDistancePrice = 2
    } = body;
    
    try {
      const result = calculateKellyPositionSize(
        accountSize, winRate, avgWinR, avgLossR, stopDistancePrice, entryPrice
      );
      
      return {
        ...result,
        accountSize,
        winRate,
        avgWinR,
        avgLossR
      };
    } catch (error) {
      console.error('[ExecutionRoutes] Kelly error:', error);
      return reply.status(500).send({ error: 'Kelly calculation failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/execution/stats - Execution statistics
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/execution/stats', async (request: FastifyRequest, reply: FastifyReply) => {
    const { days = '30' } = request.query as Record<string, string>;
    
    try {
      const stats = await getExecutionStats(parseInt(days));
      return stats;
    } catch (error) {
      console.error('[ExecutionRoutes] Stats error:', error);
      return reply.status(500).send({ error: 'Failed to fetch stats' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // PATCH /api/ta/execution/plans/:id/status - Update plan status
  // ─────────────────────────────────────────────────────────────
  fastify.patch('/api/ta/execution/plans/:id/status', async (request: FastifyRequest, reply: FastifyReply) => {
    const { id } = request.params as { id: string };
    const { status } = request.body as { status: string };
    
    if (!['PENDING', 'ACTIVE', 'FILLED', 'CANCELLED', 'EXPIRED'].includes(status)) {
      return reply.status(400).send({ error: 'Invalid status' });
    }
    
    try {
      await updatePlanStatus(id, status as any);
      return { success: true, planId: id, newStatus: status };
    } catch (error) {
      console.error('[ExecutionRoutes] Status update error:', error);
      return reply.status(500).send({ error: 'Failed to update plan status' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/execution/config - Get execution config
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/execution/config', async (request: FastifyRequest, reply: FastifyReply) => {
    return {
      executionConfig: DEFAULT_EXECUTION_CONFIG,
      riskLimits: DEFAULT_RISK_LIMITS
    };
  });
}

export default registerExecutionRoutes;
