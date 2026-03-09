/**
 * Dataset Pipeline
 * 
 * Manages ML dataset creation, backfill, and statistics
 */

import { Db, Collection } from 'mongodb';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface DatasetStats {
  version: string;
  totalRows: number;
  
  // Split distribution
  trainRows: number;
  valRows: number;
  testRows: number;
  
  // Label distribution
  entryHitRate: number;
  avgR: number;
  winRate: number;
  
  // Time coverage
  minTimestamp: Date;
  maxTimestamp: Date;
  
  // Pattern distribution
  patternCounts: Record<string, number>;
  
  // Quality
  featureCompleteness: number;
  
  updatedAt: Date;
}

export interface PendingOutcome {
  scenarioId: string;
  asset: string;
  timeframe: string;
  runId: string;
  entry: number;
  stop: number;
  target1: number;
  target2?: number;
  direction: 'LONG' | 'SHORT';
  openTs: number;
  features: Record<string, number>;
  status: 'PENDING' | 'EVALUATED' | 'EXPIRED';
  createdAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// COLLECTIONS
// ═══════════════════════════════════════════════════════════════

const COLLECTION_DATASET = 'ta_ml_rows_v4';
const COLLECTION_STATS = 'ta_dataset_stats';
const COLLECTION_PENDING = 'ta_pending_outcomes';

// ═══════════════════════════════════════════════════════════════
// DATASET SERVICE
// ═══════════════════════════════════════════════════════════════

export class DatasetService {
  private db: Db;
  private datasetCol: Collection;
  private statsCol: Collection;
  private pendingCol: Collection;
  
  constructor(db: Db) {
    this.db = db;
    this.datasetCol = db.collection(COLLECTION_DATASET);
    this.statsCol = db.collection(COLLECTION_STATS);
    this.pendingCol = db.collection(COLLECTION_PENDING);
  }
  
  /**
   * Initialize indexes
   */
  async ensureIndexes(): Promise<void> {
    // Dataset indexes
    await this.datasetCol.createIndex({ rowId: 1 }, { unique: true });
    await this.datasetCol.createIndex({ scenarioId: 1 });
    await this.datasetCol.createIndex({ split: 1 });
    await this.datasetCol.createIndex({ timestamp: 1 });
    
    // Pending outcomes
    await this.pendingCol.createIndex({ scenarioId: 1 }, { unique: true });
    await this.pendingCol.createIndex({ status: 1, openTs: 1 });
    await this.pendingCol.createIndex({ createdAt: 1 });
    
    console.log('[DatasetService] Indexes created');
  }
  
  /**
   * Compute and store dataset statistics
   */
  async computeStats(): Promise<DatasetStats> {
    const totalRows = await this.datasetCol.countDocuments();
    
    // Split distribution
    const splitAgg = await this.datasetCol.aggregate([
      { $group: { _id: '$split', count: { $sum: 1 } } }
    ]).toArray();
    
    const trainRows = splitAgg.find(s => s._id === 'train')?.count || 0;
    const valRows = splitAgg.find(s => s._id === 'val')?.count || 0;
    const testRows = splitAgg.find(s => s._id === 'test')?.count || 0;
    
    // Label stats
    const labelAgg = await this.datasetCol.aggregate([
      {
        $group: {
          _id: null,
          avgEntryHit: { $avg: '$labels.label_entry_hit' },
          avgR: { $avg: '$labels.label_r_multiple' },
          minTs: { $min: '$timestamp' },
          maxTs: { $max: '$timestamp' },
        }
      }
    ]).toArray();
    
    const labelStats = labelAgg[0] || {};
    
    // Win rate (R > 0 given entry hit)
    const winAgg = await this.datasetCol.aggregate([
      { $match: { 'labels.label_entry_hit': 1 } },
      {
        $group: {
          _id: null,
          total: { $sum: 1 },
          wins: { $sum: { $cond: [{ $gt: ['$labels.label_r_multiple', 0] }, 1, 0] } }
        }
      }
    ]).toArray();
    
    const winRate = winAgg[0] ? winAgg[0].wins / winAgg[0].total : 0;
    
    // Pattern distribution
    const patternAgg = await this.datasetCol.aggregate([
      { $group: { _id: '$patternType', count: { $sum: 1 } } }
    ]).toArray();
    
    const patternCounts: Record<string, number> = {};
    for (const p of patternAgg) {
      patternCounts[p._id || 'unknown'] = p.count;
    }
    
    // Feature completeness (sample check)
    const sampleRow = await this.datasetCol.findOne();
    const featureCompleteness = sampleRow?.features
      ? Object.keys(sampleRow.features).length / 20  // Assume 20 expected features
      : 0;
    
    const stats: DatasetStats = {
      version: 'v4',
      totalRows,
      trainRows,
      valRows,
      testRows,
      entryHitRate: labelStats.avgEntryHit || 0,
      avgR: labelStats.avgR || 0,
      winRate,
      minTimestamp: labelStats.minTs ? new Date(labelStats.minTs) : new Date(),
      maxTimestamp: labelStats.maxTs ? new Date(labelStats.maxTs) : new Date(),
      patternCounts,
      featureCompleteness: Math.min(1, featureCompleteness),
      updatedAt: new Date(),
    };
    
    // Store stats
    await this.statsCol.updateOne(
      { version: 'v4' },
      { $set: stats },
      { upsert: true }
    );
    
    return stats;
  }
  
  /**
   * Get latest stats
   */
  async getStats(): Promise<DatasetStats | null> {
    return this.statsCol.findOne({ version: 'v4' }) as any;
  }
  
  /**
   * Add pending outcome for future evaluation
   */
  async addPendingOutcome(pending: Omit<PendingOutcome, 'status' | 'createdAt'>): Promise<void> {
    await this.pendingCol.updateOne(
      { scenarioId: pending.scenarioId },
      { 
        $set: {
          ...pending,
          status: 'PENDING',
          createdAt: new Date(),
        }
      },
      { upsert: true }
    );
  }
  
  /**
   * Get pending outcomes ready for evaluation
   */
  async getPendingOutcomes(maxBarsAgo: number = 100): Promise<PendingOutcome[]> {
    const cutoff = Date.now() - maxBarsAgo * 24 * 60 * 60 * 1000; // Assuming daily bars
    
    return this.pendingCol
      .find({
        status: 'PENDING',
        openTs: { $lt: cutoff }
      })
      .toArray() as any;
  }
  
  /**
   * Mark outcome as evaluated
   */
  async markEvaluated(scenarioId: string): Promise<void> {
    await this.pendingCol.updateOne(
      { scenarioId },
      { $set: { status: 'EVALUATED' } }
    );
  }
  
  /**
   * Expire old pending outcomes
   */
  async expireOldPending(daysOld: number = 180): Promise<number> {
    const cutoff = Date.now() - daysOld * 24 * 60 * 60 * 1000;
    
    const result = await this.pendingCol.updateMany(
      {
        status: 'PENDING',
        openTs: { $lt: cutoff }
      },
      { $set: { status: 'EXPIRED' } }
    );
    
    return result.modifiedCount;
  }
  
  /**
   * Get dataset health
   */
  async getHealth(): Promise<{
    ok: boolean;
    totalRows: number;
    pendingOutcomes: number;
    lastUpdate: Date | null;
    issues: string[];
  }> {
    const stats = await this.getStats();
    const pendingCount = await this.pendingCol.countDocuments({ status: 'PENDING' });
    
    const issues: string[] = [];
    
    if (!stats || stats.totalRows < 1000) {
      issues.push('Insufficient training data (<1000 rows)');
    }
    
    if (stats && stats.featureCompleteness < 0.8) {
      issues.push('Low feature completeness');
    }
    
    if (stats && stats.trainRows < stats.valRows) {
      issues.push('Train set smaller than validation set');
    }
    
    return {
      ok: issues.length === 0,
      totalRows: stats?.totalRows || 0,
      pendingOutcomes: pendingCount,
      lastUpdate: stats?.updatedAt || null,
      issues,
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

export function createDatasetService(db: Db): DatasetService {
  return new DatasetService(db);
}
