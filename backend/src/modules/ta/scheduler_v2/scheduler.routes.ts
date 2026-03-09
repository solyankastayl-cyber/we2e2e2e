/**
 * Phase 8.5 — Scheduler V2 API Routes
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';
import {
  createSchedulerService,
  SchedulerService,
} from './scheduler.service.js';
import { 
  createJobRunsStorage, 
  createJobStateStorage,
  createJobStorageIndexes 
} from './job.storage.js';
import { createLockIndexes } from './lock.service.js';
import { JobKey, JOB_DEFINITIONS, SchedulerConfig } from './scheduler.types.js';

let schedulerInstance: SchedulerService | null = null;

export async function registerSchedulerV2Routes(
  app: FastifyInstance,
  opts: { db: Db }
): Promise<void> {
  // Create indexes
  await createJobStorageIndexes(opts.db);
  await createLockIndexes(opts.db);

  // Initialize scheduler (but don't start yet)
  schedulerInstance = createSchedulerService(opts.db);

  const runsStorage = createJobRunsStorage(opts.db);
  const stateStorage = createJobStateStorage(opts.db);

  // GET /scheduler/status
  app.get('/scheduler/status', async () => {
    if (!schedulerInstance) {
      return { error: 'Scheduler not initialized' };
    }
    return schedulerInstance.getStatus();
  });

  // GET /scheduler/health
  app.get('/scheduler/health', async () => {
    if (!schedulerInstance) {
      return { healthy: false, error: 'Scheduler not initialized' };
    }
    return schedulerInstance.getHealth();
  });

  // POST /scheduler/start
  app.post('/scheduler/start', async () => {
    if (!schedulerInstance) {
      return { error: 'Scheduler not initialized' };
    }
    await schedulerInstance.start();
    return { ok: true, message: 'Scheduler started' };
  });

  // POST /scheduler/stop
  app.post('/scheduler/stop', async () => {
    if (!schedulerInstance) {
      return { error: 'Scheduler not initialized' };
    }
    schedulerInstance.stop();
    return { ok: true, message: 'Scheduler stopped' };
  });

  // POST /scheduler/run/:jobKey
  app.post('/scheduler/run/:jobKey', async (req, reply) => {
    const { jobKey } = req.params as { jobKey: string };
    const { force } = req.query as { force?: string };

    if (!schedulerInstance) {
      return reply.code(500).send({ error: 'Scheduler not initialized' });
    }

    if (!(jobKey in JOB_DEFINITIONS)) {
      return reply.code(400).send({ error: `Unknown job: ${jobKey}` });
    }

    const result = await schedulerInstance.runJob(jobKey as JobKey, force === 'true');
    return result;
  });

  // GET /scheduler/runs
  app.get('/scheduler/runs', async (req) => {
    const { jobKey, limit } = req.query as { jobKey?: string; limit?: string };

    if (jobKey && jobKey in JOB_DEFINITIONS) {
      const runs = await runsStorage.getRunsByJob(
        jobKey as JobKey, 
        limit ? parseInt(limit, 10) : 50
      );
      return { runs };
    }

    const runs = await runsStorage.getRecentRuns(limit ? parseInt(limit, 10) : 100);
    return { runs };
  });

  // GET /scheduler/state/:jobKey
  app.get('/scheduler/state/:jobKey', async (req, reply) => {
    const { jobKey } = req.params as { jobKey: string };

    if (!(jobKey in JOB_DEFINITIONS)) {
      return reply.code(400).send({ error: `Unknown job: ${jobKey}` });
    }

    const state = await stateStorage.getState(jobKey as JobKey);
    return { state };
  });

  // GET /scheduler/jobs
  app.get('/scheduler/jobs', async () => {
    return { 
      jobs: Object.values(JOB_DEFINITIONS).map(j => ({
        key: j.key,
        name: j.name,
        description: j.description,
        dependsOn: j.dependsOn,
        priority: j.priority,
        cronExpression: j.cronExpression,
      }))
    };
  });

  // PATCH /scheduler/config
  app.patch('/scheduler/config', async (req, reply) => {
    if (!schedulerInstance) {
      return reply.code(500).send({ error: 'Scheduler not initialized' });
    }

    const update = req.body as Partial<SchedulerConfig>;
    schedulerInstance.updateConfig(update);
    
    return { ok: true, message: 'Config updated' };
  });
}
