/**
 * Phase 5.1 B2 — Backtest Job Queue (Storage)
 * 
 * MongoDB operations for job management
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';
import {
  BacktestJobDoc,
  BacktestJobStatus,
  BacktestJobProgress,
  CreateJobInput,
  JOBS_COLLECTION,
} from './backtest.job.schema.js';

// ═══════════════════════════════════════════════════════════════
// Job Queue Class
// ═══════════════════════════════════════════════════════════════

export class BacktestJobQueue {
  private db: Db;
  private jobs: Collection;

  constructor(db: Db) {
    this.db = db;
    this.jobs = db.collection(JOBS_COLLECTION);
  }

  // ─────────────────────────────────────────────────────────────
  // Indexes
  // ─────────────────────────────────────────────────────────────

  async ensureIndexes(): Promise<void> {
    await this.jobs.createIndex({ jobId: 1 }, { unique: true });
    await this.jobs.createIndex({ status: 1, createdAt: 1 });
    await this.jobs.createIndex({ updatedAt: 1 });
    await this.jobs.createIndex({ runId: 1 });
    // TTL index - remove completed jobs after 30 days
    await this.jobs.createIndex(
      { completedAt: 1 },
      { expireAfterSeconds: 30 * 24 * 60 * 60, sparse: true }
    );
    console.log('[BacktestJobQueue] Indexes ensured');
  }

  // ─────────────────────────────────────────────────────────────
  // Create Job
  // ─────────────────────────────────────────────────────────────

  async createJob(input: CreateJobInput): Promise<BacktestJobDoc> {
    const now = new Date();
    const jobId = uuidv4();

    const job: BacktestJobDoc = {
      jobId,
      status: 'QUEUED',
      createdAt: now,
      updatedAt: now,
      request: {
        assets: input.assets,
        tf: input.tf,
        from: input.from,
        to: input.to,
        seed: input.seed || 1337,
        warmupBars: input.warmupBars || 300,
        decisionEngine: input.decisionEngine || 'MOCK',
      },
      progress: {
        pct: 0,
        barsDone: 0,
        barsTotal: 0,
        asset: null,
        step: 'QUEUED',
        updatedAt: now,
      },
      cancelRequested: false,
    };

    await this.jobs.insertOne(job);
    
    const { _id, ...result } = job;
    return result as BacktestJobDoc;
  }

  // ─────────────────────────────────────────────────────────────
  // Get Job
  // ─────────────────────────────────────────────────────────────

  async getJob(jobId: string): Promise<BacktestJobDoc | null> {
    const doc = await this.jobs.findOne({ jobId });
    if (!doc) return null;
    
    const { _id, ...job } = doc as any;
    return job as BacktestJobDoc;
  }

  // ─────────────────────────────────────────────────────────────
  // List Jobs
  // ─────────────────────────────────────────────────────────────

  async listJobs(
    status?: BacktestJobStatus,
    limit: number = 20
  ): Promise<BacktestJobDoc[]> {
    const query = status ? { status } : {};
    
    const docs = await this.jobs
      .find(query)
      .sort({ createdAt: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...job } = doc as any;
      return job as BacktestJobDoc;
    });
  }

  // ─────────────────────────────────────────────────────────────
  // Claim Next Job (atomic)
  // ─────────────────────────────────────────────────────────────

  async claimNextJob(): Promise<BacktestJobDoc | null> {
    const result = await this.jobs.findOneAndUpdate(
      { status: 'QUEUED' },
      { 
        $set: { 
          status: 'RUNNING',
          updatedAt: new Date(),
          'progress.step': 'STARTING',
        } 
      },
      { 
        sort: { createdAt: 1 },  // FIFO
        returnDocument: 'after',
      }
    );

    if (!result) return null;
    
    const { _id, ...job } = result as any;
    return job as BacktestJobDoc;
  }

  // ─────────────────────────────────────────────────────────────
  // Update Progress
  // ─────────────────────────────────────────────────────────────

  async updateProgress(
    jobId: string,
    progress: Partial<BacktestJobProgress>
  ): Promise<void> {
    const update: any = {
      updatedAt: new Date(),
    };

    if (progress.pct !== undefined) update['progress.pct'] = progress.pct;
    if (progress.barsDone !== undefined) update['progress.barsDone'] = progress.barsDone;
    if (progress.barsTotal !== undefined) update['progress.barsTotal'] = progress.barsTotal;
    if (progress.asset !== undefined) update['progress.asset'] = progress.asset;
    if (progress.step !== undefined) update['progress.step'] = progress.step;
    update['progress.updatedAt'] = new Date();

    await this.jobs.updateOne(
      { jobId },
      { $set: update }
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Mark Completed
  // ─────────────────────────────────────────────────────────────

  async markCompleted(jobId: string, runId: string): Promise<void> {
    const now = new Date();
    await this.jobs.updateOne(
      { jobId },
      {
        $set: {
          status: 'COMPLETED',
          runId,
          completedAt: now,
          updatedAt: now,
          'progress.pct': 100,
          'progress.step': 'COMPLETED',
        },
      }
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Mark Failed
  // ─────────────────────────────────────────────────────────────

  async markFailed(jobId: string, error: { message: string; stack?: string }): Promise<void> {
    const now = new Date();
    await this.jobs.updateOne(
      { jobId },
      {
        $set: {
          status: 'FAILED',
          completedAt: now,
          updatedAt: now,
          error,
          'progress.step': 'FAILED',
        },
      }
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Mark Cancelled
  // ─────────────────────────────────────────────────────────────

  async markCancelled(jobId: string): Promise<void> {
    const now = new Date();
    await this.jobs.updateOne(
      { jobId },
      {
        $set: {
          status: 'CANCELLED',
          completedAt: now,
          updatedAt: now,
          'progress.step': 'CANCELLED',
        },
      }
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Request Cancel
  // ─────────────────────────────────────────────────────────────

  async requestCancel(jobId: string): Promise<boolean> {
    const result = await this.jobs.updateOne(
      { jobId, status: { $in: ['QUEUED', 'RUNNING'] } },
      { $set: { cancelRequested: true, updatedAt: new Date() } }
    );
    return result.modifiedCount > 0;
  }

  // ─────────────────────────────────────────────────────────────
  // Check Cancel Requested
  // ─────────────────────────────────────────────────────────────

  async isCancelRequested(jobId: string): Promise<boolean> {
    const doc = await this.jobs.findOne(
      { jobId },
      { projection: { cancelRequested: 1 } }
    );
    return doc?.cancelRequested === true;
  }

  // ─────────────────────────────────────────────────────────────
  // Count Running Jobs
  // ─────────────────────────────────────────────────────────────

  async countRunning(): Promise<number> {
    return this.jobs.countDocuments({ status: 'RUNNING' });
  }

  // ─────────────────────────────────────────────────────────────
  // Count Queued Jobs
  // ─────────────────────────────────────────────────────────────

  async countQueued(): Promise<number> {
    return this.jobs.countDocuments({ status: 'QUEUED' });
  }
}

// ═══════════════════════════════════════════════════════════════
// Singleton
// ═══════════════════════════════════════════════════════════════

let queueInstance: BacktestJobQueue | null = null;

export function getBacktestJobQueue(db: Db): BacktestJobQueue {
  if (!queueInstance) {
    queueInstance = new BacktestJobQueue(db);
  }
  return queueInstance;
}
