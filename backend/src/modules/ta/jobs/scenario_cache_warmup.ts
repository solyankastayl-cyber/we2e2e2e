/**
 * Scenario Cache Warmup Job
 * 
 * Pre-computes Monte Carlo simulations for common pattern/regime combinations
 */

import { Db } from 'mongodb';

export interface ScenarioCacheEntry {
  cacheKey: string;
  patternId: string;
  regime: 'LOW' | 'MED' | 'HIGH';  // Volatility regime
  riskModel: 'CONSERVATIVE' | 'MODERATE' | 'AGGRESSIVE';
  
  // Monte Carlo results
  paths: number;
  p_target: number;
  p_stop: number;
  p_timeout: number;
  
  // R distribution percentiles
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  
  // Expected values
  expectedR: number;
  expectedEV: number;
  
  createdAt: Date;
  expiresAt: Date;
}

// Core patterns to cache
const CORE_PATTERNS = [
  'TRIANGLE_ASC', 'TRIANGLE_DESC', 'TRIANGLE_SYM',
  'CHANNEL_UP', 'CHANNEL_DOWN', 'CHANNEL_HORIZ',
  'FLAG_BULL', 'FLAG_BEAR',
  'HS_TOP', 'HS_BOTTOM', 'IHS',
  'DOUBLE_TOP', 'DOUBLE_BOTTOM',
  'WEDGE_RISING', 'WEDGE_FALLING',
  'HARMONIC_GARTLEY', 'HARMONIC_BAT', 'HARMONIC_BUTTERFLY',
  'BOS_BULL', 'BOS_BEAR',
  'CANDLE_ENGULF_BULL', 'CANDLE_ENGULF_BEAR',
  'RSI_DIV_BULL', 'RSI_DIV_BEAR'
];

const REGIMES: ScenarioCacheEntry['regime'][] = ['LOW', 'MED', 'HIGH'];
const RISK_MODELS: ScenarioCacheEntry['riskModel'][] = ['CONSERVATIVE', 'MODERATE', 'AGGRESSIVE'];

export class ScenarioCacheWarmup {
  private db: Db;
  private collectionName = 'ta_scenario_cache';
  private ttlHours = 24;

  constructor(db: Db, ttlHours = 24) {
    this.db = db;
    this.ttlHours = ttlHours;
  }

  async ensureIndexes(): Promise<void> {
    const collection = this.db.collection(this.collectionName);
    await collection.createIndex({ cacheKey: 1 }, { unique: true });
    await collection.createIndex({ patternId: 1, regime: 1, riskModel: 1 });
    await collection.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 });
  }

  /**
   * Generate cache key
   */
  private genKey(patternId: string, regime: string, riskModel: string): string {
    return `${patternId}:${regime}:${riskModel}`;
  }

  /**
   * Simulate Monte Carlo paths (simplified)
   */
  private simulate(
    patternId: string, 
    regime: ScenarioCacheEntry['regime'],
    riskModel: ScenarioCacheEntry['riskModel'],
    paths: number = 1000
  ): Omit<ScenarioCacheEntry, 'cacheKey' | 'createdAt' | 'expiresAt'> {
    // Volatility multipliers
    const volMult = { LOW: 0.7, MED: 1.0, HIGH: 1.5 };
    const vol = volMult[regime];
    
    // Risk model base probabilities
    const riskBase = {
      CONSERVATIVE: { target: 0.55, stop: 0.35 },
      MODERATE: { target: 0.50, stop: 0.30 },
      AGGRESSIVE: { target: 0.45, stop: 0.25 }
    };
    
    // Pattern-specific adjustments
    const patternBonus = this.getPatternBonus(patternId);
    
    // Simulate paths
    const results: number[] = [];
    let targets = 0;
    let stops = 0;
    let timeouts = 0;
    
    for (let i = 0; i < paths; i++) {
      const rand = Math.random();
      const pTarget = riskBase[riskModel].target + patternBonus - (vol - 1) * 0.05;
      const pStop = riskBase[riskModel].stop + (vol - 1) * 0.05;
      
      if (rand < pTarget) {
        // Hit target
        const r = 1.5 + Math.random() * vol * 2;
        results.push(r);
        targets++;
      } else if (rand < pTarget + pStop) {
        // Hit stop
        const r = -1 - Math.random() * 0.5;
        results.push(r);
        stops++;
      } else {
        // Timeout
        const r = (Math.random() - 0.5) * 0.5;
        results.push(r);
        timeouts++;
      }
    }
    
    // Sort for percentiles
    results.sort((a, b) => a - b);
    
    return {
      patternId,
      regime,
      riskModel,
      paths,
      p_target: targets / paths,
      p_stop: stops / paths,
      p_timeout: timeouts / paths,
      p10: results[Math.floor(paths * 0.1)],
      p25: results[Math.floor(paths * 0.25)],
      p50: results[Math.floor(paths * 0.5)],
      p75: results[Math.floor(paths * 0.75)],
      p90: results[Math.floor(paths * 0.9)],
      expectedR: results.reduce((s, r) => s + r, 0) / paths,
      expectedEV: (targets / paths) * 1.5 - (stops / paths) * 1.0
    };
  }

  /**
   * Get pattern-specific probability bonus
   */
  private getPatternBonus(patternId: string): number {
    const bonuses: Record<string, number> = {
      'TRIANGLE_ASC': 0.08,
      'TRIANGLE_DESC': 0.06,
      'FLAG_BULL': 0.07,
      'HS_BOTTOM': 0.09,
      'DOUBLE_BOTTOM': 0.08,
      'HARMONIC_GARTLEY': 0.10,
      'HARMONIC_BAT': 0.09,
      'BOS_BULL': 0.06,
      'RSI_DIV_BULL': 0.05
    };
    return bonuses[patternId] || 0.02;
  }

  /**
   * Warmup single entry
   */
  async warmupEntry(
    patternId: string,
    regime: ScenarioCacheEntry['regime'],
    riskModel: ScenarioCacheEntry['riskModel']
  ): Promise<ScenarioCacheEntry> {
    const cacheKey = this.genKey(patternId, regime, riskModel);
    const now = new Date();
    const expiresAt = new Date(now.getTime() + this.ttlHours * 60 * 60 * 1000);
    
    const simResult = this.simulate(patternId, regime, riskModel);
    
    const entry: ScenarioCacheEntry = {
      cacheKey,
      ...simResult,
      createdAt: now,
      expiresAt
    };
    
    await this.db.collection(this.collectionName).updateOne(
      { cacheKey },
      { $set: entry },
      { upsert: true }
    );
    
    return entry;
  }

  /**
   * Full cache warmup
   */
  async warmupAll(patterns?: string[]): Promise<{ total: number; cached: number }> {
    const patternsToCache = patterns || CORE_PATTERNS;
    let cached = 0;
    
    for (const patternId of patternsToCache) {
      for (const regime of REGIMES) {
        for (const riskModel of RISK_MODELS) {
          try {
            await this.warmupEntry(patternId, regime, riskModel);
            cached++;
          } catch (e) {
            // Skip errors
          }
        }
      }
    }
    
    return {
      total: patternsToCache.length * REGIMES.length * RISK_MODELS.length,
      cached
    };
  }

  /**
   * Get cached scenario
   */
  async get(
    patternId: string,
    regime: ScenarioCacheEntry['regime'],
    riskModel: ScenarioCacheEntry['riskModel']
  ): Promise<ScenarioCacheEntry | null> {
    const cacheKey = this.genKey(patternId, regime, riskModel);
    const entry = await this.db.collection(this.collectionName)
      .findOne({ cacheKey });
    return entry as ScenarioCacheEntry | null;
  }

  /**
   * Get cache stats
   */
  async getStats(): Promise<{
    totalEntries: number;
    byPattern: Record<string, number>;
    byRegime: Record<string, number>;
  }> {
    const totalEntries = await this.db.collection(this.collectionName).countDocuments();
    
    const byPattern: Record<string, number> = {};
    const patternCounts = await this.db.collection(this.collectionName).aggregate([
      { $group: { _id: '$patternId', count: { $sum: 1 } } }
    ]).toArray();
    patternCounts.forEach(p => { byPattern[p._id] = p.count; });
    
    const byRegime: Record<string, number> = {};
    const regimeCounts = await this.db.collection(this.collectionName).aggregate([
      { $group: { _id: '$regime', count: { $sum: 1 } } }
    ]).toArray();
    regimeCounts.forEach(r => { byRegime[r._id] = r.count; });
    
    return { totalEntries, byPattern, byRegime };
  }
}

// Singleton
let warmupInstance: ScenarioCacheWarmup | null = null;

export function getScenarioCacheWarmup(db: Db): ScenarioCacheWarmup {
  if (!warmupInstance) {
    warmupInstance = new ScenarioCacheWarmup(db);
  }
  return warmupInstance;
}
