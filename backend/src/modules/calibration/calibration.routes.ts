/**
 * Phase 5.2 B4 — Calibration Routes
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { CalibrationTrainer, getCalibrationStorage } from './calibration.train.js';
import { getCalibrationService } from './calibration.service.js';
import { CalibrationTrainRequest } from './calibration.types.js';

interface RouteContext {
  db: Db;
}

export async function registerCalibrationRoutes(
  app: FastifyInstance,
  { db }: RouteContext
): Promise<void> {
  const service = getCalibrationService(db);
  const storage = getCalibrationStorage(db);
  await storage.ensureIndexes();

  // ─────────────────────────────────────────────────────────────
  // POST /train - Train new calibration model
  // ─────────────────────────────────────────────────────────────
  app.post('/train', async (request: FastifyRequest<{
    Body: CalibrationTrainRequest
  }>) => {
    const body = request.body || {};
    const trainer = new CalibrationTrainer(db);

    try {
      const model = await trainer.train(body);
      service.clearCache();  // Reload new model

      return {
        ok: true,
        modelId: model.modelId,
        version: model.version,
        sampleSize: model.sampleSize,
        metrics: model.metrics,
      };
    } catch (err: any) {
      return {
        ok: false,
        error: err.message,
      };
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /status - Get calibration model status
  // ─────────────────────────────────────────────────────────────
  app.get('/status', async () => {
    const status = await service.getStatus();
    return { ok: true, ...status };
  });

  // ─────────────────────────────────────────────────────────────
  // POST /apply - Apply calibration to probability
  // ─────────────────────────────────────────────────────────────
  app.post('/apply', async (request: FastifyRequest<{
    Body: { pRaw: number }
  }>) => {
    const { pRaw } = request.body || {};

    if (typeof pRaw !== 'number' || pRaw < 0 || pRaw > 1) {
      return { ok: false, error: 'pRaw must be a number between 0 and 1' };
    }

    const result = await service.calibrate(pRaw);
    return { ok: true, ...result };
  });

  // ─────────────────────────────────────────────────────────────
  // POST /apply/batch - Apply calibration to multiple probabilities
  // ─────────────────────────────────────────────────────────────
  app.post('/apply/batch', async (request: FastifyRequest<{
    Body: { pRaws: number[] }
  }>) => {
    const { pRaws } = request.body || {};

    if (!Array.isArray(pRaws)) {
      return { ok: false, error: 'pRaws must be an array' };
    }

    const results = await service.calibrateBatch(pRaws);
    return { ok: true, results };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /reliability - Get reliability buckets
  // ─────────────────────────────────────────────────────────────
  app.get('/reliability', async () => {
    const buckets = await service.getReliability();
    return { ok: true, buckets };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /models - List calibration models
  // ─────────────────────────────────────────────────────────────
  app.get('/models', async (request: FastifyRequest<{
    Querystring: { limit?: string }
  }>) => {
    const { limit } = request.query;
    const models = await storage.listModels(limit ? parseInt(limit, 10) : 10);

    return {
      ok: true,
      count: models.length,
      models: models.map(m => ({
        modelId: m.modelId,
        version: m.version,
        trainedAt: m.trainedAt,
        sampleSize: m.sampleSize,
        ece: m.metrics.ece,
        brier: m.metrics.brier,
      })),
    };
  });

  console.log('[Calibration] Routes registered: /train, /status, /apply, /reliability, /models');
}
