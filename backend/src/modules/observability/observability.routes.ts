/**
 * Phase 4 — Observability Routes
 * ================================
 * 
 * Log Endpoints:
 *   GET /api/logs/decision    — Decision logs
 *   GET /api/logs/execution   — Execution logs
 *   GET /api/logs/metabrain   — MetaBrain logs
 *   GET /api/logs/memory      — Memory logs
 *   GET /api/logs/tree        — Scenario tree logs
 *   GET /api/logs/system      — System metrics
 * 
 * Explain:
 *   GET /api/decision/explain — Explain decision
 *   GET /api/decision/explain/:id — Explain specific decision
 * 
 * Replay:
 *   GET /api/replay/snapshots — List snapshots
 *   GET /api/replay/decision/:id — Replay decision
 *   POST /api/replay/simulate — Simulate with snapshot
 *   GET /api/replay/compare — Compare decisions
 */

import { FastifyInstance } from 'fastify';
import { getDecisionLogs, getDecisionStats, getDecisionById } from './logs.decision.service.js';
import { getExecutionLogs, getExecutionStats } from './logs.execution.service.js';
import { getMetaBrainLogs, getMetaBrainStats } from './logs.metabrain.service.js';
import { getMemoryLogs, getMemoryStats } from './logs.memory.service.js';
import { getTreeLogs, getTreeStats } from './logs.tree.service.js';
import { explainDecision, explainLatestDecision, getFactorsSummary } from './explain.service.js';
import { getSnapshots, getSnapshot, replaySnapshot, compareDecisions, getReplayStats } from '../replay/replay.service.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerObservabilityRoutes(app: FastifyInstance): Promise<void> {
  
  // ─────────────────────────────────────────────────────────────
  // DECISION LOGS
  // ─────────────────────────────────────────────────────────────
  
  app.get<{ Querystring: { symbol?: string; signal?: string; limit?: string; offset?: string } }>(
    '/api/logs/decision',
    async (request, reply) => {
      try {
        const { logs, total } = getDecisionLogs({
          symbol: request.query.symbol,
          signal: request.query.signal,
          limit: request.query.limit ? parseInt(request.query.limit) : 50,
          offset: request.query.offset ? parseInt(request.query.offset) : 0,
        });
        
        return reply.send({
          ok: true,
          data: { decisions: logs, total, stats: getDecisionStats(request.query.symbol) },
        });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  // ─────────────────────────────────────────────────────────────
  // EXECUTION LOGS
  // ─────────────────────────────────────────────────────────────
  
  app.get<{ Querystring: { symbol?: string; limit?: string } }>(
    '/api/logs/execution',
    async (request, reply) => {
      try {
        const { logs, total } = getExecutionLogs({
          symbol: request.query.symbol,
          limit: request.query.limit ? parseInt(request.query.limit) : 50,
        });
        
        return reply.send({
          ok: true,
          data: { execution: logs, total, stats: getExecutionStats() },
        });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  // ─────────────────────────────────────────────────────────────
  // METABRAIN LOGS
  // ─────────────────────────────────────────────────────────────
  
  app.get<{ Querystring: { event?: string; limit?: string } }>(
    '/api/logs/metabrain',
    async (request, reply) => {
      try {
        const logs = getMetaBrainLogs({
          event: request.query.event as any,
          limit: request.query.limit ? parseInt(request.query.limit) : 50,
        });
        
        return reply.send({
          ok: true,
          data: { events: logs, stats: getMetaBrainStats() },
        });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  // ─────────────────────────────────────────────────────────────
  // MEMORY LOGS
  // ─────────────────────────────────────────────────────────────
  
  app.get<{ Querystring: { symbol?: string; limit?: string } }>(
    '/api/logs/memory',
    async (request, reply) => {
      try {
        const logs = getMemoryLogs({
          symbol: request.query.symbol,
          limit: request.query.limit ? parseInt(request.query.limit) : 50,
        });
        
        return reply.send({
          ok: true,
          data: { matches: logs, stats: getMemoryStats() },
        });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  // ─────────────────────────────────────────────────────────────
  // TREE LOGS
  // ─────────────────────────────────────────────────────────────
  
  app.get<{ Querystring: { symbol?: string; limit?: string } }>(
    '/api/logs/tree',
    async (request, reply) => {
      try {
        const logs = getTreeLogs({
          symbol: request.query.symbol,
          limit: request.query.limit ? parseInt(request.query.limit) : 50,
        });
        
        return reply.send({
          ok: true,
          data: { branches: logs, stats: getTreeStats() },
        });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  // ─────────────────────────────────────────────────────────────
  // SYSTEM LOGS (AGGREGATED METRICS)
  // ─────────────────────────────────────────────────────────────
  
  app.get('/api/logs/system', async (request, reply) => {
    try {
      const decisionStats = getDecisionStats();
      const executionStats = getExecutionStats();
      const memoryStats = getMemoryStats();
      const treeStats = getTreeStats();
      
      return reply.send({
        ok: true,
        data: {
          signalsToday: decisionStats.longs + decisionStats.shorts,
          decisionsToday: decisionStats.total,
          executionsToday: executionStats.total,
          activeStrategies: Object.keys(executionStats.byStrategy).length,
          memoryMatches: memoryStats.totalQueries,
          avgConfidence: decisionStats.avgConfidence,
          winRate: decisionStats.winRate,
          avgEntropy: treeStats.avgEntropy,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // EXPLAIN ENDPOINTS
  // ─────────────────────────────────────────────────────────────
  
  app.get<{ Querystring: { symbol?: string } }>(
    '/api/decision/explain',
    async (request, reply) => {
      try {
        const symbol = request.query.symbol || 'BTCUSDT';
        const explanation = explainLatestDecision(symbol);
        
        if (!explanation) {
          return reply.status(404).send({ ok: false, error: 'No recent decision found' });
        }
        
        return reply.send({ ok: true, data: explanation });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  app.get<{ Params: { id: string } }>(
    '/api/decision/explain/:id',
    async (request, reply) => {
      try {
        const explanation = explainDecision(request.params.id);
        
        if (!explanation) {
          return reply.status(404).send({ ok: false, error: 'Decision not found' });
        }
        
        return reply.send({ ok: true, data: explanation });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  app.get('/api/decision/factors', async (request, reply) => {
    try {
      const summary = getFactorsSummary();
      return reply.send({ ok: true, data: summary });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // REPLAY ENDPOINTS
  // ─────────────────────────────────────────────────────────────
  
  app.get<{ Querystring: { symbol?: string; limit?: string } }>(
    '/api/replay/snapshots',
    async (request, reply) => {
      try {
        const snapshots = getSnapshots({
          symbol: request.query.symbol,
          limit: request.query.limit ? parseInt(request.query.limit) : 50,
        });
        
        return reply.send({
          ok: true,
          data: { snapshots, stats: getReplayStats() },
        });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  app.get<{ Params: { id: string } }>(
    '/api/replay/decision/:id',
    async (request, reply) => {
      try {
        const result = replaySnapshot(request.params.id);
        
        if (!result) {
          return reply.status(404).send({ ok: false, error: 'Snapshot not found' });
        }
        
        return reply.send({ ok: true, data: result });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  app.post<{ Body: { snapshotId: string } }>(
    '/api/replay/simulate',
    async (request, reply) => {
      try {
        const { snapshotId } = request.body;
        const result = replaySnapshot(snapshotId);
        
        if (!result) {
          return reply.status(404).send({ ok: false, error: 'Snapshot not found' });
        }
        
        return reply.send({ ok: true, data: result });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  app.get<{ Querystring: { symbol?: string; limit?: string } }>(
    '/api/replay/compare',
    async (request, reply) => {
      try {
        const symbol = request.query.symbol || 'BTCUSDT';
        const limit = request.query.limit ? parseInt(request.query.limit) : 10;
        
        const comparison = compareDecisions(symbol, limit);
        
        return reply.send({ ok: true, data: comparison });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  console.log('[Observability Routes] Registered:');
  console.log('  Logs:');
  console.log('    - GET /api/logs/decision');
  console.log('    - GET /api/logs/execution');
  console.log('    - GET /api/logs/metabrain');
  console.log('    - GET /api/logs/memory');
  console.log('    - GET /api/logs/tree');
  console.log('    - GET /api/logs/system');
  console.log('  Explain:');
  console.log('    - GET /api/decision/explain');
  console.log('    - GET /api/decision/explain/:id');
  console.log('    - GET /api/decision/factors');
  console.log('  Replay:');
  console.log('    - GET /api/replay/snapshots');
  console.log('    - GET /api/replay/decision/:id');
  console.log('    - POST /api/replay/simulate');
  console.log('    - GET /api/replay/compare');
}
