/**
 * Scenario Cache
 * 
 * Caches Monte Carlo simulation results to avoid recomputation
 */

import { Db, Collection } from 'mongodb';
import { createHash } from 'crypto';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface ScenarioCacheEntry {
  cacheKey: string;
  scenarioId?: string;
  patternType: string;
  volatilityRegime: 'LOW' | 'MEDIUM' | 'HIGH';
  direction: 'LONG' | 'SHORT';
  riskRewardRatio: number;
  
  // Simulation results
  simulation: {
    numPaths: number;
    pTarget1: number;
    pTarget2: number;
    pStop: number;
    pTimeout: number;
    expectedR: number;
    rDistribution: Array<{ percentile: number; value: number }>;
    confidence: number;
    scenarioEV: number;
  };
  
  // Metadata
  createdAt: Date;
  expiresAt: Date;
  hitCount: number;
}

export interface DistributionStorage {
  scenarioId: string;
  runId: string;
  timestamp: Date;
  
  paths: number;
  distribution: {
    percentiles: number[];
    values: number[];
    histogram: Array<{ bucket: number; count: number }>;
  };
  
  // Summary
  mean: number;
  median: number;
  std: number;
  skew: number;
}

// ═══════════════════════════════════════════════════════════════
// COLLECTIONS
// ═══════════════════════════════════════════════════════════════

const COLLECTION_CACHE = 'ta_scenario_cache';
const COLLECTION_DISTRIBUTIONS = 'ta_scenario_distributions';

// ═══════════════════════════════════════════════════════════════
// SCENARIO CACHE SERVICE
// ═══════════════════════════════════════════════════════════════

export class ScenarioCacheService {
  private db: Db;
  private cacheCol: Collection;
  private distCol: Collection;
  private ttlMs: number;
  
  constructor(db: Db, ttlHours: number = 24) {
    this.db = db;
    this.cacheCol = db.collection(COLLECTION_CACHE);
    this.distCol = db.collection(COLLECTION_DISTRIBUTIONS);
    this.ttlMs = ttlHours * 60 * 60 * 1000;
  }
  
  /**
   * Initialize indexes
   */
  async ensureIndexes(): Promise<void> {
    await this.cacheCol.createIndex({ cacheKey: 1 }, { unique: true });
    await this.cacheCol.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 }); // TTL index
    await this.cacheCol.createIndex({ patternType: 1, volatilityRegime: 1 });
    
    await this.distCol.createIndex({ scenarioId: 1 });
    await this.distCol.createIndex({ runId: 1 });
    await this.distCol.createIndex({ timestamp: -1 });
    
    console.log('[ScenarioCache] Indexes created');
  }
  
  /**
   * Generate cache key
   */
  generateCacheKey(params: {
    patternType: string;
    volatilityRegime: string;
    direction: string;
    riskRewardRatio: number;
  }): string {
    const normalized = {
      p: params.patternType,
      v: params.volatilityRegime,
      d: params.direction,
      rr: Math.round(params.riskRewardRatio * 10) / 10, // Round to 1 decimal
    };
    
    const str = JSON.stringify(normalized);
    return createHash('md5').update(str).digest('hex').slice(0, 16);
  }
  
  /**
   * Get cached simulation
   */
  async get(cacheKey: string): Promise<ScenarioCacheEntry | null> {
    const entry = await this.cacheCol.findOne({ 
      cacheKey,
      expiresAt: { $gt: new Date() }
    }) as ScenarioCacheEntry | null;
    
    if (entry) {
      // Increment hit count
      await this.cacheCol.updateOne(
        { cacheKey },
        { $inc: { hitCount: 1 } }
      );
    }
    
    return entry;
  }
  
  /**
   * Store simulation in cache
   */
  async set(
    params: {
      patternType: string;
      volatilityRegime: 'LOW' | 'MEDIUM' | 'HIGH';
      direction: 'LONG' | 'SHORT';
      riskRewardRatio: number;
      scenarioId?: string;
    },
    simulation: ScenarioCacheEntry['simulation']
  ): Promise<string> {
    const cacheKey = this.generateCacheKey(params);
    
    const entry: ScenarioCacheEntry = {
      cacheKey,
      scenarioId: params.scenarioId,
      patternType: params.patternType,
      volatilityRegime: params.volatilityRegime,
      direction: params.direction,
      riskRewardRatio: params.riskRewardRatio,
      simulation,
      createdAt: new Date(),
      expiresAt: new Date(Date.now() + this.ttlMs),
      hitCount: 0,
    };
    
    await this.cacheCol.updateOne(
      { cacheKey },
      { $set: entry },
      { upsert: true }
    );
    
    return cacheKey;
  }
  
  /**
   * Store distribution for scenario
   */
  async storeDistribution(
    scenarioId: string,
    runId: string,
    rValues: number[]
  ): Promise<void> {
    const sorted = [...rValues].sort((a, b) => a - b);
    const n = sorted.length;
    
    // Calculate percentiles
    const percentiles = [5, 10, 25, 50, 75, 90, 95];
    const values = percentiles.map(p => sorted[Math.floor(p / 100 * n)] || 0);
    
    // Build histogram
    const bucketSize = 0.5;
    const histogram: Array<{ bucket: number; count: number }> = [];
    const minR = Math.floor(Math.min(...sorted) / bucketSize) * bucketSize;
    const maxR = Math.ceil(Math.max(...sorted) / bucketSize) * bucketSize;
    
    for (let bucket = minR; bucket <= maxR; bucket += bucketSize) {
      const count = sorted.filter(r => r >= bucket && r < bucket + bucketSize).length;
      histogram.push({ bucket, count });
    }
    
    // Calculate moments
    const mean = sorted.reduce((a, b) => a + b, 0) / n;
    const median = sorted[Math.floor(n / 2)];
    const variance = sorted.reduce((s, r) => s + Math.pow(r - mean, 2), 0) / n;
    const std = Math.sqrt(variance);
    
    // Skewness
    const skew = sorted.reduce((s, r) => s + Math.pow((r - mean) / std, 3), 0) / n;
    
    const distribution: DistributionStorage = {
      scenarioId,
      runId,
      timestamp: new Date(),
      paths: n,
      distribution: {
        percentiles,
        values,
        histogram,
      },
      mean,
      median,
      std,
      skew,
    };
    
    await this.distCol.insertOne(distribution);
  }
  
  /**
   * Get distribution for scenario
   */
  async getDistribution(scenarioId: string): Promise<DistributionStorage | null> {
    return this.distCol.findOne(
      { scenarioId },
      { sort: { timestamp: -1 } }
    ) as any;
  }
  
  /**
   * Get cache stats
   */
  async getStats(): Promise<{
    entries: number;
    hitRate: number;
    distributions: number;
    avgPaths: number;
  }> {
    const entries = await this.cacheCol.countDocuments();
    
    const hitAgg = await this.cacheCol.aggregate([
      { $group: { _id: null, totalHits: { $sum: '$hitCount' } } }
    ]).toArray();
    
    const totalHits = hitAgg[0]?.totalHits || 0;
    const hitRate = entries > 0 ? totalHits / entries : 0;
    
    const distributions = await this.distCol.countDocuments();
    
    const pathsAgg = await this.distCol.aggregate([
      { $group: { _id: null, avgPaths: { $avg: '$paths' } } }
    ]).toArray();
    
    const avgPaths = pathsAgg[0]?.avgPaths || 0;
    
    return { entries, hitRate, distributions, avgPaths };
  }
  
  /**
   * Clear expired entries
   */
  async clearExpired(): Promise<number> {
    const result = await this.cacheCol.deleteMany({
      expiresAt: { $lt: new Date() }
    });
    return result.deletedCount;
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

export function createScenarioCacheService(db: Db, ttlHours?: number): ScenarioCacheService {
  return new ScenarioCacheService(db, ttlHours);
}
