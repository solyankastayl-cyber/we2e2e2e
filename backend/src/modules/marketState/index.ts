/**
 * Market State Engine
 * 
 * Determines market regime from OHLC data:
 * - TRENDING_UP / TRENDING_DOWN
 * - RANGE
 * - VOLATILE
 * - COMPRESSING
 */

import { Db } from 'mongodb';
import { FastifyInstance, FastifyRequest } from 'fastify';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export type MarketState = 
  | 'TRENDING_UP'
  | 'TRENDING_DOWN'
  | 'RANGE'
  | 'VOLATILE'
  | 'COMPRESSING';

export interface MarketStateResult {
  state: MarketState;
  confidence: number;
  
  // Component scores
  trendStrength: number;      // -1 to +1 (negative = down, positive = up)
  volatilityRegime: 'LOW' | 'MEDIUM' | 'HIGH';
  rangeScore: number;         // 0-1 (how range-bound)
  compressionScore: number;   // 0-1 (how compressed)
  
  // Metrics used
  metrics: {
    slopeMA20: number;
    slopeMA50: number;
    atr14: number;
    atrRatio: number;        // ATR / price
    hhhlCount: number;       // higher highs/higher lows
    lhllCount: number;       // lower highs/lower lows
    rangeWidth: number;      // as % of price
    volatilityTrend: number; // ATR slope
  };
}

interface Candle {
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

// ═══════════════════════════════════════════════════════════════
// Market State Calculator
// ═══════════════════════════════════════════════════════════════

export function computeMarketState(candles: Candle[]): MarketStateResult {
  if (candles.length < 50) {
    return getDefaultState();
  }

  const closes = candles.map(c => c.close);
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);

  // Calculate metrics
  const ma20 = calculateSMA(closes, 20);
  const ma50 = calculateSMA(closes, 50);
  const slopeMA20 = calculateSlope(ma20.slice(-10));
  const slopeMA50 = calculateSlope(ma50.slice(-10));

  const atr14 = calculateATR(candles, 14);
  const currentPrice = closes[closes.length - 1];
  const atrRatio = atr14 / currentPrice;

  // HH/HL and LH/LL structure
  const { hhhlCount, lhllCount } = countSwingStructure(highs, lows);

  // Range metrics
  const recentHighs = highs.slice(-20);
  const recentLows = lows.slice(-20);
  const rangeHigh = Math.max(...recentHighs);
  const rangeLow = Math.min(...recentLows);
  const rangeWidth = (rangeHigh - rangeLow) / currentPrice;

  // Volatility trend (is ATR expanding or compressing?)
  const atrSeries = calculateATRSeries(candles, 14);
  const volatilityTrend = calculateSlope(atrSeries.slice(-10));

  // Build metrics
  const metrics = {
    slopeMA20,
    slopeMA50,
    atr14,
    atrRatio,
    hhhlCount,
    lhllCount,
    rangeWidth,
    volatilityTrend,
  };

  // Calculate component scores
  const trendStrength = calculateTrendStrength(slopeMA20, slopeMA50, hhhlCount, lhllCount);
  const volatilityRegime = classifyVolatility(atrRatio);
  const rangeScore = calculateRangeScore(rangeWidth, slopeMA20, slopeMA50);
  const compressionScore = calculateCompressionScore(volatilityTrend, rangeWidth);

  // Determine state
  const { state, confidence } = determineState(
    trendStrength,
    volatilityRegime,
    rangeScore,
    compressionScore
  );

  return {
    state,
    confidence,
    trendStrength,
    volatilityRegime,
    rangeScore,
    compressionScore,
    metrics,
  };
}

// ═══════════════════════════════════════════════════════════════
// Component Calculations
// ═══════════════════════════════════════════════════════════════

function calculateTrendStrength(
  slopeMA20: number,
  slopeMA50: number,
  hhhlCount: number,
  lhllCount: number
): number {
  // Normalize slopes to -1 to +1
  const slopeScore = (Math.tanh(slopeMA20 * 100) + Math.tanh(slopeMA50 * 100)) / 2;
  
  // Structure score from swing points
  const structureScore = (hhhlCount - lhllCount) / Math.max(hhhlCount + lhllCount, 1);
  
  // Combine
  return 0.6 * slopeScore + 0.4 * structureScore;
}

function classifyVolatility(atrRatio: number): 'LOW' | 'MEDIUM' | 'HIGH' {
  if (atrRatio < 0.015) return 'LOW';
  if (atrRatio > 0.035) return 'HIGH';
  return 'MEDIUM';
}

function calculateRangeScore(
  rangeWidth: number,
  slopeMA20: number,
  slopeMA50: number
): number {
  // Low slope + tight range = more range-bound
  const slopeMagnitude = Math.abs(slopeMA20) + Math.abs(slopeMA50);
  const slopeFactor = 1 - Math.min(slopeMagnitude * 50, 1);
  
  // Tight range score
  const rangeFactor = rangeWidth < 0.1 ? (0.1 - rangeWidth) / 0.1 : 0;
  
  return (slopeFactor + rangeFactor) / 2;
}

function calculateCompressionScore(
  volatilityTrend: number,
  rangeWidth: number
): number {
  // Compression = volatility decreasing + range narrowing
  const volCompressing = volatilityTrend < 0 ? Math.min(-volatilityTrend * 100, 1) : 0;
  const tightRange = rangeWidth < 0.08 ? 1 - (rangeWidth / 0.08) : 0;
  
  return (volCompressing + tightRange) / 2;
}

function determineState(
  trendStrength: number,
  volatilityRegime: 'LOW' | 'MEDIUM' | 'HIGH',
  rangeScore: number,
  compressionScore: number
): { state: MarketState; confidence: number } {
  
  const scores: Array<{ state: MarketState; score: number }> = [];
  
  // TRENDING_UP
  if (trendStrength > 0.3) {
    scores.push({
      state: 'TRENDING_UP',
      score: trendStrength * (volatilityRegime !== 'LOW' ? 1 : 0.8),
    });
  }
  
  // TRENDING_DOWN
  if (trendStrength < -0.3) {
    scores.push({
      state: 'TRENDING_DOWN',
      score: -trendStrength * (volatilityRegime !== 'LOW' ? 1 : 0.8),
    });
  }
  
  // RANGE
  if (rangeScore > 0.4) {
    scores.push({
      state: 'RANGE',
      score: rangeScore,
    });
  }
  
  // VOLATILE
  if (volatilityRegime === 'HIGH') {
    scores.push({
      state: 'VOLATILE',
      score: 0.7,
    });
  }
  
  // COMPRESSING
  if (compressionScore > 0.5) {
    scores.push({
      state: 'COMPRESSING',
      score: compressionScore,
    });
  }
  
  // Default to RANGE if nothing strong
  if (scores.length === 0) {
    return { state: 'RANGE', confidence: 0.4 };
  }
  
  // Pick highest score
  scores.sort((a, b) => b.score - a.score);
  return {
    state: scores[0].state,
    confidence: Math.min(scores[0].score, 0.95),
  };
}

// ═══════════════════════════════════════════════════════════════
// Helper Functions
// ═══════════════════════════════════════════════════════════════

function calculateSMA(values: number[], period: number): number[] {
  const result: number[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      result.push(values[i]);
      continue;
    }
    const sum = values.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
    result.push(sum / period);
  }
  return result;
}

function calculateATR(candles: Candle[], period: number): number {
  if (candles.length < period + 1) return 0;
  
  let atr = 0;
  for (let i = 1; i <= period; i++) {
    const idx = candles.length - period - 1 + i;
    const high = candles[idx].high;
    const low = candles[idx].low;
    const prevClose = candles[idx - 1].close;
    const tr = Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose));
    atr += tr;
  }
  return atr / period;
}

function calculateATRSeries(candles: Candle[], period: number): number[] {
  const result: number[] = [];
  for (let i = period; i < candles.length; i++) {
    const slice = candles.slice(i - period, i + 1);
    let atr = 0;
    for (let j = 1; j < slice.length; j++) {
      const tr = Math.max(
        slice[j].high - slice[j].low,
        Math.abs(slice[j].high - slice[j - 1].close),
        Math.abs(slice[j].low - slice[j - 1].close)
      );
      atr += tr;
    }
    result.push(atr / period);
  }
  return result;
}

function calculateSlope(values: number[]): number {
  if (values.length < 2) return 0;
  const n = values.length;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
  for (let i = 0; i < n; i++) {
    sumX += i;
    sumY += values[i];
    sumXY += i * values[i];
    sumX2 += i * i;
  }
  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  // Normalize by average value
  const avgY = sumY / n;
  return avgY !== 0 ? slope / avgY : slope;
}

function countSwingStructure(
  highs: number[],
  lows: number[]
): { hhhlCount: number; lhllCount: number } {
  let hhhlCount = 0;
  let lhllCount = 0;
  
  // Look at last 20 bars for swing structure
  const lookback = Math.min(20, highs.length - 1);
  
  for (let i = highs.length - lookback; i < highs.length - 1; i++) {
    // Higher high
    if (highs[i + 1] > highs[i]) hhhlCount++;
    else if (highs[i + 1] < highs[i]) lhllCount++;
    
    // Higher low / lower low
    if (lows[i + 1] > lows[i]) hhhlCount++;
    else if (lows[i + 1] < lows[i]) lhllCount++;
  }
  
  return { hhhlCount, lhllCount };
}

function getDefaultState(): MarketStateResult {
  return {
    state: 'RANGE',
    confidence: 0.3,
    trendStrength: 0,
    volatilityRegime: 'MEDIUM',
    rangeScore: 0.5,
    compressionScore: 0,
    metrics: {
      slopeMA20: 0,
      slopeMA50: 0,
      atr14: 0,
      atrRatio: 0,
      hhhlCount: 0,
      lhllCount: 0,
      rangeWidth: 0,
      volatilityTrend: 0,
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// Pattern Weight Adjustments
// ═══════════════════════════════════════════════════════════════

export function getPatternWeightAdjustment(
  patternType: string,
  marketState: MarketState
): number {
  const adjustments: Record<MarketState, Record<string, number>> = {
    TRENDING_UP: {
      'BULL_FLAG': 0.3,
      'BEAR_FLAG': -0.3,
      'ASCENDING_TRIANGLE': 0.2,
      'DESCENDING_TRIANGLE': -0.2,
      'DOUBLE_TOP': -0.2,
      'DOUBLE_BOTTOM': 0.1,
    },
    TRENDING_DOWN: {
      'BULL_FLAG': -0.3,
      'BEAR_FLAG': 0.3,
      'ASCENDING_TRIANGLE': -0.2,
      'DESCENDING_TRIANGLE': 0.2,
      'DOUBLE_TOP': 0.1,
      'DOUBLE_BOTTOM': -0.2,
    },
    RANGE: {
      'SUPPORT': 0.2,
      'RESISTANCE': 0.2,
      'HORIZONTAL_CHANNEL': 0.3,
      'BULL_FLAG': -0.2,
      'BEAR_FLAG': -0.2,
    },
    VOLATILE: {
      'BREAKAWAY_GAP': 0.2,
      'EXHAUSTION_GAP': 0.1,
      'SUPPORT': -0.1,
      'RESISTANCE': -0.1,
    },
    COMPRESSING: {
      'SYMMETRICAL_TRIANGLE': 0.3,
      'WEDGE_RISING': 0.2,
      'WEDGE_FALLING': 0.2,
      'BULL_FLAG': -0.1,
      'BEAR_FLAG': -0.1,
    },
  };

  return adjustments[marketState]?.[patternType] || 0;
}

// ═══════════════════════════════════════════════════════════════
// Routes
// ═══════════════════════════════════════════════════════════════

export async function registerMarketStateRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  
  // GET /state - Get current market state
  app.get('/state', async (request: FastifyRequest<{
    Querystring: { asset?: string; tf?: string; bars?: string }
  }>) => {
    const { asset = 'BTCUSDT', tf = '1d', bars = '100' } = request.query;
    
    // Load candles
    const candles = await loadCandles(db, asset, tf, parseInt(bars, 10));
    
    if (candles.length < 50) {
      return { ok: false, error: 'Insufficient candle data' };
    }
    
    const result = computeMarketState(candles);
    return { ok: true, asset, timeframe: tf, ...result };
  });

  // POST /analyze - Analyze provided candles
  app.post('/analyze', async (request: FastifyRequest<{
    Body: { candles: Candle[] }
  }>) => {
    const { candles } = request.body || {};
    
    if (!candles || !Array.isArray(candles)) {
      return { ok: false, error: 'candles array required' };
    }
    
    const result = computeMarketState(candles);
    return { ok: true, ...result };
  });

  // GET /adjustment/:pattern
  app.get('/adjustment/:pattern', async (request: FastifyRequest<{
    Params: { pattern: string };
    Querystring: { state?: string }
  }>) => {
    const { pattern } = request.params;
    const { state } = request.query;
    
    if (!state) {
      // Return all state adjustments for this pattern
      const states: MarketState[] = ['TRENDING_UP', 'TRENDING_DOWN', 'RANGE', 'VOLATILE', 'COMPRESSING'];
      const adjustments: Record<string, number> = {};
      
      for (const s of states) {
        adjustments[s] = getPatternWeightAdjustment(pattern, s);
      }
      
      return { ok: true, pattern, adjustments };
    }
    
    const adjustment = getPatternWeightAdjustment(pattern, state as MarketState);
    return { ok: true, pattern, state, adjustment };
  });

  console.log('[MarketState] Routes registered: /state, /analyze, /adjustment');
}

async function loadCandles(db: Db, asset: string, tf: string, limit: number): Promise<Candle[]> {
  const collections = ['candles_binance', 'ta_candles'];
  
  for (const coll of collections) {
    try {
      const candles = await db.collection(coll)
        .find({
          symbol: asset.toUpperCase(),
          interval: tf.toLowerCase(),
        })
        .sort({ openTime: -1 })
        .limit(limit)
        .toArray();
      
      if (candles.length > 0) {
        return candles.reverse().map(c => ({
          openTime: c.openTime,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }));
      }
    } catch {
      // Collection not found
    }
  }
  
  // Generate mock data for testing
  return generateMockCandles(limit);
}

function generateMockCandles(count: number): Candle[] {
  const candles: Candle[] = [];
  let price = 100;
  let time = Date.now() - count * 24 * 60 * 60 * 1000;
  
  for (let i = 0; i < count; i++) {
    const change = (Math.random() - 0.5) * 2;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * 0.5;
    const low = Math.min(open, close) - Math.random() * 0.5;
    
    candles.push({ openTime: time, open, high, low, close });
    price = close;
    time += 24 * 60 * 60 * 1000;
  }
  
  return candles;
}

// ═══════════════════════════════════════════════════════════════
// Module Export
// ═══════════════════════════════════════════════════════════════

export async function registerMarketStateModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[MarketState] Registering Market State Engine...');
  
  await app.register(async (instance) => {
    await registerMarketStateRoutes(instance, { db });
  }, { prefix: '/marketState' });
  
  console.log('[MarketState] ✅ Market State Engine registered at /api/ta/marketState/*');
}
