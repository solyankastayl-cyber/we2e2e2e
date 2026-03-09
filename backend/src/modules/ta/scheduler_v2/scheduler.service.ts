/**
 * Phase 8.5 — Auto Scheduler Service
 * 
 * Orchestrates the full ML pipeline:
 * outcomes -> dataset -> train -> eval -> register -> promote
 */

import cron from 'node-cron';
import { Db } from 'mongodb';
import { 
  JobKey, 
  JobStatus, 
  SchedulerConfig, 
  DEFAULT_SCHEDULER_CONFIG,
  JOB_DEFINITIONS,
  JobContext 
} from './scheduler.types.js';
import { createLockService, LockService } from './lock.service.js';
import { 
  createJobRunsStorage, 
  createJobStateStorage, 
  JobRunsStorage, 
  JobStateStorage 
} from './job.storage.js';
import { getAllExecutors, JobExecutor } from './job.executors.js';

const LOCK_TTL_MS = 5 * 60 * 1000;  // 5 minutes

export interface SchedulerService {
  start(): Promise<void>;
  stop(): void;
  runJob(jobKey: JobKey, force?: boolean): Promise<{ success: boolean; runId?: string; error?: string; counts?: Record<string, number> }>;
  getStatus(): SchedulerStatus;
  getHealth(): Promise<SchedulerHealth>;
  updateConfig(update: Partial<SchedulerConfig>): void;
}

export interface SchedulerStatus {
  enabled: boolean;
  freezeEnabled: boolean;
  startedAt: Date | null;
  isRunning: boolean;
  activeJobs: string[];
  tasksCount: number;
  stats: {
    totalRuns: number;
    successRuns: number;
    failedRuns: number;
    lastRunAt: Date | null;
  };
}

export interface SchedulerHealth {
  healthy: boolean;
  locksOk: boolean;
  activeLocks: number;
  lastSuccessAt: Record<JobKey, Date | undefined>;
  backlogSize: Record<string, number>;
}

export function createSchedulerService(db: Db, customExecutors?: Partial<Record<JobKey, JobExecutor>>): SchedulerService {
  let config = { ...DEFAULT_SCHEDULER_CONFIG };
  let startedAt: Date | null = null;
  let isRunning = false;
  const scheduledTasks: cron.ScheduledTask[] = [];
  const activeJobs = new Set<string>();
  
  // Merge custom executors with defaults
  const executors = { ...getAllExecutors(), ...customExecutors };
  
  const stats = {
    totalRuns: 0,
    successRuns: 0,
    failedRuns: 0,
    lastRunAt: null as Date | null,
  };

  const lockService = createLockService(db);
  const runsStorage = createJobRunsStorage(db);
  const stateStorage = createJobStateStorage(db);

  const log = (msg: string, data?: any) => {
    console.log(`[Scheduler] ${msg}`, data || '');
  };

  const ctx: JobContext = { db, config, logger: log };

  /**
   * Check preconditions for a job
   */
  async function checkPreconditions(jobKey: JobKey): Promise<{ ok: boolean; reason?: string }> {
    const jobDef = JOB_DEFINITIONS[jobKey];
    
    // Check dependencies completed successfully
    for (const depKey of jobDef.dependsOn) {
      const depState = await stateStorage.getState(depKey);
      if (!depState?.lastSuccessAt) {
        return { ok: false, reason: `Dependency ${depKey} never succeeded` };
      }
      
      // Check if dependency ran after our last run
      const ourState = await stateStorage.getState(jobKey);
      if (ourState?.lastSuccessAt && depState.lastSuccessAt < ourState.lastSuccessAt) {
        return { ok: false, reason: `Dependency ${depKey} not updated since our last run` };
      }
    }

    // Check minimum items threshold
    if (jobDef.minNewItems) {
      const state = await stateStorage.getState(jobKey);
      const counter = state?.counters?.rowsSinceLastTrain || 0;
      if (counter < jobDef.minNewItems) {
        return { ok: false, reason: `Threshold not met: ${counter} < ${jobDef.minNewItems}` };
      }
    }

    return { ok: true };
  }

  /**
   * Execute a job with locking
   */
  async function executeJob(jobKey: JobKey, force: boolean = false): Promise<{ success: boolean; runId?: string; error?: string; counts?: Record<string, number> }> {
    // Check freeze
    if (config.freezeEnabled && JOB_DEFINITIONS[jobKey].freezeAware) {
      log(`Job ${jobKey} skipped - system frozen`);
      return { success: false, error: 'system_frozen' };
    }

    // Check preconditions (unless forced)
    if (!force) {
      const preconditions = await checkPreconditions(jobKey);
      if (!preconditions.ok) {
        log(`Job ${jobKey} skipped - ${preconditions.reason}`);
        return { success: false, error: preconditions.reason };
      }
    }

    // Try to acquire lock
    const lockKey = `job:${jobKey}`;
    const acquired = await lockService.acquire(lockKey, LOCK_TTL_MS);
    if (!acquired) {
      log(`Job ${jobKey} skipped - lock held`);
      return { success: false, error: 'lock_held' };
    }

    activeJobs.add(jobKey);
    const runId = await runsStorage.startRun(jobKey);
    stats.totalRuns++;

    try {
      log(`Starting job: ${jobKey}`, { runId });
      
      // Execute job
      const executor = executors[jobKey];
      let result: { counts?: Record<string, number>; error?: string } = {};
      
      if (executor) {
        result = await executor.execute(ctx);
      } else {
        log(`Job ${jobKey} has no executor - skipping`);
        result = { counts: { skipped: 1 } };
      }

      if (result.error) {
        await runsStorage.completeRun(runId, 'FAILED', { error: result.error, counts: result.counts });
        stats.failedRuns++;
        return { success: false, runId, error: result.error, counts: result.counts };
      }

      await runsStorage.completeRun(runId, 'SUCCESS', { counts: result.counts });
      await stateStorage.updateState(jobKey, { lastSuccessAt: new Date() });
      
      // Reset counters for jobs that depend on us
      await stateStorage.resetCounters(jobKey);
      
      stats.successRuns++;
      stats.lastRunAt = new Date();
      
      log(`Completed job: ${jobKey}`, result.counts);
      return { success: true, runId, counts: result.counts };

    } catch (err: any) {
      await runsStorage.completeRun(runId, 'FAILED', { error: err.message });
      stats.failedRuns++;
      log(`Job ${jobKey} failed: ${err.message}`);
      return { success: false, runId, error: err.message };

    } finally {
      await lockService.release(lockKey);
      activeJobs.delete(jobKey);
    }
  }

  return {
    async start(): Promise<void> {
      if (isRunning) {
        log('Already running');
        return;
      }

      if (!config.enabled) {
        log('Disabled by config');
        return;
      }

      startedAt = new Date();
      isRunning = true;

      // Schedule P0 jobs
      const outcomesTask = cron.schedule(config.cron.outcomesCron, () => {
        executeJob('JOB_OUTCOMES_BACKFILL_V3');
      });
      scheduledTasks.push(outcomesTask);

      const datasetTask = cron.schedule(config.cron.datasetCron, () => {
        executeJob('JOB_DATASET_BUILD_V3');
      });
      scheduledTasks.push(datasetTask);

      const trainTask = cron.schedule(config.cron.trainCron, () => {
        executeJob('JOB_TRAIN_MODEL');
      });
      scheduledTasks.push(trainTask);

      // Schedule P1 jobs
      const calibrationTask = cron.schedule(config.cron.calibrationCron, () => {
        executeJob('JOB_REBUILD_CALIBRATION');
      });
      scheduledTasks.push(calibrationTask);

      const driftTask = cron.schedule(config.cron.driftCron, () => {
        executeJob('JOB_DRIFT_CHECK');
      });
      scheduledTasks.push(driftTask);

      log(`Started with ${scheduledTasks.length} scheduled tasks`);
    },

    stop(): void {
      for (const task of scheduledTasks) {
        task.stop();
      }
      scheduledTasks.length = 0;
      isRunning = false;
      log('Stopped');
    },

    async runJob(jobKey: JobKey, force = false): Promise<{ success: boolean; runId?: string; error?: string; counts?: Record<string, number> }> {
      if (!force && config.freezeEnabled) {
        return { success: false, error: 'system_frozen' };
      }
      return executeJob(jobKey, force);
    },

    getStatus(): SchedulerStatus {
      return {
        enabled: config.enabled,
        freezeEnabled: config.freezeEnabled,
        startedAt,
        isRunning,
        activeJobs: Array.from(activeJobs),
        tasksCount: scheduledTasks.length,
        stats: { ...stats },
      };
    },

    async getHealth(): Promise<SchedulerHealth> {
      const activeLocks = await lockService.getActiveLocks();
      
      const lastSuccessAt: Record<JobKey, Date | undefined> = {} as any;
      for (const jobKey of Object.keys(JOB_DEFINITIONS) as JobKey[]) {
        const state = await stateStorage.getState(jobKey);
        lastSuccessAt[jobKey] = state?.lastSuccessAt;
      }

      return {
        healthy: isRunning && activeLocks.length <= 3,
        locksOk: activeLocks.length <= 5,
        activeLocks: activeLocks.length,
        lastSuccessAt,
        backlogSize: {},  // Would query pending items
      };
    },

    updateConfig(update: Partial<SchedulerConfig>): void {
      config = { ...config, ...update };
      log('Config updated', update);
    },
  };
}
