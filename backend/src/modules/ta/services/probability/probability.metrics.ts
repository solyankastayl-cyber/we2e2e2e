/**
 * Probability Metrics (P4.2)
 * 
 * Logging and tracking of probability predictions
 */

import { Db } from 'mongodb';
import type { ProbabilityMetrics, ProbabilityPack, CompositionWeights } from './probability.types.js';

export class ProbabilityMetricsLogger {
  private db: Db;
  private collectionName = 'ta_probability_metrics';

  constructor(db: Db) {
    this.db = db;
  }

  async ensureIndexes(): Promise<void> {
    const collection = this.db.collection(this.collectionName);
    await collection.createIndex({ runId: 1 }, { unique: true });
    await collection.createIndex({ asset: 1, timeframe: 1, timestamp: -1 });
    await collection.createIndex({ timestamp: -1 });
  }

  /**
   * Log probability prediction
   */
  async log(
    runId: string,
    asset: string,
    timeframe: string,
    pack: ProbabilityPack
  ): Promise<void> {
    const metrics: ProbabilityMetrics = {
      runId,
      asset,
      timeframe,
      pEntryPredicted: pack.pEntry,
      pWinPredicted: pack.pWin,
      compositionMethod: pack.compositionMethod,
      weights: pack.weights,
      timestamp: new Date()
    };

    await this.db.collection(this.collectionName).insertOne(metrics);
  }

  /**
   * Get recent metrics
   */
  async getRecent(limit: number = 100): Promise<ProbabilityMetrics[]> {
    const docs = await this.db.collection(this.collectionName)
      .find({})
      .sort({ timestamp: -1 })
      .limit(limit)
      .toArray();
    return docs as unknown as ProbabilityMetrics[];
  }

  /**
   * Get metrics for asset/timeframe
   */
  async getForAsset(
    asset: string,
    timeframe: string,
    limit: number = 50
  ): Promise<ProbabilityMetrics[]> {
    const docs = await this.db.collection(this.collectionName)
      .find({ asset, timeframe })
      .sort({ timestamp: -1 })
      .limit(limit)
      .toArray();
    return docs as unknown as ProbabilityMetrics[];
  }

  /**
   * Get average weights used
   */
  async getAverageWeights(): Promise<CompositionWeights> {
    const result = await this.db.collection(this.collectionName).aggregate([
      {
        $group: {
          _id: null,
          avgMl: { $avg: '$weights.ml' },
          avgScenario: { $avg: '$weights.scenario' },
          avgPriors: { $avg: '$weights.priors' }
        }
      }
    ]).toArray();

    if (result.length === 0) {
      return { ml: 0.33, scenario: 0.33, priors: 0.34 };
    }

    return {
      ml: result[0].avgMl || 0.33,
      scenario: result[0].avgScenario || 0.33,
      priors: result[0].avgPriors || 0.34
    };
  }

  /**
   * Get prediction drift (compare recent vs historical)
   */
  async getPredictionDrift(): Promise<{
    recentAvg: number;
    historicalAvg: number;
    drift: number;
  }> {
    // Recent (last 50)
    const recent = await this.db.collection(this.collectionName)
      .find({})
      .sort({ timestamp: -1 })
      .limit(50)
      .toArray();
    
    // Historical (50-200)
    const historical = await this.db.collection(this.collectionName)
      .find({})
      .sort({ timestamp: -1 })
      .skip(50)
      .limit(150)
      .toArray();

    const recentAvg = recent.length > 0
      ? recent.reduce((s, d) => s + (d.pEntryPredicted || 0), 0) / recent.length
      : 0.5;
    
    const historicalAvg = historical.length > 0
      ? historical.reduce((s, d) => s + (d.pEntryPredicted || 0), 0) / historical.length
      : 0.5;

    return {
      recentAvg,
      historicalAvg,
      drift: Math.abs(recentAvg - historicalAvg)
    };
  }
}

// Singleton
let metricsLogger: ProbabilityMetricsLogger | null = null;

export function getProbabilityMetricsLogger(db: Db): ProbabilityMetricsLogger {
  if (!metricsLogger) {
    metricsLogger = new ProbabilityMetricsLogger(db);
  }
  return metricsLogger;
}
