/**
 * P1.2 — Module Gating Routes
 * 
 * API endpoints for module gating management
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { Db } from 'mongodb';
import { AnalysisModule, ALL_MODULES } from './module_attribution.types.js';
import {
  ModuleGate,
  ModuleGateStatus,
  ModuleGateHistory,
  GatingRules,
  DEFAULT_GATING_RULES,
  GatesResponse,
  GateRebuildResponse,
  GateOverrideRequest,
  GateOverrideResponse
} from './learning.gating.types.js';
import {
  computeModuleGates,
  calculateGatingSummary,
  isGatingChangeAllowed,
  getDefaultGates
} from './learning.gating.ts';
import {
  saveModuleGates,
  getAllModuleGates,
  getModuleGate,
  getModuleGatesMap,
  saveGateHistory,
  getGateHistory,
  getRecentGateChanges,
  countRecentGateChanges,
  resetAllGates,
  cleanupExpiredGates
} from './learning.gating.storage.js';
import {
  getGatedWeights,
  getGateStatusesForExplain
} from './learning.gating.integration.js';
import { getModuleAttributions, getModuleWeights } from './module_storage.js';

// ═══════════════════════════════════════════════════════════════
// CONTROLLER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Rebuild gates from current attribution and weights
 */
export async function rebuildGates(regime?: string): Promise<{
  modulesProcessed: number;
  statusChanges: number;
  gates: ModuleGate[];
}> {
  // Get current weights
  const weights = await getModuleWeights(regime);
  const weightMap = new Map(weights.map(w => [w.module, w]));
  
  // Get current gates
  const currentGates = await getModuleGatesMap(regime);
  
  // Build gating inputs
  const inputs = ALL_MODULES.map(module => {
    const weight = weightMap.get(module);
    return {
      module,
      weight: weight?.weight ?? 1.0,
      sampleSize: weight?.basedOnSample ?? 0,
      avgOutcomeImpact: weight?.basedOnEdgeScore 
        ? (weight.basedOnEdgeScore - 1.5) / 1.5  // Normalize edge score to -1..1
        : 0,
      degradationStreak: 0,  // Would need historical data
      regime
    };
  });
  
  // Compute new gates
  const newGates = computeModuleGates(inputs, currentGates, DEFAULT_GATING_RULES);
  
  // Count status changes and save history
  let statusChanges = 0;
  for (const gate of newGates) {
    const key = regime ? `${gate.module}:${regime}` : gate.module;
    const current = currentGates.get(key);
    
    if (current && current.status !== gate.status) {
      statusChanges++;
      
      // Save history
      await saveGateHistory({
        module: gate.module,
        regime,
        previousStatus: current.status,
        newStatus: gate.status,
        reason: gate.reason,
        score: gate.score,
        changedAt: new Date(),
        changedBy: 'AUTO'
      });
    }
  }
  
  // Save gates
  await saveModuleGates(newGates);
  
  return {
    modulesProcessed: newGates.length,
    statusChanges,
    gates: newGates
  };
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerGatingRoutes(app: FastifyInstance): Promise<void> {
  /**
   * GET /api/ta/metabrain/learning/gates
   * Get current module gates
   */
  app.get('/api/ta/metabrain/learning/gates', async (
    request: FastifyRequest<{ Querystring: { regime?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { regime } = request.query;
      
      const gates = await getAllModuleGates(regime);
      const summary = calculateGatingSummary(gates);
      
      return reply.send({
        success: true,
        data: {
          gates,
          summary
        }
      } as GatesResponse);
    } catch (err) {
      return reply.status(500).send({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to get gates'
      });
    }
  });
  
  /**
   * GET /api/ta/metabrain/learning/gates/:module
   * Get gate for specific module
   */
  app.get('/api/ta/metabrain/learning/gates/:module', async (
    request: FastifyRequest<{ 
      Params: { module: string };
      Querystring: { regime?: string } 
    }>,
    reply: FastifyReply
  ) => {
    try {
      const { module } = request.params;
      const { regime } = request.query;
      
      if (!ALL_MODULES.includes(module as AnalysisModule)) {
        return reply.status(400).send({
          success: false,
          error: `Unknown module: ${module}`
        });
      }
      
      const gate = await getModuleGate(module as AnalysisModule, regime);
      
      if (!gate) {
        return reply.send({
          success: true,
          data: {
            module,
            status: 'ACTIVE',
            reason: 'No gate record found'
          }
        });
      }
      
      return reply.send({
        success: true,
        data: gate
      });
    } catch (err) {
      return reply.status(500).send({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to get gate'
      });
    }
  });
  
  /**
   * POST /api/ta/metabrain/learning/gates/rebuild
   * Rebuild all gates from current data
   */
  app.post('/api/ta/metabrain/learning/gates/rebuild', async (
    request: FastifyRequest<{ Body: { regime?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { regime } = request.body ?? {};
      
      const result = await rebuildGates(regime);
      
      return reply.send({
        success: true,
        data: {
          modulesProcessed: result.modulesProcessed,
          statusChanges: result.statusChanges,
          newGates: result.gates,
          rebuiltAt: new Date()
        }
      } as GateRebuildResponse);
    } catch (err) {
      return reply.status(500).send({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to rebuild gates'
      });
    }
  });
  
  /**
   * POST /api/ta/metabrain/learning/gates/override
   * Manually override a gate status
   */
  app.post('/api/ta/metabrain/learning/gates/override', async (
    request: FastifyRequest<{ Body: GateOverrideRequest }>,
    reply: FastifyReply
  ) => {
    try {
      const { module, regime, status, reason, durationDays } = request.body;
      
      if (!ALL_MODULES.includes(module)) {
        return reply.status(400).send({
          success: false,
          error: `Unknown module: ${module}`
        });
      }
      
      // Get current gate
      const currentGate = await getModuleGate(module, regime);
      const previousStatus = currentGate?.status ?? 'ACTIVE';
      
      // Check governance
      const currentGates = await getAllModuleGates(regime);
      const recentChanges = await countRecentGateChanges(module, 24);
      
      const governance = isGatingChangeAllowed(
        currentGates,
        { module, status } as ModuleGate,
        recentChanges
      );
      
      if (!governance.allowed) {
        return reply.status(403).send({
          success: false,
          error: governance.reason
        });
      }
      
      // Create new gate
      const now = Date.now();
      const newGate: ModuleGate = {
        module,
        regime,
        status,
        reason,
        score: currentGate?.score ?? 0,
        sampleSize: currentGate?.sampleSize ?? 0,
        avgOutcomeImpact: currentGate?.avgOutcomeImpact ?? 0,
        weight: currentGate?.weight ?? 1.0,
        gatedUntil: status === 'HARD_GATED' && durationDays
          ? now + durationDays * 24 * 60 * 60 * 1000
          : undefined,
        updatedAt: now,
        createdAt: currentGate?.createdAt ?? now
      };
      
      // Save gate
      await saveModuleGates([newGate]);
      
      // Save history
      if (previousStatus !== status) {
        await saveGateHistory({
          module,
          regime,
          previousStatus,
          newStatus: status,
          reason,
          score: newGate.score,
          changedAt: new Date(),
          changedBy: 'MANUAL'
        });
      }
      
      return reply.send({
        success: true,
        data: {
          gate: newGate,
          previousStatus
        }
      } as GateOverrideResponse);
    } catch (err) {
      return reply.status(500).send({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to override gate'
      });
    }
  });
  
  /**
   * POST /api/ta/metabrain/learning/gates/reset
   * Reset a gate to ACTIVE
   */
  app.post('/api/ta/metabrain/learning/gates/reset', async (
    request: FastifyRequest<{ Body: { module: string; regime?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { module, regime } = request.body;
      
      if (!ALL_MODULES.includes(module as AnalysisModule)) {
        return reply.status(400).send({
          success: false,
          error: `Unknown module: ${module}`
        });
      }
      
      const currentGate = await getModuleGate(module as AnalysisModule, regime);
      const previousStatus = currentGate?.status ?? 'ACTIVE';
      
      if (previousStatus === 'ACTIVE') {
        return reply.send({
          success: true,
          data: {
            message: 'Module already active',
            gate: currentGate
          }
        });
      }
      
      // Reset to ACTIVE
      const now = Date.now();
      const newGate: ModuleGate = {
        module: module as AnalysisModule,
        regime,
        status: 'ACTIVE',
        reason: 'Manual reset',
        score: 0,
        sampleSize: currentGate?.sampleSize ?? 0,
        avgOutcomeImpact: currentGate?.avgOutcomeImpact ?? 0,
        weight: currentGate?.weight ?? 1.0,
        updatedAt: now,
        createdAt: currentGate?.createdAt ?? now
      };
      
      await saveModuleGates([newGate]);
      
      // Save history
      await saveGateHistory({
        module: module as AnalysisModule,
        regime,
        previousStatus,
        newStatus: 'ACTIVE',
        reason: 'Manual reset',
        score: 0,
        changedAt: new Date(),
        changedBy: 'MANUAL'
      });
      
      return reply.send({
        success: true,
        data: {
          gate: newGate,
          previousStatus
        }
      });
    } catch (err) {
      return reply.status(500).send({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to reset gate'
      });
    }
  });
  
  /**
   * GET /api/ta/metabrain/learning/gates/history
   * Get gate history
   */
  app.get('/api/ta/metabrain/learning/gates/history', async (
    request: FastifyRequest<{ Querystring: { module?: string; regime?: string; limit?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { module, regime, limit } = request.query;
      const limitNum = limit ? parseInt(limit, 10) : 50;
      
      if (module) {
        if (!ALL_MODULES.includes(module as AnalysisModule)) {
          return reply.status(400).send({
            success: false,
            error: `Unknown module: ${module}`
          });
        }
        
        const history = await getGateHistory(module as AnalysisModule, regime, limitNum);
        return reply.send({ success: true, data: { history } });
      }
      
      // Get all recent changes
      const history = await getRecentGateChanges(24 * 7);  // Last week
      return reply.send({ success: true, data: { history: history.slice(0, limitNum) } });
    } catch (err) {
      return reply.status(500).send({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to get history'
      });
    }
  });
  
  /**
   * POST /api/ta/metabrain/learning/gates/cleanup
   * Cleanup expired hard gates
   */
  app.post('/api/ta/metabrain/learning/gates/cleanup', async (
    request: FastifyRequest,
    reply: FastifyReply
  ) => {
    try {
      const count = await cleanupExpiredGates();
      
      return reply.send({
        success: true,
        data: {
          expiredGatesReset: count,
          cleanedAt: new Date()
        }
      });
    } catch (err) {
      return reply.status(500).send({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to cleanup gates'
      });
    }
  });
  
  /**
   * GET /api/ta/metabrain/learning/gates/explain
   * Get gate statuses for explain API
   */
  app.get('/api/ta/metabrain/learning/gates/explain', async (
    request: FastifyRequest<{ Querystring: { regime?: string } }>,
    reply: FastifyReply
  ) => {
    try {
      const { regime } = request.query;
      const statuses = await getGateStatusesForExplain(regime);
      
      return reply.send({
        success: true,
        data: {
          gates: statuses
        }
      });
    } catch (err) {
      return reply.status(500).send({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to get explain data'
      });
    }
  });
}
