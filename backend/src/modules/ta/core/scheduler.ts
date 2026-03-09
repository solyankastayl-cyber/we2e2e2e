/**
 * Scheduler Jobs
 * 
 * Background jobs for system maintenance
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuid } from 'uuid';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type JobType = 
  | 'PATTERN_DISCOVERY'
  | 'STABILITY_RECALC'
  | 'DATASET_BACKFILL'
  | 'MODEL_RETRAIN'
  | 'REPLAY_VALIDATION'
  | 'QUALITY_REBUILD'
  | 'DATASET_STATS';

export interface JobRecord {
  jobId: string;
  type: JobType;
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
  
  // Scheduling
  scheduledAt: Date;
  startedAt?: Date;
  finishedAt?: Date;
  
  // Config
  config?: Record<string, any>;
  
  // Results
  result?: Record<string, any>;
  error?: string;
  
  // Metrics
  duration?: number;
  itemsProcessed?: number;
}

export interface JobSchedule {
  type: JobType;
  cronExpression?: string;
  intervalMs?: number;
  enabled: boolean;
  lastRun?: Date;
  nextRun?: Date;
}

// ═══════════════════════════════════════════════════════════════
// COLLECTIONS
// ═══════════════════════════════════════════════════════════════

const COLLECTION_JOBS = 'ta_scheduler_jobs';
const COLLECTION_SCHEDULES = 'ta_job_schedules';

// ═══════════════════════════════════════════════════════════════
// JOB SCHEDULER
// ═══════════════════════════════════════════════════════════════

export class JobScheduler {
  private db: Db;
  private jobsCol: Collection;
  private schedulesCol: Collection;
  
  constructor(db: Db) {
    this.db = db;
    this.jobsCol = db.collection(COLLECTION_JOBS);
    this.schedulesCol = db.collection(COLLECTION_SCHEDULES);
  }
  
  /**
   * Initialize scheduler
   */
  async initialize(): Promise<void> {
    await this.jobsCol.createIndex({ jobId: 1 }, { unique: true });
    await this.jobsCol.createIndex({ type: 1, status: 1 });
    await this.jobsCol.createIndex({ scheduledAt: -1 });
    
    await this.schedulesCol.createIndex({ type: 1 }, { unique: true });
    
    // Initialize default schedules
    const defaultSchedules: JobSchedule[] = [
      { type: 'PATTERN_DISCOVERY', intervalMs: 7 * 24 * 60 * 60 * 1000, enabled: true }, // Weekly
      { type: 'STABILITY_RECALC', intervalMs: 24 * 60 * 60 * 1000, enabled: true },      // Daily
      { type: 'DATASET_BACKFILL', intervalMs: 6 * 60 * 60 * 1000, enabled: true },       // 6 hours
      { type: 'MODEL_RETRAIN', intervalMs: 7 * 24 * 60 * 60 * 1000, enabled: false },    // Weekly, manual
      { type: 'REPLAY_VALIDATION', intervalMs: 24 * 60 * 60 * 1000, enabled: true },     // Daily
      { type: 'QUALITY_REBUILD', intervalMs: 24 * 60 * 60 * 1000, enabled: true },       // Daily
      { type: 'DATASET_STATS', intervalMs: 60 * 60 * 1000, enabled: true },              // Hourly
    ];
    
    for (const schedule of defaultSchedules) {
      await this.schedulesCol.updateOne(
        { type: schedule.type },
        { $setOnInsert: schedule },
        { upsert: true }
      );
    }
    
    console.log('[JobScheduler] Initialized with default schedules');
  }
  
  /**
   * Schedule a job
   */
  async scheduleJob(type: JobType, config?: Record<string, any>): Promise<string> {
    const jobId = `job_${type.toLowerCase()}_${Date.now()}`;
    
    const job: JobRecord = {
      jobId,
      type,
      status: 'PENDING',
      scheduledAt: new Date(),
      config,
    };
    
    await this.jobsCol.insertOne(job);
    console.log(`[JobScheduler] Scheduled job ${jobId}`);
    
    return jobId;
  }
  
  /**
   * Start a job
   */
  async startJob(jobId: string): Promise<void> {
    await this.jobsCol.updateOne(
      { jobId },
      { $set: { status: 'RUNNING', startedAt: new Date() } }
    );
  }
  
  /**
   * Complete a job
   */
  async completeJob(
    jobId: string, 
    result: Record<string, any>,
    itemsProcessed?: number
  ): Promise<void> {
    const job = await this.jobsCol.findOne({ jobId }) as JobRecord | null;
    const duration = job?.startedAt 
      ? Date.now() - job.startedAt.getTime()
      : 0;
    
    await this.jobsCol.updateOne(
      { jobId },
      { 
        $set: { 
          status: 'DONE',
          finishedAt: new Date(),
          result,
          duration,
          itemsProcessed,
        }
      }
    );
    
    // Update schedule last run
    if (job) {
      await this.schedulesCol.updateOne(
        { type: job.type },
        { $set: { lastRun: new Date() } }
      );
    }
  }
  
  /**
   * Fail a job
   */
  async failJob(jobId: string, error: string): Promise<void> {
    await this.jobsCol.updateOne(
      { jobId },
      { 
        $set: { 
          status: 'FAILED',
          finishedAt: new Date(),
          error,
        }
      }
    );
  }
  
  /**
   * Get job by ID
   */
  async getJob(jobId: string): Promise<JobRecord | null> {
    return this.jobsCol.findOne({ jobId }) as any;
  }
  
  /**
   * Get jobs due for execution
   */
  async getDueJobs(): Promise<JobSchedule[]> {
    const now = Date.now();
    const dueJobs: JobSchedule[] = [];
    
    const schedules = await this.schedulesCol.find({ enabled: true }).toArray() as unknown as JobSchedule[];
    
    for (const schedule of schedules) {
      const lastRun = schedule.lastRun?.getTime() || 0;
      const interval = schedule.intervalMs || 24 * 60 * 60 * 1000;
      
      if (now - lastRun >= interval) {
        // Check if there's already a running job of this type
        const running = await this.jobsCol.countDocuments({
          type: schedule.type,
          status: { $in: ['PENDING', 'RUNNING'] }
        });
        
        if (running === 0) {
          dueJobs.push(schedule);
        }
      }
    }
    
    return dueJobs;
  }
  
  /**
   * Get recent jobs
   */
  async getRecentJobs(limit: number = 50): Promise<JobRecord[]> {
    return this.jobsCol
      .find()
      .sort({ scheduledAt: -1 })
      .limit(limit)
      .toArray() as any;
  }
  
  /**
   * Get job history for type
   */
  async getJobHistory(type: JobType, limit: number = 10): Promise<JobRecord[]> {
    return this.jobsCol
      .find({ type })
      .sort({ scheduledAt: -1 })
      .limit(limit)
      .toArray() as any;
  }
  
  /**
   * Get all schedules
   */
  async getSchedules(): Promise<JobSchedule[]> {
    return this.schedulesCol.find().toArray() as any;
  }
  
  /**
   * Enable/disable schedule
   */
  async setScheduleEnabled(type: JobType, enabled: boolean): Promise<void> {
    await this.schedulesCol.updateOne(
      { type },
      { $set: { enabled } }
    );
  }
  
  /**
   * Get scheduler status
   */
  async getStatus(): Promise<{
    schedulesCount: number;
    activeSchedules: number;
    pendingJobs: number;
    runningJobs: number;
    recentJobs: JobRecord[];
  }> {
    const schedules = await this.getSchedules();
    const pendingJobs = await this.jobsCol.countDocuments({ status: 'PENDING' });
    const runningJobs = await this.jobsCol.countDocuments({ status: 'RUNNING' });
    const recentJobs = await this.getRecentJobs(10);
    
    return {
      schedulesCount: schedules.length,
      activeSchedules: schedules.filter(s => s.enabled).length,
      pendingJobs,
      runningJobs,
      recentJobs,
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

export function createJobScheduler(db: Db): JobScheduler {
  return new JobScheduler(db);
}
