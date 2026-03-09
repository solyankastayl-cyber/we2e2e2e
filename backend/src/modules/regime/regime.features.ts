/**
 * Phase 9 — Regime Feature Calculator
 * 
 * Computes features for regime classification
 */

import { RegimeFeatures } from './regime.types.js';

// ═══════════════════════════════════════════════════════════════
// INDICATOR CALCULATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate ATR
 */
function calculateATR(highs: number[], lows: number[], closes: number[], period: number = 14): number[] {
  const atrs: number[] = [];
  
  for (let i = 0; i < highs.length; i++) {
    if (i === 0) {
      atrs.push(highs[i] - lows[i]);
      continue;
    }
    
    const tr = Math.max(
      highs[i] - lows[i],
      Math.abs(highs[i] - closes[i - 1]),
      Math.abs(lows[i] - closes[i - 1])
    );
    
    if (i < period) {
      atrs.push(tr);
    } else {
      atrs.push((atrs[i - 1] * (period - 1) + tr) / period);
    }
  }
  
  return atrs;
}

/**
 * Calculate EMA
 */
function calculateEMA(values: number[], period: number): number[] {
  const emas: number[] = [];
  const multiplier = 2 / (period + 1);
  
  for (let i = 0; i < values.length; i++) {
    if (i === 0) {
      emas.push(values[i]);
    } else {
      emas.push((values[i] - emas[i - 1]) * multiplier + emas[i - 1]);
    }
  }
  
  return emas;
}

/**
 * Calculate Bollinger Band Width
 */
function calculateBBWidth(closes: number[], period: number = 20): number[] {
  const widths: number[] = [];
  
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) {
      widths.push(0);
      continue;
    }
    
    const slice = closes.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const variance = slice.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / period;
    const stdDev = Math.sqrt(variance);
    
    const width = (2 * stdDev * 2) / mean;  // (Upper - Lower) / Middle
    widths.push(width);
  }
  
  return widths;
}

/**
 * Calculate ADX (simplified)
 */
function calculateADX(highs: number[], lows: number[], closes: number[], period: number = 14): number[] {
  const adxValues: number[] = [];
  const plusDM: number[] = [];
  const minusDM: number[] = [];
  
  for (let i = 0; i < highs.length; i++) {
    if (i === 0) {
      plusDM.push(0);
      minusDM.push(0);
      adxValues.push(0);
      continue;
    }
    
    const upMove = highs[i] - highs[i - 1];
    const downMove = lows[i - 1] - lows[i];
    
    plusDM.push(upMove > downMove && upMove > 0 ? upMove : 0);
    minusDM.push(downMove > upMove && downMove > 0 ? downMove : 0);
    
    if (i < period) {
      adxValues.push(0.5);
      continue;
    }
    
    const atr = calculateATR([highs[i]], [lows[i]], [closes[i]], 1)[0];
    if (atr === 0) {
      adxValues.push(adxValues[i - 1]);
      continue;
    }
    
    const plusDI = (plusDM.slice(-period).reduce((a, b) => a + b, 0) / period) / atr;
    const minusDI = (minusDM.slice(-period).reduce((a, b) => a + b, 0) / period) / atr;
    
    const dx = Math.abs(plusDI - minusDI) / (plusDI + minusDI + 0.0001);
    const adx = i >= period * 2 
      ? (adxValues[i - 1] * (period - 1) + dx) / period
      : dx;
    
    adxValues.push(Math.min(1, adx));
  }
  
  return adxValues;
}

/**
 * Calculate MACD
 */
function calculateMACD(closes: number[]): { macd: number[]; signal: number[]; histogram: number[] } {
  const ema12 = calculateEMA(closes, 12);
  const ema26 = calculateEMA(closes, 26);
  
  const macd = ema12.map((v, i) => v - ema26[i]);
  const signal = calculateEMA(macd, 9);
  const histogram = macd.map((v, i) => v - signal[i]);
  
  return { macd, signal, histogram };
}

// ═══════════════════════════════════════════════════════════════
// MAIN FEATURE CALCULATOR
// ═══════════════════════════════════════════════════════════════

export interface CandleInput {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * Calculate all regime features from candles
 */
export function calculateRegimeFeatures(candles: CandleInput[]): RegimeFeatures {
  if (candles.length < 50) {
    return getDefaultFeatures();
  }
  
  const opens = candles.map(c => c.open);
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);
  const closes = candles.map(c => c.close);
  const volumes = candles.map(c => c.volume);
  
  // ATR and volatility
  const atrs = calculateATR(highs, lows, closes, 14);
  const currentATR = atrs[atrs.length - 1];
  const avgATR = atrs.slice(-50).reduce((a, b) => a + b, 0) / 50;
  const volatility = avgATR > 0 ? currentATR / avgATR : 1;
  
  const recentATRs = atrs.slice(-10);
  const olderATRs = atrs.slice(-20, -10);
  const recentAvgATR = recentATRs.reduce((a, b) => a + b, 0) / recentATRs.length;
  const olderAvgATR = olderATRs.reduce((a, b) => a + b, 0) / olderATRs.length;
  const volatilityTrend = olderAvgATR > 0 ? (recentAvgATR - olderAvgATR) / olderAvgATR : 0;
  
  // ADX / Trend strength
  const adxValues = calculateADX(highs, lows, closes, 14);
  const trendStrength = adxValues[adxValues.length - 1];
  
  // Trend direction
  const ema20 = calculateEMA(closes, 20);
  const ema50 = calculateEMA(closes, 50);
  const currentPrice = closes[closes.length - 1];
  const trendDirection = ema50[ema50.length - 1] > 0 
    ? (currentPrice - ema50[ema50.length - 1]) / ema50[ema50.length - 1] * 10
    : 0;
  
  // Compression (Bollinger width)
  const bbWidths = calculateBBWidth(closes, 20);
  const currentBBWidth = bbWidths[bbWidths.length - 1];
  const avgBBWidth = bbWidths.slice(-50).reduce((a, b) => a + b, 0) / 50;
  const compression = avgBBWidth > 0 ? 1 - (currentBBWidth / avgBBWidth) : 0;
  
  const recentBB = bbWidths.slice(-10).reduce((a, b) => a + b, 0) / 10;
  const olderBB = bbWidths.slice(-20, -10).reduce((a, b) => a + b, 0) / 10;
  const compressionTrend = olderBB > 0 ? (olderBB - recentBB) / olderBB : 0;  // Positive = compressing
  
  // Range score (HH/HL structure)
  const rangeScore = calculateRangeScore(highs, lows, closes);
  
  // Range width
  const highest = Math.max(...highs.slice(-20));
  const lowest = Math.min(...lows.slice(-20));
  const rangeWidth = currentPrice > 0 ? (highest - lowest) / currentPrice : 0;
  
  // Liquidity activity (wick analysis)
  const { activity: liquidityActivity, bias: liquidityBias } = calculateLiquidityMetrics(candles.slice(-20));
  
  // Momentum (MACD)
  const { macd, histogram } = calculateMACD(closes);
  const momentum = normalizeValue(histogram[histogram.length - 1], -avgATR, avgATR);
  
  // Momentum divergence
  const priceTrend = closes.slice(-10).reduce((a, b) => a + b, 0) / 10 - closes.slice(-20, -10).reduce((a, b) => a + b, 0) / 10;
  const macdTrend = macd.slice(-10).reduce((a, b) => a + b, 0) / 10 - macd.slice(-20, -10).reduce((a, b) => a + b, 0) / 10;
  const momentumDivergence = Math.sign(priceTrend) !== Math.sign(macdTrend) ? 1 : 0;
  
  // Volume
  const currentVolume = volumes[volumes.length - 1];
  const avgVolume = volumes.slice(-50).reduce((a, b) => a + b, 0) / 50;
  const volumeProfile = avgVolume > 0 ? currentVolume / avgVolume : 1;
  
  const recentVol = volumes.slice(-10).reduce((a, b) => a + b, 0) / 10;
  const olderVol = volumes.slice(-20, -10).reduce((a, b) => a + b, 0) / 10;
  const volumeTrend = olderVol > 0 ? (recentVol - olderVol) / olderVol : 0;
  
  return {
    trendStrength: clamp(trendStrength, 0, 1),
    trendDirection: clamp(trendDirection, -1, 1),
    volatility: clamp(volatility, 0, 3),
    volatilityTrend: clamp(volatilityTrend, -1, 1),
    compression: clamp(compression, 0, 1),
    compressionTrend: clamp(compressionTrend, -1, 1),
    rangeScore: clamp(rangeScore, 0, 1),
    rangeWidth: clamp(rangeWidth, 0, 0.5),
    liquidityActivity: clamp(liquidityActivity, 0, 1),
    liquidityBias: clamp(liquidityBias, -1, 1),
    momentum: clamp(momentum, -1, 1),
    momentumDivergence: clamp(momentumDivergence, 0, 1),
    volumeProfile: clamp(volumeProfile, 0, 5),
    volumeTrend: clamp(volumeTrend, -1, 1)
  };
}

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function calculateRangeScore(highs: number[], lows: number[], closes: number[]): number {
  // Check for HH/HL (uptrend) or LH/LL (downtrend) structure
  const recentHighs = highs.slice(-20);
  const recentLows = lows.slice(-20);
  
  let hhCount = 0;
  let hlCount = 0;
  let lhCount = 0;
  let llCount = 0;
  
  for (let i = 5; i < recentHighs.length; i++) {
    const prevHighs = Math.max(...recentHighs.slice(i - 5, i));
    const prevLows = Math.min(...recentLows.slice(i - 5, i));
    
    if (recentHighs[i] > prevHighs) hhCount++;
    if (recentLows[i] > prevLows) hlCount++;
    if (recentHighs[i] < prevHighs) lhCount++;
    if (recentLows[i] < prevLows) llCount++;
  }
  
  // High range score = no clear trend structure
  const trendScore = Math.max(hhCount + hlCount, lhCount + llCount);
  const total = recentHighs.length - 5;
  
  return total > 0 ? 1 - (trendScore / total) : 0.5;
}

function calculateLiquidityMetrics(candles: CandleInput[]): { activity: number; bias: number } {
  let sweepCount = 0;
  let upSweeps = 0;
  let downSweeps = 0;
  
  for (let i = 1; i < candles.length; i++) {
    const candle = candles[i];
    const body = Math.abs(candle.close - candle.open);
    const upperWick = candle.high - Math.max(candle.open, candle.close);
    const lowerWick = Math.min(candle.open, candle.close) - candle.low;
    const totalRange = candle.high - candle.low;
    
    if (totalRange === 0) continue;
    
    // Significant wick = potential sweep
    if (upperWick / totalRange > 0.3) {
      sweepCount++;
      upSweeps++;
    }
    if (lowerWick / totalRange > 0.3) {
      sweepCount++;
      downSweeps++;
    }
  }
  
  const activity = sweepCount / (candles.length * 2);  // Max 2 sweeps per candle
  const bias = upSweeps + downSweeps > 0 
    ? (downSweeps - upSweeps) / (upSweeps + downSweeps)  // Positive = more downside sweeps (bullish)
    : 0;
  
  return { activity, bias };
}

function normalizeValue(value: number, min: number, max: number): number {
  if (max === min) return 0;
  return ((value - min) / (max - min)) * 2 - 1;  // Scale to -1 to 1
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function getDefaultFeatures(): RegimeFeatures {
  return {
    trendStrength: 0.5,
    trendDirection: 0,
    volatility: 1,
    volatilityTrend: 0,
    compression: 0.5,
    compressionTrend: 0,
    rangeScore: 0.5,
    rangeWidth: 0.05,
    liquidityActivity: 0.2,
    liquidityBias: 0,
    momentum: 0,
    momentumDivergence: 0,
    volumeProfile: 1,
    volumeTrend: 0
  };
}
