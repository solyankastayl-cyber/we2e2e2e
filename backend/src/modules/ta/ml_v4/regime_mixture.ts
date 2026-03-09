/**
 * P1.5 — Regime Mixture Models
 * 
 * Train separate models for different market regimes:
 * - TREND_UP
 * - TREND_DOWN
 * - RANGE
 * 
 * Use regime-specific models during inference
 */

export type MarketRegime = 'TREND_UP' | 'TREND_DOWN' | 'RANGE' | 'TRANSITION';

export interface RegimeFeatures {
  maSlope20: number;      // MA(20) slope normalized
  maSlope50: number;      // MA(50) slope normalized
  adx: number;            // ADX value (0-100)
  adxSlope: number;       // ADX change
  volatility: number;     // ATR/price
  rangeCompression: number; // recent range vs historical
  trendStrength: number;  // composite trend indicator
}

export interface RegimeConfig {
  // ADX thresholds
  adxTrendThreshold: number;     // ADX > this = trending (default 25)
  adxStrongTrendThreshold: number; // ADX > this = strong trend (default 40)
  
  // Slope thresholds (normalized)
  slopeUpThreshold: number;      // slope > this = uptrend
  slopeDownThreshold: number;    // slope < this = downtrend
  
  // Volatility thresholds
  highVolThreshold: number;      // vol > this = high volatility
  lowVolThreshold: number;       // vol < this = low volatility
  
  // Confidence threshold for regime
  minConfidence: number;         // minimum confidence to assign regime
}

export const DEFAULT_REGIME_CONFIG: RegimeConfig = {
  adxTrendThreshold: 25,
  adxStrongTrendThreshold: 40,
  slopeUpThreshold: 0.001,
  slopeDownThreshold: -0.001,
  highVolThreshold: 0.05,
  lowVolThreshold: 0.015,
  minConfidence: 0.6,
};

export interface RegimeDetectionResult {
  regime: MarketRegime;
  confidence: number;
  features: RegimeFeatures;
  reasoning: string[];
}

/**
 * Detect market regime from features
 */
export function detectRegime(
  features: RegimeFeatures,
  config: RegimeConfig = DEFAULT_REGIME_CONFIG
): RegimeDetectionResult {
  const reasoning: string[] = [];
  let regimeScores: Record<MarketRegime, number> = {
    TREND_UP: 0,
    TREND_DOWN: 0,
    RANGE: 0,
    TRANSITION: 0,
  };
  
  // ADX analysis
  if (features.adx >= config.adxStrongTrendThreshold) {
    reasoning.push(`Strong trend (ADX=${features.adx.toFixed(1)})`);
    if (features.maSlope20 > 0) {
      regimeScores.TREND_UP += 0.4;
    } else {
      regimeScores.TREND_DOWN += 0.4;
    }
  } else if (features.adx >= config.adxTrendThreshold) {
    reasoning.push(`Moderate trend (ADX=${features.adx.toFixed(1)})`);
    if (features.maSlope20 > 0) {
      regimeScores.TREND_UP += 0.25;
    } else {
      regimeScores.TREND_DOWN += 0.25;
    }
  } else {
    reasoning.push(`Low trend strength (ADX=${features.adx.toFixed(1)})`);
    regimeScores.RANGE += 0.3;
  }
  
  // MA slope analysis
  if (features.maSlope20 > config.slopeUpThreshold && features.maSlope50 > 0) {
    reasoning.push('MA slopes positive');
    regimeScores.TREND_UP += 0.25;
  } else if (features.maSlope20 < config.slopeDownThreshold && features.maSlope50 < 0) {
    reasoning.push('MA slopes negative');
    regimeScores.TREND_DOWN += 0.25;
  } else {
    reasoning.push('MA slopes mixed/flat');
    regimeScores.RANGE += 0.2;
  }
  
  // Volatility analysis
  if (features.volatility > config.highVolThreshold) {
    reasoning.push('High volatility');
    regimeScores.TRANSITION += 0.15;
  } else if (features.volatility < config.lowVolThreshold) {
    reasoning.push('Low volatility');
    regimeScores.RANGE += 0.15;
  }
  
  // Range compression
  if (features.rangeCompression < 0.7) {
    reasoning.push('Range compressed');
    regimeScores.RANGE += 0.1;
  }
  
  // Find best regime
  const entries = Object.entries(regimeScores) as [MarketRegime, number][];
  entries.sort((a, b) => b[1] - a[1]);
  
  const [bestRegime, bestScore] = entries[0];
  const totalScore = entries.reduce((sum, [_, s]) => sum + s, 0);
  const confidence = totalScore > 0 ? bestScore / totalScore : 0;
  
  // If confidence too low, mark as transition
  const finalRegime = confidence >= config.minConfidence ? bestRegime : 'TRANSITION';
  
  return {
    regime: finalRegime,
    confidence,
    features,
    reasoning,
  };
}

/**
 * Calculate regime features from raw market data
 */
export function calculateRegimeFeatures(
  closes: number[],
  highs: number[],
  lows: number[],
  atr: number
): RegimeFeatures {
  const n = closes.length;
  if (n < 50) {
    return {
      maSlope20: 0,
      maSlope50: 0,
      adx: 20,
      adxSlope: 0,
      volatility: 0.02,
      rangeCompression: 1,
      trendStrength: 0,
    };
  }
  
  // Calculate MAs
  const ma20 = sma(closes.slice(-25), 20);
  const ma50 = sma(closes.slice(-55), 50);
  
  // MA slopes (change over last 5 bars, normalized)
  const ma20_prev = sma(closes.slice(-30, -5), 20);
  const ma50_prev = sma(closes.slice(-60, -5), 50);
  
  const price = closes[n - 1];
  const maSlope20 = price > 0 ? (ma20 - ma20_prev) / price / 5 : 0;
  const maSlope50 = price > 0 ? (ma50 - ma50_prev) / price / 5 : 0;
  
  // Simplified ADX calculation
  const adx = calculateSimpleADX(highs.slice(-20), lows.slice(-20), closes.slice(-20));
  const adx_prev = calculateSimpleADX(highs.slice(-25, -5), lows.slice(-25, -5), closes.slice(-25, -5));
  const adxSlope = adx - adx_prev;
  
  // Volatility
  const volatility = price > 0 ? atr / price : 0.02;
  
  // Range compression (recent range vs historical)
  const recentRange = Math.max(...highs.slice(-10)) - Math.min(...lows.slice(-10));
  const historicalRange = Math.max(...highs.slice(-50)) - Math.min(...lows.slice(-50));
  const rangeCompression = historicalRange > 0 ? recentRange / historicalRange : 1;
  
  // Trend strength composite
  const trendStrength = (Math.abs(maSlope20) * 100 + adx / 50) / 2;
  
  return {
    maSlope20,
    maSlope50,
    adx,
    adxSlope,
    volatility,
    rangeCompression,
    trendStrength,
  };
}

/**
 * Simple Moving Average
 */
function sma(values: number[], period: number): number {
  const slice = values.slice(-period);
  if (slice.length === 0) return 0;
  return slice.reduce((a, b) => a + b, 0) / slice.length;
}

/**
 * Simplified ADX calculation
 */
function calculateSimpleADX(highs: number[], lows: number[], closes: number[]): number {
  const n = highs.length;
  if (n < 14) return 20;
  
  let sumDMPlus = 0;
  let sumDMMinus = 0;
  let sumTR = 0;
  
  for (let i = 1; i < n; i++) {
    const highDiff = highs[i] - highs[i - 1];
    const lowDiff = lows[i - 1] - lows[i];
    
    const dmPlus = highDiff > lowDiff && highDiff > 0 ? highDiff : 0;
    const dmMinus = lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0;
    
    const tr = Math.max(
      highs[i] - lows[i],
      Math.abs(highs[i] - closes[i - 1]),
      Math.abs(lows[i] - closes[i - 1])
    );
    
    sumDMPlus += dmPlus;
    sumDMMinus += dmMinus;
    sumTR += tr;
  }
  
  if (sumTR === 0) return 20;
  
  const diPlus = (sumDMPlus / sumTR) * 100;
  const diMinus = (sumDMMinus / sumTR) * 100;
  const diSum = diPlus + diMinus;
  
  if (diSum === 0) return 20;
  
  const dx = (Math.abs(diPlus - diMinus) / diSum) * 100;
  return Math.min(100, Math.max(0, dx));
}

/**
 * Get regime-specific model key
 */
export function getRegimeModelKey(regime: MarketRegime, modelType: 'entry' | 'r'): string {
  return `model_${modelType}_${regime.toLowerCase()}`;
}

/**
 * Regime mixture: combine predictions from multiple models
 */
export function mixRegimePredictions(
  predictions: Array<{ regime: MarketRegime; pEntry: number; rExpected: number; weight: number }>
): { pEntry: number; rExpected: number } {
  const totalWeight = predictions.reduce((sum, p) => sum + p.weight, 0);
  if (totalWeight === 0) {
    return { pEntry: 0.5, rExpected: 0 };
  }
  
  let pEntry = 0;
  let rExpected = 0;
  
  for (const p of predictions) {
    const normalizedWeight = p.weight / totalWeight;
    pEntry += p.pEntry * normalizedWeight;
    rExpected += p.rExpected * normalizedWeight;
  }
  
  return { pEntry, rExpected };
}
