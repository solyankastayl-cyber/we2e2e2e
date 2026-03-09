/**
 * P1.2 — Reversal Classics Geometry (COMMIT 5)
 * Double/Triple Top/Bottom, Head & Shoulders
 */

import { GeometryInput, ReversalGeometry } from './geometry.types.js';

/**
 * Compute reversal pattern geometry
 */
export function computeReversalGeometry(input: GeometryInput): ReversalGeometry | null {
  const { pivotHighs, pivotLows, pivotHighIdxs, pivotLowIdxs, atr, patternType } = input;
  
  const upper = patternType.toUpperCase();
  const isHeadShoulders = upper.includes('HEAD') || upper.includes('SHOULDER');
  const isDouble = upper.includes('DOUBLE');
  const isTriple = upper.includes('TRIPLE');

  if (isHeadShoulders) {
    return computeHSGeometry(input);
  } else if (isDouble || isTriple) {
    return computeDoubleTripleGeometry(input);
  }

  return null;
}

function computeHSGeometry(input: GeometryInput): ReversalGeometry | null {
  const { pivotHighs, pivotLows, pivotHighIdxs, pivotLowIdxs, atr } = input;
  
  // H&S needs at least 3 highs (LS, H, RS) and 2 lows (neckline points)
  if (pivotHighs.length < 3 || pivotLows.length < 2) return null;

  // Identify head (highest) and shoulders
  const headIdx = pivotHighs.indexOf(Math.max(...pivotHighs));
  
  // Left shoulder duration
  const leftDuration = headIdx > 0 ? pivotHighIdxs[headIdx] - pivotHighIdxs[0] : 0;
  
  // Right shoulder duration  
  const rightDuration = headIdx < pivotHighs.length - 1 
    ? pivotHighIdxs[pivotHighIdxs.length - 1] - pivotHighIdxs[headIdx]
    : 0;

  // Symmetry ratio
  const symmetryTimeRatio = rightDuration > 0 ? leftDuration / rightDuration : 1;

  // Neckline slope
  let necklineSlope = 0;
  if (pivotLows.length >= 2 && pivotLowIdxs.length >= 2) {
    const dx = pivotLowIdxs[pivotLowIdxs.length - 1] - pivotLowIdxs[0];
    const dy = pivotLows[pivotLows.length - 1] - pivotLows[0];
    if (dx > 0) {
      const avgPrice = pivotLows.reduce((a, b) => a + b, 0) / pivotLows.length;
      necklineSlope = avgPrice > 0 ? dy / dx / avgPrice : 0;
    }
  }

  // Pattern height
  const head = Math.max(...pivotHighs);
  const neckline = Math.min(...pivotLows);
  const heightATR = atr > 0 ? (head - neckline) / atr : 0;

  return {
    symmetryTimeRatio,
    necklineSlope,
    heightATR,
  };
}

function computeDoubleTripleGeometry(input: GeometryInput): ReversalGeometry | null {
  const { pivotHighs, pivotLows, pivotHighIdxs, pivotLowIdxs, atr, patternType } = input;
  
  const isTop = patternType.toUpperCase().includes('TOP');
  const peaks = isTop ? pivotHighs : pivotLows;
  const peakIdxs = isTop ? pivotHighIdxs : pivotLowIdxs;

  if (peaks.length < 2) return null;

  // Time between first and last peak
  const leftDuration = peakIdxs.length >= 2 
    ? peakIdxs[Math.floor(peakIdxs.length / 2)] - peakIdxs[0]
    : 0;
  const rightDuration = peakIdxs.length >= 2
    ? peakIdxs[peakIdxs.length - 1] - peakIdxs[Math.floor(peakIdxs.length / 2)]
    : 0;

  const symmetryTimeRatio = rightDuration > 0 ? leftDuration / rightDuration : 1;

  // Neckline
  const necklinePeaks = isTop ? pivotLows : pivotHighs;
  const necklineIdxs = isTop ? pivotLowIdxs : pivotHighIdxs;
  
  let necklineSlope = 0;
  if (necklinePeaks.length >= 2) {
    const dx = necklineIdxs[necklineIdxs.length - 1] - necklineIdxs[0];
    const dy = necklinePeaks[necklinePeaks.length - 1] - necklinePeaks[0];
    const avgPrice = necklinePeaks.reduce((a, b) => a + b, 0) / necklinePeaks.length;
    if (dx > 0 && avgPrice > 0) necklineSlope = dy / dx / avgPrice;
  }

  // Height
  const peakLevel = isTop ? Math.max(...peaks) : Math.min(...peaks);
  const necklineLevel = isTop ? Math.min(...necklinePeaks) : Math.max(...necklinePeaks);
  const heightATR = atr > 0 ? Math.abs(peakLevel - necklineLevel) / atr : 0;

  return {
    symmetryTimeRatio,
    necklineSlope,
    heightATR,
  };
}

export function reversalMaturity(geom: ReversalGeometry, price: number, necklineLevel: number): number {
  // Higher maturity when closer to neckline break
  const distToNeckline = Math.abs(price - necklineLevel);
  const height = geom.heightATR;
  
  if (height <= 0) return 0.5;
  
  const proximityFactor = 1 - Math.min(distToNeckline / height, 1);
  return Math.min(proximityFactor, 1);
}

export function reversalFitError(geom: ReversalGeometry): number {
  // Good reversal: symmetric (ratio ~1), adequate height
  const symmetryPenalty = Math.abs(geom.symmetryTimeRatio - 1) / 2;
  const heightPenalty = geom.heightATR < 2 ? (2 - geom.heightATR) / 4 : 0;
  
  return Math.min(symmetryPenalty + heightPenalty, 1);
}
