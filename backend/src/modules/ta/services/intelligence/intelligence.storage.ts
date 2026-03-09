/**
 * Intelligence Storage (P4.1)
 * 
 * Immutable storage for IntelligencePack runs
 */

import { Db } from 'mongodb';
import type { IntelligencePack } from './intelligence.types.js';

export class IntelligenceStorage {
  private db: Db;
  private collectionName = 'ta_intelligence_runs';

  constructor(db: Db) {
    this.db = db;
  }

  async ensureIndexes(): Promise<void> {
    const collection = this.db.collection(this.collectionName);
    
    // Unique run ID
    await collection.createIndex({ runId: 1 }, { unique: true });
    
    // Asset + timeframe + timestamp for queries
    await collection.createIndex({ asset: 1, timeframe: 1, asOfTs: -1 });
    
    // Created at for cleanup/pagination
    await collection.createIndex({ createdAt: -1 });
    
    // Bias for filtering
    await collection.createIndex({ topBias: 1 });
    
    // EV for ranking
    await collection.createIndex({ 'expectation.expectedEV': -1 });
  }

  /**
   * Save intelligence pack (insert-only, immutable)
   */
  async save(pack: IntelligencePack): Promise<void> {
    // Remove MongoDB _id if present to avoid conflicts
    const doc = { ...pack };
    delete (doc as any)._id;
    
    await this.db.collection(this.collectionName).insertOne(doc);
  }

  /**
   * Get by run ID
   */
  async getByRunId(runId: string): Promise<IntelligencePack | null> {
    const doc = await this.db.collection(this.collectionName)
      .findOne({ runId }, { projection: { _id: 0 } });
    return doc as IntelligencePack | null;
  }

  /**
   * Get latest for asset/timeframe
   */
  async getLatest(asset: string, timeframe: string): Promise<IntelligencePack | null> {
    const doc = await this.db.collection(this.collectionName)
      .findOne(
        { asset: asset.toUpperCase(), timeframe: timeframe.toLowerCase() },
        { sort: { asOfTs: -1, createdAt: -1 }, projection: { _id: 0 } }
      );
    return doc as IntelligencePack | null;
  }

  /**
   * Get history for asset/timeframe
   */
  async getHistory(
    asset: string,
    timeframe: string,
    limit: number = 50
  ): Promise<IntelligencePack[]> {
    const docs = await this.db.collection(this.collectionName)
      .find({ asset: asset.toUpperCase(), timeframe: timeframe.toLowerCase() })
      .sort({ asOfTs: -1, createdAt: -1 })
      .limit(limit)
      .project({ _id: 0 })
      .toArray();
    return docs as IntelligencePack[];
  }

  /**
   * Get top opportunities (high EV)
   */
  async getTopOpportunities(limit: number = 10): Promise<IntelligencePack[]> {
    const docs = await this.db.collection(this.collectionName)
      .find({
        topBias: { $in: ['LONG', 'SHORT'] },
        'expectation.expectedEV': { $gt: 0 }
      })
      .sort({ 'expectation.expectedEV': -1 })
      .limit(limit)
      .project({ _id: 0 })
      .toArray();
    return docs as IntelligencePack[];
  }

  /**
   * Count documents
   */
  async count(): Promise<number> {
    return this.db.collection(this.collectionName).countDocuments();
  }

  /**
   * Get stats
   */
  async getStats(): Promise<{
    total: number;
    byBias: Record<string, number>;
    avgEV: number;
    avgConfidence: number;
  }> {
    const total = await this.count();
    
    // By bias
    const biasCounts = await this.db.collection(this.collectionName)
      .aggregate([
        { $group: { _id: '$topBias', count: { $sum: 1 } } }
      ]).toArray();
    
    const byBias: Record<string, number> = {};
    biasCounts.forEach(b => { byBias[b._id] = b.count; });
    
    // Averages
    const avgResult = await this.db.collection(this.collectionName)
      .aggregate([
        {
          $group: {
            _id: null,
            avgEV: { $avg: '$expectation.expectedEV' },
            avgConfidence: { $avg: '$confidence' }
          }
        }
      ]).toArray();
    
    const avgs = avgResult[0] || { avgEV: 0, avgConfidence: 0 };
    
    return {
      total,
      byBias,
      avgEV: avgs.avgEV || 0,
      avgConfidence: avgs.avgConfidence || 0
    };
  }
}

// Singleton
let storageInstance: IntelligenceStorage | null = null;

export function getIntelligenceStorage(db: Db): IntelligenceStorage {
  if (!storageInstance) {
    storageInstance = new IntelligenceStorage(db);
  }
  return storageInstance;
}
