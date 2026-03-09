/**
 * Phase 5.1 B2 — Backtest Job Controller (Routes)
 * 
 * API endpoints for async job management
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { getBacktestJobQueue } from './backtest.queue.js';
import { CreateJobInput, BacktestJobStatus, JOB_LIMITS } from './backtest.job.schema.js';

interface RouteContext {
  db: Db;
}

export async function registerBacktestJobRoutes(
  app: FastifyInstance,
  { db }: RouteContext
): Promise<void> {
  const queue = getBacktestJobQueue(db);

  // ─────────────────────────────────────────────────────────────
  // POST /jobs - Create new backtest job
  // ─────────────────────────────────────────────────────────────
  app.post('/jobs', async (request: FastifyRequest<{
    Body: CreateJobInput
  }>) => {
    const body = request.body;

    // Validate required fields
    if (!body.assets || !Array.isArray(body.assets) || body.assets.length === 0) {
      return { ok: false, error: 'assets array required' };
    }
    if (!body.tf) {
      return { ok: false, error: 'tf (timeframe) required' };
    }
    if (!body.from || !body.to) {
      return { ok: false, error: 'from and to dates required' };
    }

    // Validate limits
    if (body.assets.length > JOB_LIMITS.maxAssetsPerJob) {
      return { 
        ok: false, 
        error: `Max ${JOB_LIMITS.maxAssetsPerJob} assets per job` 
      };
    }

    // Check queue capacity
    const queuedCount = await queue.countQueued();
    const runningCount = await queue.countRunning();
    if (queuedCount + runningCount >= 20) {
      return { 
        ok: false, 
        error: 'Job queue is full. Please wait for current jobs to complete.' 
      };
    }

    // Create job
    const job = await queue.createJob(body);

    return {
      ok: true,
      jobId: job.jobId,
      status: job.status,
    };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /jobs/:jobId - Get job status and progress
  // ─────────────────────────────────────────────────────────────
  app.get('/jobs/:jobId', async (request: FastifyRequest<{
    Params: { jobId: string }
  }>) => {
    const { jobId } = request.params;

    const job = await queue.getJob(jobId);
    if (!job) {
      return { ok: false, error: 'Job not found' };
    }

    return {
      ok: true,
      jobId: job.jobId,
      status: job.status,
      progress: job.progress,
      request: job.request,
      runId: job.runId,
      error: job.error,
      createdAt: job.createdAt,
      updatedAt: job.updatedAt,
      completedAt: job.completedAt,
    };
  });

  // ─────────────────────────────────────────────────────────────
  // POST /jobs/:jobId/cancel - Cancel a job
  // ─────────────────────────────────────────────────────────────
  app.post('/jobs/:jobId/cancel', async (request: FastifyRequest<{
    Params: { jobId: string }
  }>) => {
    const { jobId } = request.params;

    const success = await queue.requestCancel(jobId);
    
    if (!success) {
      const job = await queue.getJob(jobId);
      if (!job) {
        return { ok: false, error: 'Job not found' };
      }
      return { 
        ok: false, 
        error: `Cannot cancel job in ${job.status} status` 
      };
    }

    return { ok: true, message: 'Cancel requested' };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /jobs - List jobs
  // ─────────────────────────────────────────────────────────────
  app.get('/jobs', async (request: FastifyRequest<{
    Querystring: { status?: string; limit?: string }
  }>) => {
    const { status, limit } = request.query;

    const statusFilter = status as BacktestJobStatus | undefined;
    const limitNum = limit ? parseInt(limit, 10) : 20;

    const jobs = await queue.listJobs(statusFilter, limitNum);

    // Also get queue stats
    const queuedCount = await queue.countQueued();
    const runningCount = await queue.countRunning();

    return {
      ok: true,
      count: jobs.length,
      queue: {
        queued: queuedCount,
        running: runningCount,
        maxConcurrent: JOB_LIMITS.maxConcurrentJobs,
      },
      jobs: jobs.map(job => ({
        jobId: job.jobId,
        status: job.status,
        progress: job.progress,
        request: {
          assets: job.request.assets,
          tf: job.request.tf,
          from: job.request.from,
          to: job.request.to,
        },
        runId: job.runId,
        createdAt: job.createdAt,
        completedAt: job.completedAt,
      })),
    };
  });

  console.log('[BacktestJobs] Routes registered: POST/GET /jobs, POST /jobs/:id/cancel');
}
