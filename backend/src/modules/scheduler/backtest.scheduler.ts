/**
 * Phase 5.3 B6 — Backtest Scheduler
 * 
 * Automated research - runs backtests on schedule
 * Tracks edge decay over time
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';
import { FastifyInstance, FastifyRequest } from 'fastify';
import { getBacktestJobQueue } from '../backtest/jobs/backtest.queue.js';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export interface ScheduleDoc {
  scheduleId: string;
  name: string;
  enabled: boolean;
  
  cron: string;  // "0 2 * * 1" = every Monday at 02:00
  
  config: {
    assets: string[];
    tf: string;
    windowYears: number;
  };
  
  lastRun?: Date;
  lastRunId?: string;
  nextRun?: Date;
  
  createdAt: Date;
  updatedAt: Date;
}

export interface EdgeHistoryDoc {
  pattern: string;
  timestamp: Date;
  runId: string;
  
  trades: number;
  winRate: number;
  profitFactor: number;
  avgR: number;
}

// ═══════════════════════════════════════════════════════════════
// Cron Parser (simple)
// ═══════════════════════════════════════════════════════════════

function parseNextRun(cron: string, from: Date = new Date()): Date {
  // Simple parser for: "minute hour day month weekday"
  const parts = cron.split(' ');
  if (parts.length !== 5) {
    throw new Error(`Invalid cron: ${cron}`);
  }

  const [minute, hour, day, month, weekday] = parts;
  
  // For simplicity, just handle common cases
  const next = new Date(from);
  next.setMinutes(parseInt(minute) || 0);
  next.setHours(parseInt(hour) || 0);
  next.setSeconds(0);
  next.setMilliseconds(0);

  // If weekday is specified (0-6, 0=Sunday)
  if (weekday !== '*') {
    const targetDay = parseInt(weekday);
    const currentDay = next.getDay();
    let daysToAdd = targetDay - currentDay;
    if (daysToAdd <= 0) daysToAdd += 7;
    next.setDate(next.getDate() + daysToAdd);
  } else if (next <= from) {
    // If already passed today, move to tomorrow
    next.setDate(next.getDate() + 1);
  }

  return next;
}

// ═══════════════════════════════════════════════════════════════
// Scheduler Service
// ═══════════════════════════════════════════════════════════════

const SCHEDULES_COLLECTION = 'ta_schedules';
const EDGE_HISTORY_COLLECTION = 'ta_edge_history';

export class BacktestScheduler {
  private db: Db;
  private schedules: Collection;
  private edgeHistory: Collection;
  private running: boolean = false;

  constructor(db: Db) {
    this.db = db;
    this.schedules = db.collection(SCHEDULES_COLLECTION);
    this.edgeHistory = db.collection(EDGE_HISTORY_COLLECTION);
  }

  async ensureIndexes(): Promise<void> {
    await this.schedules.createIndex({ scheduleId: 1 }, { unique: true });
    await this.schedules.createIndex({ enabled: 1, nextRun: 1 });
    await this.edgeHistory.createIndex({ pattern: 1, timestamp: -1 });
    await this.edgeHistory.createIndex({ runId: 1 });
    console.log('[BacktestScheduler] Indexes ensured');
  }

  // ─────────────────────────────────────────────────────────────
  // Schedule CRUD
  // ─────────────────────────────────────────────────────────────

  async createSchedule(input: {
    name: string;
    cron: string;
    assets: string[];
    tf: string;
    windowYears?: number;
  }): Promise<ScheduleDoc> {
    const now = new Date();
    const nextRun = parseNextRun(input.cron, now);

    const doc: ScheduleDoc = {
      scheduleId: uuidv4(),
      name: input.name,
      enabled: true,
      cron: input.cron,
      config: {
        assets: input.assets,
        tf: input.tf,
        windowYears: input.windowYears || 5,
      },
      nextRun,
      createdAt: now,
      updatedAt: now,
    };

    await this.schedules.insertOne(doc);
    
    const { _id, ...result } = doc as any;
    return result;
  }

  async getSchedule(scheduleId: string): Promise<ScheduleDoc | null> {
    const doc = await this.schedules.findOne({ scheduleId });
    if (!doc) return null;
    const { _id, ...result } = doc as any;
    return result;
  }

  async listSchedules(): Promise<ScheduleDoc[]> {
    const docs = await this.schedules.find({}).sort({ createdAt: -1 }).toArray();
    return docs.map(doc => {
      const { _id, ...result } = doc as any;
      return result;
    });
  }

  async enableSchedule(scheduleId: string): Promise<boolean> {
    const result = await this.schedules.updateOne(
      { scheduleId },
      { $set: { enabled: true, updatedAt: new Date() } }
    );
    return result.modifiedCount > 0;
  }

  async disableSchedule(scheduleId: string): Promise<boolean> {
    const result = await this.schedules.updateOne(
      { scheduleId },
      { $set: { enabled: false, updatedAt: new Date() } }
    );
    return result.modifiedCount > 0;
  }

  // ─────────────────────────────────────────────────────────────
  // Run Schedule
  // ─────────────────────────────────────────────────────────────

  async runScheduleNow(scheduleId: string): Promise<{ jobId: string } | null> {
    const schedule = await this.getSchedule(scheduleId);
    if (!schedule) return null;

    // Create backtest job
    const queue = getBacktestJobQueue(this.db);
    
    const toDate = new Date();
    const fromDate = new Date();
    fromDate.setFullYear(fromDate.getFullYear() - schedule.config.windowYears);

    const job = await queue.createJob({
      assets: schedule.config.assets,
      tf: schedule.config.tf,
      from: fromDate.toISOString(),
      to: toDate.toISOString(),
    });

    // Update schedule
    await this.schedules.updateOne(
      { scheduleId },
      {
        $set: {
          lastRun: new Date(),
          lastRunId: job.jobId,
          nextRun: parseNextRun(schedule.cron),
          updatedAt: new Date(),
        },
      }
    );

    return { jobId: job.jobId };
  }

  // ─────────────────────────────────────────────────────────────
  // Scheduler Loop
  // ─────────────────────────────────────────────────────────────

  async start(): Promise<void> {
    if (this.running) return;
    this.running = true;

    console.log('[BacktestScheduler] Started');

    while (this.running) {
      try {
        await this.checkAndRunDueSchedules();
      } catch (err: any) {
        console.error('[BacktestScheduler] Error:', err.message);
      }
      
      await sleep(60000);  // Check every minute
    }
  }

  stop(): void {
    this.running = false;
    console.log('[BacktestScheduler] Stopped');
  }

  private async checkAndRunDueSchedules(): Promise<void> {
    const now = new Date();

    const dueSchedules = await this.schedules
      .find({
        enabled: true,
        nextRun: { $lte: now },
      })
      .toArray();

    for (const schedule of dueSchedules) {
      console.log(`[BacktestScheduler] Running schedule: ${schedule.name}`);
      await this.runScheduleNow(schedule.scheduleId);
    }
  }

  // ─────────────────────────────────────────────────────────────
  // Edge History
  // ─────────────────────────────────────────────────────────────

  async recordEdgeHistory(runId: string): Promise<void> {
    // Get trades from run
    const trades = await this.db.collection('ta_backtest_trades')
      .find({ runId })
      .toArray();

    // Group by pattern
    const patternMetrics = new Map<string, {
      trades: number;
      wins: number;
      losses: number;
      sumR: number;
    }>();

    for (const trade of trades) {
      const patterns = trade.decisionSnapshot?.patternsUsed || [];
      for (const pattern of patterns) {
        const existing = patternMetrics.get(pattern) || {
          trades: 0,
          wins: 0,
          losses: 0,
          sumR: 0,
        };

        existing.trades++;
        existing.sumR += trade.rMultiple || 0;
        
        if (trade.exitType === 'T1' || trade.exitType === 'T2') {
          existing.wins++;
        } else if (trade.exitType === 'STOP') {
          existing.losses++;
        }

        patternMetrics.set(pattern, existing);
      }
    }

    // Save to history
    const timestamp = new Date();
    const docs: EdgeHistoryDoc[] = [];

    for (const [pattern, metrics] of patternMetrics) {
      const winRate = (metrics.wins + metrics.losses) > 0
        ? metrics.wins / (metrics.wins + metrics.losses)
        : 0;
      
      const positiveR = trades
        .filter(t => t.decisionSnapshot?.patternsUsed?.includes(pattern) && t.rMultiple > 0)
        .reduce((sum, t) => sum + t.rMultiple, 0);
      const negativeR = Math.abs(trades
        .filter(t => t.decisionSnapshot?.patternsUsed?.includes(pattern) && t.rMultiple < 0)
        .reduce((sum, t) => sum + t.rMultiple, 0));
      
      const profitFactor = negativeR > 0 ? positiveR / negativeR : positiveR > 0 ? 10 : 0;
      const avgR = metrics.trades > 0 ? metrics.sumR / metrics.trades : 0;

      docs.push({
        pattern,
        timestamp,
        runId,
        trades: metrics.trades,
        winRate,
        profitFactor,
        avgR,
      });
    }

    if (docs.length > 0) {
      await this.edgeHistory.insertMany(docs);
    }
  }

  async getEdgeHistory(pattern: string, limit: number = 20): Promise<EdgeHistoryDoc[]> {
    const docs = await this.edgeHistory
      .find({ pattern })
      .sort({ timestamp: -1 })
      .limit(limit)
      .toArray();

    return docs.map(doc => {
      const { _id, ...result } = doc as any;
      return result;
    });
  }

  async detectEdgeDecay(pattern: string): Promise<{
    decaying: boolean;
    pfDrop?: number;
    recent: number[];
  }> {
    const history = await this.getEdgeHistory(pattern, 5);
    
    if (history.length < 3) {
      return { decaying: false, recent: history.map(h => h.profitFactor) };
    }

    const recent = history.slice(0, 3).map(h => h.profitFactor);
    const avgRecent = recent.reduce((a, b) => a + b, 0) / recent.length;
    
    // Check if all recent PF < 1
    const decaying = avgRecent < 1;
    
    // Calculate drop from older
    const older = history.slice(3);
    if (older.length > 0) {
      const avgOlder = older.reduce((sum, h) => sum + h.profitFactor, 0) / older.length;
      return {
        decaying,
        pfDrop: avgOlder - avgRecent,
        recent,
      };
    }

    return { decaying, recent };
  }
}

// ═══════════════════════════════════════════════════════════════
// Routes
// ═══════════════════════════════════════════════════════════════

export async function registerSchedulerRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const scheduler = new BacktestScheduler(db);
  await scheduler.ensureIndexes();

  // POST /schedules - Create schedule
  app.post('/schedules', async (request: FastifyRequest<{
    Body: {
      name: string;
      cron: string;
      assets: string[];
      tf: string;
      windowYears?: number;
    }
  }>) => {
    const body = request.body;
    
    if (!body.name || !body.cron || !body.assets || !body.tf) {
      return { ok: false, error: 'name, cron, assets, tf required' };
    }

    const schedule = await scheduler.createSchedule(body);
    return { ok: true, schedule };
  });

  // GET /schedules - List schedules
  app.get('/schedules', async () => {
    const schedules = await scheduler.listSchedules();
    return { ok: true, count: schedules.length, schedules };
  });

  // GET /schedules/:id - Get schedule
  app.get('/schedules/:id', async (request: FastifyRequest<{
    Params: { id: string }
  }>) => {
    const schedule = await scheduler.getSchedule(request.params.id);
    if (!schedule) {
      return { ok: false, error: 'Schedule not found' };
    }
    return { ok: true, schedule };
  });

  // POST /schedules/:id/run - Run schedule now
  app.post('/schedules/:id/run', async (request: FastifyRequest<{
    Params: { id: string }
  }>) => {
    const result = await scheduler.runScheduleNow(request.params.id);
    if (!result) {
      return { ok: false, error: 'Schedule not found' };
    }
    return { ok: true, ...result };
  });

  // POST /schedules/:id/enable
  app.post('/schedules/:id/enable', async (request: FastifyRequest<{
    Params: { id: string }
  }>) => {
    const success = await scheduler.enableSchedule(request.params.id);
    return { ok: success };
  });

  // POST /schedules/:id/disable
  app.post('/schedules/:id/disable', async (request: FastifyRequest<{
    Params: { id: string }
  }>) => {
    const success = await scheduler.disableSchedule(request.params.id);
    return { ok: success };
  });

  // GET /edge/history/:pattern
  app.get('/edge/history/:pattern', async (request: FastifyRequest<{
    Params: { pattern: string };
    Querystring: { limit?: string };
  }>) => {
    const { pattern } = request.params;
    const limit = request.query.limit ? parseInt(request.query.limit, 10) : 20;
    const history = await scheduler.getEdgeHistory(pattern, limit);
    return { ok: true, pattern, history };
  });

  // GET /edge/decay/:pattern
  app.get('/edge/decay/:pattern', async (request: FastifyRequest<{
    Params: { pattern: string }
  }>) => {
    const { pattern } = request.params;
    const result = await scheduler.detectEdgeDecay(pattern);
    return { ok: true, pattern, ...result };
  });

  console.log('[Scheduler] Routes registered: /schedules, /edge/history, /edge/decay');
}

// ═══════════════════════════════════════════════════════════════
// Module
// ═══════════════════════════════════════════════════════════════

export async function registerSchedulerModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[Scheduler] Registering Backtest Scheduler v5.3...');
  
  await app.register(async (instance) => {
    await registerSchedulerRoutes(instance, { db });
  }, { prefix: '/scheduler' });
  
  // Start scheduler loop (optional - can be disabled)
  // const scheduler = new BacktestScheduler(db);
  // scheduler.start();
  
  console.log('[Scheduler] ✅ Backtest Scheduler registered at /api/ta/scheduler/*');
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
