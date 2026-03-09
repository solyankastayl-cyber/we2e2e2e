/**
 * Phase 6 — Volume Profile Service
 * ==================================
 * Volume at price analysis
 */

import { VolumeProfileResult, VolumeProfileLevel } from './indicators.types.js';

// ═══════════════════════════════════════════════════════════════
// VOLUME PROFILE CALCULATION
// ═══════════════════════════════════════════════════════════════

interface OHLCV {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * Build volume profile from OHLCV data
 */
export function buildVolumeProfile(
  candles: OHLCV[],
  numLevels: number = 50
): VolumeProfileResult {
  if (candles.length === 0) {
    return {
      poc: 0, vah: 0, val: 0, valueAreaVolume: 0,
      levels: [], hvn: [], lvn: [],
      currentPricePosition: 'IN_VA',
      support: [], resistance: [],
    };
  }
  
  // Find price range
  let minPrice = Infinity;
  let maxPrice = -Infinity;
  
  for (const c of candles) {
    if (c.low < minPrice) minPrice = c.low;
    if (c.high > maxPrice) maxPrice = c.high;
  }
  
  const priceRange = maxPrice - minPrice;
  const levelSize = priceRange / numLevels;
  
  // Initialize volume buckets
  const volumeByLevel: number[] = new Array(numLevels).fill(0);
  
  // Distribute volume across price levels
  for (const c of candles) {
    const candleRange = c.high - c.low;
    if (candleRange === 0) continue;
    
    // Distribute volume proportionally
    for (let i = 0; i < numLevels; i++) {
      const levelLow = minPrice + i * levelSize;
      const levelHigh = levelLow + levelSize;
      
      // Calculate overlap
      const overlapLow = Math.max(c.low, levelLow);
      const overlapHigh = Math.min(c.high, levelHigh);
      
      if (overlapHigh > overlapLow) {
        const overlap = (overlapHigh - overlapLow) / candleRange;
        volumeByLevel[i] += c.volume * overlap;
      }
    }
  }
  
  // Calculate total volume
  const totalVolume = volumeByLevel.reduce((a, b) => a + b, 0);
  
  // Find POC (Point of Control)
  let pocIndex = 0;
  let maxVolume = 0;
  for (let i = 0; i < numLevels; i++) {
    if (volumeByLevel[i] > maxVolume) {
      maxVolume = volumeByLevel[i];
      pocIndex = i;
    }
  }
  const poc = minPrice + (pocIndex + 0.5) * levelSize;
  
  // Calculate Value Area (70% of volume)
  const valueAreaTarget = totalVolume * 0.7;
  let valueAreaVolume = volumeByLevel[pocIndex];
  let vaLowIndex = pocIndex;
  let vaHighIndex = pocIndex;
  
  while (valueAreaVolume < valueAreaTarget && (vaLowIndex > 0 || vaHighIndex < numLevels - 1)) {
    const addLow = vaLowIndex > 0 ? volumeByLevel[vaLowIndex - 1] : 0;
    const addHigh = vaHighIndex < numLevels - 1 ? volumeByLevel[vaHighIndex + 1] : 0;
    
    if (addLow >= addHigh && vaLowIndex > 0) {
      vaLowIndex--;
      valueAreaVolume += addLow;
    } else if (vaHighIndex < numLevels - 1) {
      vaHighIndex++;
      valueAreaVolume += addHigh;
    } else {
      break;
    }
  }
  
  const val = minPrice + vaLowIndex * levelSize;
  const vah = minPrice + (vaHighIndex + 1) * levelSize;
  
  // Build levels array
  const avgVolume = totalVolume / numLevels;
  const levels: VolumeProfileLevel[] = [];
  const hvn: number[] = [];
  const lvn: number[] = [];
  
  for (let i = 0; i < numLevels; i++) {
    const price = minPrice + (i + 0.5) * levelSize;
    const volume = volumeByLevel[i];
    const percentage = totalVolume > 0 ? volume / totalVolume : 0;
    
    let type: VolumeProfileLevel['type'];
    if (i === pocIndex) {
      type = 'POC';
    } else if (i === vaHighIndex) {
      type = 'VAH';
    } else if (i === vaLowIndex) {
      type = 'VAL';
    } else if (volume > avgVolume * 1.5) {
      type = 'HVN';
      hvn.push(Math.round(price * 100) / 100);
    } else if (volume < avgVolume * 0.5) {
      type = 'LVN';
      lvn.push(Math.round(price * 100) / 100);
    } else {
      type = 'NORMAL';
    }
    
    levels.push({
      price: Math.round(price * 100) / 100,
      volume: Math.round(volume * 100) / 100,
      percentage: Math.round(percentage * 10000) / 10000,
      type,
    });
  }
  
  // Current price position
  const currentPrice = candles[candles.length - 1].close;
  let currentPricePosition: VolumeProfileResult['currentPricePosition'];
  if (Math.abs(currentPrice - poc) < levelSize) {
    currentPricePosition = 'AT_POC';
  } else if (currentPrice > vah) {
    currentPricePosition = 'ABOVE_VA';
  } else if (currentPrice < val) {
    currentPricePosition = 'BELOW_VA';
  } else {
    currentPricePosition = 'IN_VA';
  }
  
  // Volume-based support/resistance
  const support = hvn.filter(p => p < currentPrice).slice(-3);
  const resistance = hvn.filter(p => p > currentPrice).slice(0, 3);
  
  return {
    poc: Math.round(poc * 100) / 100,
    vah: Math.round(vah * 100) / 100,
    val: Math.round(val * 100) / 100,
    valueAreaVolume: Math.round((valueAreaVolume / totalVolume) * 10000) / 10000,
    levels,
    hvn,
    lvn,
    currentPricePosition,
    support,
    resistance,
  };
}

/**
 * Generate mock volume profile for testing
 */
export function getMockVolumeProfile(
  currentPrice: number,
  range: number = 0.1
): VolumeProfileResult {
  const minPrice = currentPrice * (1 - range);
  const maxPrice = currentPrice * (1 + range);
  const priceRange = maxPrice - minPrice;
  
  // Generate mock levels
  const numLevels = 20;
  const levelSize = priceRange / numLevels;
  const levels: VolumeProfileLevel[] = [];
  const hvn: number[] = [];
  const lvn: number[] = [];
  
  // POC near current price
  const pocIndex = Math.floor(numLevels / 2) + Math.floor(Math.random() * 3) - 1;
  const poc = minPrice + (pocIndex + 0.5) * levelSize;
  
  // Value Area around POC
  const vaLowIndex = Math.max(0, pocIndex - 3);
  const vaHighIndex = Math.min(numLevels - 1, pocIndex + 3);
  const val = minPrice + vaLowIndex * levelSize;
  const vah = minPrice + (vaHighIndex + 1) * levelSize;
  
  for (let i = 0; i < numLevels; i++) {
    const price = minPrice + (i + 0.5) * levelSize;
    
    // Volume peaks at POC, decreases away from it
    const distFromPoc = Math.abs(i - pocIndex);
    const baseVolume = 1000000 * Math.exp(-distFromPoc * 0.3);
    const volume = baseVolume * (0.8 + Math.random() * 0.4);
    
    let type: VolumeProfileLevel['type'];
    if (i === pocIndex) {
      type = 'POC';
    } else if (i === vaHighIndex) {
      type = 'VAH';
    } else if (i === vaLowIndex) {
      type = 'VAL';
    } else if (volume > 800000) {
      type = 'HVN';
      hvn.push(Math.round(price * 100) / 100);
    } else if (volume < 200000) {
      type = 'LVN';
      lvn.push(Math.round(price * 100) / 100);
    } else {
      type = 'NORMAL';
    }
    
    levels.push({
      price: Math.round(price * 100) / 100,
      volume: Math.round(volume),
      percentage: Math.round((volume / 10000000) * 10000) / 10000,
      type,
    });
  }
  
  // Current price position
  let currentPricePosition: VolumeProfileResult['currentPricePosition'];
  if (Math.abs(currentPrice - poc) < levelSize) {
    currentPricePosition = 'AT_POC';
  } else if (currentPrice > vah) {
    currentPricePosition = 'ABOVE_VA';
  } else if (currentPrice < val) {
    currentPricePosition = 'BELOW_VA';
  } else {
    currentPricePosition = 'IN_VA';
  }
  
  return {
    poc: Math.round(poc * 100) / 100,
    vah: Math.round(vah * 100) / 100,
    val: Math.round(val * 100) / 100,
    valueAreaVolume: 0.7,
    levels,
    hvn,
    lvn,
    currentPricePosition,
    support: hvn.filter(p => p < currentPrice).slice(-3),
    resistance: hvn.filter(p => p > currentPrice).slice(0, 3),
  };
}

/**
 * Calculate volume profile boost for decision engine
 */
export function getVolumeProfileBoost(profile: VolumeProfileResult, side: 'LONG' | 'SHORT'): number {
  let boost = 1.0;
  
  // Position relative to value area
  if (profile.currentPricePosition === 'AT_POC') {
    // At POC - neutral, wait for direction
    boost *= 0.95;
  } else if (profile.currentPricePosition === 'BELOW_VA' && side === 'LONG') {
    // Below value area, going long - potential reversal to mean
    boost *= 1.1;
  } else if (profile.currentPricePosition === 'ABOVE_VA' && side === 'SHORT') {
    // Above value area, going short - potential reversal to mean
    boost *= 1.1;
  } else if (profile.currentPricePosition === 'ABOVE_VA' && side === 'LONG') {
    // Breakout above VA, going long - momentum play
    boost *= 1.05;
  } else if (profile.currentPricePosition === 'BELOW_VA' && side === 'SHORT') {
    // Breakdown below VA, going short - momentum play
    boost *= 1.05;
  }
  
  // LVN ahead = potential fast move through
  if (profile.lvn.length > 3) {
    boost *= 1.05;
  }
  
  return Math.round(Math.max(0.8, Math.min(1.2, boost)) * 100) / 100;
}
