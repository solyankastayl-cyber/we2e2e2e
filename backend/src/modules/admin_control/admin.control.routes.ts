/**
 * Phase 3 — Admin Control Plane Routes
 * ======================================
 * 
 * Command System:
 *   POST /api/admin/commands           — Execute command
 *   GET  /api/admin/commands           — List commands
 *   GET  /api/admin/commands/:id       — Get command
 *   POST /api/admin/commands/dry-run   — Dry run
 *   POST /api/admin/commands/:id/rollback — Rollback
 * 
 * Override Registry:
 *   GET  /api/admin/overrides          — List overrides
 *   POST /api/admin/overrides          — Create override
 *   DELETE /api/admin/overrides/:id    — Remove override
 * 
 * Status:
 *   GET /api/admin/status              — System status
 *   GET /api/admin/metabrain/state     — MetaBrain state
 *   GET /api/admin/modules/status      — Module statuses
 *   GET /api/admin/strategies          — Strategy statuses
 *   GET /api/admin/audit/stats         — Audit statistics
 */

import { FastifyInstance } from 'fastify';
import { executeCommand, getCommand } from './admin.command.execute.js';
import { executeDryRun, getImpactSummary } from './admin.command.dryrun.js';
import { rollbackCommand, canRollback } from './admin.command.rollback.js';
import { getAuditRecords, getAuditStats } from './admin.command.audit.js';
import {
  createOverride,
  getActiveOverrides,
  getOverrideById,
  deactivateOverride,
  removeOverride,
  getOverrideCount,
} from './admin.override.registry.js';
import {
  getSystemStatus,
  getMetaBrainState,
  getModuleStatuses,
  getStrategyStatuses,
} from './admin.state.service.js';
import { AdminCommandType, CommandRequest, OverrideRequest, CommandStatus } from './admin.command.types.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerAdminControlRoutes(app: FastifyInstance): Promise<void> {
  
  // ─────────────────────────────────────────────────────────────
  // COMMAND ROUTES
  // ─────────────────────────────────────────────────────────────
  
  /**
   * POST /api/admin/commands — Execute admin command
   */
  app.post<{ Body: CommandRequest }>('/api/admin/commands', async (request, reply) => {
    try {
      const result = await executeCommand(request.body);
      
      const status = result.status === CommandStatus.EXECUTED ? 200 : 400;
      return reply.status(status).send({
        ok: result.status === CommandStatus.EXECUTED,
        data: result,
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * GET /api/admin/commands — List command history
   */
  app.get<{
    Querystring: { limit?: string; offset?: string; actor?: string; status?: string }
  }>('/api/admin/commands', async (request, reply) => {
    try {
      const options = {
        limit: request.query.limit ? parseInt(request.query.limit) : 50,
        offset: request.query.offset ? parseInt(request.query.offset) : 0,
        actor: request.query.actor,
        status: request.query.status as CommandStatus | undefined,
      };
      
      const { records, total } = await getAuditRecords(options);
      
      return reply.send({
        ok: true,
        data: {
          commands: records.map(r => ({
            id: r.commandId,
            type: r.type,
            actor: r.actor,
            ts: r.ts,
            status: r.status,
            reason: r.reason,
          })),
          total,
          limit: options.limit,
          offset: options.offset,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * GET /api/admin/commands/:id — Get command details
   */
  app.get<{ Params: { id: string } }>('/api/admin/commands/:id', async (request, reply) => {
    try {
      const command = await getCommand(request.params.id);
      
      if (!command) {
        return reply.status(404).send({ ok: false, error: 'Command not found' });
      }
      
      const rollbackInfo = await canRollback(request.params.id);
      
      return reply.send({
        ok: true,
        data: {
          ...command,
          canRollback: rollbackInfo.canRollback,
          rollbackReason: rollbackInfo.reason,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * POST /api/admin/commands/dry-run — Simulate command execution
   */
  app.post<{ Body: CommandRequest }>('/api/admin/commands/dry-run', async (request, reply) => {
    try {
      const result = await executeDryRun(request.body);
      
      return reply.send({
        ok: result.valid,
        data: {
          ...result,
          summary: getImpactSummary(result.impact),
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * POST /api/admin/commands/:id/rollback — Rollback a command
   */
  app.post<{ Params: { id: string } }>('/api/admin/commands/:id/rollback', async (request, reply) => {
    try {
      const result = await rollbackCommand(request.params.id);
      
      const status = result.status === CommandStatus.ROLLED_BACK ? 200 : 400;
      return reply.status(status).send({
        ok: result.status === CommandStatus.ROLLED_BACK,
        data: result,
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // OVERRIDE ROUTES
  // ─────────────────────────────────────────────────────────────
  
  /**
   * GET /api/admin/overrides — List active overrides
   */
  app.get('/api/admin/overrides', async (request, reply) => {
    try {
      const overrides = await getActiveOverrides();
      
      return reply.send({
        ok: true,
        data: {
          overrides,
          count: overrides.length,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * POST /api/admin/overrides — Create manual override
   */
  app.post<{ Body: OverrideRequest }>('/api/admin/overrides', async (request, reply) => {
    try {
      const override = await createOverride(request.body);
      
      return reply.status(201).send({
        ok: true,
        data: override,
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * GET /api/admin/overrides/:id — Get override details
   */
  app.get<{ Params: { id: string } }>('/api/admin/overrides/:id', async (request, reply) => {
    try {
      const override = await getOverrideById(request.params.id);
      
      if (!override) {
        return reply.status(404).send({ ok: false, error: 'Override not found' });
      }
      
      return reply.send({ ok: true, data: override });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * DELETE /api/admin/overrides/:id — Remove override
   */
  app.delete<{ Params: { id: string } }>('/api/admin/overrides/:id', async (request, reply) => {
    try {
      const removed = await removeOverride(request.params.id);
      
      if (!removed) {
        return reply.status(404).send({ ok: false, error: 'Override not found' });
      }
      
      return reply.send({ ok: true, data: { removed: true } });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // STATUS ROUTES
  // ─────────────────────────────────────────────────────────────
  
  /**
   * GET /api/admin/status — System status overview
   */
  app.get('/api/admin/status', async (request, reply) => {
    try {
      const systemStatus = getSystemStatus();
      const auditStats = await getAuditStats();
      
      return reply.send({
        ok: true,
        data: {
          ...systemStatus,
          activeOverrides: getOverrideCount(),
          commandsToday: auditStats.today,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * GET /api/admin/metabrain/state — MetaBrain state
   */
  app.get('/api/admin/metabrain/state', async (request, reply) => {
    try {
      const state = getMetaBrainState();
      
      return reply.send({
        ok: true,
        data: state,
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * GET /api/admin/modules/status — All module statuses
   */
  app.get('/api/admin/modules/status', async (request, reply) => {
    try {
      const modules = getModuleStatuses();
      
      return reply.send({
        ok: true,
        data: {
          modules,
          active: modules.filter(m => m.status === 'ACTIVE').length,
          gated: modules.filter(m => m.status !== 'ACTIVE').length,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * GET /api/admin/strategies — All strategy statuses
   */
  app.get('/api/admin/strategies', async (request, reply) => {
    try {
      const strategies = getStrategyStatuses();
      
      return reply.send({
        ok: true,
        data: {
          strategies,
          active: strategies.filter(s => s.active).length,
          inactive: strategies.filter(s => !s.active).length,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * GET /api/admin/audit/stats — Audit statistics
   */
  app.get('/api/admin/audit/stats', async (request, reply) => {
    try {
      const stats = await getAuditStats();
      
      return reply.send({
        ok: true,
        data: stats,
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  /**
   * GET /api/admin/command-types — Available command types
   */
  app.get('/api/admin/command-types', async (request, reply) => {
    return reply.send({
      ok: true,
      data: {
        types: Object.values(AdminCommandType),
      },
    });
  });
  
  console.log('[Admin Control Routes] Registered:');
  console.log('  Commands:');
  console.log('    - POST /api/admin/commands');
  console.log('    - GET  /api/admin/commands');
  console.log('    - GET  /api/admin/commands/:id');
  console.log('    - POST /api/admin/commands/dry-run');
  console.log('    - POST /api/admin/commands/:id/rollback');
  console.log('  Overrides:');
  console.log('    - GET  /api/admin/overrides');
  console.log('    - POST /api/admin/overrides');
  console.log('    - GET  /api/admin/overrides/:id');
  console.log('    - DELETE /api/admin/overrides/:id');
  console.log('  Status:');
  console.log('    - GET /api/admin/status');
  console.log('    - GET /api/admin/metabrain/state');
  console.log('    - GET /api/admin/modules/status');
  console.log('    - GET /api/admin/strategies');
  console.log('    - GET /api/admin/audit/stats');
  console.log('    - GET /api/admin/command-types');
}
