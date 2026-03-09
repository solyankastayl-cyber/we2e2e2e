/**
 * Forecast Storage (P4.4)
 * 
 * Immutable storage for forecast runs
 */

import { Db } from 'mongodb';
import type { ForecastPack } from './forecast.types.js';

export class ForecastStorage {
  private db: Db;
  private collectionName = 'ta_forecast_runs';

  constructor(db: Db) {
    this.db = db;
  }

  async ensureIndexes(): Promise<void> {
    const collection = this.db.collection(this.collectionName);
    await collection.createIndex({ runId: 1 }, { unique: true });
    await collection.createIndex({ asset: 1, tf: 1, createdAt: -1 });
    await collection.createIndex({ decisionRunId: 1 });
    await collection.createIndex({ intelligenceRunId: 1 });
    await collection.createIndex({ createdAt: -1 });
  }

  /**
   * Save forecast (insert-only)
   */
  async save(pack: ForecastPack): Promise<void> {
    const doc = { ...pack };
    delete (doc as any)._id;
    await this.db.collection(this.collectionName).insertOne(doc);
  }

  /**
   * Get by run ID
   */
  async getByRunId(runId: string): Promise<ForecastPack | null> {
    const doc = await this.db.collection(this.collectionName)
      .findOne({ runId }, { projection: { _id: 0 } });
    return doc as ForecastPack | null;
  }

  /**
   * Get latest for asset/tf
   */
  async getLatest(asset: string, tf: string): Promise<ForecastPack | null> {
    const doc = await this.db.collection(this.collectionName)
      .findOne(
        { asset: asset.toUpperCase(), tf: tf.toLowerCase() },
        { sort: { createdAt: -1 }, projection: { _id: 0 } }
      );
    return doc as ForecastPack | null;
  }

  /**
   * Get history
   */
  async getHistory(asset: string, tf: string, limit: number = 20): Promise<ForecastPack[]> {
    const docs = await this.db.collection(this.collectionName)
      .find({ asset: asset.toUpperCase(), tf: tf.toLowerCase() })
      .sort({ createdAt: -1 })
      .limit(limit)
      .project({ _id: 0 })
      .toArray();
    return docs as ForecastPack[];
  }

  /**
   * Get by decision run
   */
  async getByDecisionRun(decisionRunId: string): Promise<ForecastPack | null> {
    const doc = await this.db.collection(this.collectionName)
      .findOne({ decisionRunId }, { projection: { _id: 0 } });
    return doc as ForecastPack | null;
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
    byAsset: Record<string, number>;
    avgHorizon: number;
  }> {
    const total = await this.count();
    
    const assetCounts = await this.db.collection(this.collectionName)
      .aggregate([
        { $group: { _id: '$asset', count: { $sum: 1 } } }
      ]).toArray();
    
    const byAsset: Record<string, number> = {};
    assetCounts.forEach(a => { byAsset[a._id] = a.count; });
    
    const avgResult = await this.db.collection(this.collectionName)
      .aggregate([
        { $group: { _id: null, avgHorizon: { $avg: '$horizonBars' } } }
      ]).toArray();
    
    return {
      total,
      byAsset,
      avgHorizon: avgResult[0]?.avgHorizon || 0
    };
  }
}

// Singleton
let storageInstance: ForecastStorage | null = null;

export function getForecastStorage(db: Db): ForecastStorage {
  if (!storageInstance) {
    storageInstance = new ForecastStorage(db);
  }
  return storageInstance;
}
