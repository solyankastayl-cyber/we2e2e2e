/**
 * Context Engine
 * 
 * Analyzes what happened BEFORE a pattern:
 * - Was there an impulse?
 * - Was there compression?
 * - Was there a level test?
 * - What's the overall structure?
 * 
 * This gives patterns different probabilities based on context.
 */

import { Db } from 'mongodb';
import { FastifyInstance, FastifyRequest } from 'fastify';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export interface ContextResult {
  // Trend context
  trend: {
    direction: 'UP' | 'DOWN' | 'NEUTRAL';
    strength: number;        // 0-1
    duration: number;        // bars
    impulseRecent: boolean;  // was there a strong impulse recently?
  };
  
  // Volatility context
  volatility: {
    regime: 'LOW' | 'MEDIUM' | 'HIGH';
    expanding: boolean;
    compressing: boolean;
    cluster: 'CALM' | 'ACTIVE' | 'EXPLOSIVE';
  };
  
  // Structure context
  structure: {
    hhhlSequence: number;    // count of HH/HL
    lhllSequence: number;    // count of LH/LL
    rangebound: boolean;
    breakingUp: boolean;
    breakingDown: boolean;
  };
  
  // Liquidity context
  liquidity: {
    recentSweepHigh: boolean;
    recentSweepLow: boolean;
    recentBreakout: boolean;
    recentRetest: boolean;
    distanceFromLevel: number;  // ATR units
  };
  
  // Summary score
  score: {
    bullish: number;         // 0-1
    bearish: number;         // 0-1
    neutral: number;         // 0-1
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
// Context Calculator
// ═══════════════════════════════════════════════════════════════

export function computeContext(
  candles: Candle[],
  lookback: number = 100
): ContextResult {
  if (candles.length < 20) {
    return getDefaultContext();
  }
  
  const window = candles.slice(-Math.min(lookback, candles.length));
  const closes = window.map(c => c.close);
  const highs = window.map(c => c.high);
  const lows = window.map(c => c.low);
  
  // Calculate ATR for reference
  const atr = calculateATR(window);
  const currentPrice = closes[closes.length - 1];
  
  // Trend context
  const trend = analyzeTrend(window, atr);
  
  // Volatility context
  const volatility = analyzeVolatility(window, atr, currentPrice);
  
  // Structure context
  const structure = analyzeStructure(highs, lows);
  
  // Liquidity context
  const liquidity = analyzeLiquidity(window, atr);
  
  // Calculate summary scores
  const score = calculateScores(trend, volatility, structure, liquidity);
  
  return {
    trend,
    volatility,
    structure,
    liquidity,
    score,
  };
}

// ═══════════════════════════════════════════════════════════════
// Trend Analysis
// ═══════════════════════════════════════════════════════════════

function analyzeTrend(
  candles: Candle[],
  atr: number
): ContextResult['trend'] {
  const closes = candles.map(c => c.close);
  
  // Calculate trend direction and strength
  const ma20 = calculateSMA(closes, Math.min(20, closes.length));
  const ma50 = calculateSMA(closes, Math.min(50, closes.length));
  
  const currentMA20 = ma20[ma20.length - 1];
  const currentMA50 = ma50[ma50.length - 1];
  const currentPrice = closes[closes.length - 1];
  
  // Direction
  let direction: 'UP' | 'DOWN' | 'NEUTRAL' = 'NEUTRAL';
  if (currentPrice > currentMA20 && currentMA20 > currentMA50) {
    direction = 'UP';
  } else if (currentPrice < currentMA20 && currentMA20 < currentMA50) {
    direction = 'DOWN';
  }
  
  // Strength (0-1)
  const priceVsMA = Math.abs(currentPrice - currentMA20) / (atr || 1);
  const maSlope = Math.abs(calculateSlope(ma20.slice(-10)));
  const strength = Math.min(0.5 * priceVsMA + 0.5 * maSlope * 100, 1);
  
  // Duration - count bars since last cross
  let duration = 0;
  for (let i = closes.length - 1; i >= 0; i--) {
    if (direction === 'UP' && closes[i] < ma20[i]) break;
    if (direction === 'DOWN' && closes[i] > ma20[i]) break;
    duration++;
  }
  
  // Recent impulse - was there a strong move in last 5-10 bars?
  const recentCandles = candles.slice(-10);
  const maxMove = Math.max(
    ...recentCandles.map((c, i, arr) => 
      i > 0 ? Math.abs(c.close - arr[i-1].close) : 0
    )
  );
  const impulseRecent = maxMove > atr * 2;
  
  return { direction, strength, duration, impulseRecent };
}

// ═══════════════════════════════════════════════════════════════
// Volatility Analysis
// ═══════════════════════════════════════════════════════════════

function analyzeVolatility(
  candles: Candle[],
  atr: number,
  currentPrice: number
): ContextResult['volatility'] {
  const atrRatio = atr / currentPrice;
  
  // Regime
  let regime: 'LOW' | 'MEDIUM' | 'HIGH' = 'MEDIUM';
  if (atrRatio < 0.015) regime = 'LOW';
  else if (atrRatio > 0.035) regime = 'HIGH';
  
  // ATR trend
  const atrSeries = calculateATRSeries(candles);
  const atrSlope = calculateSlope(atrSeries.slice(-10));
  
  const expanding = atrSlope > 0.001;
  const compressing = atrSlope < -0.001;
  
  // Cluster analysis
  const recentRanges = candles.slice(-5).map(c => c.high - c.low);
  const avgRecentRange = recentRanges.reduce((a, b) => a + b, 0) / recentRanges.length;
  
  let cluster: 'CALM' | 'ACTIVE' | 'EXPLOSIVE' = 'ACTIVE';
  if (avgRecentRange < atr * 0.5) cluster = 'CALM';
  else if (avgRecentRange > atr * 1.5) cluster = 'EXPLOSIVE';
  
  return { regime, expanding, compressing, cluster };
}

// ═══════════════════════════════════════════════════════════════
// Structure Analysis
// ═══════════════════════════════════════════════════════════════

function analyzeStructure(
  highs: number[],
  lows: number[]
): ContextResult['structure'] {
  let hhhlSequence = 0;
  let lhllSequence = 0;
  
  // Count swing structure
  for (let i = 1; i < Math.min(highs.length, 20); i++) {
    if (highs[highs.length - i] > highs[highs.length - i - 1]) hhhlSequence++;
    if (lows[lows.length - i] > lows[lows.length - i - 1]) hhhlSequence++;
    if (highs[highs.length - i] < highs[highs.length - i - 1]) lhllSequence++;
    if (lows[lows.length - i] < lows[lows.length - i - 1]) lhllSequence++;
  }
  
  // Range detection
  const recentHighs = highs.slice(-20);
  const recentLows = lows.slice(-20);
  const highRange = Math.max(...recentHighs) - Math.min(...recentHighs);
  const lowRange = Math.max(...recentLows) - Math.min(...recentLows);
  const avgPrice = (recentHighs[recentHighs.length - 1] + recentLows[recentLows.length - 1]) / 2;
  
  const rangebound = (highRange / avgPrice < 0.08) && (lowRange / avgPrice < 0.08);
  
  // Breaking out detection
  const currentHigh = highs[highs.length - 1];
  const currentLow = lows[lows.length - 1];
  const prevHighs = recentHighs.slice(0, -3);
  const prevLows = recentLows.slice(0, -3);
  
  const recentMaxHigh = Math.max(...prevHighs);
  const recentMinLow = Math.min(...prevLows);
  
  const breakingUp = currentHigh > recentMaxHigh * 1.001;
  const breakingDown = currentLow < recentMinLow * 0.999;
  
  return {
    hhhlSequence,
    lhllSequence,
    rangebound,
    breakingUp,
    breakingDown,
  };
}

// ═══════════════════════════════════════════════════════════════
// Liquidity Analysis
// ═══════════════════════════════════════════════════════════════

function analyzeLiquidity(
  candles: Candle[],
  atr: number
): ContextResult['liquidity'] {
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);
  const closes = candles.map(c => c.close);
  
  // Find recent significant levels (simplified)
  const recentHigh = Math.max(...highs.slice(-30));
  const recentLow = Math.min(...lows.slice(-30));
  
  // Check for liquidity sweeps (price went past level then returned)
  const last5 = candles.slice(-5);
  const sweepCheckHigh = last5.some(c => c.high >= recentHigh);
  const sweepCheckLow = last5.some(c => c.low <= recentLow);
  const currentPrice = closes[closes.length - 1];
  
  // A sweep typically means: touched high/low then closed back inside
  const recentSweepHigh = sweepCheckHigh && currentPrice < recentHigh - atr * 0.5;
  const recentSweepLow = sweepCheckLow && currentPrice > recentLow + atr * 0.5;
  
  // Breakout (closed beyond level)
  const recentBreakout = currentPrice > recentHigh || currentPrice < recentLow;
  
  // Retest (came back to test after breakout - simplified)
  const recentRetest = false;  // Would need more complex logic
  
  // Distance from level
  const distanceToHigh = (recentHigh - currentPrice) / atr;
  const distanceToLow = (currentPrice - recentLow) / atr;
  const distanceFromLevel = Math.min(distanceToHigh, distanceToLow);
  
  return {
    recentSweepHigh,
    recentSweepLow,
    recentBreakout,
    recentRetest,
    distanceFromLevel,
  };
}

// ═══════════════════════════════════════════════════════════════
// Score Calculation
// ═══════════════════════════════════════════════════════════════

function calculateScores(
  trend: ContextResult['trend'],
  volatility: ContextResult['volatility'],
  structure: ContextResult['structure'],
  liquidity: ContextResult['liquidity']
): ContextResult['score'] {
  let bullish = 0.33;
  let bearish = 0.33;
  let neutral = 0.34;
  
  // Trend influence
  if (trend.direction === 'UP') {
    bullish += 0.2 * trend.strength;
    bearish -= 0.1 * trend.strength;
  } else if (trend.direction === 'DOWN') {
    bearish += 0.2 * trend.strength;
    bullish -= 0.1 * trend.strength;
  }
  
  // Structure influence
  const structureRatio = structure.hhhlSequence / Math.max(structure.hhhlSequence + structure.lhllSequence, 1);
  if (structureRatio > 0.6) {
    bullish += 0.15;
    bearish -= 0.1;
  } else if (structureRatio < 0.4) {
    bearish += 0.15;
    bullish -= 0.1;
  }
  
  // Breakout influence
  if (structure.breakingUp) {
    bullish += 0.15;
  } else if (structure.breakingDown) {
    bearish += 0.15;
  }
  
  // Liquidity influence
  if (liquidity.recentSweepHigh) {
    bearish += 0.1;  // Sweep high often leads to reversal down
  }
  if (liquidity.recentSweepLow) {
    bullish += 0.1;  // Sweep low often leads to reversal up
  }
  
  // Range/neutral influence
  if (structure.rangebound && !structure.breakingUp && !structure.breakingDown) {
    neutral += 0.2;
    bullish -= 0.1;
    bearish -= 0.1;
  }
  
  // Normalize to sum to 1
  const total = bullish + bearish + neutral;
  return {
    bullish: Math.max(0, bullish / total),
    bearish: Math.max(0, bearish / total),
    neutral: Math.max(0, neutral / total),
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

function calculateATR(candles: Candle[]): number {
  if (candles.length < 15) return 1;
  let atr = 0;
  for (let i = 1; i < Math.min(15, candles.length); i++) {
    const tr = Math.max(
      candles[i].high - candles[i].low,
      Math.abs(candles[i].high - candles[i - 1].close),
      Math.abs(candles[i].low - candles[i - 1].close)
    );
    atr += tr;
  }
  return atr / 14;
}

function calculateATRSeries(candles: Candle[]): number[] {
  const result: number[] = [];
  for (let i = 14; i < candles.length; i++) {
    const slice = candles.slice(i - 14, i + 1);
    result.push(calculateATR(slice));
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
  return (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
}

function getDefaultContext(): ContextResult {
  return {
    trend: { direction: 'NEUTRAL', strength: 0, duration: 0, impulseRecent: false },
    volatility: { regime: 'MEDIUM', expanding: false, compressing: false, cluster: 'ACTIVE' },
    structure: { hhhlSequence: 0, lhllSequence: 0, rangebound: false, breakingUp: false, breakingDown: false },
    liquidity: { recentSweepHigh: false, recentSweepLow: false, recentBreakout: false, recentRetest: false, distanceFromLevel: 0 },
    score: { bullish: 0.33, bearish: 0.33, neutral: 0.34 },
  };
}

// ═══════════════════════════════════════════════════════════════
// Context-Based Pattern Adjustment
// ═══════════════════════════════════════════════════════════════

export function getContextPatternBoost(
  patternType: string,
  patternDirection: 'LONG' | 'SHORT',
  context: ContextResult
): number {
  let boost = 0;
  
  // If pattern direction aligns with context, boost it
  if (patternDirection === 'LONG' && context.score.bullish > 0.5) {
    boost += 0.2 * context.score.bullish;
  } else if (patternDirection === 'SHORT' && context.score.bearish > 0.5) {
    boost += 0.2 * context.score.bearish;
  } else if (context.score.neutral > 0.5) {
    // Neutral context penalizes strong directional patterns
    if (['BULL_FLAG', 'BEAR_FLAG'].includes(patternType)) {
      boost -= 0.1;
    }
  }
  
  // Impulse context
  if (context.trend.impulseRecent) {
    if (['BULL_FLAG', 'BEAR_FLAG', 'ASCENDING_TRIANGLE'].includes(patternType)) {
      boost += 0.15;  // Continuation patterns work better after impulse
    }
  }
  
  // Compression context
  if (context.volatility.compressing) {
    if (['SYMMETRICAL_TRIANGLE', 'WEDGE_RISING', 'WEDGE_FALLING'].includes(patternType)) {
      boost += 0.2;  // These patterns work well during compression
    }
  }
  
  // Liquidity sweep context
  if (context.liquidity.recentSweepHigh && patternDirection === 'SHORT') {
    boost += 0.15;
  }
  if (context.liquidity.recentSweepLow && patternDirection === 'LONG') {
    boost += 0.15;
  }
  
  return boost;
}

// ═══════════════════════════════════════════════════════════════
// Routes
// ═══════════════════════════════════════════════════════════════

export async function registerContextRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  
  // GET /analyze
  app.get('/analyze', async (request: FastifyRequest<{
    Querystring: { asset?: string; tf?: string; lookback?: string }
  }>) => {
    const { asset = 'BTCUSDT', tf = '1d', lookback = '100' } = request.query;
    
    const candles = await loadCandles(db, asset, tf, parseInt(lookback, 10));
    
    if (candles.length < 20) {
      return { ok: false, error: 'Insufficient candle data' };
    }
    
    const result = computeContext(candles);
    return { ok: true, asset, timeframe: tf, ...result };
  });

  // POST /boost
  app.post('/boost', async (request: FastifyRequest<{
    Body: { 
      patternType: string;
      direction: 'LONG' | 'SHORT';
      candles?: Candle[];
    }
  }>) => {
    const { patternType, direction, candles } = request.body || {};
    
    if (!patternType || !direction) {
      return { ok: false, error: 'patternType and direction required' };
    }
    
    // Use provided candles or generate mock
    const candleData = candles && candles.length > 0 
      ? candles 
      : generateMockCandles(100);
    
    const context = computeContext(candleData);
    const boost = getContextPatternBoost(patternType, direction, context);
    
    return { ok: true, patternType, direction, boost, context: context.score };
  });

  console.log('[Context] Routes registered: /analyze, /boost');
}

async function loadCandles(db: Db, asset: string, tf: string, limit: number): Promise<Candle[]> {
  const collections = ['candles_binance', 'ta_candles'];
  
  for (const coll of collections) {
    try {
      const candles = await db.collection(coll)
        .find({ symbol: asset.toUpperCase(), interval: tf.toLowerCase() })
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
    } catch { /* Collection not found */ }
  }
  
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

export async function registerContextModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[Context] Registering Context Engine...');
  
  await app.register(async (instance) => {
    await registerContextRoutes(instance, { db });
  }, { prefix: '/context' });
  
  console.log('[Context] ✅ Context Engine registered at /api/ta/context/*');
}
