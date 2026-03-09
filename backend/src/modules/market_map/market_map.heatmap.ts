/**
 * Phase 2.5 — Market Map Heatmap
 * ================================
 * Generates probability heatmap for price levels
 * Shows where price is likely to be in the future
 */

import { HeatmapResponse, HeatmapLevel } from './market_map.types.js';

// ═══════════════════════════════════════════════════════════════
// BASE PRICES
// ═══════════════════════════════════════════════════════════════

const BASE_PRICES: Record<string, number> = {
  BTCUSDT: 87000,
  ETHUSDT: 3200,
  SOLUSDT: 145,
  BNBUSDT: 620,
  XRPUSDT: 0.52,
  ADAUSDT: 0.45,
};

// ═══════════════════════════════════════════════════════════════
// LEVEL TYPE DETECTION
// ═══════════════════════════════════════════════════════════════

type LevelType = 'support' | 'resistance' | 'magnet' | 'neutral';

/**
 * Determine level type based on position relative to current price
 */
function determineLevelType(
  levelPrice: number,
  currentPrice: number,
  probability: number
): LevelType {
  const diff = levelPrice - currentPrice;
  const diffPct = diff / currentPrice;
  
  if (probability > 0.4) {
    return 'magnet';  // High probability = price magnet
  }
  
  if (diffPct < -0.02) {
    return 'support';
  }
  
  if (diffPct > 0.02) {
    return 'resistance';
  }
  
  return 'neutral';
}

// ═══════════════════════════════════════════════════════════════
// PROBABILITY DISTRIBUTION
// ═══════════════════════════════════════════════════════════════

/**
 * Generate gaussian probability distribution
 */
function gaussianProbability(x: number, mean: number, stdDev: number): number {
  const coefficient = 1 / (stdDev * Math.sqrt(2 * Math.PI));
  const exponent = -Math.pow(x - mean, 2) / (2 * Math.pow(stdDev, 2));
  return coefficient * Math.exp(exponent);
}

/**
 * Generate bimodal distribution (for breakout scenarios)
 */
function bimodalProbability(
  x: number,
  mean: number,
  stdDev: number,
  bullishBias: number = 0
): number {
  // Two peaks: one above and one below current price
  const upperMean = mean * (1.05 + bullishBias * 0.03);
  const lowerMean = mean * (0.95 - bullishBias * 0.03);
  
  const upperProb = gaussianProbability(x, upperMean, stdDev) * (0.5 + bullishBias * 0.2);
  const lowerProb = gaussianProbability(x, lowerMean, stdDev) * (0.5 - bullishBias * 0.2);
  
  return upperProb + lowerProb;
}

// ═══════════════════════════════════════════════════════════════
// HEATMAP GENERATION
// ═══════════════════════════════════════════════════════════════

/**
 * Generate price probability heatmap
 */
export async function getHeatmap(
  symbol: string,
  timeframe: string = '1d',
  numLevels: number = 10,
  rangePercent: number = 0.15
): Promise<HeatmapResponse> {
  const currentPrice = BASE_PRICES[symbol] || 100;
  
  // Define price range
  const minPrice = currentPrice * (1 - rangePercent);
  const maxPrice = currentPrice * (1 + rangePercent);
  const stepSize = (maxPrice - minPrice) / (numLevels - 1);
  
  // Standard deviation (2% of price for typical volatility)
  const stdDev = currentPrice * 0.02;
  
  // Bullish bias based on time (for demo)
  const hour = new Date().getHours();
  const bullishBias = Math.sin(hour * Math.PI / 12) * 0.3;  // -0.3 to 0.3
  
  // Generate levels
  const levels: HeatmapLevel[] = [];
  let totalProb = 0;
  const rawProbs: number[] = [];
  
  // First pass: calculate raw probabilities
  for (let i = 0; i < numLevels; i++) {
    const price = minPrice + i * stepSize;
    const prob = bimodalProbability(price, currentPrice, stdDev * 2, bullishBias);
    rawProbs.push(prob);
    totalProb += prob;
  }
  
  // Second pass: normalize and create levels
  for (let i = 0; i < numLevels; i++) {
    const price = Math.round((minPrice + i * stepSize) * 100) / 100;
    const probability = Math.round((rawProbs[i] / totalProb) * 100) / 100;
    const type = determineLevelType(price, currentPrice, probability);
    
    levels.push({
      price,
      probability,
      type,
    });
  }
  
  // Sort by probability descending
  levels.sort((a, b) => b.probability - a.probability);
  
  // Calculate price range stats
  const mean = currentPrice;
  const normalizedStdDev = stdDev;
  
  return {
    symbol,
    timeframe,
    ts: Date.now(),
    levels,
    priceRange: {
      min: Math.round(minPrice * 100) / 100,
      max: Math.round(maxPrice * 100) / 100,
      mean: Math.round(mean * 100) / 100,
      stdDev: Math.round(normalizedStdDev * 100) / 100,
    },
  };
}

/**
 * Get heatmap for specific price range
 */
export async function getHeatmapInRange(
  symbol: string,
  timeframe: string,
  minPrice: number,
  maxPrice: number,
  numLevels: number = 10
): Promise<HeatmapResponse> {
  const currentPrice = BASE_PRICES[symbol] || ((minPrice + maxPrice) / 2);
  const stepSize = (maxPrice - minPrice) / (numLevels - 1);
  const stdDev = currentPrice * 0.02;
  
  const levels: HeatmapLevel[] = [];
  let totalProb = 0;
  const rawProbs: number[] = [];
  
  for (let i = 0; i < numLevels; i++) {
    const price = minPrice + i * stepSize;
    const prob = gaussianProbability(price, currentPrice, stdDev * 3);
    rawProbs.push(prob);
    totalProb += prob;
  }
  
  for (let i = 0; i < numLevels; i++) {
    const price = Math.round((minPrice + i * stepSize) * 100) / 100;
    const probability = Math.round((rawProbs[i] / totalProb) * 100) / 100;
    const type = determineLevelType(price, currentPrice, probability);
    
    levels.push({ price, probability, type });
  }
  
  levels.sort((a, b) => b.probability - a.probability);
  
  return {
    symbol,
    timeframe,
    ts: Date.now(),
    levels,
    priceRange: {
      min: minPrice,
      max: maxPrice,
      mean: currentPrice,
      stdDev: Math.round(stdDev * 100) / 100,
    },
  };
}
