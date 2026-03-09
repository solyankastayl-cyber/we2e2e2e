/**
 * Edge Storage (P5.0.6)
 * 
 * MongoDB storage for edge runs, stats, and global baseline
 */

import { Db, Collection, ObjectId } from 'mongodb';
import type { 
  EdgeRun, 
  EdgeAggregate, 
  GlobalBaseline,
  EdgeDimension,
  EdgeRebuildRequest,
  EdgeRebuildResult,
} from './domain/types.js';

// Collection names
const EDGE_RUNS_COLLECTION = 'ta_edge_runs';
const EDGE_STATS_COLLECTION = 'ta_edge_stats';
const EDGE_GLOBAL_COLLECTION = 'ta_edge_global';

/**
 * Edge Storage class
 */
export class EdgeStorage {
  private db: Db;
  private runsCollection: Collection;
  private statsCollection: Collection;
  private globalCollection: Collection;

  constructor(db: Db) {
    this.db = db;
    this.runsCollection = db.collection(EDGE_RUNS_COLLECTION);
    this.statsCollection = db.collection(EDGE_STATS_COLLECTION);
    this.globalCollection = db.collection(EDGE_GLOBAL_COLLECTION);
  }

  /**
   * Ensure indexes exist
   */
  async ensureIndexes(): Promise<void> {
    // Edge runs indexes
    await this.runsCollection.createIndex({ runId: 1 }, { unique: true });
    await this.runsCollection.createIndex({ startedAt: -1 });
    await this.runsCollection.createIndex({ status: 1 });
    
    // Edge stats indexes
    await this.statsCollection.createIndex(
      { edgeRunId: 1, dimension: 1, key: 1 },
      { unique: true }
    );
    await this.statsCollection.createIndex({ dimension: 1, edgeScore: -1 });
    await this.statsCollection.createIndex({ edgeRunId: 1 });
    await this.statsCollection.createIndex({ updatedAt: -1 });
    
    // Global baseline index
    await this.globalCollection.createIndex({ edgeRunId: 1 }, { unique: true });
    
    console.log('[EdgeStorage] Indexes ensured');
  }

  // ═══════════════════════════════════════════════════════════════
  // Edge Runs
  // ═══════════════════════════════════════════════════════════════

  /**
   * Create new edge run
   */
  async createRun(params: EdgeRebuildRequest): Promise<EdgeRun> {
    const runId = new ObjectId().toHexString();
    
    const run: EdgeRun = {
      runId,
      params,
      startedAt: new Date(),
      status: 'RUNNING',
      rowsProcessed: 0,
      aggregatesCreated: 0,
    };
    
    await this.runsCollection.insertOne(run);
    return run;
  }

  /**
   * Update run status
   */
  async updateRun(
    runId: string,
    update: Partial<EdgeRun>
  ): Promise<void> {
    await this.runsCollection.updateOne(
      { runId },
      { $set: update }
    );
  }

  /**
   * Complete run
   */
  async completeRun(
    runId: string,
    result: {
      status: 'SUCCESS' | 'FAILED';
      rowsProcessed: number;
      aggregatesCreated: number;
      globalBaseline?: GlobalBaseline;
      errors?: string[];
    }
  ): Promise<void> {
    await this.runsCollection.updateOne(
      { runId },
      {
        $set: {
          status: result.status,
          finishedAt: new Date(),
          rowsProcessed: result.rowsProcessed,
          aggregatesCreated: result.aggregatesCreated,
          globalBaseline: result.globalBaseline,
          errors: result.errors,
        }
      }
    );
  }

  /**
   * Get run by ID
   */
  async getRun(runId: string): Promise<EdgeRun | null> {
    const doc = await this.runsCollection.findOne({ runId });
    if (!doc) return null;
    
    // Remove MongoDB _id
    const { _id, ...run } = doc as any;
    return run as EdgeRun;
  }

  /**
   * Get latest successful run
   */
  async getLatestRun(): Promise<EdgeRun | null> {
    const doc = await this.runsCollection.findOne(
      { status: 'SUCCESS' },
      { sort: { finishedAt: -1 } }
    );
    
    if (!doc) return null;
    
    const { _id, ...run } = doc as any;
    return run as EdgeRun;
  }

  /**
   * List recent runs
   */
  async listRuns(limit: number = 20): Promise<EdgeRun[]> {
    const docs = await this.runsCollection
      .find({})
      .sort({ startedAt: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...run } = doc as any;
      return run as EdgeRun;
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Edge Stats
  // ═══════════════════════════════════════════════════════════════

  /**
   * Save aggregates for a run
   */
  async saveAggregates(
    edgeRunId: string,
    aggregates: EdgeAggregate[]
  ): Promise<number> {
    if (aggregates.length === 0) return 0;
    
    // Add runId to each aggregate
    const docs = aggregates.map(agg => ({
      edgeRunId,
      ...agg,
    }));
    
    // Use bulk upsert
    const bulkOps = docs.map(doc => ({
      updateOne: {
        filter: {
          edgeRunId,
          dimension: doc.dimension,
          key: doc.key,
        },
        update: { $set: doc },
        upsert: true,
      }
    }));
    
    const result = await this.statsCollection.bulkWrite(bulkOps);
    return result.upsertedCount + result.modifiedCount;
  }

  /**
   * Get aggregates for latest run
   */
  async getLatestAggregates(
    dimension?: EdgeDimension
  ): Promise<EdgeAggregate[]> {
    const latestRun = await this.getLatestRun();
    if (!latestRun) return [];
    
    return this.getAggregatesByRunId(latestRun.runId, dimension);
  }

  /**
   * Get aggregates by run ID
   */
  async getAggregatesByRunId(
    edgeRunId: string,
    dimension?: EdgeDimension
  ): Promise<EdgeAggregate[]> {
    const query: any = { edgeRunId };
    if (dimension) {
      query.dimension = dimension;
    }
    
    const docs = await this.statsCollection
      .find(query)
      .sort({ edgeScore: -1 })
      .toArray();
    
    return docs.map(doc => {
      const { _id, edgeRunId: _, ...agg } = doc as any;
      return agg as EdgeAggregate;
    });
  }

  /**
   * Get top performers for a dimension
   */
  async getTopPerformers(
    dimension: EdgeDimension,
    limit: number = 10
  ): Promise<EdgeAggregate[]> {
    const latestRun = await this.getLatestRun();
    if (!latestRun) return [];
    
    const docs = await this.statsCollection
      .find({
        edgeRunId: latestRun.runId,
        dimension,
        sampleSize: { $gte: 30 },
      })
      .sort({ edgeScore: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, edgeRunId: _, ...agg } = doc as any;
      return agg as EdgeAggregate;
    });
  }

  /**
   * Get worst performers for a dimension
   */
  async getWorstPerformers(
    dimension: EdgeDimension,
    limit: number = 10
  ): Promise<EdgeAggregate[]> {
    const latestRun = await this.getLatestRun();
    if (!latestRun) return [];
    
    const docs = await this.statsCollection
      .find({
        edgeRunId: latestRun.runId,
        dimension,
        sampleSize: { $gte: 30 },
      })
      .sort({ edgeScore: 1 })
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, edgeRunId: _, ...agg } = doc as any;
      return agg as EdgeAggregate;
    });
  }

  /**
   * Get aggregate by dimension and key
   */
  async getAggregate(
    dimension: EdgeDimension,
    key: string
  ): Promise<EdgeAggregate | null> {
    const latestRun = await this.getLatestRun();
    if (!latestRun) return null;
    
    const doc = await this.statsCollection.findOne({
      edgeRunId: latestRun.runId,
      dimension,
      key,
    });
    
    if (!doc) return null;
    
    const { _id, edgeRunId: _, ...agg } = doc as any;
    return agg as EdgeAggregate;
  }

  // ═══════════════════════════════════════════════════════════════
  // Global Baseline
  // ═══════════════════════════════════════════════════════════════

  /**
   * Save global baseline
   */
  async saveGlobalBaseline(
    edgeRunId: string,
    baseline: GlobalBaseline
  ): Promise<void> {
    await this.globalCollection.updateOne(
      { edgeRunId },
      { 
        $set: { 
          edgeRunId,
          ...baseline,
          updatedAt: new Date(),
        } 
      },
      { upsert: true }
    );
  }

  /**
   * Get latest global baseline
   */
  async getLatestGlobalBaseline(): Promise<GlobalBaseline | null> {
    const latestRun = await this.getLatestRun();
    if (!latestRun) return null;
    
    const doc = await this.globalCollection.findOne({
      edgeRunId: latestRun.runId,
    });
    
    if (!doc) return null;
    
    return {
      totalSamples: doc.totalSamples,
      globalWinRate: doc.globalWinRate,
      globalAvgR: doc.globalAvgR,
      globalAvgEV: doc.globalAvgEV,
      globalPF: doc.globalPF,
    };
  }

  // ═══════════════════════════════════════════════════════════════
  // Cleanup
  // ═══════════════════════════════════════════════════════════════

  /**
   * Delete old runs (keep last N)
   */
  async cleanupOldRuns(keepCount: number = 10): Promise<number> {
    const runs = await this.runsCollection
      .find({})
      .sort({ startedAt: -1 })
      .skip(keepCount)
      .toArray();
    
    if (runs.length === 0) return 0;
    
    const runIds = runs.map(r => (r as any).runId);
    
    // Delete stats for old runs
    await this.statsCollection.deleteMany({
      edgeRunId: { $in: runIds }
    });
    
    // Delete global baselines for old runs
    await this.globalCollection.deleteMany({
      edgeRunId: { $in: runIds }
    });
    
    // Delete old runs
    const result = await this.runsCollection.deleteMany({
      runId: { $in: runIds }
    });
    
    return result.deletedCount;
  }
}

// Singleton
let storageInstance: EdgeStorage | null = null;

export function getEdgeStorage(db: Db): EdgeStorage {
  if (!storageInstance) {
    storageInstance = new EdgeStorage(db);
  }
  return storageInstance;
}
