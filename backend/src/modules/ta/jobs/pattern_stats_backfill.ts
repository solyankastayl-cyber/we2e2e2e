/**
 * Pattern Stats Backfill Job
 * 
 * Calculates historical pattern performance metrics:
 * - winRate
 * - profitFactor
 * - avgR
 * - sampleSize
 */

import { Db } from 'mongodb';

export interface PatternStatsRecord {
  patternId: string;
  sampleSize: number;
  winRate: number;
  profitFactor: number;
  avgR: number;
  pf_30: number;
  pf_100: number;
  pf_300: number;
  winRate_30: number;
  winRate_100: number;
  winRate_300: number;
  enabled: boolean;
  updatedAt: Date;
}

export class PatternStatsBackfill {
  private db: Db;
  private outcomesCollection = 'ta_pattern_outcomes';
  private statsCollection = 'ta_pattern_stats';

  constructor(db: Db) {
    this.db = db;
  }

  async ensureIndexes(): Promise<void> {
    const stats = this.db.collection(this.statsCollection);
    await stats.createIndex({ patternId: 1 }, { unique: true });
    await stats.createIndex({ enabled: 1 });
    await stats.createIndex({ profitFactor: -1 });
    
    const outcomes = this.db.collection(this.outcomesCollection);
    await outcomes.createIndex({ patternId: 1 });
    await outcomes.createIndex({ closedAt: -1 });
  }

  /**
   * Calculate profit factor from trades
   */
  private calcPF(trades: { rMultiple: number }[]): number {
    const wins = trades.filter(t => t.rMultiple > 0);
    const losses = trades.filter(t => t.rMultiple <= 0);
    
    const totalWins = wins.reduce((sum, t) => sum + t.rMultiple, 0);
    const totalLosses = Math.abs(losses.reduce((sum, t) => sum + t.rMultiple, 0));
    
    return totalLosses > 0 ? totalWins / totalLosses : totalWins > 0 ? 10 : 0;
  }

  /**
   * Calculate win rate
   */
  private calcWinRate(trades: { rMultiple: number }[]): number {
    if (trades.length === 0) return 0;
    const wins = trades.filter(t => t.rMultiple > 0).length;
    return wins / trades.length;
  }

  /**
   * Calculate avg R
   */
  private calcAvgR(trades: { rMultiple: number }[]): number {
    if (trades.length === 0) return 0;
    const sum = trades.reduce((s, t) => s + t.rMultiple, 0);
    return sum / trades.length;
  }

  /**
   * Backfill stats for a single pattern
   */
  async backfillPattern(patternId: string): Promise<PatternStatsRecord> {
    const outcomes = await this.db.collection(this.outcomesCollection)
      .find({ patternId })
      .sort({ closedAt: -1 })
      .toArray();

    const trades = outcomes.map(o => ({ rMultiple: o.rMultiple || 0 }));
    const last30 = trades.slice(0, 30);
    const last100 = trades.slice(0, 100);
    const last300 = trades.slice(0, 300);

    const stats: PatternStatsRecord = {
      patternId,
      sampleSize: trades.length,
      winRate: this.calcWinRate(trades),
      profitFactor: this.calcPF(trades),
      avgR: this.calcAvgR(trades),
      pf_30: this.calcPF(last30),
      pf_100: this.calcPF(last100),
      pf_300: this.calcPF(last300),
      winRate_30: this.calcWinRate(last30),
      winRate_100: this.calcWinRate(last100),
      winRate_300: this.calcWinRate(last300),
      enabled: true,
      updatedAt: new Date()
    };

    // Auto-disable poor performers
    if (trades.length >= 50 && stats.profitFactor < 0.8) {
      stats.enabled = false;
    }

    // Upsert
    await this.db.collection(this.statsCollection).updateOne(
      { patternId },
      { $set: stats },
      { upsert: true }
    );

    return stats;
  }

  /**
   * Backfill all patterns
   */
  async backfillAll(): Promise<{ processed: number; skipped: number }> {
    // Get all unique pattern IDs from outcomes
    const patternIds = await this.db.collection(this.outcomesCollection)
      .distinct('patternId');

    let processed = 0;
    let skipped = 0;

    for (const patternId of patternIds) {
      try {
        await this.backfillPattern(patternId);
        processed++;
      } catch (e) {
        skipped++;
      }
    }

    return { processed, skipped };
  }

  /**
   * Seed initial stats from pattern registry (no outcomes yet)
   */
  async seedFromRegistry(patternIds: string[]): Promise<number> {
    let seeded = 0;
    
    for (const patternId of patternIds) {
      const exists = await this.db.collection(this.statsCollection)
        .findOne({ patternId });
      
      if (!exists) {
        // Create initial record with default values
        const initialStats: PatternStatsRecord = {
          patternId,
          sampleSize: 0,
          winRate: 0.5,  // Prior
          profitFactor: 1.0,
          avgR: 0,
          pf_30: 1.0,
          pf_100: 1.0,
          pf_300: 1.0,
          winRate_30: 0.5,
          winRate_100: 0.5,
          winRate_300: 0.5,
          enabled: true,
          updatedAt: new Date()
        };
        
        await this.db.collection(this.statsCollection).insertOne(initialStats);
        seeded++;
      }
    }
    
    return seeded;
  }

  /**
   * Get all stats
   */
  async getAll(): Promise<PatternStatsRecord[]> {
    const stats = await this.db.collection(this.statsCollection)
      .find({})
      .sort({ profitFactor: -1 })
      .toArray();
    return stats as unknown as PatternStatsRecord[];
  }
}

// Singleton
let backfillInstance: PatternStatsBackfill | null = null;

export function getPatternStatsBackfill(db: Db): PatternStatsBackfill {
  if (!backfillInstance) {
    backfillInstance = new PatternStatsBackfill(db);
  }
  return backfillInstance;
}
