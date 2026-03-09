/**
 * Pattern Stats Persistence
 * 
 * Stores rolling profit factor and enables/disables patterns based on performance
 */

import { Db } from 'mongodb';

export interface PatternStats {
  patternId: string;
  pf_30: number;   // Profit factor last 30 trades
  pf_100: number;  // Profit factor last 100 trades
  pf_300: number;  // Profit factor last 300 trades
  winRate_30: number;
  winRate_100: number;
  winRate_300: number;
  totalTrades: number;
  enabled: boolean;
  lastUpdated: Date;
}

export class PatternStatsStore {
  private db: Db;
  private collectionName = 'ta_pattern_stats';

  constructor(db: Db) {
    this.db = db;
  }

  async ensureIndexes(): Promise<void> {
    const collection = this.db.collection(this.collectionName);
    await collection.createIndex({ patternId: 1 }, { unique: true });
    await collection.createIndex({ enabled: 1 });
    await collection.createIndex({ pf_100: -1 });
  }

  /**
   * Get pattern stats
   */
  async getStats(patternId: string): Promise<PatternStats | null> {
    const stats = await this.db.collection(this.collectionName)
      .findOne({ patternId });
    return stats as PatternStats | null;
  }

  /**
   * Update pattern stats
   */
  async updateStats(patternId: string, stats: Partial<PatternStats>): Promise<void> {
    await this.db.collection(this.collectionName).updateOne(
      { patternId },
      { 
        $set: { 
          ...stats, 
          lastUpdated: new Date() 
        },
        $setOnInsert: { patternId }
      },
      { upsert: true }
    );
  }

  /**
   * Get all enabled patterns
   */
  async getEnabledPatterns(): Promise<PatternStats[]> {
    const patterns = await this.db.collection(this.collectionName)
      .find({ enabled: true })
      .toArray();
    return patterns as unknown as PatternStats[];
  }

  /**
   * Get top performing patterns
   */
  async getTopPatterns(limit = 20): Promise<PatternStats[]> {
    const patterns = await this.db.collection(this.collectionName)
      .find({ enabled: true, totalTrades: { $gte: 30 } })
      .sort({ pf_100: -1 })
      .limit(limit)
      .toArray();
    return patterns as unknown as PatternStats[];
  }

  /**
   * Get degrading patterns (pf dropping)
   */
  async getDegradingPatterns(): Promise<PatternStats[]> {
    const patterns = await this.db.collection(this.collectionName)
      .find({
        enabled: true,
        totalTrades: { $gte: 100 },
        $expr: { $lt: ['$pf_30', '$pf_100'] }
      })
      .toArray();
    return patterns as unknown as PatternStats[];
  }

  /**
   * Auto-disable patterns with bad performance
   */
  async autoDisable(pfThreshold = 0.8, minTrades = 50): Promise<number> {
    const result = await this.db.collection(this.collectionName).updateMany(
      {
        enabled: true,
        totalTrades: { $gte: minTrades },
        pf_100: { $lt: pfThreshold }
      },
      { $set: { enabled: false, lastUpdated: new Date() } }
    );
    return result.modifiedCount;
  }

  /**
   * Recalculate stats from outcomes
   */
  async recalculate(patternId: string, outcomes: { isWin: boolean; rMultiple: number }[]): Promise<PatternStats> {
    const total = outcomes.length;
    
    const calcPF = (trades: { isWin: boolean; rMultiple: number }[]) => {
      const wins = trades.filter(t => t.isWin).map(t => Math.abs(t.rMultiple));
      const losses = trades.filter(t => !t.isWin).map(t => Math.abs(t.rMultiple));
      const totalWins = wins.reduce((a, b) => a + b, 0) || 0;
      const totalLosses = losses.reduce((a, b) => a + b, 0) || 1;
      return totalWins / totalLosses;
    };

    const calcWinRate = (trades: { isWin: boolean }[]) => {
      const wins = trades.filter(t => t.isWin).length;
      return trades.length > 0 ? wins / trades.length : 0;
    };

    const last30 = outcomes.slice(-30);
    const last100 = outcomes.slice(-100);
    const last300 = outcomes.slice(-300);

    const stats: PatternStats = {
      patternId,
      pf_30: calcPF(last30),
      pf_100: calcPF(last100),
      pf_300: calcPF(last300),
      winRate_30: calcWinRate(last30),
      winRate_100: calcWinRate(last100),
      winRate_300: calcWinRate(last300),
      totalTrades: total,
      enabled: true,
      lastUpdated: new Date()
    };

    // Auto-disable if performance is bad
    if (total >= 50 && stats.pf_100 < 0.8) {
      stats.enabled = false;
    }

    await this.updateStats(patternId, stats);
    return stats;
  }
}

// Singleton
let storeInstance: PatternStatsStore | null = null;

export function getPatternStatsStore(db: Db): PatternStatsStore {
  if (!storeInstance) {
    storeInstance = new PatternStatsStore(db);
  }
  return storeInstance;
}
