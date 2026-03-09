/**
 * MetaBrain v1 — API Routes
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { RISK_MODE_CONFIG, DEFAULT_METABRAIN_CONFIG } from './metabrain.types.js';
import {
  runMetaBrain,
  getCurrentState,
  getCurrentDecision,
  forceRecompute,
  getRiskMultiplier,
  getConfidenceThreshold,
  getStrategyMultiplier
} from './metabrain.controller.js';
import { calculateRiskScore, riskScoreToMode } from './metabrain.risk_mode.js';
import { determineSignalThresholds, generateStrategyPolicies } from './metabrain.policy.js';
import { getRecentActions, getActionStats } from './metabrain.storage.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerMetaBrainRoutes(fastify: FastifyInstance): Promise<void> {

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/status — For Digital Twin Live Context
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/status', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      let state = await getCurrentState();
      
      if (!state) {
        // Return defaults for Digital Twin
        return {
          riskMode: 'NORMAL',
          confidenceThreshold: 0.6,
          metaRiskMultiplier: 1.0
        };
      }
      
      return {
        riskMode: state.currentRiskMode,
        confidenceThreshold: state.currentDecision?.confidenceThreshold || 0.6,
        metaRiskMultiplier: state.currentDecision?.riskMultiplier || 1.0
      };
    } catch (error) {
      console.error('[MetaBrainRoutes] Status error:', error);
      return {
        riskMode: 'NORMAL',
        confidenceThreshold: 0.6,
        metaRiskMultiplier: 1.0
      };
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/state - Get current MetaBrain state
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/state', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      let state = await getCurrentState();
      
      // If no state, run initial computation
      if (!state) {
        await runMetaBrain();
        state = await getCurrentState();
      }
      
      if (!state) {
        return reply.status(500).send({ error: 'Failed to get MetaBrain state' });
      }
      
      return {
        riskMode: state.currentRiskMode,
        systemHealth: state.systemHealth,
        context: {
          regime: state.currentContext.regime,
          volatility: state.currentContext.volatility,
          drawdownPct: Math.round(state.currentContext.drawdownPct * 10000) / 100,
          edgeHealth: Math.round(state.currentContext.edgeHealth * 100) / 100,
          marketCondition: state.currentContext.marketCondition,
          openPositions: state.currentContext.openPositions
        },
        decision: {
          riskMultiplier: state.currentDecision.riskMultiplier,
          confidenceThreshold: state.currentDecision.confidenceThreshold,
          strategyMultiplier: state.currentDecision.strategyMultiplier,
          effectiveBaseRisk: state.currentDecision.effectiveBaseRisk,
          reason: state.currentDecision.reason
        },
        stats: {
          totalDecisions: state.totalDecisions,
          modeChangesToday: state.modeChangesToday,
          historyLength: state.riskModeHistory?.length || 0
        },
        updatedAt: state.updatedAt
      };
    } catch (error) {
      console.error('[MetaBrainRoutes] State error:', error);
      return reply.status(500).send({ error: 'Failed to get MetaBrain state' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/decision - Get current decision only
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/decision', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const decision = await getCurrentDecision();
      
      if (!decision) {
        // Run computation if no decision
        const newDecision = await runMetaBrain();
        return newDecision;
      }
      
      return decision;
    } catch (error) {
      console.error('[MetaBrainRoutes] Decision error:', error);
      return reply.status(500).send({ error: 'Failed to get decision' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/metabrain/recompute - Force recomputation
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/metabrain/recompute', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    
    try {
      // Optional: provide sources for computation
      const sources = body.sources ? {
        regime: body.sources.regime,
        state: body.sources.state,
        physics: body.sources.physics,
        portfolio: body.sources.portfolio,
        edge: body.sources.edge,
        strategy: body.sources.strategy,
        governance: body.sources.governance
      } : undefined;
      
      const decision = await forceRecompute(sources);
      
      return {
        success: true,
        decision
      };
    } catch (error) {
      console.error('[MetaBrainRoutes] Recompute error:', error);
      return reply.status(500).send({ error: 'Recomputation failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/multipliers - Get all multipliers
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/multipliers', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const [riskMult, confThreshold, stratMult] = await Promise.all([
        getRiskMultiplier(),
        getConfidenceThreshold(),
        getStrategyMultiplier()
      ]);
      
      return {
        riskMultiplier: riskMult,
        confidenceThreshold: confThreshold,
        strategyMultiplier: stratMult
      };
    } catch (error) {
      console.error('[MetaBrainRoutes] Multipliers error:', error);
      return reply.status(500).send({ error: 'Failed to get multipliers' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/actions - Get recent actions
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/actions', async (request: FastifyRequest, reply: FastifyReply) => {
    const { limit = '20', type } = request.query as Record<string, string>;
    
    try {
      const actions = await getRecentActions(parseInt(limit), type);
      
      return {
        count: actions.length,
        actions: actions.map(a => ({
          actionId: a.actionId,
          type: a.actionType,
          from: a.from,
          to: a.to,
          reason: a.reason,
          timestamp: a.timestamp
        }))
      };
    } catch (error) {
      console.error('[MetaBrainRoutes] Actions error:', error);
      return reply.status(500).send({ error: 'Failed to get actions' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/stats - Get action statistics
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/stats', async (request: FastifyRequest, reply: FastifyReply) => {
    const { days = '30' } = request.query as Record<string, string>;
    
    try {
      const stats = await getActionStats(parseInt(days));
      
      return stats;
    } catch (error) {
      console.error('[MetaBrainRoutes] Stats error:', error);
      return reply.status(500).send({ error: 'Failed to get stats' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/metabrain/simulate - Simulate with custom context
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/metabrain/simulate', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    
    const {
      regime = 'COMPRESSION',
      volatility = 1.0,
      drawdownPct = 0,
      edgeHealth = 0.5,
      bestStrategyScore = 0.5,
      governanceFrozen = false
    } = body;
    
    try {
      // Build mock sources
      const sources = {
        regime: { regime, confidence: 0.7 },
        state: { state: 'NEUTRAL' },
        physics: { volatility, atrRatio: volatility },
        portfolio: { 
          accountSize: 100000, 
          unrealizedPnL: -drawdownPct * 100000, 
          realizedPnL: 0, 
          totalRisk: 2, 
          openPositions: 2 
        },
        edge: { 
          avgProfitFactor: 1 + edgeHealth * 0.5, 
          recentWinRate: 0.5 + edgeHealth * 0.2, 
          edgeTrend: 0 
        },
        strategy: { bestScore: bestStrategyScore, activeCount: 3 },
        governance: { frozen: governanceFrozen }
      };
      
      // Don't save, just simulate
      const { buildMetaBrainContext, getDefaultContext } = await import('./metabrain.context.js');
      const { computeRiskMode, calculateRiskScore } = await import('./metabrain.risk_mode.js');
      const { buildMetaDecision } = await import('./metabrain.policy.js');
      
      const context = buildMetaBrainContext(
        sources.regime,
        sources.state,
        sources.physics,
        sources.portfolio,
        sources.edge,
        sources.strategy,
        sources.governance
      );
      
      const { mode, reasons } = computeRiskMode(context);
      const decision = buildMetaDecision(context, mode, reasons);
      const riskScore = calculateRiskScore(context);
      
      return {
        simulation: true,
        input: { regime, volatility, drawdownPct, edgeHealth, bestStrategyScore, governanceFrozen },
        result: {
          riskMode: mode,
          riskScore: Math.round(riskScore),
          decision: {
            riskMultiplier: decision.riskMultiplier,
            confidenceThreshold: decision.confidenceThreshold,
            strategyMultiplier: decision.strategyMultiplier,
            effectiveBaseRisk: decision.effectiveBaseRisk
          },
          reason: reasons,
          context: {
            marketCondition: context.marketCondition,
            volatilityLevel: context.volatility,
            edgeHealth: Math.round(context.edgeHealth * 100) / 100
          }
        }
      };
    } catch (error) {
      console.error('[MetaBrainRoutes] Simulation error:', error);
      return reply.status(500).send({ error: 'Simulation failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/config - Get configuration
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/config', async (request: FastifyRequest, reply: FastifyReply) => {
    return {
      riskModes: RISK_MODE_CONFIG,
      config: DEFAULT_METABRAIN_CONFIG
    };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/metabrain/history - Get risk mode history
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/metabrain/history', async (request: FastifyRequest, reply: FastifyReply) => {
    const { limit = '20' } = request.query as Record<string, string>;
    
    try {
      const state = await getCurrentState();
      const history = state?.riskModeHistory || [];
      
      return {
        count: history.length,
        history: history.slice(-parseInt(limit)).reverse()
      };
    } catch (error) {
      console.error('[MetaBrainRoutes] History error:', error);
      return reply.status(500).send({ error: 'Failed to get history' });
    }
  });
}

export default registerMetaBrainRoutes;
