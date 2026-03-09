/**
 * D3 — Market Physics Computations
 * 
 * Core algorithms for detecting market energy states
 */

import { 
  PhysicsState, 
  MarketPhysicsResult, 
  PhysicsConfig, 
  DEFAULT_PHYSICS_CONFIG 
} from './physics.types.js';

interface Candle {
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ═══════════════════════════════════════════════════════════════
// Helper Functions
// ═══════════════════════════════════════════════════════════════

function calculateATR(candles: Candle[], period: number): number[] {
  if (candles.length < period + 1) return [];
  
  const tr: number[] = [];
  for (let i = 1; i < candles.length; i++) {
    const curr = candles[i];
    const prev = candles[i - 1];
    tr.push(Math.max(
      curr.high - curr.low,
      Math.abs(curr.high - prev.close),
      Math.abs(curr.low - prev.close)
    ));
  }
  
  // EMA of TR
  const atr: number[] = [];
  const k = 2 / (period + 1);
  atr[0] = tr.slice(0, period).reduce((a, b) => a + b, 0) / period;
  
  for (let i = 1; i < tr.length; i++) {
    atr.push(tr[i] * k + atr[i - 1] * (1 - k));
  }
  
  return atr;
}

function calculateBollingerWidth(candles: Candle[], period: number): number[] {
  if (candles.length < period) return [];
  
  const widths: number[] = [];
  
  for (let i = period - 1; i < candles.length; i++) {
    const slice = candles.slice(i - period + 1, i + 1);
    const closes = slice.map(c => c.close);
    const avg = closes.reduce((a, b) => a + b, 0) / period;
    const std = Math.sqrt(closes.reduce((sum, c) => sum + (c - avg) ** 2, 0) / period);
    
    // Width = (Upper - Lower) / Middle = 4 * std / avg
    widths.push((4 * std) / avg);
  }
  
  return widths;
}

function calculateRSI(candles: Candle[], period: number = 14): number {
  if (candles.length < period + 1) return 50;
  
  const changes = [];
  for (let i = 1; i < candles.length; i++) {
    changes.push(candles[i].close - candles[i - 1].close);
  }
  
  const recentChanges = changes.slice(-period);
  const gains = recentChanges.filter(c => c > 0).reduce((a, b) => a + b, 0) / period;
  const losses = Math.abs(recentChanges.filter(c => c < 0).reduce((a, b) => a + b, 0)) / period;
  
  if (losses === 0) return 100;
  const rs = gains / losses;
  return 100 - (100 / (1 + rs));
}

// ═══════════════════════════════════════════════════════════════
// Compression Detection
// ═══════════════════════════════════════════════════════════════

export function computeCompression(
  candles: Candle[],
  config: PhysicsConfig = DEFAULT_PHYSICS_CONFIG
): { score: number; atrRatio: number; rangeContraction: number; bollingerWidth: number } {
  const { compressionATRPeriod, compressionThreshold, bollingerPeriod, bollingerSqueezeFactor } = config;
  
  if (candles.length < Math.max(compressionATRPeriod * 2, bollingerPeriod)) {
    return { score: 0, atrRatio: 1, rangeContraction: 0, bollingerWidth: 1 };
  }
  
  // ATR ratio: recent vs historical
  const atr = calculateATR(candles, compressionATRPeriod);
  const recentATR = atr.slice(-5).reduce((a, b) => a + b, 0) / 5;
  const historicalATR = atr.slice(-compressionATRPeriod * 2, -compressionATRPeriod)
    .reduce((a, b) => a + b, 0) / compressionATRPeriod;
  
  const atrRatio = historicalATR > 0 ? recentATR / historicalATR : 1;
  
  // Range contraction
  const recentCandles = candles.slice(-10);
  const recentRange = Math.max(...recentCandles.map(c => c.high)) - 
                     Math.min(...recentCandles.map(c => c.low));
  const historicalCandles = candles.slice(-30, -10);
  const historicalRange = historicalCandles.length > 0
    ? Math.max(...historicalCandles.map(c => c.high)) - Math.min(...historicalCandles.map(c => c.low))
    : recentRange;
  
  const rangeContraction = historicalRange > 0 ? 1 - (recentRange / historicalRange) : 0;
  
  // Bollinger width
  const bbWidths = calculateBollingerWidth(candles, bollingerPeriod);
  const currentBBWidth = bbWidths.length > 0 ? bbWidths[bbWidths.length - 1] : 1;
  const avgBBWidth = bbWidths.length > 0 
    ? bbWidths.slice(-20).reduce((a, b) => a + b, 0) / Math.min(20, bbWidths.length)
    : 1;
  const bollingerWidth = avgBBWidth > 0 ? currentBBWidth / avgBBWidth : 1;
  
  // Compression score
  let score = 0;
  
  // Lower ATR ratio = more compression
  if (atrRatio < compressionThreshold) {
    score += (compressionThreshold - atrRatio) / compressionThreshold * 0.4;
  }
  
  // Higher range contraction = more compression
  score += Math.max(0, rangeContraction) * 0.35;
  
  // Lower BB width = more compression
  if (bollingerWidth < bollingerSqueezeFactor) {
    score += (bollingerSqueezeFactor - bollingerWidth) / bollingerSqueezeFactor * 0.25;
  }
  
  return {
    score: Math.min(1, Math.max(0, score)),
    atrRatio,
    rangeContraction: Math.max(0, rangeContraction),
    bollingerWidth,
  };
}

// ═══════════════════════════════════════════════════════════════
// Pressure Detection
// ═══════════════════════════════════════════════════════════════

export function computePressure(
  candles: Candle[],
  config: PhysicsConfig = DEFAULT_PHYSICS_CONFIG
): { score: number; levelTests: number; trendPersistence: number; direction: 'BULL' | 'BEAR' | 'NEUTRAL' } {
  const { levelTestLookback, minLevelTests, trendPersistenceThreshold } = config;
  
  if (candles.length < levelTestLookback) {
    return { score: 0, levelTests: 0, trendPersistence: 0, direction: 'NEUTRAL' };
  }
  
  const recentCandles = candles.slice(-levelTestLookback);
  
  // Find key levels
  const highs = recentCandles.map(c => c.high);
  const lows = recentCandles.map(c => c.low);
  const maxHigh = Math.max(...highs);
  const minLow = Math.min(...lows);
  
  // Count level tests (touches within 0.5% of extreme)
  const tolerance = 0.005;
  const highTests = highs.filter(h => Math.abs(h - maxHigh) / maxHigh < tolerance).length;
  const lowTests = lows.filter(l => Math.abs(l - minLow) / minLow < tolerance).length;
  
  const levelTests = Math.max(highTests, lowTests);
  
  // Trend persistence (consecutive closes in direction)
  let bullBars = 0;
  let bearBars = 0;
  for (let i = 1; i < recentCandles.length; i++) {
    if (recentCandles[i].close > recentCandles[i - 1].close) {
      bullBars++;
    } else {
      bearBars++;
    }
  }
  
  const totalBars = recentCandles.length - 1;
  const trendPersistence = Math.abs(bullBars - bearBars) / totalBars;
  const direction: 'BULL' | 'BEAR' | 'NEUTRAL' = 
    bullBars > bearBars * 1.3 ? 'BULL' :
    bearBars > bullBars * 1.3 ? 'BEAR' : 'NEUTRAL';
  
  // Pressure score
  let score = 0;
  
  // More level tests = more pressure
  if (levelTests >= minLevelTests) {
    score += (levelTests / (minLevelTests * 2)) * 0.5;
  }
  
  // Higher trend persistence = more pressure
  if (trendPersistence > trendPersistenceThreshold) {
    score += trendPersistence * 0.5;
  }
  
  return {
    score: Math.min(1, Math.max(0, score)),
    levelTests,
    trendPersistence,
    direction,
  };
}

// ═══════════════════════════════════════════════════════════════
// Energy Calculation
// ═══════════════════════════════════════════════════════════════

export function computeEnergy(
  compressionScore: number,
  pressureScore: number,
  liquidityBias: number,  // From liquidity engine
  momentumScore: number,
  config: PhysicsConfig = DEFAULT_PHYSICS_CONFIG
): number {
  const { energyWeights } = config;
  
  const energy = 
    compressionScore * energyWeights.compression +
    pressureScore * energyWeights.pressure +
    Math.abs(liquidityBias) * energyWeights.liquidity +
    momentumScore * energyWeights.momentum;
  
  return Math.min(1, Math.max(0, energy));
}

// ═══════════════════════════════════════════════════════════════
// Release Detection
// ═══════════════════════════════════════════════════════════════

export function computeRelease(
  candles: Candle[],
  config: PhysicsConfig = DEFAULT_PHYSICS_CONFIG
): { probability: number; isReleasing: boolean; volumeProfile: number } {
  const { releaseATRSpike, releaseVolumeSpike, compressionATRPeriod } = config;
  
  if (candles.length < compressionATRPeriod + 5) {
    return { probability: 0, isReleasing: false, volumeProfile: 1 };
  }
  
  // Check for ATR spike
  const atr = calculateATR(candles, compressionATRPeriod);
  const currentATR = atr[atr.length - 1];
  const avgATR = atr.slice(-compressionATRPeriod).reduce((a, b) => a + b, 0) / compressionATRPeriod;
  const atrSpike = avgATR > 0 ? currentATR / avgATR : 1;
  
  // Check for volume spike
  const recentVolume = candles.slice(-5).map(c => c.volume);
  const avgVolume = candles.slice(-30, -5)
    .reduce((sum, c) => sum + c.volume, 0) / 25;
  const volumeProfile = avgVolume > 0 
    ? recentVolume.reduce((a, b) => a + b, 0) / 5 / avgVolume 
    : 1;
  
  // Detect release
  const isReleasing = atrSpike > releaseATRSpike || volumeProfile > releaseVolumeSpike;
  
  // Release probability based on current conditions
  let probability = 0;
  if (atrSpike > 1.2) probability += 0.3;
  if (volumeProfile > 1.3) probability += 0.3;
  if (atrSpike > releaseATRSpike) probability += 0.2;
  if (volumeProfile > releaseVolumeSpike) probability += 0.2;
  
  return {
    probability: Math.min(1, probability),
    isReleasing,
    volumeProfile,
  };
}

// ═══════════════════════════════════════════════════════════════
// Exhaustion Detection
// ═══════════════════════════════════════════════════════════════

export function computeExhaustion(
  candles: Candle[],
  config: PhysicsConfig = DEFAULT_PHYSICS_CONFIG
): { score: number; momentumDecay: number } {
  const { exhaustionLookback, momentumDecayThreshold } = config;
  
  if (candles.length < exhaustionLookback + 14) {
    return { score: 0, momentumDecay: 0 };
  }
  
  // RSI divergence check
  const currentRSI = calculateRSI(candles, 14);
  const historicalRSI = calculateRSI(candles.slice(0, -exhaustionLookback), 14);
  
  // Momentum decay
  const recentReturns = candles.slice(-exhaustionLookback)
    .map((c, i, arr) => i > 0 ? (c.close - arr[i-1].close) / arr[i-1].close : 0);
  const historicalReturns = candles.slice(-exhaustionLookback * 2, -exhaustionLookback)
    .map((c, i, arr) => i > 0 ? (c.close - arr[i-1].close) / arr[i-1].close : 0);
  
  const recentMomentum = Math.abs(recentReturns.reduce((a, b) => a + b, 0));
  const historicalMomentum = Math.abs(historicalReturns.reduce((a, b) => a + b, 0));
  
  const momentumDecay = historicalMomentum > 0 
    ? 1 - (recentMomentum / historicalMomentum) 
    : 0;
  
  // Exhaustion score
  let score = 0;
  
  // RSI extreme + divergence
  if (currentRSI > 70 || currentRSI < 30) {
    score += 0.3;
  }
  
  // Momentum decay
  if (momentumDecay > momentumDecayThreshold) {
    score += momentumDecay * 0.5;
  }
  
  // Small bodies after move
  const recentCandles = candles.slice(-5);
  const avgBody = recentCandles.reduce((sum, c) => sum + Math.abs(c.close - c.open), 0) / 5;
  const avgRange = recentCandles.reduce((sum, c) => sum + (c.high - c.low), 0) / 5;
  if (avgRange > 0 && avgBody / avgRange < 0.3) {
    score += 0.2;
  }
  
  return {
    score: Math.min(1, Math.max(0, score)),
    momentumDecay: Math.max(0, momentumDecay),
  };
}

// ═══════════════════════════════════════════════════════════════
// Main Physics Analysis
// ═══════════════════════════════════════════════════════════════

export function analyzeMarketPhysics(
  candles: Candle[],
  asset: string,
  timeframe: string,
  liquidityBias: number = 0,
  config: PhysicsConfig = DEFAULT_PHYSICS_CONFIG
): MarketPhysicsResult {
  // Compute individual components
  const compression = computeCompression(candles, config);
  const pressure = computePressure(candles, config);
  const momentumScore = calculateRSI(candles, 14) / 100;
  const energyScore = computeEnergy(compression.score, pressure.score, liquidityBias, momentumScore, config);
  const release = computeRelease(candles, config);
  const exhaustion = computeExhaustion(candles, config);
  
  // Determine physics state
  let physicsState: PhysicsState = 'NEUTRAL';
  let stateConfidence = 0.5;
  
  if (release.isReleasing) {
    physicsState = 'RELEASE';
    stateConfidence = release.probability;
  } else if (exhaustion.score > 0.6) {
    physicsState = 'EXHAUSTION';
    stateConfidence = exhaustion.score;
  } else if (compression.score > 0.5 && pressure.score > 0.4) {
    physicsState = 'PRESSURE';
    stateConfidence = (compression.score + pressure.score) / 2;
  } else if (compression.score > 0.5) {
    physicsState = 'COMPRESSION';
    stateConfidence = compression.score;
  } else if (release.probability > 0.5) {
    physicsState = 'EXPANSION';
    stateConfidence = release.probability;
  }
  
  // Direction bias
  const directionBias = pressure.direction;
  
  // Calculate physics boost
  let physicsBoost = 1.0;
  
  if (physicsState === 'COMPRESSION' && energyScore > 0.5) {
    physicsBoost = 1.0 + energyScore * 0.2;  // Up to 1.2
  } else if (physicsState === 'PRESSURE') {
    physicsBoost = 1.0 + pressure.score * 0.15;  // Up to 1.15
  } else if (physicsState === 'EXHAUSTION') {
    physicsBoost = 1.0 - exhaustion.score * 0.2;  // Down to 0.8
  }
  
  return {
    asset,
    timeframe,
    timestamp: new Date(),
    compressionScore: compression.score,
    pressureScore: pressure.score,
    energyScore,
    releaseProbability: release.probability,
    exhaustionScore: exhaustion.score,
    physicsState,
    stateConfidence,
    directionBias,
    physicsBoost: Math.min(1.3, Math.max(0.7, physicsBoost)),
    metrics: {
      atrRatio: compression.atrRatio,
      rangeContraction: compression.rangeContraction,
      bollingerWidth: compression.bollingerWidth,
      levelTests: pressure.levelTests,
      trendPersistence: pressure.trendPersistence,
      volumeProfile: release.volumeProfile,
    },
  };
}
