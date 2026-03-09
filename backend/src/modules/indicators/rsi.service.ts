/**
 * Phase 6 — RSI / Momentum Service
 * ==================================
 * RSI calculation with divergence detection
 */

import { RSIResult, RSIDivergence, MomentumState, MACDResult, StochasticResult } from './indicators.types.js';

// ═══════════════════════════════════════════════════════════════
// RSI CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate RSI from price data
 */
export function calculateRSI(closes: number[], period: number = 14): number {
  if (closes.length < period + 1) {
    return 50; // Default neutral
  }
  
  let gains = 0;
  let losses = 0;
  
  // Calculate initial average gain/loss
  for (let i = 1; i <= period; i++) {
    const change = closes[i] - closes[i - 1];
    if (change > 0) gains += change;
    else losses -= change;
  }
  
  let avgGain = gains / period;
  let avgLoss = losses / period;
  
  // Use Wilder's smoothing for remaining data
  for (let i = period + 1; i < closes.length; i++) {
    const change = closes[i] - closes[i - 1];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? -change : 0;
    
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
  }
  
  if (avgLoss === 0) return 100;
  
  const rs = avgGain / avgLoss;
  const rsi = 100 - (100 / (1 + rs));
  
  return Math.round(rsi * 100) / 100;
}

/**
 * Detect RSI divergences
 */
export function detectDivergence(
  prices: number[],
  rsiValues: number[],
  lookback: number = 20
): RSIDivergence | undefined {
  if (prices.length < lookback || rsiValues.length < lookback) {
    return undefined;
  }
  
  const recent = prices.length - 1;
  const prior = prices.length - lookback;
  
  const priceNow = prices[recent];
  const pricePrior = prices[prior];
  const rsiNow = rsiValues[recent];
  const rsiPrior = rsiValues[prior];
  
  // Bullish divergence: price lower low, RSI higher low
  if (priceNow < pricePrior && rsiNow > rsiPrior && rsiNow < 40) {
    return {
      type: 'BULLISH',
      confidence: Math.min((rsiNow - rsiPrior) / 20, 1),
      priceAction: 'LOWER_LOW',
      rsiAction: 'HIGHER_LOW',
    };
  }
  
  // Bearish divergence: price higher high, RSI lower high
  if (priceNow > pricePrior && rsiNow < rsiPrior && rsiNow > 60) {
    return {
      type: 'BEARISH',
      confidence: Math.min((rsiPrior - rsiNow) / 20, 1),
      priceAction: 'HIGHER_HIGH',
      rsiAction: 'LOWER_HIGH',
    };
  }
  
  // Hidden bullish: price higher low, RSI lower low (trend continuation)
  if (priceNow > pricePrior && rsiNow < rsiPrior && rsiNow < 50) {
    return {
      type: 'HIDDEN_BULLISH',
      confidence: Math.min((pricePrior - priceNow) / priceNow * 10, 1),
      priceAction: 'HIGHER_LOW',
      rsiAction: 'LOWER_LOW',
    };
  }
  
  // Hidden bearish: price lower high, RSI higher high
  if (priceNow < pricePrior && rsiNow > rsiPrior && rsiNow > 50) {
    return {
      type: 'HIDDEN_BEARISH',
      confidence: Math.min((rsiNow - rsiPrior) / 20, 1),
      priceAction: 'LOWER_HIGH',
      rsiAction: 'HIGHER_HIGH',
    };
  }
  
  return undefined;
}

/**
 * Get RSI analysis result
 */
export function analyzeRSI(closes: number[], period: number = 14): RSIResult {
  const rsi = calculateRSI(closes, period);
  
  // Calculate RSI history for divergence
  const rsiHistory: number[] = [];
  for (let i = period; i < closes.length; i++) {
    rsiHistory.push(calculateRSI(closes.slice(0, i + 1), period));
  }
  
  // Determine signal
  let signal: 'OVERBOUGHT' | 'OVERSOLD' | 'NEUTRAL';
  if (rsi > 70) signal = 'OVERBOUGHT';
  else if (rsi < 30) signal = 'OVERSOLD';
  else signal = 'NEUTRAL';
  
  // Determine trend from RSI slope
  let trend: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  if (rsiHistory.length >= 5) {
    const recent = rsiHistory.slice(-5);
    const slope = (recent[4] - recent[0]) / 5;
    if (slope > 2) trend = 'BULLISH';
    else if (slope < -2) trend = 'BEARISH';
    else trend = 'NEUTRAL';
  } else {
    trend = 'NEUTRAL';
  }
  
  // Calculate strength (distance from neutral)
  const strength = Math.abs(rsi - 50) / 50;
  
  // Detect divergence
  const divergence = detectDivergence(closes, rsiHistory);
  
  return {
    value: rsi,
    signal,
    divergence,
    trend,
    strength: Math.round(strength * 100) / 100,
  };
}

// ═══════════════════════════════════════════════════════════════
// MACD CALCULATION
// ═══════════════════════════════════════════════════════════════

function calculateEMA(data: number[], period: number): number[] {
  const ema: number[] = [];
  const multiplier = 2 / (period + 1);
  
  // Start with SMA
  let sum = 0;
  for (let i = 0; i < period && i < data.length; i++) {
    sum += data[i];
  }
  ema.push(sum / Math.min(period, data.length));
  
  // Calculate EMA
  for (let i = period; i < data.length; i++) {
    ema.push((data[i] - ema[ema.length - 1]) * multiplier + ema[ema.length - 1]);
  }
  
  return ema;
}

export function calculateMACD(
  closes: number[],
  fastPeriod: number = 12,
  slowPeriod: number = 26,
  signalPeriod: number = 9
): MACDResult {
  const emaFast = calculateEMA(closes, fastPeriod);
  const emaSlow = calculateEMA(closes, slowPeriod);
  
  // MACD line
  const macdLine: number[] = [];
  const offset = slowPeriod - fastPeriod;
  for (let i = 0; i < emaSlow.length; i++) {
    macdLine.push(emaFast[i + offset] - emaSlow[i]);
  }
  
  // Signal line
  const signalLine = calculateEMA(macdLine, signalPeriod);
  
  const macd = macdLine[macdLine.length - 1] || 0;
  const signal = signalLine[signalLine.length - 1] || 0;
  const histogram = macd - signal;
  
  // Detect crossover
  let crossover: 'BULLISH' | 'BEARISH' | 'NONE' = 'NONE';
  if (macdLine.length >= 2 && signalLine.length >= 2) {
    const prevMacd = macdLine[macdLine.length - 2];
    const prevSignal = signalLine[signalLine.length - 2];
    
    if (prevMacd < prevSignal && macd > signal) crossover = 'BULLISH';
    else if (prevMacd > prevSignal && macd < signal) crossover = 'BEARISH';
  }
  
  return {
    macd: Math.round(macd * 100) / 100,
    signal: Math.round(signal * 100) / 100,
    histogram: Math.round(histogram * 100) / 100,
    crossover,
  };
}

// ═══════════════════════════════════════════════════════════════
// STOCHASTIC
// ═══════════════════════════════════════════════════════════════

export function calculateStochastic(
  highs: number[],
  lows: number[],
  closes: number[],
  kPeriod: number = 14,
  dPeriod: number = 3
): StochasticResult {
  if (closes.length < kPeriod) {
    return { k: 50, d: 50, signal: 'NEUTRAL' };
  }
  
  // Calculate %K values
  const kValues: number[] = [];
  for (let i = kPeriod - 1; i < closes.length; i++) {
    const periodHighs = highs.slice(i - kPeriod + 1, i + 1);
    const periodLows = lows.slice(i - kPeriod + 1, i + 1);
    
    const highestHigh = Math.max(...periodHighs);
    const lowestLow = Math.min(...periodLows);
    
    const range = highestHigh - lowestLow;
    const k = range > 0 ? ((closes[i] - lowestLow) / range) * 100 : 50;
    kValues.push(k);
  }
  
  // Calculate %D (SMA of %K)
  const dValues: number[] = [];
  for (let i = dPeriod - 1; i < kValues.length; i++) {
    const sum = kValues.slice(i - dPeriod + 1, i + 1).reduce((a, b) => a + b, 0);
    dValues.push(sum / dPeriod);
  }
  
  const k = kValues[kValues.length - 1] || 50;
  const d = dValues[dValues.length - 1] || 50;
  
  let signal: 'OVERBOUGHT' | 'OVERSOLD' | 'NEUTRAL';
  if (k > 80 && d > 80) signal = 'OVERBOUGHT';
  else if (k < 20 && d < 20) signal = 'OVERSOLD';
  else signal = 'NEUTRAL';
  
  return {
    k: Math.round(k * 100) / 100,
    d: Math.round(d * 100) / 100,
    signal,
  };
}

// ═══════════════════════════════════════════════════════════════
// COMBINED MOMENTUM STATE
// ═══════════════════════════════════════════════════════════════

export function analyzeMomentum(
  highs: number[],
  lows: number[],
  closes: number[]
): MomentumState {
  const rsi = analyzeRSI(closes);
  const macd = calculateMACD(closes);
  const stochastic = calculateStochastic(highs, lows, closes);
  
  // Calculate composite score (0-1)
  let composite = 0.5;
  
  // RSI contribution
  composite += (rsi.value - 50) / 100 * 0.4;
  
  // MACD contribution
  if (macd.histogram > 0) composite += 0.1;
  else if (macd.histogram < 0) composite -= 0.1;
  
  // Stochastic contribution
  composite += (stochastic.k - 50) / 200;
  
  // Clamp to 0-1
  composite = Math.max(0, Math.min(1, composite));
  
  // Determine bias
  let bias: 'LONG' | 'SHORT' | 'NEUTRAL';
  if (composite > 0.6) bias = 'LONG';
  else if (composite < 0.4) bias = 'SHORT';
  else bias = 'NEUTRAL';
  
  return {
    rsi,
    macd,
    stochastic,
    composite: Math.round(composite * 100) / 100,
    bias,
  };
}

/**
 * Calculate momentum boost for decision engine
 */
export function getMomentumBoost(momentum: MomentumState): number {
  let boost = 1.0;
  
  // RSI divergence boost
  if (momentum.rsi.divergence) {
    if (momentum.rsi.divergence.type === 'BULLISH') {
      boost *= 1.1 + momentum.rsi.divergence.confidence * 0.1;
    } else if (momentum.rsi.divergence.type === 'BEARISH') {
      boost *= 0.9 - momentum.rsi.divergence.confidence * 0.1;
    }
  }
  
  // MACD crossover boost
  if (momentum.macd?.crossover === 'BULLISH') boost *= 1.05;
  else if (momentum.macd?.crossover === 'BEARISH') boost *= 0.95;
  
  // Overbought/oversold adjustment
  if (momentum.rsi.signal === 'OVERBOUGHT') boost *= 0.85;
  else if (momentum.rsi.signal === 'OVERSOLD') boost *= 1.15;
  
  // Clamp to reasonable range
  return Math.round(Math.max(0.7, Math.min(1.3, boost)) * 100) / 100;
}
