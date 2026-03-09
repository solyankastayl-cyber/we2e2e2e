/**
 * Synthetic Market Data Generator
 * 
 * Generates realistic OHLCV data when real API is unavailable
 * Uses statistical properties of real crypto markets
 */

import { Db, Collection } from 'mongodb';

const COLLECTION_NAME = 'ta_candles';

interface Candle {
  asset: string;
  timeframe: string;
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closeTime: number;
}

interface SyntheticConfig {
  assets: string[];
  timeframes: string[];
  startDate: string;
  endDate: string;
}

// Statistical properties for each asset (approximate)
const ASSET_STATS: Record<string, {
  basePrice: number;
  dailyVolatility: number;
  trendStrength: number;
  volumeBase: number;
}> = {
  BTCUSDT: { basePrice: 30000, dailyVolatility: 0.035, trendStrength: 0.001, volumeBase: 50000 },
  ETHUSDT: { basePrice: 2000, dailyVolatility: 0.045, trendStrength: 0.001, volumeBase: 100000 },
  BNBUSDT: { basePrice: 300, dailyVolatility: 0.04, trendStrength: 0.0008, volumeBase: 200000 },
  SOLUSDT: { basePrice: 50, dailyVolatility: 0.06, trendStrength: 0.001, volumeBase: 500000 },
  XRPUSDT: { basePrice: 0.5, dailyVolatility: 0.05, trendStrength: 0.0005, volumeBase: 1000000 },
  DOGEUSDT: { basePrice: 0.08, dailyVolatility: 0.07, trendStrength: 0.0003, volumeBase: 2000000 },
};

// Timeframe configs
const TF_CONFIGS: Record<string, { intervalMs: number; volMult: number }> = {
  '1d': { intervalMs: 24 * 60 * 60 * 1000, volMult: 1.0 },
  '4h': { intervalMs: 4 * 60 * 60 * 1000, volMult: 0.5 },
  '1h': { intervalMs: 60 * 60 * 1000, volMult: 0.25 },
  '15m': { intervalMs: 15 * 60 * 1000, volMult: 0.12 },
};

export class SyntheticDataGenerator {
  private db: Db;
  private collection: Collection<Candle>;
  
  constructor(db: Db) {
    this.db = db;
    this.collection = db.collection(COLLECTION_NAME);
  }
  
  async ensureIndexes(): Promise<void> {
    await this.collection.createIndex(
      { asset: 1, timeframe: 1, openTime: 1 },
      { unique: true }
    );
    await this.collection.createIndex({ asset: 1, timeframe: 1 });
    await this.collection.createIndex({ openTime: 1 });
  }
  
  /**
   * Generate synthetic market data
   */
  async generate(config: SyntheticConfig): Promise<{
    totalCandles: number;
    byAsset: Record<string, number>;
    byTimeframe: Record<string, number>;
  }> {
    await this.ensureIndexes();
    
    const byAsset: Record<string, number> = {};
    const byTimeframe: Record<string, number> = {};
    let totalCandles = 0;
    
    const startTs = new Date(config.startDate).getTime();
    const endTs = new Date(config.endDate).getTime();
    
    for (const asset of config.assets) {
      byAsset[asset] = 0;
      const stats = ASSET_STATS[asset] || ASSET_STATS.BTCUSDT;
      
      for (const tf of config.timeframes) {
        console.log(`[SyntheticGen] Generating ${asset} ${tf}...`);
        
        const tfConfig = TF_CONFIGS[tf] || TF_CONFIGS['1d'];
        const candles = this.generateSeries(
          asset,
          tf,
          startTs,
          endTs,
          stats,
          tfConfig
        );
        
        if (candles.length > 0) {
          // Bulk upsert
          const bulkOps = candles.map(c => ({
            updateOne: {
              filter: { asset: c.asset, timeframe: c.timeframe, openTime: c.openTime },
              update: { $set: c },
              upsert: true,
            },
          }));
          
          // Insert in batches of 1000
          for (let i = 0; i < bulkOps.length; i += 1000) {
            const batch = bulkOps.slice(i, i + 1000);
            await this.collection.bulkWrite(batch, { ordered: false });
          }
          
          byAsset[asset] += candles.length;
          byTimeframe[tf] = (byTimeframe[tf] || 0) + candles.length;
          totalCandles += candles.length;
          
          console.log(`[SyntheticGen] ${asset} ${tf}: ${candles.length} candles`);
        }
      }
    }
    
    return { totalCandles, byAsset, byTimeframe };
  }
  
  /**
   * Generate a series of candles
   */
  private generateSeries(
    asset: string,
    tf: string,
    startTs: number,
    endTs: number,
    stats: typeof ASSET_STATS.BTCUSDT,
    tfConfig: typeof TF_CONFIGS['1d']
  ): Candle[] {
    const candles: Candle[] = [];
    const { intervalMs, volMult } = tfConfig;
    const { basePrice, dailyVolatility, trendStrength, volumeBase } = stats;
    
    // Adjust volatility for timeframe
    const tfVolatility = dailyVolatility * volMult;
    
    // Random walk with trend and mean reversion
    let price = basePrice;
    let trend = 0;
    
    // Generate market phases (bull/bear/sideways)
    const phases = this.generateMarketPhases(startTs, endTs);
    
    for (let ts = startTs; ts < endTs; ts += intervalMs) {
      // Get current phase
      const phase = this.getPhaseAt(phases, ts);
      
      // Phase-adjusted drift
      const phaseDrift = phase === 'BULL' ? 0.0005 : phase === 'BEAR' ? -0.0005 : 0;
      
      // Trend momentum
      trend = trend * 0.95 + trendStrength * (Math.random() - 0.5 + phaseDrift);
      
      // Random returns with volatility clustering
      const volMultiplier = 0.5 + Math.random() * 1.5;
      const returns = this.normalRandom() * tfVolatility * volMultiplier + trend;
      
      // Generate OHLC
      const open = price;
      const close = price * (1 + returns);
      
      // High/Low based on volatility
      const wickSize = Math.abs(returns) * (1 + Math.random());
      const high = Math.max(open, close) * (1 + wickSize * 0.5);
      const low = Math.min(open, close) * (1 - wickSize * 0.5);
      
      // Volume with some randomness
      const volume = volumeBase * (0.5 + Math.random() * 1.5) * (1 + Math.abs(returns) * 10);
      
      candles.push({
        asset,
        timeframe: tf,
        openTime: ts,
        open: this.round(open, 2),
        high: this.round(high, 2),
        low: this.round(low, 2),
        close: this.round(close, 2),
        volume: Math.round(volume),
        closeTime: ts + intervalMs - 1,
      });
      
      // Update price
      price = close;
      
      // Add occasional jumps (events)
      if (Math.random() < 0.005) {
        price *= 1 + (Math.random() - 0.5) * 0.1;
      }
      
      // Mean reversion to base
      if (price > basePrice * 3) {
        price *= 0.99;
      } else if (price < basePrice * 0.3) {
        price *= 1.01;
      }
    }
    
    return candles;
  }
  
  /**
   * Generate market phases
   */
  private generateMarketPhases(startTs: number, endTs: number): Array<{
    start: number;
    end: number;
    type: 'BULL' | 'BEAR' | 'SIDEWAYS';
  }> {
    const phases: Array<{ start: number; end: number; type: 'BULL' | 'BEAR' | 'SIDEWAYS' }> = [];
    let ts = startTs;
    
    while (ts < endTs) {
      const type = ['BULL', 'BEAR', 'SIDEWAYS'][Math.floor(Math.random() * 3)] as 'BULL' | 'BEAR' | 'SIDEWAYS';
      const duration = (30 + Math.random() * 120) * 24 * 60 * 60 * 1000; // 30-150 days
      
      phases.push({
        start: ts,
        end: Math.min(ts + duration, endTs),
        type,
      });
      
      ts += duration;
    }
    
    return phases;
  }
  
  /**
   * Get phase at timestamp
   */
  private getPhaseAt(phases: Array<{ start: number; end: number; type: string }>, ts: number): string {
    for (const phase of phases) {
      if (ts >= phase.start && ts < phase.end) {
        return phase.type;
      }
    }
    return 'SIDEWAYS';
  }
  
  /**
   * Normal distribution random
   */
  private normalRandom(): number {
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
  }
  
  /**
   * Round to decimals
   */
  private round(value: number, decimals: number): number {
    const mult = Math.pow(10, decimals);
    return Math.round(value * mult) / mult;
  }
  
  /**
   * Get candle count
   */
  async getCandleCount(): Promise<{
    total: number;
    byAsset: Record<string, number>;
    byTimeframe: Record<string, number>;
  }> {
    const total = await this.collection.countDocuments();
    
    const assetAgg = await this.collection.aggregate([
      { $group: { _id: '$asset', count: { $sum: 1 } } }
    ]).toArray();
    
    const tfAgg = await this.collection.aggregate([
      { $group: { _id: '$timeframe', count: { $sum: 1 } } }
    ]).toArray();
    
    const byAsset: Record<string, number> = {};
    for (const a of assetAgg) {
      byAsset[a._id] = a.count;
    }
    
    const byTimeframe: Record<string, number> = {};
    for (const t of tfAgg) {
      byTimeframe[t._id] = t.count;
    }
    
    return { total, byAsset, byTimeframe };
  }
}

export function createSyntheticDataGenerator(db: Db): SyntheticDataGenerator {
  return new SyntheticDataGenerator(db);
}
