/**
 * P1.3-P1.5 — ML V4 API Routes
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';
import {
  buildDatasetV4,
  createDatasetV4Storage,
  createDatasetV4Indexes,
} from './dataset_v4.builder.js';
import { 
  DEFAULT_DATASET_V4_CONFIG,
  DatasetV4Config 
} from './labels_v4.types.js';
import { getLabelStats } from './labels_v4.builder.js';
import { getSplitBoundaries } from './time_split.js';
import {
  detectRegime,
  calculateRegimeFeatures,
  DEFAULT_REGIME_CONFIG,
  RegimeFeatures,
} from './regime_mixture.js';
import {
  createEVPredictor,
  calculateActualEV,
  evaluateEVPredictions,
} from './ev_predictor.js';

export async function registerMLV4Routes(
  app: FastifyInstance,
  opts: { db: Db }
): Promise<void> {
  await createDatasetV4Indexes(opts.db);
  
  const storage = createDatasetV4Storage(opts.db);
  const evPredictor = createEVPredictor(opts.db);

  // GET /ml_v4/status
  app.get('/ml_v4/status', async () => {
    const stats = await storage.getStats();
    const splitBounds = getSplitBoundaries();
    
    return {
      ok: true,
      version: '4.0',
      features: ['Labels V4 (EV decomposition)', 'Time-based split with purging', 'Regime mixture'],
      stats,
      splitBoundaries: splitBounds,
    };
  });

  // POST /ml_v4/dataset/build
  app.post('/ml_v4/dataset/build', async (req) => {
    const customConfig = req.body as Partial<DatasetV4Config>;
    const config = { ...DEFAULT_DATASET_V4_CONFIG, ...customConfig };
    
    const result = await buildDatasetV4(opts.db, config);
    return result;
  });

  // GET /ml_v4/dataset/stats
  app.get('/ml_v4/dataset/stats', async () => {
    const stats = await storage.getStats();
    return stats;
  });

  // GET /ml_v4/dataset/split_info
  app.get('/ml_v4/dataset/split_info', async () => {
    const stats = await storage.getStats();
    const bounds = getSplitBoundaries();
    
    return {
      boundaries: bounds,
      counts: {
        train: stats.trainRows,
        val: stats.valRows,
        test: stats.testRows,
      },
      purgeWindow: bounds.purgeWindow,
    };
  });

  // GET /ml_v4/dataset/train
  app.get('/ml_v4/dataset/train', async (req) => {
    const { limit } = req.query as { limit?: string };
    const rows = await storage.getRows({ split: 'train', limit: parseInt(limit || '1000') });
    return { rows, count: rows.length };
  });

  // GET /ml_v4/dataset/val
  app.get('/ml_v4/dataset/val', async (req) => {
    const { limit } = req.query as { limit?: string };
    const rows = await storage.getRows({ split: 'val', limit: parseInt(limit || '1000') });
    return { rows, count: rows.length };
  });

  // GET /ml_v4/dataset/test
  app.get('/ml_v4/dataset/test', async (req) => {
    const { limit } = req.query as { limit?: string };
    const rows = await storage.getRows({ split: 'test', limit: parseInt(limit || '1000') });
    return { rows, count: rows.length };
  });

  // POST /ml_v4/regime/detect
  app.post('/ml_v4/regime/detect', async (req, reply) => {
    const features = req.body as RegimeFeatures;
    
    if (!features || features.adx === undefined) {
      return reply.code(400).send({ error: 'RegimeFeatures required' });
    }
    
    const result = detectRegime(features, DEFAULT_REGIME_CONFIG);
    return result;
  });

  // POST /ml_v4/regime/calculate_features
  app.post('/ml_v4/regime/calculate_features', async (req, reply) => {
    const { closes, highs, lows, atr } = req.body as {
      closes: number[];
      highs: number[];
      lows: number[];
      atr: number;
    };
    
    if (!closes || !highs || !lows || closes.length < 50) {
      return reply.code(400).send({ error: 'Need at least 50 candles' });
    }
    
    const features = calculateRegimeFeatures(closes, highs, lows, atr);
    const regime = detectRegime(features);
    
    return { features, regime };
  });

  // POST /ml_v4/predict
  app.post('/ml_v4/predict', async (req, reply) => {
    const { features, regime } = req.body as {
      features: Record<string, number>;
      regime?: string;
    };
    
    if (!features) {
      return reply.code(400).send({ error: 'features required' });
    }
    
    const prediction = evPredictor.predict(features, regime as any);
    return prediction;
  });

  // POST /ml_v4/predict/batch
  app.post('/ml_v4/predict/batch', async (req, reply) => {
    const { scenarioIds } = req.body as { scenarioIds: string[] };
    
    if (!scenarioIds?.length) {
      return reply.code(400).send({ error: 'scenarioIds array required' });
    }
    
    // Get dataset rows for these scenarios
    const rows = await opts.db.collection('ta_ml_dataset_v4')
      .find({ scenarioId: { $in: scenarioIds } })
      .toArray();
    
    const predictions = evPredictor.predictBatch(rows as any[]);
    
    return {
      predictions: predictions.map((p, i) => ({
        scenarioId: scenarioIds[i],
        ...p,
      })),
    };
  });

  // GET /ml_v4/metrics
  app.get('/ml_v4/metrics', async () => {
    const metrics = evPredictor.getMetrics();
    return metrics;
  });

  // POST /ml_v4/evaluate
  app.post('/ml_v4/evaluate', async (req) => {
    const { split } = req.body as { split?: 'train' | 'val' | 'test' };
    
    // Get rows for evaluation
    const rows = await storage.getRows({ split: split || 'val' });
    
    if (rows.length === 0) {
      return { error: 'No data for evaluation' };
    }
    
    // Get predictions
    const predictions = evPredictor.predictBatch(rows);
    
    // Evaluate
    const evaluation = evaluateEVPredictions(predictions, rows);
    const actualEV = calculateActualEV(rows);
    const labelStats = getLabelStats(rows.map(r => r.labels));
    
    return {
      split: split || 'val',
      rowCount: rows.length,
      actualEV,
      evaluation,
      labelStats,
    };
  });

  // DELETE /ml_v4/dataset/clear
  app.delete('/ml_v4/dataset/clear', async () => {
    await storage.clear();
    return { ok: true, message: 'Dataset V4 cleared' };
  });
}
