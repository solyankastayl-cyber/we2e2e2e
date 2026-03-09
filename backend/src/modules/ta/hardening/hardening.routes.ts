/**
 * Decision Pipeline Hardening — API Routes
 * 
 * Audit trails, model registry, feature schema, deep health
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { getDecisionAuditService } from '../core/audit.service.js';
import { getModelRegistry } from '../core/model.registry.js';
import * as fs from 'fs';

interface RouteOptions {
  db: Db;
}

export async function registerHardeningRoutes(
  app: FastifyInstance,
  options: RouteOptions
): Promise<void> {
  const { db } = options;

  const auditService = getDecisionAuditService(db);
  const registry = getModelRegistry(db);

  // Init indexes on registration
  await auditService.ensureIndexes();
  await registry.ensureIndexes();

  // ═══════════════════════════════════════════════════════════════
  // PIPELINE AUDIT ROUTES (decision-level audit, separate from ta.controller audit)
  // ═══════════════════════════════════════════════════════════════

  /**
   * GET /pipeline/runs — list recent pipeline runs
   */
  app.get('/pipeline/runs', async (
    request: FastifyRequest<{ Querystring: { limit?: string } }>
  ) => {
    const limit = parseInt(request.query.limit || '50');
    const runs = await auditService.getRecentRuns(limit);
    return { ok: true, runs: runs.map(stripId), count: runs.length };
  });

  /**
   * GET /pipeline/run/:runId — get specific pipeline run
   */
  app.get('/pipeline/run/:runId', async (
    request: FastifyRequest<{ Params: { runId: string } }>
  ) => {
    const run = await auditService.getRun(request.params.runId);
    if (!run) return { ok: false, error: 'Run not found' };
    return { ok: true, run: stripId(run) };
  });

  /**
   * GET /pipeline/trail/:runId — full audit trail for a run
   */
  app.get('/pipeline/trail/:runId', async (
    request: FastifyRequest<{ Params: { runId: string } }>
  ) => {
    const trail = await auditService.getAuditTrail(request.params.runId);
    return { ok: true, trail: trail.map(stripId), layers: trail.length };
  });

  /**
   * GET /pipeline/decision/:runId — get stored decision for a run
   */
  app.get('/pipeline/decision/:runId', async (
    request: FastifyRequest<{ Params: { runId: string } }>
  ) => {
    const decision = await auditService.getDecision(request.params.runId);
    if (!decision) return { ok: false, error: 'Decision not found' };
    return { ok: true, decision: stripId(decision) };
  });

  // ═══════════════════════════════════════════════════════════════
  // MODEL REGISTRY ROUTES
  // ═══════════════════════════════════════════════════════════════

  /**
   * GET /registry/models — all registered models
   */
  app.get('/registry/models', async () => {
    const models = await registry.getAllModels();
    return { ok: true, models: models.map(stripId), count: models.length };
  });

  /**
   * GET /registry/models/active — active models by type
   */
  app.get('/registry/models/active', async () => {
    const entry = await registry.getActiveModel('entry');
    const r = await registry.getActiveModel('r');
    const regime = await registry.getActiveModel('regime');
    return {
      ok: true,
      active: {
        entry: entry ? stripId(entry) : null,
        r: r ? stripId(r) : null,
        regime: regime ? stripId(regime) : null,
      },
    };
  });

  /**
   * POST /registry/models/register — register a new model
   */
  app.post('/registry/models/register', async (
    request: FastifyRequest<{
      Body: {
        modelId: string;
        name: string;
        type: 'entry' | 'r' | 'regime';
        version: string;
        stage: string;
        artifactPath: string;
        metrics: Record<string, number>;
        trainingInfo: {
          datasetSize: number;
          trainRows: number;
          valRows: number;
          testRows: number;
          trainPeriod: { from: string; to: string };
          features: string[];
        };
      }
    }>
  ) => {
    const body = request.body;
    if (!body.modelId || !body.type || !body.version) {
      return { ok: false, error: 'modelId, type, version required' };
    }

    const id = await registry.registerModel({
      modelId: body.modelId,
      name: body.name || body.modelId,
      type: body.type,
      version: body.version,
      stage: (body.stage || 'SHADOW') as any,
      artifactPath: body.artifactPath || '',
      metrics: body.metrics || {},
      trainingInfo: body.trainingInfo || {
        datasetSize: 0, trainRows: 0, valRows: 0, testRows: 0,
        trainPeriod: { from: '', to: '' }, features: [],
      },
    });

    return { ok: true, modelId: id };
  });

  /**
   * POST /registry/models/:modelId/promote — promote model stage
   */
  app.post('/registry/models/:modelId/promote', async (
    request: FastifyRequest<{
      Params: { modelId: string };
      Body: { stage: string };
    }>
  ) => {
    const stage = request.body?.stage;
    if (!stage) return { ok: false, error: 'stage required' };

    const success = await registry.promoteModel(request.params.modelId, stage as any);
    return { ok: success };
  });

  /**
   * POST /registry/models/:modelId/quality-gates — check quality gates
   */
  app.post('/registry/models/:modelId/quality-gates', async (
    request: FastifyRequest<{
      Params: { modelId: string };
      Body: { previousModelId?: string };
    }>
  ) => {
    const result = await registry.checkQualityGates(
      request.params.modelId,
      request.body?.previousModelId
    );
    return { ok: true, ...result };
  });

  // ═══════════════════════════════════════════════════════════════
  // FEATURE SCHEMA ROUTES
  // ═══════════════════════════════════════════════════════════════

  /**
   * GET /registry/schema — active feature schema
   */
  app.get('/registry/schema', async () => {
    const schema = await registry.getActiveSchema();
    return { ok: true, schema: schema ? stripId(schema) : null };
  });

  /**
   * POST /registry/schema/register — register new feature schema
   */
  app.post('/registry/schema/register', async (
    request: FastifyRequest<{
      Body: { version: string; features: string[] };
    }>
  ) => {
    const { version, features } = request.body || {};
    if (!version || !features?.length) {
      return { ok: false, error: 'version, features[] required' };
    }

    await registry.registerFeatureSchema(version, features);
    return { ok: true, version, featureCount: features.length };
  });

  /**
   * POST /registry/schema/validate — validate features against active schema
   */
  app.post('/registry/schema/validate', async (
    request: FastifyRequest<{
      Body: { features: Record<string, any> };
    }>
  ) => {
    const { features } = request.body || {};
    if (!features) return { ok: false, error: 'features object required' };

    const result = await registry.validateFeatures(features);
    return { ok: true, ...result };
  });

  // ═══════════════════════════════════════════════════════════════
  // DEEP HEALTH CHECK
  // ═══════════════════════════════════════════════════════════════

  /**
   * GET /health/deep — comprehensive pipeline health check
   */
  app.get('/health/deep', async () => {
    const checks: Record<string, { status: string; detail?: any }> = {};

    // 1. MongoDB
    try {
      const stats = await db.command({ ping: 1 });
      checks['mongodb'] = { status: 'ok', detail: { ping: stats.ok } };
    } catch (e: any) {
      checks['mongodb'] = { status: 'fail', detail: e.message };
    }

    // 2. Candles data
    try {
      const count = await db.collection('ta_candles').countDocuments();
      checks['candles'] = {
        status: count > 0 ? 'ok' : 'warn',
        detail: { count, collection: 'ta_candles' },
      };
    } catch (e: any) {
      checks['candles'] = { status: 'fail', detail: e.message };
    }

    // 3. ML Dataset
    try {
      const count = await db.collection('ta_ml_rows_v4').countDocuments();
      checks['dataset_v4'] = {
        status: count > 1000 ? 'ok' : 'warn',
        detail: { rows: count },
      };
    } catch (e: any) {
      checks['dataset_v4'] = { status: 'fail', detail: e.message };
    }

    // 4. ML Models
    const entryModelPath = '/app/ml_artifacts/entry_model/model.joblib';
    const rModelPath = '/app/ml_artifacts/r_model/model.joblib';
    checks['ml_models'] = {
      status: fs.existsSync(entryModelPath) && fs.existsSync(rModelPath) ? 'ok' : 'warn',
      detail: {
        entry: fs.existsSync(entryModelPath),
        r: fs.existsSync(rModelPath),
      },
    };

    // 5. Model Registry
    try {
      const activeEntry = await registry.getActiveModel('entry');
      const activeR = await registry.getActiveModel('r');
      checks['model_registry'] = {
        status: 'ok',
        detail: {
          entryModel: activeEntry?.modelId || 'none',
          rModel: activeR?.modelId || 'none',
        },
      };
    } catch (e: any) {
      checks['model_registry'] = { status: 'fail', detail: e.message };
    }

    // 6. Feature Schema
    try {
      const schema = await registry.getActiveSchema();
      checks['feature_schema'] = {
        status: schema ? 'ok' : 'warn',
        detail: schema
          ? { version: schema.version, features: schema.features.length }
          : { message: 'No active schema registered' },
      };
    } catch (e: any) {
      checks['feature_schema'] = { status: 'fail', detail: e.message };
    }

    // 7. Recent audit runs
    try {
      const runs = await auditService.getRecentRuns(1);
      const lastRun = runs[0];
      checks['audit'] = {
        status: 'ok',
        detail: {
          lastRun: lastRun ? {
            runId: lastRun.runId,
            status: lastRun.status,
            timestamp: lastRun.timestamp,
          } : 'no runs yet',
        },
      };
    } catch (e: any) {
      checks['audit'] = { status: 'fail', detail: e.message };
    }

    // 8. Quality scores
    try {
      const count = await db.collection('ta_pattern_quality').countDocuments();
      checks['quality_engine'] = {
        status: count > 0 ? 'ok' : 'warn',
        detail: { patterns: count },
      };
    } catch (e: any) {
      checks['quality_engine'] = { status: 'fail', detail: e.message };
    }

    const allOk = Object.values(checks).every(c => c.status === 'ok');
    const hasFailures = Object.values(checks).some(c => c.status === 'fail');

    return {
      ok: !hasFailures,
      status: allOk ? 'healthy' : hasFailures ? 'degraded' : 'partial',
      timestamp: new Date().toISOString(),
      checks,
    };
  });

  console.log('[Hardening Routes] Registered:');
  console.log('  - GET  /pipeline/runs');
  console.log('  - GET  /pipeline/run/:runId');
  console.log('  - GET  /pipeline/trail/:runId');
  console.log('  - GET  /pipeline/decision/:runId');
  console.log('  - GET  /registry/models');
  console.log('  - GET  /registry/models/active');
  console.log('  - POST /registry/models/register');
  console.log('  - POST /registry/models/:modelId/promote');
  console.log('  - POST /registry/models/:modelId/quality-gates');
  console.log('  - GET  /registry/schema');
  console.log('  - POST /registry/schema/register');
  console.log('  - POST /registry/schema/validate');
  console.log('  - GET  /health/deep');
}

/**
 * Strip MongoDB _id from objects
 */
function stripId(obj: any): any {
  if (!obj) return obj;
  const { _id, ...rest } = obj;
  return rest;
}
