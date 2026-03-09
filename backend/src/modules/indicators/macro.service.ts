/**
 * Phase 6 — Macro Service
 * ========================
 * Fear & Greed, BTC Dominance, Alt Dominance
 */

import { MacroData, MacroBoost } from './indicators.types.js';

// ═══════════════════════════════════════════════════════════════
// MOCK MACRO DATA (would come from external APIs in production)
// ═══════════════════════════════════════════════════════════════

/**
 * Get current macro data
 */
export function getMacroData(): MacroData {
  // Simulate realistic values with some randomness
  const baseFG = 55;
  const baseBTCD = 52;
  const baseAltD = 38;
  
  const fgValue = Math.max(0, Math.min(100, baseFG + (Math.random() - 0.5) * 20));
  const btcdValue = Math.max(40, Math.min(65, baseBTCD + (Math.random() - 0.5) * 5));
  const altdValue = Math.max(25, Math.min(50, baseAltD + (Math.random() - 0.5) * 5));
  
  // Fear & Greed classification
  let fgClassification: MacroData['fearGreedIndex']['classification'];
  if (fgValue <= 20) fgClassification = 'EXTREME_FEAR';
  else if (fgValue <= 40) fgClassification = 'FEAR';
  else if (fgValue <= 60) fgClassification = 'NEUTRAL';
  else if (fgValue <= 80) fgClassification = 'GREED';
  else fgClassification = 'EXTREME_GREED';
  
  // BTC Dominance trend
  const btcdChange = (Math.random() - 0.5) * 3;
  let btcdTrend: 'RISING' | 'FALLING' | 'STABLE';
  if (btcdChange > 0.5) btcdTrend = 'RISING';
  else if (btcdChange < -0.5) btcdTrend = 'FALLING';
  else btcdTrend = 'STABLE';
  
  // Alt Dominance trend (usually inverse of BTC.D)
  const altdChange = -btcdChange * 0.8 + (Math.random() - 0.5);
  let altdTrend: 'RISING' | 'FALLING' | 'STABLE';
  if (altdChange > 0.5) altdTrend = 'RISING';
  else if (altdChange < -0.5) altdTrend = 'FALLING';
  else altdTrend = 'STABLE';
  
  return {
    fearGreedIndex: {
      value: Math.round(fgValue),
      classification: fgClassification,
      change24h: Math.round((Math.random() - 0.5) * 10),
    },
    btcDominance: {
      value: Math.round(btcdValue * 100) / 100,
      change7d: Math.round(btcdChange * 100) / 100,
      trend: btcdTrend,
    },
    altDominance: {
      value: Math.round(altdValue * 100) / 100,
      change7d: Math.round(altdChange * 100) / 100,
      trend: altdTrend,
    },
    totalMarketCap: 2500000000000,
    totalMarketCapChange24h: (Math.random() - 0.5) * 0.05,
  };
}

// ═══════════════════════════════════════════════════════════════
// MACRO BOOST CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate macro boost for decision engine
 */
export function calculateMacroBoost(macro: MacroData, isBTC: boolean = false): MacroBoost {
  const notes: string[] = [];
  
  // Fear & Greed Factor
  // Extreme fear = contrarian long boost
  // Extreme greed = contrarian short boost / caution
  let fearGreedFactor = 1.0;
  
  if (macro.fearGreedIndex.classification === 'EXTREME_FEAR') {
    fearGreedFactor = 1.15;
    notes.push('Extreme fear: potential reversal zone');
  } else if (macro.fearGreedIndex.classification === 'FEAR') {
    fearGreedFactor = 1.05;
    notes.push('Fear sentiment: mild bullish contrarian');
  } else if (macro.fearGreedIndex.classification === 'EXTREME_GREED') {
    fearGreedFactor = 0.85;
    notes.push('Extreme greed: caution advised');
  } else if (macro.fearGreedIndex.classification === 'GREED') {
    fearGreedFactor = 0.95;
    notes.push('Greed sentiment: mild caution');
  }
  
  // Dominance Factor
  let dominanceFactor = 1.0;
  
  if (isBTC) {
    // For BTC trades
    if (macro.btcDominance.trend === 'RISING') {
      dominanceFactor = 1.05;
      notes.push('BTC dominance rising: BTC preferred');
    } else if (macro.btcDominance.trend === 'FALLING') {
      dominanceFactor = 0.95;
      notes.push('BTC dominance falling: alts may outperform');
    }
  } else {
    // For alt trades
    if (macro.altDominance.trend === 'RISING') {
      dominanceFactor = 1.08;
      notes.push('Alt dominance rising: alt season signal');
    } else if (macro.altDominance.trend === 'FALLING') {
      dominanceFactor = 0.92;
      notes.push('Alt dominance falling: rotate to BTC');
    }
    
    // Strong alt season when BTC.D < 48
    if (macro.btcDominance.value < 48) {
      dominanceFactor *= 1.05;
      notes.push('Low BTC dominance: strong alt environment');
    }
    
    // Risk-off when BTC.D > 55
    if (macro.btcDominance.value > 55) {
      dominanceFactor *= 0.95;
      notes.push('High BTC dominance: risk-off for alts');
    }
  }
  
  // Combined boost
  const combined = fearGreedFactor * dominanceFactor;
  
  // Determine signal
  let signal: 'RISK_ON' | 'RISK_OFF' | 'NEUTRAL';
  if (combined > 1.05) signal = 'RISK_ON';
  else if (combined < 0.95) signal = 'RISK_OFF';
  else signal = 'NEUTRAL';
  
  return {
    fearGreedFactor: Math.round(fearGreedFactor * 100) / 100,
    dominanceFactor: Math.round(dominanceFactor * 100) / 100,
    combined: Math.round(Math.max(0.8, Math.min(1.2, combined)) * 100) / 100,
    signal,
    notes,
  };
}

/**
 * Get macro analysis for a symbol
 */
export function analyzeMacro(symbol: string): MacroBoost {
  const macro = getMacroData();
  const isBTC = symbol.startsWith('BTC');
  return calculateMacroBoost(macro, isBTC);
}
