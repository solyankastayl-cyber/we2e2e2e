/**
 * Phase 5 — Strategy Platform Routes
 * ====================================
 * 
 * List & CRUD:
 *   GET  /api/strategy/list        — All strategies
 *   GET  /api/strategy/:id         — Single strategy
 *   POST /api/strategy/create      — Create custom strategy
 *   POST /api/strategy/activate    — Enable strategy
 *   POST /api/strategy/deactivate  — Disable strategy
 * 
 * Allocation:
 *   GET  /api/strategy/allocation  — Capital allocation
 *   POST /api/strategy/allocation  — Set allocation
 * 
 * Performance:
 *   GET  /api/strategy/performance — Performance summary
 * 
 * Backtest:
 *   POST /api/strategy/backtest    — Run backtest
 *   GET  /api/strategy/compare     — Compare strategies
 * 
 * Filter:
 *   POST /api/strategy/filter      — Test strategy filter on decision
 */

import { FastifyInstance } from 'fastify';
import {
  getAllStrategies,
  getStrategy,
  createStrategy,
  activateStrategy,
  deactivateStrategy,
  deleteStrategy,
  getAllocations,
  setAllocation,
  rebalanceAllocations,
  getPerformanceSummary,
  getStrategyStats,
} from './strategy.service.js';
import { runBacktest, compareStrategies, getRecentBacktests } from './strategy.backtest.js';
import { applyStrategyFilter, getMatchingSummary } from './strategy.filter.js';
import { DecisionInput, BacktestRequest, StrategyConditions, StrategyRisk } from './strategy.types.js';

// ═══════════════════════════════════════════════════════════════
// INTERNAL ROUTES (relative paths)
// ═══════════════════════════════════════════════════════════════

async function strategyRoutes(app: FastifyInstance): Promise<void> {
  
  // ─────────────────────────────────────────────────────────────
  // LIST & CRUD
  // ─────────────────────────────────────────────────────────────
  
  app.get('/list', async (request, reply) => {
    try {
      const strategies = getAllStrategies();
      const stats = getStrategyStats();
      
      return reply.send({
        ok: true,
        data: { strategies, stats },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  app.get<{ Params: { id: string } }>('/:id', async (request, reply) => {
    try {
      const strategy = getStrategy(request.params.id);
      
      if (!strategy) {
        return reply.status(404).send({ ok: false, error: 'Strategy not found' });
      }
      
      return reply.send({ ok: true, data: strategy });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  app.post<{
    Body: {
      name: string;
      description: string;
      conditions: StrategyConditions;
      risk: StrategyRisk;
      allocation: number;
    }
  }>('/create', async (request, reply) => {
    try {
      const { name, description, conditions, risk, allocation } = request.body;
      
      const strategy = createStrategy(name, description, conditions, risk, allocation);
      
      return reply.status(201).send({ ok: true, data: strategy });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  app.post<{ Body: { strategyId: string } }>('/activate', async (request, reply) => {
    try {
      const success = activateStrategy(request.body.strategyId);
      
      if (!success) {
        return reply.status(404).send({ ok: false, error: 'Strategy not found' });
      }
      
      return reply.send({ ok: true, data: { activated: request.body.strategyId } });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  app.post<{ Body: { strategyId: string } }>('/deactivate', async (request, reply) => {
    try {
      const success = deactivateStrategy(request.body.strategyId);
      
      if (!success) {
        return reply.status(404).send({ ok: false, error: 'Strategy not found' });
      }
      
      return reply.send({ ok: true, data: { deactivated: request.body.strategyId } });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  app.delete<{ Params: { id: string } }>('/:id', async (request, reply) => {
    try {
      const success = deleteStrategy(request.params.id);
      
      if (!success) {
        return reply.status(400).send({ ok: false, error: 'Cannot delete registry strategy' });
      }
      
      return reply.send({ ok: true, data: { deleted: request.params.id } });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // ALLOCATION
  // ─────────────────────────────────────────────────────────────
  
  app.get('/allocation', async (request, reply) => {
    try {
      const allocations = getAllocations();
      const stats = getStrategyStats();
      
      return reply.send({
        ok: true,
        data: {
          allocations,
          totalAllocation: stats.totalAllocation,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  app.post<{ Body: { strategyId: string; allocation: number } }>(
    '/allocation',
    async (request, reply) => {
      try {
        const { strategyId, allocation } = request.body;
        
        const success = setAllocation(strategyId, allocation);
        
        if (!success) {
          return reply.status(400).send({ ok: false, error: 'Invalid allocation' });
        }
        
        return reply.send({ ok: true, data: { strategyId, allocation } });
      } catch (err: any) {
        return reply.status(500).send({ ok: false, error: err.message });
      }
    }
  );
  
  app.post('/rebalance', async (request, reply) => {
    try {
      rebalanceAllocations();
      const allocations = getAllocations();
      
      return reply.send({ ok: true, data: { allocations } });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // PERFORMANCE
  // ─────────────────────────────────────────────────────────────
  
  app.get('/performance', async (request, reply) => {
    try {
      const summary = getPerformanceSummary();
      
      return reply.send({ ok: true, data: summary });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // BACKTEST
  // ─────────────────────────────────────────────────────────────
  
  app.post<{ Body: BacktestRequest }>('/backtest', async (request, reply) => {
    try {
      const result = await runBacktest(request.body);
      
      return reply.send({ ok: true, data: result });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  app.get('/backtests', async (request, reply) => {
    try {
      const results = getRecentBacktests();
      
      return reply.send({ ok: true, data: { backtests: results } });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  app.post<{
    Body: {
      strategyIds: string[];
      symbol: string;
      startDate: string;
      endDate: string;
    }
  }>('/compare', async (request, reply) => {
    try {
      const { strategyIds, symbol, startDate, endDate } = request.body;
      
      const comparison = await compareStrategies(strategyIds, symbol, startDate, endDate);
      
      return reply.send({ ok: true, data: { comparison } });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // FILTER TEST
  // ─────────────────────────────────────────────────────────────
  
  app.post<{ Body: DecisionInput }>('/filter', async (request, reply) => {
    try {
      const result = applyStrategyFilter(request.body);
      const summary = getMatchingSummary(request.body);
      
      return reply.send({
        ok: true,
        data: { ...result, summary },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
}

// ═══════════════════════════════════════════════════════════════
// PUBLIC REGISTRATION (with prefix)
// ═══════════════════════════════════════════════════════════════

export async function registerStrategyRoutes(app: FastifyInstance): Promise<void> {
  await app.register(strategyRoutes, { prefix: '/api/strategy' });
  
  console.log('[Strategy Platform] Routes registered at /api/strategy:');
  console.log('  List & CRUD:');
  console.log('    - GET  /api/strategy/list');
  console.log('    - GET  /api/strategy/:id');
  console.log('    - POST /api/strategy/create');
  console.log('    - POST /api/strategy/activate');
  console.log('    - POST /api/strategy/deactivate');
  console.log('    - DELETE /api/strategy/:id');
  console.log('  Allocation:');
  console.log('    - GET  /api/strategy/allocation');
  console.log('    - POST /api/strategy/allocation');
  console.log('    - POST /api/strategy/rebalance');
  console.log('  Performance & Backtest:');
  console.log('    - GET  /api/strategy/performance');
  console.log('    - POST /api/strategy/backtest');
  console.log('    - GET  /api/strategy/backtests');
  console.log('    - POST /api/strategy/compare');
  console.log('    - POST /api/strategy/filter');
}
