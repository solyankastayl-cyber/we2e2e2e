/**
 * P1.2 — Channel Geometry (COMMIT 3)
 */

import { GeometryInput, ChannelGeometry } from './geometry.types.js';

interface LineParams {
  slope: number;
  intercept: number;
}

function fitLine(xs: number[], ys: number[]): LineParams {
  if (xs.length < 2) return { slope: 0, intercept: ys[0] || 0 };
  
  const n = xs.length;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
  for (let i = 0; i < n; i++) {
    sumX += xs[i]; sumY += ys[i]; sumXY += xs[i] * ys[i]; sumX2 += xs[i] * xs[i];
  }
  const denom = n * sumX2 - sumX * sumX;
  if (Math.abs(denom) < 1e-10) return { slope: 0, intercept: sumY / n };
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

function lineFitError(xs: number[], ys: number[], line: LineParams): number {
  if (xs.length === 0) return 0;
  let err = 0;
  for (let i = 0; i < xs.length; i++) {
    err += Math.abs(ys[i] - (line.slope * xs[i] + line.intercept));
  }
  return err / xs.length;
}

function countTouches(xs: number[], ys: number[], line: LineParams, tol: number): number {
  let count = 0;
  for (let i = 0; i < xs.length; i++) {
    if (Math.abs(ys[i] - (line.slope * xs[i] + line.intercept)) <= tol) count++;
  }
  return count;
}

/**
 * Compute channel geometry
 */
export function computeChannelGeometry(input: GeometryInput): ChannelGeometry | null {
  const { pivotHighs, pivotLows, pivotHighIdxs, pivotLowIdxs, atr } = input;
  
  if (pivotHighs.length < 2 || pivotLows.length < 2) return null;

  // Fit lines
  const lineHigh = input.lineHigh || fitLine(pivotHighIdxs, pivotHighs);
  const lineLow = input.lineLow || fitLine(pivotLowIdxs, pivotLows);

  // Midline slope
  const slopeMid = (lineHigh.slope + lineLow.slope) / 2;

  // Channel width (average distance between lines at pivot points)
  const midIdx = (pivotHighIdxs[0] + pivotHighIdxs[pivotHighIdxs.length - 1]) / 2;
  const highAtMid = lineHigh.slope * midIdx + lineHigh.intercept;
  const lowAtMid = lineLow.slope * midIdx + lineLow.intercept;
  const width = Math.abs(highAtMid - lowAtMid);
  const widthATR = atr > 0 ? width / atr : 0;

  // Parallelism error (slope difference normalized)
  const avgPrice = (pivotHighs.reduce((a, b) => a + b, 0) / pivotHighs.length);
  const slopeDiff = Math.abs(lineHigh.slope - lineLow.slope);
  const parallelismError = avgPrice > 0 ? Math.min(slopeDiff / (avgPrice * 0.001), 1) : 0;

  // Total touches
  const tol = Math.min(avgPrice * 0.005, atr * 0.2);
  const touchesHigh = countTouches(pivotHighIdxs, pivotHighs, lineHigh, tol);
  const touchesLow = countTouches(pivotLowIdxs, pivotLows, lineLow, tol);
  const touches = touchesHigh + touchesLow;

  return {
    slopeMid,
    widthATR,
    parallelismError,
    touches,
  };
}

export function channelMaturity(geom: ChannelGeometry, price: number, lineHigh: LineParams, lineLow: LineParams, currentIdx: number): number {
  // Higher maturity when price is near channel boundary
  const highPrice = lineHigh.slope * currentIdx + lineHigh.intercept;
  const lowPrice = lineLow.slope * currentIdx + lineLow.intercept;
  const width = highPrice - lowPrice;
  
  if (width <= 0) return 0.5;
  
  const distToHigh = Math.abs(price - highPrice) / width;
  const distToLow = Math.abs(price - lowPrice) / width;
  const minDist = Math.min(distToHigh, distToLow);
  
  return Math.max(0, 1 - minDist * 2);
}

export function channelFitError(geom: ChannelGeometry): number {
  // Good channel: parallel (low error), good touches
  const parallelPenalty = geom.parallelismError;
  const touchPenalty = Math.max(0, (4 - geom.touches) / 8);
  return Math.min(parallelPenalty + touchPenalty, 1);
}
