/**
 * D2.1 — Fractal Signature Extractor
 * 
 * Converts price movement into normalized shape vectors
 */

import { 
  FractalSignature, 
  FractalConfig, 
  DEFAULT_FRACTAL_CONFIG 
} from './fractal.types.js';
import { v4 as uuidv4 } from 'uuid';

interface Candle {
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * Calculate EMA for smoothing
 */
function ema(values: number[], period: number): number[] {
  if (values.length === 0) return [];
  
  const k = 2 / (period + 1);
  const result: number[] = [values[0]];
  
  for (let i = 1; i < values.length; i++) {
    result.push(values[i] * k + result[i - 1] * (1 - k));
  }
  
  return result;
}

/**
 * Calculate ATR for volatility normalization
 */
function calculateATR(candles: Candle[], period: number = 14): number {
  if (candles.length < period + 1) return 0;
  
  let trSum = 0;
  for (let i = candles.length - period; i < candles.length; i++) {
    const curr = candles[i];
    const prev = candles[i - 1];
    
    const tr = Math.max(
      curr.high - curr.low,
      Math.abs(curr.high - prev.close),
      Math.abs(curr.low - prev.close)
    );
    trSum += tr;
  }
  
  return trSum / period;
}

/**
 * Extract fractal signature from candles
 * 
 * Steps:
 * 1. Calculate log returns
 * 2. Smooth with EMA
 * 3. Downsample to signature length
 * 4. Normalize to unit vector
 */
export function extractFractalSignature(
  candles: Candle[],
  asset: string,
  timeframe: string,
  config: FractalConfig = DEFAULT_FRACTAL_CONFIG
): FractalSignature | null {
  const { signatureLength, inputCandles, smoothingPeriod } = config;
  
  if (candles.length < inputCandles) {
    return null;
  }
  
  // Take last inputCandles
  const window = candles.slice(-inputCandles);
  
  // 1. Calculate log returns
  const logReturns: number[] = [];
  for (let i = 1; i < window.length; i++) {
    const ret = Math.log(window[i].close / window[i - 1].close);
    logReturns.push(ret);
  }
  
  // 2. Smooth with EMA
  const smoothed = ema(logReturns, smoothingPeriod);
  
  // 3. Downsample to signature length
  const downsampled: number[] = [];
  const step = smoothed.length / signatureLength;
  
  for (let i = 0; i < signatureLength; i++) {
    const startIdx = Math.floor(i * step);
    const endIdx = Math.floor((i + 1) * step);
    
    // Average values in this bucket
    let sum = 0;
    let count = 0;
    for (let j = startIdx; j < endIdx && j < smoothed.length; j++) {
      sum += smoothed[j];
      count++;
    }
    
    downsampled.push(count > 0 ? sum / count : 0);
  }
  
  // 4. Normalize to unit vector (L2 norm)
  const norm = Math.sqrt(downsampled.reduce((sum, v) => sum + v * v, 0));
  const vector = norm > 0 
    ? downsampled.map(v => v / norm)
    : downsampled;
  
  // Calculate metadata
  const atr = calculateATR(window, 14);
  const avgPrice = window.reduce((s, c) => s + c.close, 0) / window.length;
  const volatility = atr / avgPrice;
  
  // Trend bias: cumulative return
  const totalReturn = Math.log(window[window.length - 1].close / window[0].close);
  const trendBias = Math.tanh(totalReturn * 10); // Normalize to -1 to 1
  
  // Compression: ratio of recent ATR to historical ATR
  const recentATR = calculateATR(window.slice(-14), 7);
  const historicalATR = calculateATR(window.slice(0, -14), 14);
  const compression = historicalATR > 0 
    ? Math.max(0, Math.min(1, 1 - recentATR / historicalATR))
    : 0;
  
  // Impulse strength: max consecutive move
  let maxImpulse = 0;
  let currentImpulse = 0;
  let prevSign = 0;
  
  for (const ret of logReturns) {
    const sign = ret >= 0 ? 1 : -1;
    if (sign === prevSign) {
      currentImpulse += Math.abs(ret);
    } else {
      maxImpulse = Math.max(maxImpulse, currentImpulse);
      currentImpulse = Math.abs(ret);
    }
    prevSign = sign;
  }
  maxImpulse = Math.max(maxImpulse, currentImpulse);
  const impulseStrength = Math.tanh(maxImpulse * 50); // Normalize
  
  return {
    id: uuidv4(),
    asset,
    timeframe,
    startTs: window[0].openTime,
    endTs: window[window.length - 1].openTime,
    startBarIndex: 0,
    endBarIndex: window.length - 1,
    vector,
    vectorLength: signatureLength,
    volatility,
    trendBias,
    compression,
    impulseStrength,
    source: 'live',
    createdAt: new Date(),
  };
}

/**
 * Calculate cosine similarity between two signatures
 */
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;
  
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  
  const denominator = Math.sqrt(normA) * Math.sqrt(normB);
  return denominator > 0 ? dotProduct / denominator : 0;
}

/**
 * Calculate euclidean distance between signatures
 */
export function euclideanDistance(a: number[], b: number[]): number {
  if (a.length !== b.length) return Infinity;
  
  let sum = 0;
  for (let i = 0; i < a.length; i++) {
    const diff = a[i] - b[i];
    sum += diff * diff;
  }
  
  return Math.sqrt(sum);
}
