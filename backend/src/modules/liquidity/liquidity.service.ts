/**
 * Liquidity Engine - Service Layer
 * 
 * Provides liquidity analysis via MongoDB candle data
 */

import { Db, Collection } from 'mongodb';
import { 
  LiquidityAnalysis, 
  LiquidityConfig, 
  DEFAULT_LIQUIDITY_CONFIG,
  Candle,
} from './liquidity.types.js';
import { analyzeLiquidity } from './liquidity.detector.js';

export class LiquidityService {
  private db: Db;
  private candlesCollection: Collection;

  constructor(db: Db) {
    this.db = db;
    // Use archive candles collection
    this.candlesCollection = db.collection('candles_binance');
  }

  /**
   * Analyze liquidity for an asset/timeframe
   */
  async analyze(
    asset: string,
    timeframe: string,
    lookback: number = 200,
    config: Partial<LiquidityConfig> = {}
  ): Promise<LiquidityAnalysis> {
    const fullConfig = { ...DEFAULT_LIQUIDITY_CONFIG, ...config };
    
    // Fetch candles from MongoDB
    const candles = await this.fetchCandles(asset, timeframe, lookback);
    
    if (candles.length === 0) {
      // Try ta_candles collection as fallback
      const taCandles = await this.fetchTACandles(asset, timeframe, lookback);
      if (taCandles.length > 0) {
        return analyzeLiquidity(taCandles, asset, timeframe, fullConfig);
      }
    }
    
    return analyzeLiquidity(candles, asset, timeframe, fullConfig);
  }

  /**
   * Get boost factor based on liquidity context
   * Used to adjust pattern scoring in Decision Engine
   */
  async getLiquidityBoost(
    asset: string,
    timeframe: string,
    patternDirection: 'BULLISH' | 'BEARISH'
  ): Promise<{
    boost: number;
    reason: string;
    analysis: LiquidityAnalysis;
  }> {
    const analysis = await this.analyze(asset, timeframe, 200);
    
    let boost = 1.0;
    let reason = 'neutral liquidity';
    
    const { metrics } = analysis;
    
    // Bullish pattern + swept lows = strong boost
    if (patternDirection === 'BULLISH' && metrics.recentSweepDown) {
      boost = 1.25;
      reason = 'swept lows - bullish confluence';
    }
    // Bearish pattern + swept highs = strong boost
    else if (patternDirection === 'BEARISH' && metrics.recentSweepUp) {
      boost = 1.25;
      reason = 'swept highs - bearish confluence';
    }
    // Bullish pattern but liquidity above = reduced confidence
    else if (patternDirection === 'BULLISH' && metrics.zonesAbove > metrics.zonesBelow * 2) {
      boost = 0.85;
      reason = 'heavy liquidity above - possible rejection';
    }
    // Bearish pattern but liquidity below = reduced confidence
    else if (patternDirection === 'BEARISH' && metrics.zonesBelow > metrics.zonesAbove * 2) {
      boost = 0.85;
      reason = 'heavy liquidity below - possible bounce';
    }
    // Pattern into nearby liquidity zone
    else if (metrics.distanceToNearestZoneATR < 1) {
      boost = 0.9;
      reason = 'price near liquidity zone - caution';
    }
    
    return { boost, reason, analysis };
  }

  /**
   * Fetch candles from archive collection
   */
  private async fetchCandles(
    symbol: string,
    interval: string,
    limit: number
  ): Promise<Candle[]> {
    const docs = await this.candlesCollection
      .find({ symbol, interval })
      .sort({ openTime: -1 })
      .limit(limit)
      .toArray();
    
    // Convert and reverse to chronological order
    return docs
      .map(doc => ({
        openTime: doc.openTime,
        closeTime: doc.closeTime,
        open: doc.open,
        high: doc.high,
        low: doc.low,
        close: doc.close,
        volume: doc.volume,
      }))
      .reverse();
  }

  /**
   * Fetch candles from ta_candles collection (fallback)
   */
  private async fetchTACandles(
    asset: string,
    timeframe: string,
    limit: number
  ): Promise<Candle[]> {
    const docs = await this.db.collection('ta_candles')
      .find({ asset, timeframe })
      .sort({ openTime: -1 })
      .limit(limit)
      .toArray();
    
    return docs
      .map(doc => ({
        openTime: doc.openTime,
        closeTime: doc.closeTime || doc.openTime + 86400000,
        open: doc.open,
        high: doc.high,
        low: doc.low,
        close: doc.close,
        volume: doc.volume || 0,
      }))
      .reverse();
  }
}
