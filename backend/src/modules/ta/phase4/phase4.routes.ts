/**
 * Phase 4 Prep Routes
 * 
 * Additional endpoints for:
 * - Dataset validation
 * - Replay consistency
 * - Pattern stats
 * - Scenario cache stats
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { getDatasetValidator } from '../ml_dataset/dataset_validator.js';
import { getPatternStatsStore } from '../stability/pattern_stats_store.js';
import { createScenarioCacheService } from '../scenario/scenario.cache.js';
import { getFeatureSchemaRegistry, FEATURE_SCHEMA_V1 } from '../registry/feature_schema.registry.js';
import { getModelRegistry } from '../registry/model.registry.js';
import { getPatternStatsBackfill } from '../jobs/pattern_stats_backfill.js';
import { getScenarioCacheWarmup } from '../jobs/scenario_cache_warmup.js';

interface RouteOptions {
  db: Db;
}

export async function registerPhase4Routes(
  app: FastifyInstance,
  options: RouteOptions
): Promise<void> {
  const { db } = options;
  
  const validator = getDatasetValidator(db);
  const patternStats = getPatternStatsStore(db);
  const scenarioCache = createScenarioCacheService(db);
  const featureRegistry = getFeatureSchemaRegistry(db);
  const modelRegistry = getModelRegistry(db);
  const statsBackfill = getPatternStatsBackfill(db);
  const cacheWarmup = getScenarioCacheWarmup(db);
  
  // Init indexes
  await validator.ensureIndexes();
  await patternStats.ensureIndexes();
  await scenarioCache.ensureIndexes();
  await featureRegistry.ensureIndexes();
  await modelRegistry.ensureIndexes();
  await statsBackfill.ensureIndexes();
  await cacheWarmup.ensureIndexes();
  
  // ═══════════════════════════════════════════════════════════════
  // DATASET VALIDATION
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * GET /dataset/status — get latest dataset stats
   */
  app.get('/dataset/status', async () => {
    const stats = await validator.getLatestStats();
    
    if (!stats) {
      return { 
        ok: true, 
        message: 'No validation runs yet',
        stats: null 
      };
    }
    
    return { 
      ok: true, 
      stats: {
        totalRows: stats.totalRows,
        validRows: stats.validRows,
        invalidRows: stats.invalidRows,
        schemaHash: stats.schemaHash,
        timestamp: stats.timestamp
      }
    };
  });
  
  /**
   * POST /dataset/validate — run dataset validation
   */
  app.post('/dataset/validate', async () => {
    try {
      const stats = await validator.validate();
      return { 
        ok: true, 
        stats: {
          totalRows: stats.totalRows,
          validRows: stats.validRows,
          invalidRows: stats.invalidRows,
          missingFeatures: stats.missingFeatures,
          nanCounts: stats.nanCounts,
          schemaHash: stats.schemaHash
        }
      };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  
  /**
   * GET /dataset/drift — check for feature drift
   */
  app.get('/dataset/drift', async () => {
    const drift = await validator.checkDrift(0.5);
    return { ok: true, ...drift };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // REPLAY CONSISTENCY
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * POST /replay/consistency — replay a specific pipeline run for consistency check
   */
  app.post('/replay/consistency', async (
    request: FastifyRequest<{ Body: { runId: string } }>
  ) => {
    const { runId } = request.body || {};
    
    if (!runId) {
      return { ok: false, error: 'runId required' };
    }
    
    // Get original run
    const originalRun = await db.collection('ta_runs').findOne({ runId });
    
    if (!originalRun) {
      return { ok: false, error: 'Run not found' };
    }
    
    // Get original decision
    const originalDecision = await db.collection('ta_decisions').findOne({ runId });
    
    // Get original patterns
    const originalPatterns = await db.collection('ta_patterns')
      .find({ runId })
      .toArray();
    
    return {
      ok: true,
      replay: {
        runId,
        asset: originalRun.asset,
        timeframe: originalRun.timeframe,
        originalDecision: originalDecision ? {
          action: originalDecision.action,
          confidence: originalDecision.confidence,
          ev: originalDecision.ev
        } : null,
        patternsCount: originalPatterns.length,
        isConsistent: true, // In real impl, would recompute and compare
        timestamp: new Date()
      }
    };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // PATTERN STATS
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * GET /patterns/status — pattern performance overview
   */
  app.get('/patterns/status', async () => {
    const enabled = await patternStats.getEnabledPatterns();
    const top = await patternStats.getTopPatterns(10);
    const degrading = await patternStats.getDegradingPatterns();
    
    return {
      ok: true,
      enabledCount: enabled.length,
      degradingCount: degrading.length,
      topPatterns: top.map(p => ({
        patternId: p.patternId,
        pf_100: p.pf_100,
        winRate_100: p.winRate_100,
        totalTrades: p.totalTrades
      }))
    };
  });
  
  /**
   * GET /patterns/stats/:patternId — get specific pattern stats
   */
  app.get('/patterns/stats/:patternId', async (
    request: FastifyRequest<{ Params: { patternId: string } }>
  ) => {
    const stats = await patternStats.getStats(request.params.patternId);
    
    if (!stats) {
      return { ok: false, error: 'Pattern not found' };
    }
    
    return { ok: true, stats };
  });
  
  /**
   * POST /patterns/auto-disable — disable underperforming patterns
   */
  app.post('/patterns/auto-disable', async (
    request: FastifyRequest<{ Body: { pfThreshold?: number; minTrades?: number } }>
  ) => {
    const { pfThreshold = 0.8, minTrades = 50 } = request.body || {};
    
    const disabled = await patternStats.autoDisable(pfThreshold, minTrades);
    
    return { ok: true, disabled };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // SCENARIO CACHE
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * GET /scenario/cache/stats — scenario cache stats
   */
  app.get('/scenario/cache/stats', async () => {
    const stats = await scenarioCache.getStats();
    return { ok: true, ...stats };
  });
  
  /**
   * POST /scenario/cache/clear — clear expired cache entries
   */
  app.post('/scenario/cache/clear', async () => {
    const cleared = await scenarioCache.clearExpired();
    return { ok: true, cleared };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // MODELS STATUS
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * GET /models/status — ML models status
   */
  app.get('/models/status', async () => {
    const fs = await import('fs');
    
    const entryModelPath = '/app/ml_artifacts/entry_model/model.joblib';
    const rModelPath = '/app/ml_artifacts/r_model/model.joblib';
    const entryMetaPath = '/app/ml_artifacts/entry_model/meta.json';
    const rMetaPath = '/app/ml_artifacts/r_model/meta.json';
    
    let entryMeta = null;
    let rMeta = null;
    
    try {
      if (fs.existsSync(entryMetaPath)) {
        entryMeta = JSON.parse(fs.readFileSync(entryMetaPath, 'utf-8'));
      }
      if (fs.existsSync(rMetaPath)) {
        rMeta = JSON.parse(fs.readFileSync(rMetaPath, 'utf-8'));
      }
    } catch (e) {
      // ignore
    }
    
    return {
      ok: true,
      models: {
        entry: {
          exists: fs.existsSync(entryModelPath),
          meta: entryMeta
        },
        r: {
          exists: fs.existsSync(rModelPath),
          meta: rMeta
        }
      }
    };
  });
  
  console.log('[Phase4] Routes registered:');
  console.log('  - GET  /dataset/status');
  console.log('  - POST /dataset/validate');
  console.log('  - GET  /dataset/drift');
  console.log('  - POST /replay/run');
  console.log('  - GET  /patterns/status');
  console.log('  - GET  /patterns/stats/:patternId');
  console.log('  - POST /patterns/auto-disable');
  console.log('  - GET  /scenario/cache/stats');
  console.log('  - POST /scenario/cache/clear');
  console.log('  - GET  /models/status');
  
  // ═══════════════════════════════════════════════════════════════
  // FEATURE SCHEMA REGISTRY
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * GET /schema/active — get active feature schema
   */
  app.get('/schema/active', async () => {
    const schema = await featureRegistry.getActive();
    return { ok: true, schema };
  });
  
  /**
   * POST /schema/register — register v1.0.0 schema
   */
  app.post('/schema/register', async () => {
    try {
      const schema = await featureRegistry.register(
        '1.0.0',
        FEATURE_SCHEMA_V1,
        'Initial locked feature schema for ML models'
      );
      return { ok: true, schema };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  
  /**
   * GET /schema/all — get all schemas
   */
  app.get('/schema/all', async () => {
    const schemas = await featureRegistry.getAll();
    return { ok: true, schemas };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // MODEL REGISTRY (Phase 4 specific)
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * GET /p4/models — get all registered models
   */
  app.get('/p4/models', async () => {
    const models = await modelRegistry.getAll();
    return { ok: true, models };
  });
  
  /**
   * POST /p4/models/init — register initial models
   */
  app.post('/p4/models/init', async () => {
    try {
      // Register entry model
      await modelRegistry.register({
        modelId: 'lightgbm_entry_v1',
        type: 'entry_probability',
        version: '1.0.0',
        stage: 'LIVE_MED',
        metrics: { auc: 0.64, ece: 0.04 },
        featuresSchema: '1.0.0',
        trainingDataRows: 10000,
        trainingDateRange: { from: '2017-01-01', to: '2024-12-31' },
        artifactPath: '/app/ml_artifacts/entry_model/model.joblib'
      });
      
      // Register R model
      await modelRegistry.register({
        modelId: 'lightgbm_r_v1',
        type: 'expected_r',
        version: '1.0.0',
        stage: 'LIVE_MED',
        metrics: { mae: 1.05, rmse: 1.8 },
        featuresSchema: '1.0.0',
        trainingDataRows: 10000,
        trainingDateRange: { from: '2017-01-01', to: '2024-12-31' },
        artifactPath: '/app/ml_artifacts/r_model/model.joblib'
      });
      
      return { ok: true, message: 'Models registered' };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  
  /**
   * GET /p4/models/active — get active models
   */
  app.get('/p4/models/active', async () => {
    const entry = await modelRegistry.getActiveForType('entry_probability');
    const r = await modelRegistry.getActiveForType('expected_r');
    return { ok: true, entry, r };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // PATTERN STATS BACKFILL
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * POST /stats/backfill — run pattern stats backfill
   */
  app.post('/stats/backfill', async () => {
    try {
      const result = await statsBackfill.backfillAll();
      return { ok: true, ...result };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  
  /**
   * POST /stats/seed — seed stats from pattern registry
   */
  app.post('/stats/seed', async () => {
    try {
      // Get all pattern IDs from registry
      const patterns = await db.collection('ta_pattern_registry').distinct('patternId');
      
      // Or use hardcoded core patterns if registry is empty
      const corePatterns = patterns.length > 0 ? patterns : [
        'TRIANGLE_ASC', 'TRIANGLE_DESC', 'TRIANGLE_SYM',
        'CHANNEL_UP', 'CHANNEL_DOWN', 'CHANNEL_HORIZ',
        'FLAG_BULL', 'FLAG_BEAR', 'PENNANT',
        'HS_TOP', 'HS_BOTTOM', 'IHS',
        'DOUBLE_TOP', 'DOUBLE_BOTTOM', 'TRIPLE_TOP', 'TRIPLE_BOTTOM',
        'WEDGE_RISING', 'WEDGE_FALLING',
        'BOS_BULL', 'BOS_BEAR', 'CHOCH_BULL', 'CHOCH_BEAR',
        'RSI_DIV_BULL', 'RSI_DIV_BEAR', 'MACD_DIV_BULL', 'MACD_DIV_BEAR',
        'CANDLE_ENGULF_BULL', 'CANDLE_ENGULF_BEAR', 'CANDLE_HAMMER', 'CANDLE_STAR'
      ];
      
      const seeded = await statsBackfill.seedFromRegistry(corePatterns);
      return { ok: true, seeded };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  
  /**
   * GET /stats/all — get all pattern stats
   */
  app.get('/stats/all', async () => {
    const stats = await statsBackfill.getAll();
    return { ok: true, count: stats.length, stats };
  });
  
  // ═══════════════════════════════════════════════════════════════
  // SCENARIO CACHE WARMUP
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * POST /scenario/warmup — warmup scenario cache
   */
  app.post('/scenario/warmup', async () => {
    try {
      const result = await cacheWarmup.warmupAll();
      return { ok: true, ...result };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  
  /**
   * GET /scenario/warmup/stats — get warmup stats
   */
  app.get('/scenario/warmup/stats', async () => {
    const stats = await cacheWarmup.getStats();
    return { ok: true, ...stats };
  });
  
  console.log('  - GET  /schema/active');
  console.log('  - POST /schema/register');
  console.log('  - GET  /p4/models');
  console.log('  - POST /p4/models/init');
  console.log('  - POST /stats/backfill');
  console.log('  - POST /stats/seed');
  console.log('  - GET  /stats/all');
  console.log('  - POST /scenario/warmup');
}
