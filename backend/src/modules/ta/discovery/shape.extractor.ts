/**
 * P2.1 — Shape Extractor
 * 
 * Converts price windows into normalized shape vectors for clustering.
 * This enables discovery of new patterns not in textbook TA.
 */

export interface ShapeConfig {
  windowSize: number;       // 64 or 128 candles
  embeddingDim: number;     // Target dimension after PCA (16-32)
  normalize: boolean;       // Normalize to [0,1]
  includeDerivatives: boolean;
}

export const DEFAULT_SHAPE_CONFIG: ShapeConfig = {
  windowSize: 64,
  embeddingDim: 16,
  normalize: true,
  includeDerivatives: true,
};

export interface CandleInput {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ShapeVector {
  priceShape: number[];      // Normalized close prices
  hlRange: number[];         // High-low range
  volumeShape: number[];     // Normalized volume
  slope: number[];           // Price derivatives
  curvature: number[];       // Second derivatives
  compression: number[];     // Range compression
  rawDim: number;            // Original dimension
  timestamp?: number;
}

/**
 * Extract shape vector from candle window
 */
export function extractShape(
  candles: CandleInput[],
  config: ShapeConfig = DEFAULT_SHAPE_CONFIG
): ShapeVector {
  const { windowSize, normalize, includeDerivatives } = config;
  
  // Take last windowSize candles
  const window = candles.slice(-windowSize);
  
  if (window.length < windowSize) {
    throw new Error(`Not enough candles: ${window.length} < ${windowSize}`);
  }
  
  const closes = window.map(c => c.close);
  const highs = window.map(c => c.high);
  const lows = window.map(c => c.low);
  const volumes = window.map(c => c.volume);
  
  // Normalize prices to [0, 1]
  let priceShape: number[];
  if (normalize) {
    const minPrice = Math.min(...closes);
    const maxPrice = Math.max(...closes);
    const range = maxPrice - minPrice || 1;
    priceShape = closes.map(p => (p - minPrice) / range);
  } else {
    priceShape = closes;
  }
  
  // High-low range as percentage of price
  const hlRange = window.map((c, i) => {
    const range = c.high - c.low;
    return range / c.close;
  });
  
  // Normalize volume
  const maxVol = Math.max(...volumes) || 1;
  const volumeShape = volumes.map(v => v / maxVol);
  
  // Calculate derivatives if needed
  let slope: number[] = [];
  let curvature: number[] = [];
  let compression: number[] = [];
  
  if (includeDerivatives) {
    // First derivative (slope)
    for (let i = 1; i < priceShape.length; i++) {
      slope.push(priceShape[i] - priceShape[i - 1]);
    }
    
    // Second derivative (curvature)
    for (let i = 1; i < slope.length; i++) {
      curvature.push(slope[i] - slope[i - 1]);
    }
    
    // Range compression (rolling ATR ratio)
    const lookback = 10;
    for (let i = lookback; i < hlRange.length; i++) {
      const recentAvg = hlRange.slice(i - lookback, i).reduce((a, b) => a + b, 0) / lookback;
      const historicalAvg = hlRange.slice(0, i - lookback).reduce((a, b) => a + b, 0) / (i - lookback) || recentAvg;
      compression.push(historicalAvg > 0 ? recentAvg / historicalAvg : 1);
    }
  }
  
  return {
    priceShape,
    hlRange,
    volumeShape,
    slope,
    curvature,
    compression,
    rawDim: priceShape.length + hlRange.length + volumeShape.length + 
            slope.length + curvature.length + compression.length,
  };
}

/**
 * Flatten shape vector to single array for clustering
 */
export function flattenShape(shape: ShapeVector): number[] {
  return [
    ...shape.priceShape,
    ...shape.hlRange,
    ...shape.volumeShape,
    ...shape.slope,
    ...shape.curvature,
    ...shape.compression,
  ];
}

/**
 * Downsample shape to target dimension using simple averaging
 */
export function downsampleShape(
  flatShape: number[],
  targetDim: number
): number[] {
  if (flatShape.length <= targetDim) {
    return flatShape;
  }
  
  const result: number[] = [];
  const chunkSize = Math.ceil(flatShape.length / targetDim);
  
  for (let i = 0; i < targetDim; i++) {
    const start = i * chunkSize;
    const end = Math.min(start + chunkSize, flatShape.length);
    const chunk = flatShape.slice(start, end);
    const avg = chunk.reduce((a, b) => a + b, 0) / chunk.length;
    result.push(avg);
  }
  
  return result;
}

/**
 * Calculate cosine similarity between two shape vectors
 */
export function shapeSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) {
    throw new Error('Shape vectors must have same length');
  }
  
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  
  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  return denom > 0 ? dotProduct / denom : 0;
}

/**
 * Calculate Euclidean distance between shape vectors
 */
export function shapeDistance(a: number[], b: number[]): number {
  if (a.length !== b.length) {
    throw new Error('Shape vectors must have same length');
  }
  
  let sumSq = 0;
  for (let i = 0; i < a.length; i++) {
    const diff = a[i] - b[i];
    sumSq += diff * diff;
  }
  
  return Math.sqrt(sumSq);
}
