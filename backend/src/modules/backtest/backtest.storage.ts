/**
 * Phase 5.1 B1.5 — Backtest Storage
 * 
 * MongoDB collections and CRUD operations for backtest runs and trades.
 */

import { Db, Collection } from 'mongodb';
import {
  BacktestRunDoc,
  BacktestTradeDoc,
  BacktestSummary,
  BacktestRunStatus,
} from './domain/types.js';

const RUNS_COLLECTION = 'ta_backtest_runs';
const TRADES_COLLECTION = 'ta_backtest_trades';

// ═══════════════════════════════════════════════════════════════
// Storage Class
// ═══════════════════════════════════════════════════════════════

export class BacktestStorage {
  private db: Db;
  private runs: Collection;
  private trades: Collection;

  constructor(db: Db) {
    this.db = db;
    this.runs = db.collection(RUNS_COLLECTION);
    this.trades = db.collection(TRADES_COLLECTION);
  }

  // ═══════════════════════════════════════════════════════════════
  // Indexes
  // ═══════════════════════════════════════════════════════════════

  async ensureIndexes(): Promise<void> {
    // Runs indexes
    await this.runs.createIndex({ runId: 1 }, { unique: true });
    await this.runs.createIndex({ asset: 1, timeframe: 1, createdAt: -1 });
    await this.runs.createIndex({ status: 1 });
    await this.runs.createIndex({ createdAt: -1 });

    // Trades indexes
    await this.trades.createIndex({ runId: 1, openedAtIndex: 1 });
    await this.trades.createIndex({ runId: 1 });
    await this.trades.createIndex({ tradeId: 1 }, { unique: true });

    console.log('[BacktestStorage] Indexes ensured');
  }

  // ═══════════════════════════════════════════════════════════════
  // Runs CRUD
  // ═══════════════════════════════════════════════════════════════

  async insertRunCreated(run: BacktestRunDoc): Promise<void> {
    await this.runs.insertOne(run);
  }

  async markRunRunning(runId: string): Promise<void> {
    await this.runs.updateOne(
      { runId },
      { $set: { status: 'RUNNING' as BacktestRunStatus } }
    );
  }

  async markRunDone(runId: string, summary: BacktestSummary): Promise<void> {
    await this.runs.updateOne(
      { runId },
      { 
        $set: { 
          status: 'DONE' as BacktestRunStatus,
          summary,
        } 
      }
    );
  }

  async markRunFailed(runId: string, error: string): Promise<void> {
    await this.runs.updateOne(
      { runId },
      { 
        $set: { 
          status: 'FAILED' as BacktestRunStatus,
          error,
        } 
      }
    );
  }

  async getRun(runId: string): Promise<BacktestRunDoc | null> {
    const doc = await this.runs.findOne({ runId });
    if (!doc) return null;
    
    const { _id, ...run } = doc as any;
    return run as BacktestRunDoc;
  }

  async listRuns(limit: number = 20): Promise<BacktestRunDoc[]> {
    const docs = await this.runs
      .find({})
      .sort({ createdAt: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...run } = doc as any;
      return run as BacktestRunDoc;
    });
  }

  async getRunsByAsset(
    asset: string,
    timeframe: string,
    limit: number = 10
  ): Promise<BacktestRunDoc[]> {
    const docs = await this.runs
      .find({ asset, timeframe, status: 'DONE' })
      .sort({ createdAt: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...run } = doc as any;
      return run as BacktestRunDoc;
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Trades CRUD
  // ═══════════════════════════════════════════════════════════════

  async insertTrades(trades: BacktestTradeDoc[]): Promise<number> {
    if (trades.length === 0) return 0;
    
    const result = await this.trades.insertMany(trades);
    return result.insertedCount;
  }

  async getTrades(
    runId: string,
    limit: number = 200,
    skip: number = 0
  ): Promise<BacktestTradeDoc[]> {
    const docs = await this.trades
      .find({ runId })
      .sort({ signalIndex: 1 })
      .skip(skip)
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...trade } = doc as any;
      return trade as BacktestTradeDoc;
    });
  }

  async countTrades(runId: string): Promise<number> {
    return this.trades.countDocuments({ runId });
  }

  async getTradesByExitType(
    runId: string,
    exitType: string
  ): Promise<BacktestTradeDoc[]> {
    const docs = await this.trades
      .find({ runId, exitType })
      .sort({ signalIndex: 1 })
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...trade } = doc as any;
      return trade as BacktestTradeDoc;
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Cleanup
  // ═══════════════════════════════════════════════════════════════

  async deleteRun(runId: string): Promise<void> {
    await this.trades.deleteMany({ runId });
    await this.runs.deleteOne({ runId });
  }

  async cleanupOldRuns(keepCount: number = 50): Promise<number> {
    const runs = await this.runs
      .find({})
      .sort({ createdAt: -1 })
      .skip(keepCount)
      .toArray();
    
    if (runs.length === 0) return 0;
    
    const runIds = runs.map(r => (r as any).runId);
    
    await this.trades.deleteMany({ runId: { $in: runIds } });
    const result = await this.runs.deleteMany({ runId: { $in: runIds } });
    
    return result.deletedCount;
  }
}

// ═══════════════════════════════════════════════════════════════
// Singleton
// ═══════════════════════════════════════════════════════════════

let storageInstance: BacktestStorage | null = null;

export function getBacktestStorage(db: Db): BacktestStorage {
  if (!storageInstance) {
    storageInstance = new BacktestStorage(db);
  }
  return storageInstance;
}
