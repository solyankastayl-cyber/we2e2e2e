/**
 * P4.2-4.4 Routes
 * 
 * API endpoints for Probability, Explanation, and Forecast engines
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';

// P4.2: Probability
import { composeProbability, composeProbabilityDebug } from '../services/probability/probability.engine.js';
import { getProbabilityMetricsLogger } from '../services/probability/probability.metrics.js';
import { getCalibrationEngine } from '../services/probability/probability.calibration.js';

// P4.3: Explanation
import { buildExplanation, buildExplanationDebug } from '../services/explanation/explanation.engine.js';

// P4.4: Forecast
import { getForecastEngine } from '../services/forecast/forecast.engine.js';
import { getForecastStorage } from '../services/forecast/forecast.storage.js';

interface RouteOptions {
  db: Db;
}

export async function registerP4Routes(
  app: FastifyInstance,
  options: RouteOptions
): Promise<void> {
  const { db } = options;
  
  const metricsLogger = getProbabilityMetricsLogger(db);
  const calibrationEngine = getCalibrationEngine(db);
  const forecastEngine = getForecastEngine(db);
  const forecastStorage = getForecastStorage(db);
  
  // Init indexes
  await metricsLogger.ensureIndexes();
  await calibrationEngine.ensureIndexes();
  await forecastStorage.ensureIndexes();
  
  // ═══════════════════════════════════════════════════════════════
  // P4.2: PROBABILITY COMPOSITION
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * GET /probability/debug — debug probability composition
   */
  app.get('/probability/debug', async (
    request: FastifyRequest<{
      Querystring: {
        ml_p?: string;
        ml_r?: string;
        scenario_p?: string;
        scenario_p50?: string;
        prior_p?: string;
        prior_wr?: string;
        stability?: string;
      };
    }>
  ) => {
    const q = request.query;
    
    const result = composeProbabilityDebug({
      ml: q.ml_p ? {
        pEntry: parseFloat(q.ml_p),
        expectedR: parseFloat(q.ml_r || '1.5'),
        confidence: 0.7
      } : null,
      scenario: q.scenario_p ? {
        pTarget: parseFloat(q.scenario_p),
        pStop: 0.3,
        pTimeout: 0.2,
        p10: -1,
        p50: parseFloat(q.scenario_p50 || '1.5'),
        p90: 3
      } : null,
      priors: q.prior_p ? {
        pEntry: parseFloat(q.prior_p),
        winRate: parseFloat(q.prior_wr || q.prior_p),
        profitFactor: 1.2,
        sampleSize: 100
      } : null,
      stability: q.stability ? {
        multiplier: parseFloat(q.stability),
        pf30: 1.2,
        pf100: 1.3,
        degrading: parseFloat(q.stability) < 1.0
      } : null
    });
    
    return { ok: true, ...result };
  });
  
  /**
   * POST /probability/compose — compose probability from inputs
   */
  app.post('/probability/compose', async (
    request: FastifyRequest<{
      Body: {
        ml?: { pEntry: number; expectedR: number; confidence?: number; modelId?: string };
        scenario?: { pTarget: number; pStop: number; pTimeout: number; p10: number; p50: number; p90: number };
        priors?: { pEntry: number; winRate: number; profitFactor: number; sampleSize: number };
        stability?: { multiplier: number; pf30: number; pf100: number; degrading: boolean };
      };
    }>
  ) => {
    const body = request.body || {};
    
    const pack = composeProbability({
      ml: body.ml ? { ...body.ml, confidence: body.ml.confidence || 0.7 } : null,
      scenario: body.scenario || null,
      priors: body.priors || null,
      stability: body.stability || null
    });
    
    return { ok: true, pack };
  });
  
  /**
   * GET /probability/metrics — get probability metrics
   */
  app.get('/probability/metrics', async () => {
    const recent = await metricsLogger.getRecent(20);
    const avgWeights = await metricsLogger.getAverageWeights();
    const drift = await metricsLogger.getPredictionDrift();
    
    return {
      ok: true,
      recent: recent.length,
      avgWeights,
      drift
    };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // P4.3: EXPLANATION ENGINE
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * GET /explanation — get explanation for asset/tf
   */
  app.get('/explanation', async (
    request: FastifyRequest<{
      Querystring: { asset: string; tf: string };
    }>
  ) => {
    const { asset, tf } = request.query;
    
    if (!asset || !tf) {
      return { ok: false, error: 'Missing required: asset, tf' };
    }
    
    // Get latest decision data
    const decision = await db.collection('ta_decisions')
      .findOne({ asset: asset.toUpperCase(), timeframe: tf.toLowerCase() }, { sort: { timestamp: -1 } });
    
    const patterns = await db.collection('ta_patterns')
      .find({ runId: decision?.runId })
      .toArray();
    
    // Build explanation
    const explanation = buildExplanation({
      patterns: patterns.map(p => ({
        type: p.type || p.patternType || 'UNKNOWN',
        score: p.score || 0.5,
        direction: p.direction,
        confidence: p.confidence || 0.5
      })),
      ml: decision?.ml ? {
        pEntry: decision.ml.p_entry || 0.5,
        expectedR: decision.ml.expected_r || 1.5,
        contribution: 0.3
      } : undefined,
      scenario: decision?.topScenario ? {
        pTarget: decision.topScenario.probability || 0.5,
        p50: decision.topScenario.expectedR || 1.5,
        contribution: 0.3
      } : undefined,
      stability: {
        multiplier: 1.0,
        degrading: false
      }
    });
    
    return { ok: true, ...explanation };
  });
  
  /**
   * GET /explanation/debug — debug explanation with full breakdown
   */
  app.get('/explanation/debug', async (
    request: FastifyRequest<{
      Querystring: { asset: string; tf: string };
    }>
  ) => {
    const { asset, tf } = request.query;
    
    if (!asset || !tf) {
      return { ok: false, error: 'Missing required: asset, tf' };
    }
    
    // Get data
    const decision = await db.collection('ta_decisions')
      .findOne({ asset: asset.toUpperCase(), timeframe: tf.toLowerCase() }, { sort: { timestamp: -1 } });
    
    const patterns = await db.collection('ta_patterns')
      .find({ runId: decision?.runId })
      .toArray();
    
    const result = buildExplanationDebug({
      patterns: patterns.map(p => ({
        type: p.type || 'UNKNOWN',
        score: p.score || 0.5,
        direction: p.direction,
        confidence: p.confidence || 0.5
      })),
      ml: decision?.ml ? {
        pEntry: decision.ml.p_entry || 0.5,
        expectedR: decision.ml.expected_r || 1.5,
        contribution: 0.3
      } : undefined,
      scenario: decision?.topScenario ? {
        pTarget: decision.topScenario.probability || 0.5,
        p50: decision.topScenario.expectedR || 1.5,
        contribution: 0.3
      } : undefined
    });
    
    return { ok: true, ...result };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // P4.4: FORECAST ENGINE
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * GET /forecast — compute forecast for asset/tf
   */
  app.get('/forecast', async (
    request: FastifyRequest<{
      Querystring: { 
        asset: string; 
        tf: string;
        target?: string;
        stop?: string;
        patternType?: string;
      };
    }>
  ) => {
    const { asset, tf, target, stop, patternType } = request.query;
    
    if (!asset || !tf) {
      return { ok: false, error: 'Missing required: asset, tf' };
    }
    
    try {
      const pack = await forecastEngine.compute(asset, tf, {
        target: target ? parseFloat(target) : undefined,
        stop: stop ? parseFloat(stop) : undefined,
        patternType
      });
      
      return { ok: true, ...pack };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  
  /**
   * GET /forecast/latest — get latest forecast
   */
  app.get('/forecast/latest', async (
    request: FastifyRequest<{
      Querystring: { asset: string; tf: string };
    }>
  ) => {
    const { asset, tf } = request.query;
    
    if (!asset || !tf) {
      return { ok: false, error: 'Missing required: asset, tf' };
    }
    
    const pack = await forecastStorage.getLatest(asset, tf);
    
    if (!pack) {
      return { ok: false, error: 'No forecast found' };
    }
    
    return { ok: true, ...pack };
  });
  
  /**
   * GET /forecast/run/:runId — get specific forecast
   */
  app.get('/forecast/run/:runId', async (
    request: FastifyRequest<{
      Params: { runId: string };
    }>
  ) => {
    const pack = await forecastStorage.getByRunId(request.params.runId);
    
    if (!pack) {
      return { ok: false, error: 'Forecast not found' };
    }
    
    return { ok: true, ...pack };
  });
  
  /**
   * GET /forecast/history — get forecast history
   */
  app.get('/forecast/history', async (
    request: FastifyRequest<{
      Querystring: { asset: string; tf: string; limit?: string };
    }>
  ) => {
    const { asset, tf, limit } = request.query;
    
    if (!asset || !tf) {
      return { ok: false, error: 'Missing required: asset, tf' };
    }
    
    const history = await forecastStorage.getHistory(
      asset, 
      tf, 
      limit ? parseInt(limit) : 20
    );
    
    return {
      ok: true,
      count: history.length,
      history
    };
  });
  
  /**
   * GET /forecast/stats — forecast storage stats
   */
  app.get('/forecast/stats', async () => {
    const stats = await forecastStorage.getStats();
    return { ok: true, ...stats };
  });
  
  /**
   * GET /forecast/projector — debug projector path
   */
  app.get('/forecast/projector', async (
    request: FastifyRequest<{
      Querystring: {
        patternType: string;
        priceNow?: string;
        target?: string;
        breakoutLevel?: string;
      };
    }>
  ) => {
    const { patternType, priceNow, target, breakoutLevel } = request.query;
    
    if (!patternType) {
      return { ok: false, error: 'Missing required: patternType' };
    }
    
    const { buildProjectionPath } = await import('../services/forecast/forecast.projector.js');
    
    const result = buildProjectionPath({
      asset: 'DEBUG',
      timeframe: '1d',
      priceNow: priceNow ? parseFloat(priceNow) : 100,
      target: target ? parseFloat(target) : undefined,
      breakoutLevel: breakoutLevel ? parseFloat(breakoutLevel) : undefined,
      patternType,
      bias: 'LONG'
    });
    
    return {
      ok: true,
      patternType,
      method: result.method,
      pathLength: result.path.length,
      path: result.path
    };
  });
  
  console.log('[P4] Routes registered:');
  console.log('  [P4.2 Probability]');
  console.log('  - GET  /probability/debug');
  console.log('  - POST /probability/compose');
  console.log('  - GET  /probability/metrics');
  console.log('  [P4.3 Explanation]');
  console.log('  - GET  /explanation');
  console.log('  - GET  /explanation/debug');
  console.log('  [P4.4 Forecast]');
  console.log('  - GET  /forecast');
  console.log('  - GET  /forecast/latest');
  console.log('  - GET  /forecast/run/:runId');
  console.log('  - GET  /forecast/history');
  console.log('  - GET  /forecast/stats');
  console.log('  - GET  /forecast/projector');
}
