/**
 * Phase 8.5 — Job Runs Storage
 * 
 * Immutable audit trail for all job executions
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';
import { JobKey, JobStatus, JobRun, JobState } from './scheduler.types.js';

const RUNS_COLLECTION = 'ta_job_runs';
const STATE_COLLECTION = 'ta_job_state';

export interface JobRunsStorage {
  startRun(jobKey: JobKey): Promise<string>;
  completeRun(runId: string, status: JobStatus, meta?: JobRun['meta']): Promise<void>;
  getRunsByJob(jobKey: JobKey, limit?: number): Promise<JobRun[]>;
  getLatestRun(jobKey: JobKey): Promise<JobRun | null>;
  getRecentRuns(limit?: number): Promise<JobRun[]>;
}

export interface JobStateStorage {
  getState(jobKey: JobKey): Promise<JobState | null>;
  updateState(jobKey: JobKey, update: Partial<JobState>): Promise<void>;
  incrementCounter(jobKey: JobKey, counter: keyof JobState['counters'], amount?: number): Promise<void>;
  resetCounters(jobKey: JobKey): Promise<void>;
}

export function createJobRunsStorage(db: Db): JobRunsStorage {
  const collection: Collection = db.collection(RUNS_COLLECTION);

  return {
    async startRun(jobKey: JobKey): Promise<string> {
      const runId = uuidv4();
      const now = new Date();

      await collection.insertOne({
        runId,
        jobKey,
        status: 'STARTED',
        startedAt: now,
      });

      return runId;
    },

    async completeRun(runId: string, status: JobStatus, meta?: JobRun['meta']): Promise<void> {
      const now = new Date();

      await collection.updateOne(
        { runId },
        {
          $set: {
            status,
            finishedAt: now,
            ...(meta && { meta }),
          },
        }
      );
    },

    async getRunsByJob(jobKey: JobKey, limit = 50): Promise<JobRun[]> {
      return collection
        .find({ jobKey }, { projection: { _id: 0 } })
        .sort({ startedAt: -1 })
        .limit(limit)
        .toArray() as Promise<JobRun[]>;
    },

    async getLatestRun(jobKey: JobKey): Promise<JobRun | null> {
      return collection
        .findOne({ jobKey }, { sort: { startedAt: -1 }, projection: { _id: 0 } }) as Promise<JobRun | null>;
    },

    async getRecentRuns(limit = 100): Promise<JobRun[]> {
      return collection
        .find({}, { projection: { _id: 0 } })
        .sort({ startedAt: -1 })
        .limit(limit)
        .toArray() as Promise<JobRun[]>;
    },
  };
}

export function createJobStateStorage(db: Db): JobStateStorage {
  const collection: Collection = db.collection(STATE_COLLECTION);

  const defaultState = (jobKey: JobKey): JobState => ({
    jobKey,
    counters: {
      rowsSinceLastTrain: 0,
      outcomesSinceLastDataset: 0,
      scenariosSinceLastOutcomes: 0,
    },
  });

  return {
    async getState(jobKey: JobKey): Promise<JobState | null> {
      const state = await collection.findOne({ _id: jobKey });
      if (!state) return null;
      return {
        jobKey: state._id as JobKey,
        lastCursor: state.lastCursor,
        lastSuccessAt: state.lastSuccessAt,
        counters: state.counters || defaultState(jobKey).counters,
      };
    },

    async updateState(jobKey: JobKey, update: Partial<JobState>): Promise<void> {
      await collection.updateOne(
        { _id: jobKey },
        {
          $set: {
            ...update,
            updatedAt: new Date(),
          },
        },
        { upsert: true }
      );
    },

    async incrementCounter(
      jobKey: JobKey, 
      counter: keyof JobState['counters'], 
      amount = 1
    ): Promise<void> {
      await collection.updateOne(
        { _id: jobKey },
        {
          $inc: { [`counters.${counter}`]: amount },
          $set: { updatedAt: new Date() },
        },
        { upsert: true }
      );
    },

    async resetCounters(jobKey: JobKey): Promise<void> {
      await collection.updateOne(
        { _id: jobKey },
        {
          $set: {
            counters: defaultState(jobKey).counters,
            updatedAt: new Date(),
          },
        },
        { upsert: true }
      );
    },
  };
}

/**
 * Create indexes
 */
export async function createJobStorageIndexes(db: Db): Promise<void> {
  const runs = db.collection(RUNS_COLLECTION);
  const state = db.collection(STATE_COLLECTION);

  await runs.createIndex({ jobKey: 1, startedAt: -1 });
  await runs.createIndex({ status: 1, startedAt: -1 });
  await runs.createIndex({ startedAt: -1 });

  console.log('[JobStorage] Indexes created');
}
