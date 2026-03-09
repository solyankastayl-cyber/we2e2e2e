/**
 * Market Data Backfill Service
 * 
 * Fetches historical OHLCV data from Binance and stores in MongoDB
 * Target: 434,797+ candles (2017-2024)
 */

import { Db, Collection } from 'mongodb';

const BINANCE_BASE_URL = 'https://api.binance.com/api/v3';

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

interface BackfillConfig {
  assets: string[];
  timeframes: string[];
  startDate: string;
  endDate: string;
}

const COLLECTION_NAME = 'ta_candles';

export class MarketDataBackfillService {
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
   * Backfill historical data
   */
  async backfill(config: BackfillConfig): Promise<{
    totalCandles: number;
    byAsset: Record<string, number>;
    byTimeframe: Record<string, number>;
  }> {
    await this.ensureIndexes();
    
    const byAsset: Record<string, number> = {};
    const byTimeframe: Record<string, number> = {};
    let totalCandles = 0;
    
    for (const asset of config.assets) {
      byAsset[asset] = 0;
      
      for (const tf of config.timeframes) {
        console.log(`[Backfill] Fetching ${asset} ${tf}...`);
        
        const candles = await this.fetchCandles(
          asset,
          tf,
          new Date(config.startDate).getTime(),
          new Date(config.endDate).getTime()
        );
        
        if (candles.length > 0) {
          // Upsert candles
          const bulkOps = candles.map(c => ({
            updateOne: {
              filter: { asset: c.asset, timeframe: c.timeframe, openTime: c.openTime },
              update: { $set: c },
              upsert: true,
            },
          }));
          
          await this.collection.bulkWrite(bulkOps, { ordered: false });
          
          byAsset[asset] += candles.length;
          byTimeframe[tf] = (byTimeframe[tf] || 0) + candles.length;
          totalCandles += candles.length;
          
          console.log(`[Backfill] ${asset} ${tf}: ${candles.length} candles`);
        }
      }
    }
    
    return { totalCandles, byAsset, byTimeframe };
  }
  
  /**
   * Fetch candles from Binance API
   */
  private async fetchCandles(
    asset: string,
    tf: string,
    startTime: number,
    endTime: number
  ): Promise<Candle[]> {
    const candles: Candle[] = [];
    let currentStart = startTime;
    const interval = this.mapTimeframe(tf);
    
    // Binance returns max 1000 candles per request
    while (currentStart < endTime) {
      try {
        const url = `${BINANCE_BASE_URL}/klines?symbol=${asset}&interval=${interval}&startTime=${currentStart}&endTime=${endTime}&limit=1000`;
        
        const response = await fetch(url);
        
        if (!response.ok) {
          console.error(`[Backfill] API error: ${response.status}`);
          break;
        }
        
        const data = await response.json();
        
        if (!Array.isArray(data) || data.length === 0) {
          break;
        }
        
        for (const k of data) {
          candles.push({
            asset,
            timeframe: tf,
            openTime: k[0],
            open: parseFloat(k[1]),
            high: parseFloat(k[2]),
            low: parseFloat(k[3]),
            close: parseFloat(k[4]),
            volume: parseFloat(k[5]),
            closeTime: k[6],
          });
        }
        
        // Move to next batch
        currentStart = data[data.length - 1][0] + 1;
        
        // Rate limit
        await this.sleep(100);
        
      } catch (err) {
        console.error(`[Backfill] Error fetching ${asset} ${tf}:`, err);
        break;
      }
    }
    
    return candles;
  }
  
  /**
   * Map timeframe to Binance interval
   */
  private mapTimeframe(tf: string): string {
    const map: Record<string, string> = {
      '1d': '1d',
      '4h': '4h',
      '1h': '1h',
      '15m': '15m',
      '5m': '5m',
      '1m': '1m',
    };
    return map[tf.toLowerCase()] || '1d';
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
  
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export function createMarketDataBackfillService(db: Db): MarketDataBackfillService {
  return new MarketDataBackfillService(db);
}
