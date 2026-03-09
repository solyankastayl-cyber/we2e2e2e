/**
 * P1.2 — Geometry Engine Types (COMMIT 1)
 * 
 * Unified contract for pattern geometry analysis
 */

export type GeometryFamily =
  | 'TRIANGLE'
  | 'CHANNEL'
  | 'FLAG'
  | 'REVERSAL_CLASSIC'
  | 'HARMONIC'
  | 'UNKNOWN';

export interface GeometryPack {
  family: GeometryFamily;
  type: string;              // pattern type
  tf: string;                // timeframe
  fitError: number;          // 0..1 (lower is better)
  maturity: number;          // 0..1 (closer to 1 = near trigger/apex)
  breakoutEnergy?: number;   // breakout_range / ATR
  
  // Universal metrics
  durationBars: number;
  heightATR: number;
  
  // Family-specific (partial filling is normal)
  triangle?: TriangleGeometry;
  channel?: ChannelGeometry;
  flag?: FlagGeometry;
  reversal?: ReversalGeometry;
  harmonic?: HarmonicGeometry;
}

export interface TriangleGeometry {
  slopeHigh: number;           // slope of upper trendline
  slopeLow: number;            // slope of lower trendline
  convergenceRate: number;     // how fast lines converge
  apexDistanceBars: number;    // bars until apex
  touchesHigh: number;         // touches on upper line
  touchesLow: number;          // touches on lower line
  compression: number;         // std(range)/ATR (lower = more compressed)
}

export interface ChannelGeometry {
  slopeMid: number;            // slope of midline
  widthATR: number;            // channel width in ATR units
  parallelismError: number;    // 0..1, how parallel are the lines
  touches: number;             // total touches on both boundaries
}

export interface FlagGeometry {
  poleATR: number;             // pole height in ATR
  retracePct: number;          // retracement as % of pole
  channelWidthATR: number;     // flag channel width
  consolidationCompression: number; // compression within flag
}

export interface ReversalGeometry {
  symmetryTimeRatio: number;   // left/right duration ratio (~1 is symmetric)
  necklineSlope: number;       // slope of neckline
  heightATR: number;           // pattern height
}

export interface HarmonicGeometry {
  ratioAB_XA: number;          // AB leg vs XA
  ratioBC_AB: number;          // BC leg vs AB
  ratioCD_BC: number;          // CD leg vs BC
  ratioAD_XA: number;          // AD span vs XA
  ratioError: number;          // deviation from ideal ratios (0..1)
}

export interface GeometryInput {
  patternType: string;
  timeframe: string;
  direction: 'LONG' | 'SHORT' | 'BOTH';
  
  // Price levels
  pivotHighs: number[];
  pivotLows: number[];
  pivotHighIdxs: number[];
  pivotLowIdxs: number[];
  
  // Context
  atr: number;
  price: number;
  
  // Pattern bounds
  startIdx: number;
  endIdx: number;
  
  // Optional pre-computed lines
  lineHigh?: { slope: number; intercept: number };
  lineLow?: { slope: number; intercept: number };
  
  // For flags
  poleStart?: number;
  poleEnd?: number;
  
  // For harmonics
  pointX?: number;
  pointA?: number;
  pointB?: number;
  pointC?: number;
  pointD?: number;
}

/**
 * Map pattern types to geometry families
 */
export function getGeometryFamily(patternType: string): GeometryFamily {
  const upper = patternType.toUpperCase();
  
  // Triangles
  if (upper.includes('TRIANGLE') || upper.includes('WEDGE') || upper.includes('PENNANT')) {
    return 'TRIANGLE';
  }
  
  // Channels
  if (upper.includes('CHANNEL') || upper.includes('RECTANGLE') || upper.includes('RANGE')) {
    return 'CHANNEL';
  }
  
  // Flags
  if (upper.includes('FLAG') && !upper.includes('PENNANT')) {
    return 'FLAG';
  }
  
  // Reversals
  if (upper.includes('HEAD') || upper.includes('SHOULDER') || 
      upper.includes('DOUBLE') || upper.includes('TRIPLE') ||
      upper.includes('ROUNDING')) {
    return 'REVERSAL_CLASSIC';
  }
  
  // Harmonics
  if (upper.includes('GARTLEY') || upper.includes('BAT') || 
      upper.includes('BUTTERFLY') || upper.includes('CRAB') ||
      upper.includes('SHARK') || upper.includes('CYPHER') ||
      upper.includes('ABCD') || upper.includes('THREE_DRIVE')) {
    return 'HARMONIC';
  }
  
  return 'UNKNOWN';
}
