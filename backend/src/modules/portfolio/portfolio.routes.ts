/**
 * Phase 5.5 — Portfolio Routes
 * ==============================
 * API endpoints for portfolio intelligence
 * 
 * GET  /api/portfolio/state       — Current portfolio state
 * GET  /api/portfolio/exposure    — Exposure by asset/sector
 * GET  /api/portfolio/correlation — Correlation matrix
 * GET  /api/portfolio/allocation  — Strategy allocation view
 * GET  /api/portfolio/risk        — Risk assessment
 * POST /api/portfolio/check       — Check if new position allowed
 * POST /api/portfolio/position    — Open position (testing)
 * DELETE /api/portfolio/position/:id — Close position
 */

import { FastifyInstance } from 'fastify';
import {
  getPortfolioState,
  getPositions,
  getPortfolioLimits,
  openPosition,
  closePosition,
  seedTestPositions,
} from './portfolio.state.js';
import { getExposureState, checkExposureLimit } from './portfolio.exposure.js';
import { buildCorrelationMatrix, checkCorrelationRisk } from './portfolio.correlation.js';
import { getPortfolioRisk, resetRiskTracking } from './portfolio.risk.js';
import { getAllocations } from '../strategy/strategy.service.js';
import { PositionCheckResult } from './portfolio.types.js';

// ═══════════════════════════════════════════════════════════════
// INTERNAL ROUTES (relative paths)
// ═══════════════════════════════════════════════════════════════

async function portfolioRoutes(app: FastifyInstance): Promise<void> {
  
  // ─────────────────────────────────────────────────────────────
  // PORTFOLIO STATE
  // ─────────────────────────────────────────────────────────────
  
  app.get('/state', async (request, reply) => {
    try {
      const state = getPortfolioState();
      
      return reply.send({
        ok: true,
        data: state,
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // EXPOSURE
  // ─────────────────────────────────────────────────────────────
  
  app.get('/exposure', async (request, reply) => {
    try {
      const exposure = getExposureState();
      
      return reply.send({
        ok: true,
        data: exposure,
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // CORRELATION
  // ─────────────────────────────────────────────────────────────
  
  app.get('/correlation', async (request, reply) => {
    try {
      const { period = '30d' } = request.query as { period?: string };
      const correlation = buildCorrelationMatrix(period);
      
      return reply.send({
        ok: true,
        data: correlation,
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // ALLOCATION
  // ─────────────────────────────────────────────────────────────
  
  app.get('/allocation', async (request, reply) => {
    try {
      const positions = getPositions();
      const state = getPortfolioState();
      const strategyAllocations = getAllocations();
      
      // Calculate actual allocation per strategy
      const byStrategy: Record<string, { positions: number; exposure: number; pnl: number }> = {};
      
      for (const pos of positions) {
        if (!byStrategy[pos.strategyId]) {
          byStrategy[pos.strategyId] = { positions: 0, exposure: 0, pnl: 0 };
        }
        byStrategy[pos.strategyId].positions += 1;
        byStrategy[pos.strategyId].exposure += pos.size * pos.currentPrice;
        byStrategy[pos.strategyId].pnl += pos.unrealizedPnl;
      }
      
      // Merge with strategy allocations
      const allocations = strategyAllocations.map(sa => {
        const actual = byStrategy[sa.strategyId] || { positions: 0, exposure: 0, pnl: 0 };
        const actualAllocation = state.totalValue > 0 
          ? actual.exposure / state.totalValue 
          : 0;
        
        return {
          strategyId: sa.strategyId,
          strategyName: sa.name,
          targetAllocation: sa.capitalWeight,
          actualAllocation: Math.round(actualAllocation * 10000) / 10000,
          deviation: Math.round((actualAllocation - sa.capitalWeight) * 10000) / 10000,
          positions: actual.positions,
          exposure: Math.round(actual.exposure * 100) / 100,
          pnl: Math.round(actual.pnl * 100) / 100,
        };
      });
      
      const totalAllocated = allocations.reduce((sum, a) => sum + a.actualAllocation, 0);
      const maxDeviation = Math.max(...allocations.map(a => Math.abs(a.deviation)));
      
      return reply.send({
        ok: true,
        data: {
          strategies: allocations,
          totalAllocated: Math.round(totalAllocated * 10000) / 10000,
          unallocated: Math.round((1 - totalAllocated) * 10000) / 10000,
          rebalanceNeeded: maxDeviation > 0.1,
          maxDeviation: Math.round(maxDeviation * 10000) / 10000,
          lastUpdated: Date.now(),
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // RISK
  // ─────────────────────────────────────────────────────────────
  
  app.get('/risk', async (request, reply) => {
    try {
      const risk = getPortfolioRisk();
      
      return reply.send({
        ok: true,
        data: risk,
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // POSITION CHECK
  // ─────────────────────────────────────────────────────────────
  
  app.post<{
    Body: {
      symbol: string;
      side: 'LONG' | 'SHORT';
      size: number;
      price: number;
      leverage?: number;
    }
  }>('/check', async (request, reply) => {
    try {
      const { symbol, side, size, price, leverage = 1 } = request.body;
      const state = getPortfolioState();
      const limits = getPortfolioLimits();
      const exposure = getExposureState();
      const risk = getPortfolioRisk();
      
      const marginRequired = (size * price) / leverage;
      
      // Run checks
      const checks = {
        positionLimit: state.positionCount < limits.maxPositions,
        leverageLimit: exposure.leverageRatio + (size * price / state.totalValue) <= limits.maxLeverage,
        exposureLimit: checkExposureLimit(symbol, size, side, price, limits.maxSingleAssetExposure).allowed,
        correlationLimit: !checkCorrelationRisk(limits.maxCorrelatedExposure).atRisk,
        drawdownLimit: risk.currentDrawdown < limits.maxDrawdown,
        marginAvailable: state.availableMargin >= marginRequired,
      };
      
      const allPassed = Object.values(checks).every(v => v);
      
      // Calculate suggested size if not fully allowed
      let suggestedSize: number | undefined;
      if (!allPassed && checks.marginAvailable) {
        const maxByExposure = state.totalValue * limits.maxSingleAssetExposure / price;
        const maxByLeverage = (limits.maxLeverage - exposure.leverageRatio) * state.totalValue / price;
        suggestedSize = Math.min(maxByExposure, maxByLeverage, size) * 0.9;
        if (suggestedSize < 0) suggestedSize = undefined;
      }
      
      const result: PositionCheckResult = {
        allowed: allPassed,
        reason: !allPassed ? Object.entries(checks).filter(([_, v]) => !v).map(([k]) => k).join(', ') : undefined,
        checks: {
          positionLimit: checks.positionLimit,
          leverageLimit: checks.leverageLimit,
          exposureLimit: checks.exposureLimit,
          correlationLimit: checks.correlationLimit,
          drawdownLimit: checks.drawdownLimit,
        },
        suggestedSize: suggestedSize ? Math.round(suggestedSize * 10000) / 10000 : undefined,
      };
      
      return reply.send({ ok: true, data: result });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // POSITION MANAGEMENT (for testing)
  // ─────────────────────────────────────────────────────────────
  
  app.post<{
    Body: {
      symbol: string;
      side: 'LONG' | 'SHORT';
      size: number;
      leverage?: number;
      strategyId?: string;
    }
  }>('/position', async (request, reply) => {
    try {
      const { symbol, side, size, leverage = 1, strategyId = 'manual' } = request.body;
      
      const position = openPosition(symbol, side, size, leverage, strategyId);
      
      return reply.status(201).send({
        ok: true,
        data: position,
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  app.delete<{ Params: { id: string } }>('/position/:id', async (request, reply) => {
    try {
      const result = closePosition(request.params.id);
      
      if (!result) {
        return reply.status(404).send({ ok: false, error: 'Position not found' });
      }
      
      return reply.send({
        ok: true,
        data: { closed: request.params.id, pnl: result.pnl },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // LIMITS
  // ─────────────────────────────────────────────────────────────
  
  app.get('/limits', async (request, reply) => {
    try {
      const limits = getPortfolioLimits();
      return reply.send({ ok: true, data: limits });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // RESET (for testing)
  // ─────────────────────────────────────────────────────────────
  
  app.post('/reset', async (request, reply) => {
    try {
      seedTestPositions();
      resetRiskTracking(100000);
      
      return reply.send({
        ok: true,
        data: { message: 'Portfolio reset to test state' },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
}

// ═══════════════════════════════════════════════════════════════
// PUBLIC REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerPortfolioRoutes(app: FastifyInstance): Promise<void> {
  await app.register(portfolioRoutes, { prefix: '/api/portfolio' });
  
  console.log('[Portfolio Intelligence] Routes registered at /api/portfolio:');
  console.log('  State:');
  console.log('    - GET  /api/portfolio/state');
  console.log('    - GET  /api/portfolio/limits');
  console.log('  Exposure:');
  console.log('    - GET  /api/portfolio/exposure');
  console.log('    - GET  /api/portfolio/correlation');
  console.log('    - GET  /api/portfolio/allocation');
  console.log('  Risk:');
  console.log('    - GET  /api/portfolio/risk');
  console.log('    - POST /api/portfolio/check');
  console.log('  Positions:');
  console.log('    - POST   /api/portfolio/position');
  console.log('    - DELETE /api/portfolio/position/:id');
  console.log('    - POST   /api/portfolio/reset');
}
