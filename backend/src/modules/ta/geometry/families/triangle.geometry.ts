/**
 * P1.2 — Triangle/Wedge Geometry (COMMIT 2)
 * 
 * Computes geometry features for triangles and wedges:
 * - slopeHigh, slopeLow
 * - convergenceRate
 * - touchesHigh, touchesLow
 * - apexDistanceBars
 * - compression
 * - fitError
 */

import { GeometryInput, TriangleGeometry } from './geometry.types.js';

interface LineParams {
  slope: number;
  intercept: number;
}

/**
 * Fit a line using simple linear regression
 */
function fitLine(xs: number[], ys: number[]): LineParams {
  if (xs.length < 2) {
    return { slope: 0, intercept: ys[0] || 0 };
  }

  const n = xs.length;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;

  for (let i = 0; i < n; i++) {
    sumX += xs[i];
    sumY += ys[i];
    sumXY += xs[i] * ys[i];
    sumX2 += xs[i] * xs[i];
  }

  const denominator = n * sumX2 - sumX * sumX;
  if (Math.abs(denominator) < 1e-10) {
    return { slope: 0, intercept: sumY / n };
  }

  const slope = (n * sumXY - sumX * sumY) / denominator;
  const intercept = (sumY - slope * sumX) / n;

  return { slope, intercept };
}

/**
 * Calculate mean absolute error of points from line
 */
function lineFitError(xs: number[], ys: number[], line: LineParams): number {
  if (xs.length === 0) return 0;
  
  let totalError = 0;
  for (let i = 0; i < xs.length; i++) {
    const predicted = line.slope * xs[i] + line.intercept;
    totalError += Math.abs(ys[i] - predicted);
  }
  return totalError / xs.length;
}

/**
 * Count touches within tolerance of line
 */
function countTouches(xs: number[], ys: number[], line: LineParams, tolerance: number): number {
  let count = 0;
  for (let i = 0; i < xs.length; i++) {
    const predicted = line.slope * xs[i] + line.intercept;
    if (Math.abs(ys[i] - predicted) <= tolerance) {
      count++;
    }
  }
  return count;
}

/**
 * Calculate standard deviation of values
 */
function stdDev(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const squaredDiffs = values.map(v => Math.pow(v - mean, 2));
  return Math.sqrt(squaredDiffs.reduce((a, b) => a + b, 0) / values.length);
}

/**
 * Compute triangle geometry
 */
export function computeTriangleGeometry(input: GeometryInput): TriangleGeometry | null {
  const { pivotHighs, pivotLows, pivotHighIdxs, pivotLowIdxs, atr, startIdx, endIdx } = input;

  // Need at least 2 points for each line
  if (pivotHighs.length < 2 || pivotLows.length < 2) {
    return null;
  }

  // Fit upper trendline (highs)
  let lineHigh: LineParams;
  if (input.lineHigh) {
    lineHigh = input.lineHigh;
  } else {
    lineHigh = fitLine(pivotHighIdxs, pivotHighs);
  }

  // Fit lower trendline (lows)  
  let lineLow: LineParams;
  if (input.lineLow) {
    lineLow = input.lineLow;
  } else {
    lineLow = fitLine(pivotLowIdxs, pivotLows);
  }

  // Normalize slopes by price
  const avgPrice = (pivotHighs.reduce((a, b) => a + b, 0) / pivotHighs.length +
                   pivotLows.reduce((a, b) => a + b, 0) / pivotLows.length) / 2;
  
  const slopeHigh = avgPrice > 0 ? lineHigh.slope / avgPrice : lineHigh.slope;
  const slopeLow = avgPrice > 0 ? lineLow.slope / avgPrice : lineLow.slope;

  // Convergence rate (difference in slopes)
  const convergenceRate = Math.abs(slopeHigh - slopeLow);

  // Calculate apex point (where lines meet)
  const slopeDiff = lineLow.slope - lineHigh.slope;
  let apexIdx: number;
  if (Math.abs(slopeDiff) < 1e-10) {
    // Lines are parallel, no apex
    apexIdx = endIdx + 100;  // Far in future
  } else {
    apexIdx = (lineHigh.intercept - lineLow.intercept) / slopeDiff;
  }
  const apexDistanceBars = Math.max(0, apexIdx - endIdx);

  // Tolerance for touch counting (0.5% of price or 0.2 ATR)
  const tolerance = Math.min(avgPrice * 0.005, atr * 0.2);

  // Count touches
  const touchesHigh = countTouches(pivotHighIdxs, pivotHighs, lineHigh, tolerance);
  const touchesLow = countTouches(pivotLowIdxs, pivotLows, lineLow, tolerance);

  // Calculate compression (range variability in recent bars)
  // Use all pivots to estimate recent ranges
  const allPrices = [...pivotHighs, ...pivotLows].sort((a, b) => a - b);
  const ranges: number[] = [];
  for (let i = 0; i < Math.min(pivotHighs.length, pivotLows.length); i++) {
    const rangeVal = pivotHighs[i] - pivotLows[i];
    if (rangeVal > 0) ranges.push(rangeVal);
  }
  const compression = ranges.length > 0 && atr > 0 ? stdDev(ranges) / atr : 1;

  // Fit error (normalized by ATR)
  const errorHigh = lineFitError(pivotHighIdxs, pivotHighs, lineHigh);
  const errorLow = lineFitError(pivotLowIdxs, pivotLows, lineLow);
  const avgFitError = atr > 0 ? (errorHigh + errorLow) / (2 * atr) : 0;

  return {
    slopeHigh,
    slopeLow,
    convergenceRate,
    apexDistanceBars,
    touchesHigh,
    touchesLow,
    compression: Math.min(compression, 3),  // Cap at 3
  };
}

/**
 * Calculate maturity for triangle patterns
 * Higher when closer to apex
 */
export function triangleMaturity(geom: TriangleGeometry, durationBars: number): number {
  if (durationBars <= 0) return 0.5;
  
  // Maturity based on apex proximity
  const apexFactor = 1 - Math.min(geom.apexDistanceBars / (durationBars * 1.5), 1);
  
  // Bonus for good touches
  const touchBonus = Math.min((geom.touchesHigh + geom.touchesLow) / 6, 0.3);
  
  return Math.min(apexFactor + touchBonus, 1);
}

/**
 * Calculate fit error for triangle
 */
export function triangleFitError(geom: TriangleGeometry): number {
  // Low compression is good (pattern tightening)
  // Good touch count is good
  const compressionPenalty = Math.max(0, (geom.compression - 0.5) / 2);
  const touchPenalty = Math.max(0, (6 - geom.touchesHigh - geom.touchesLow) / 10);
  
  return Math.min(compressionPenalty + touchPenalty, 1);
}
