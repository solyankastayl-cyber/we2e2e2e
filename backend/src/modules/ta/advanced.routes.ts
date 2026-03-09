/**
 * Discovery, Stability, Scenario API Routes
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { createPatternDiscoveryEngine } from './discovery/pattern.discovery.js';
import { createSignalStabilityEngine } from './stability/stability.engine.js';
import { createScenarioSimulator, SimulationInput } from './scenario/scenario.simulator.js';

interface RouteOptions {
  db: Db;
}

export async function registerAdvancedRoutes(
  app: FastifyInstance,
  options: RouteOptions
): Promise<void> {
  const { db } = options;
  
  const discoveryEngine = createPatternDiscoveryEngine(db);
  const stabilityEngine = createSignalStabilityEngine(db);
  const scenarioSimulator = createScenarioSimulator();
  
  // ═══════════════════════════════════════════════════════════════
  // DISCOVERY (P2.1)
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * POST /api/ta/discovery/run-v2
   * Run pattern discovery session (shape-based)
   */
  app.post('/discovery/run-v2', async (
    request: FastifyRequest<{
      Body: {
        assets?: string[];
        timeframes?: string[];
        startDate?: string;
        endDate?: string;
      }
    }>
  ) => {
    const params = {
      assets: request.body?.assets || ['BTCUSDT', 'ETHUSDT'],
      timeframes: request.body?.timeframes || ['1d', '4h'],
      startDate: request.body?.startDate || '2020-01-01',
      endDate: request.body?.endDate || '2024-12-31',
    };
    
    try {
      const session = await discoveryEngine.runDiscovery(params);
      return { ok: true, session };
    } catch (err: any) {
      return { ok: false, error: err.message };
    }
  });
  
  /**
   * GET /api/ta/discovery/patterns-v2
   * Get discovered patterns (shape-based)
   */
  app.get('/discovery/patterns-v2', async (
    request: FastifyRequest<{
      Querystring: { status?: string }
    }>
  ) => {
    const patterns = await discoveryEngine.getDiscoveredPatterns(request.query.status);
    return { ok: true, patterns, count: patterns.length };
  });
  
  /**
   * POST /api/ta/discovery/register-v2/:patternId
   * Register a candidate pattern (shape-based)
   */
  app.post('/discovery/register-v2/:patternId', async (
    request: FastifyRequest<{
      Params: { patternId: string }
    }>
  ) => {
    const success = await discoveryEngine.registerPattern(request.params.patternId);
    return { ok: success };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // STABILITY (P2.7)
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * POST /api/ta/stability/recompute
   * Recompute all signal performance
   */
  app.post('/stability/recompute', async () => {
    const result = await stabilityEngine.recomputeAll();
    return { ok: true, ...result };
  });
  
  /**
   * GET /api/ta/stability/signals
   * Get all signals by status
   */
  app.get('/stability/signals', async (
    request: FastifyRequest<{
      Querystring: { status?: string }
    }>
  ) => {
    const signals = await stabilityEngine.getSignalsByStatus(request.query.status);
    return { ok: true, signals, count: signals.length };
  });
  
  /**
   * GET /api/ta/stability/degrading
   * Get degrading signals
   */
  app.get('/stability/degrading', async () => {
    const signals = await stabilityEngine.getDegradingSignals();
    return { ok: true, signals, count: signals.length };
  });
  
  /**
   * GET /api/ta/stability/multiplier
   * Get stability multiplier for a signal
   */
  app.get('/stability/multiplier', async (
    request: FastifyRequest<{
      Querystring: {
        pattern: string;
        asset: string;
        tf: string;
      }
    }>
  ) => {
    const { pattern, asset, tf } = request.query;
    
    if (!pattern || !asset || !tf) {
      return { ok: false, error: 'pattern, asset, tf required' };
    }
    
    const result = await stabilityEngine.getMultiplier(pattern, asset, tf);
    return { ok: true, ...result };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // SCENARIO SIMULATOR (P3.1)
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * POST /api/ta/scenario/simulate
   * Run Monte Carlo scenario simulation
   */
  app.post('/scenario/simulate', async (
    request: FastifyRequest<{
      Body: SimulationInput
    }>
  ) => {
    const input = request.body;
    
    if (!input.currentPrice || !input.entry || !input.stop || !input.target1 || !input.direction) {
      return { 
        ok: false, 
        error: 'currentPrice, entry, stop, target1, direction required' 
      };
    }
    
    const result = scenarioSimulator.simulate(input);
    return { ok: true, simulation: result };
  });
  
  /**
   * GET /api/ta/scenario/bands
   * Generate probability bands for projection
   */
  app.get('/scenario/bands', async (
    request: FastifyRequest<{
      Querystring: {
        price: string;
        volatility: string;
        bars?: string;
        regime?: string;
      }
    }>
  ) => {
    const { price, volatility, bars, regime } = request.query;
    
    if (!price || !volatility) {
      return { ok: false, error: 'price, volatility required' };
    }
    
    const bands = scenarioSimulator.generateProjectionBands(
      parseFloat(price),
      parseFloat(volatility),
      parseInt(bars || '30'),
      regime as 'LOW' | 'MEDIUM' | 'HIGH' | undefined
    );
    
    return { ok: true, bands };
  });
}
