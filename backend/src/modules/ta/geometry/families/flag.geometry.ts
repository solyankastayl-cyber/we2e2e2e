/**
 * P1.2 — Flag/Pennant Geometry (COMMIT 4)
 */

import { GeometryInput, FlagGeometry } from './geometry.types.js';

function stdDev(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  return Math.sqrt(values.map(v => Math.pow(v - mean, 2)).reduce((a, b) => a + b, 0) / values.length);
}

/**
 * Compute flag/pennant geometry
 */
export function computeFlagGeometry(input: GeometryInput): FlagGeometry | null {
  const { pivotHighs, pivotLows, atr, poleStart, poleEnd } = input;
  
  if (!poleStart || !poleEnd || pivotHighs.length < 2 || pivotLows.length < 2) {
    return null;
  }

  // Pole height
  const poleHeight = Math.abs(poleEnd - poleStart);
  const poleATR = atr > 0 ? poleHeight / atr : 0;

  // Flag bounds
  const flagHigh = Math.max(...pivotHighs);
  const flagLow = Math.min(...pivotLows);
  const flagWidth = flagHigh - flagLow;
  const channelWidthATR = atr > 0 ? flagWidth / atr : 0;

  // Retracement
  const retrace = input.direction === 'LONG' 
    ? (poleEnd - flagLow) 
    : (flagHigh - poleEnd);
  const retracePct = poleHeight > 0 ? retrace / poleHeight : 0;

  // Consolidation compression
  const ranges: number[] = [];
  for (let i = 0; i < Math.min(pivotHighs.length, pivotLows.length); i++) {
    ranges.push(pivotHighs[i] - pivotLows[i]);
  }
  const consolidationCompression = ranges.length > 0 && atr > 0 ? stdDev(ranges) / atr : 1;

  return {
    poleATR,
    retracePct,
    channelWidthATR,
    consolidationCompression: Math.min(consolidationCompression, 3),
  };
}

export function flagMaturity(geom: FlagGeometry, consolidationBars: number): number {
  // Flags tend to break out after 5-20 bars of consolidation
  const idealBars = 12;
  const barsFactor = 1 - Math.abs(consolidationBars - idealBars) / 20;
  
  // Good compression increases maturity
  const compressionBonus = Math.max(0, (1 - geom.consolidationCompression) * 0.2);
  
  return Math.min(Math.max(barsFactor + compressionBonus, 0), 1);
}

export function flagFitError(geom: FlagGeometry): number {
  // Valid flag: pole >= 3 ATR, retrace <= 55%
  const polePenalty = geom.poleATR < 3 ? (3 - geom.poleATR) / 5 : 0;
  const retracePenalty = geom.retracePct > 0.55 ? (geom.retracePct - 0.55) * 2 : 0;
  
  return Math.min(polePenalty + retracePenalty, 1);
}
