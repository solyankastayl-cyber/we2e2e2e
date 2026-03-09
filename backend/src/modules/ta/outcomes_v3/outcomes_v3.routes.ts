/**
 * Phase 8.3 + P5.0.9 — Outcomes V3 API Routes
 * 
 * P5.0.9 additions:
 * - GET /outcomes_v3/coverage - Check candle coverage
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';
import { 
  createOutcomesV3Storage, 
  createOutcomesV3Indexes 
} from './outcomes_v3.storage.js';
import { evaluateOutcomeV3, evaluateOutcomesV3Batch } from './labels_v3.evaluator.js';
import { EvalInputsV3, DEFAULT_THRESHOLDS } from './labels_v3.types.js';
import { runOutcomesBackfillJob, getBackfillStatus } from './labels_v3.job.js';
import { createMLDatasetV3Storage, createMLDatasetV3Indexes } from './ml_dataset_v3.js';
import { checkCandleCoverage, checkAllCoverage } from './outcomes_coverage.js';

export async function registerOutcomesV3Routes(
  app: FastifyInstance, 
  opts: { db: Db }
): Promise<void> {
  const storage = createOutcomesV3Storage(opts.db);
  const datasetStorage = createMLDatasetV3Storage(opts.db);

  // Create indexes on startup
  await createOutcomesV3Indexes(opts.db);
  await createMLDatasetV3Indexes(opts.db);

  // GET /outcomes_v3/latest
  app.get('/outcomes_v3/latest', async (req, reply) => {
    const { asset, timeframe, limit } = req.query as {
      asset?: string;
      timeframe?: string;
      limit?: string;
    };

    if (!asset || !timeframe) {
      return reply.code(400).send({ error: 'asset and timeframe required' });
    }

    const outcomes = await storage.findLatest(
      asset, 
      timeframe, 
      limit ? parseInt(limit, 10) : 100
    );
    
    return { outcomes, count: outcomes.length };
  });

  // GET /outcomes_v3/stats
  app.get('/outcomes_v3/stats', async (req, reply) => {
    const { asset, timeframe } = req.query as {
      asset?: string;
      timeframe?: string;
    };

    const stats = await storage.getStats({ asset, timeframe });
    return stats;
  });

  // GET /outcomes_v3/by_class
  app.get('/outcomes_v3/by_class', async (req, reply) => {
    const { asset, timeframe } = req.query as {
      asset?: string;
      timeframe?: string;
    };

    const counts = await storage.countByClass({ asset, timeframe });
    return { counts };
  });

  // POST /outcomes_v3/evaluate
  app.post('/outcomes_v3/evaluate', async (req, reply) => {
    const input = req.body as EvalInputsV3;

    if (!input.runId || !input.scenarioId || !input.entry || !input.stop || !input.t1) {
      return reply.code(400).send({ error: 'Missing required fields' });
    }

    const outcome = evaluateOutcomeV3(input, DEFAULT_THRESHOLDS);
    
    // Store if requested
    const { store } = req.query as { store?: string };
    if (store === 'true') {
      await storage.upsertByScenario(outcome);
    }

    return { outcome };
  });

  // POST /outcomes_v3/evaluate_batch
  app.post('/outcomes_v3/evaluate_batch', async (req, reply) => {
    const { inputs, store } = req.body as { 
      inputs: EvalInputsV3[]; 
      store?: boolean;
    };

    if (!inputs || !inputs.length) {
      return reply.code(400).send({ error: 'inputs array required' });
    }

    const outcomes = evaluateOutcomesV3Batch(inputs, DEFAULT_THRESHOLDS);

    if (store) {
      for (const outcome of outcomes) {
        await storage.upsertByScenario(outcome);
      }
    }

    return { 
      outcomes, 
      count: outcomes.length,
      stats: {
        wins: outcomes.filter(o => o.class === 'WIN').length,
        losses: outcomes.filter(o => o.class === 'LOSS').length,
        partials: outcomes.filter(o => o.class === 'PARTIAL').length,
        timeouts: outcomes.filter(o => o.class === 'TIMEOUT').length,
        noEntries: outcomes.filter(o => o.class === 'NO_ENTRY').length,
      }
    };
  });

  // GET /outcomes_v3/by_scenario/:id
  app.get('/outcomes_v3/by_scenario/:id', async (req, reply) => {
    const { id } = req.params as { id: string };
    const outcome = await storage.findByScenarioId(id);
    
    if (!outcome) {
      return reply.code(404).send({ error: 'Outcome not found' });
    }
    
    return { outcome };
  });

  // POST /outcomes_v3/backfill - Run backfill job
  app.post('/outcomes_v3/backfill', async (req, reply) => {
    const { asset, timeframe, limit, dryRun } = req.body as {
      asset?: string;
      timeframe?: string;
      limit?: number;
      dryRun?: boolean;
    };

    const result = await runOutcomesBackfillJob(opts.db, {
      asset,
      timeframe,
      limit: limit || 500,
      dryRun: dryRun || false,
    });

    return result;
  });

  // GET /outcomes_v3/backfill/status
  app.get('/outcomes_v3/backfill/status', async () => {
    const status = await getBackfillStatus(opts.db);
    return status;
  });

  // GET /outcomes_v3/dataset/stats - ML Dataset stats
  app.get('/outcomes_v3/dataset/stats', async () => {
    const stats = await datasetStorage.getStats();
    return stats;
  });

  // GET /outcomes_v3/dataset/rows - Get dataset rows
  app.get('/outcomes_v3/dataset/rows', async (req) => {
    const { asset, timeframe, limit } = req.query as {
      asset?: string;
      timeframe?: string;
      limit?: string;
    };

    const rows = await datasetStorage.getRows({
      asset,
      timeframe,
      limit: limit ? parseInt(limit, 10) : 100,
    });

    return { rows, count: rows.length };
  });

  // POST /outcomes_v3/dataset/export - Export for training
  app.post('/outcomes_v3/dataset/export', async (req, reply) => {
    const { trainRatio, excludeNoEntry, balanceClasses } = req.body as {
      trainRatio?: number;
      excludeNoEntry?: boolean;
      balanceClasses?: boolean;
    };

    const rows = await datasetStorage.exportForTraining({
      trainRatio,
      excludeNoEntry,
      balanceClasses,
    });

    return { rows, count: rows.length };
  });

  // P5.0.9: GET /outcomes_v3/coverage - Check candle coverage
  app.get('/outcomes_v3/coverage', async (req, reply) => {
    const { asset, timeframe, from, to } = req.query as {
      asset?: string;
      timeframe?: string;
      from?: string;
      to?: string;
    };

    if (asset && timeframe) {
      // Check specific asset/timeframe
      const result = await checkCandleCoverage(opts.db, {
        asset,
        timeframe,
        from: from ? new Date(from).getTime() : Date.now() - 90 * 24 * 60 * 60 * 1000,
        to: to ? new Date(to).getTime() : Date.now(),
      });
      return { ok: result.ok, coverage: result };
    }

    // Check all
    const result = await checkAllCoverage(opts.db);
    return result;
  });
}
