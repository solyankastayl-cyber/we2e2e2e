/**
 * P1.2 — Geometry Engine (COMMIT 6)
 * 
 * Main dispatcher that computes geometry for any pattern type
 */

import {
  GeometryPack,
  GeometryInput,
  GeometryFamily,
  getGeometryFamily,
} from './geometry.types.js';

import {
  computeTriangleGeometry,
  triangleMaturity,
  triangleFitError,
} from './families/triangle.geometry.js';

import {
  computeChannelGeometry,
  channelMaturity,
  channelFitError,
} from './families/channel.geometry.js';

import {
  computeFlagGeometry,
  flagMaturity,
  flagFitError,
} from './families/flag.geometry.js';

import {
  computeReversalGeometry,
  reversalMaturity,
  reversalFitError,
} from './families/reversal.geometry.js';

import {
  computeHarmonicGeometry,
  harmonicMaturity,
  harmonicFitError,
} from './families/harmonic.geometry.js';

/**
 * Compute geometry for any pattern/scenario
 */
export function computeGeometryForScenario(input: GeometryInput): GeometryPack {
  const family = getGeometryFamily(input.patternType);
  const durationBars = input.endIdx - input.startIdx;
  
  // Base pack
  const basePack: GeometryPack = {
    family,
    type: input.patternType,
    tf: input.timeframe,
    fitError: 0.5,  // default
    maturity: 0.5,  // default
    durationBars,
    heightATR: computeHeightATR(input),
  };

  switch (family) {
    case 'TRIANGLE':
      return computeTrianglePack(input, basePack);
    
    case 'CHANNEL':
      return computeChannelPack(input, basePack);
    
    case 'FLAG':
      return computeFlagPack(input, basePack);
    
    case 'REVERSAL_CLASSIC':
      return computeReversalPack(input, basePack);
    
    case 'HARMONIC':
      return computeHarmonicPack(input, basePack);
    
    default:
      return basePack;
  }
}

function computeHeightATR(input: GeometryInput): number {
  const allPrices = [...input.pivotHighs, ...input.pivotLows];
  if (allPrices.length < 2 || input.atr <= 0) return 0;
  
  const high = Math.max(...allPrices);
  const low = Math.min(...allPrices);
  return (high - low) / input.atr;
}

function computeTrianglePack(input: GeometryInput, base: GeometryPack): GeometryPack {
  const geom = computeTriangleGeometry(input);
  if (!geom) return base;
  
  return {
    ...base,
    triangle: geom,
    fitError: triangleFitError(geom),
    maturity: triangleMaturity(geom, base.durationBars),
  };
}

function computeChannelPack(input: GeometryInput, base: GeometryPack): GeometryPack {
  const geom = computeChannelGeometry(input);
  if (!geom) return base;
  
  const lineHigh = input.lineHigh || { slope: 0, intercept: input.pivotHighs[0] || input.price };
  const lineLow = input.lineLow || { slope: 0, intercept: input.pivotLows[0] || input.price };
  
  return {
    ...base,
    channel: geom,
    fitError: channelFitError(geom),
    maturity: channelMaturity(geom, input.price, lineHigh, lineLow, input.endIdx),
  };
}

function computeFlagPack(input: GeometryInput, base: GeometryPack): GeometryPack {
  const geom = computeFlagGeometry(input);
  if (!geom) return base;
  
  const consolidationBars = input.endIdx - input.startIdx;
  
  return {
    ...base,
    flag: geom,
    fitError: flagFitError(geom),
    maturity: flagMaturity(geom, consolidationBars),
  };
}

function computeReversalPack(input: GeometryInput, base: GeometryPack): GeometryPack {
  const geom = computeReversalGeometry(input);
  if (!geom) return base;
  
  const necklineLevel = input.pivotLows.length > 0 
    ? input.pivotLows.reduce((a, b) => a + b, 0) / input.pivotLows.length
    : input.price;
  
  return {
    ...base,
    reversal: geom,
    fitError: reversalFitError(geom),
    maturity: reversalMaturity(geom, input.price, necklineLevel),
  };
}

function computeHarmonicPack(input: GeometryInput, base: GeometryPack): GeometryPack {
  const geom = computeHarmonicGeometry(input);
  if (!geom) return base;
  
  return {
    ...base,
    harmonic: geom,
    fitError: harmonicFitError(geom),
    maturity: harmonicMaturity(geom),
  };
}

/**
 * Compute geometry boost for ranking
 */
export function computeGeometryBoost(pack: GeometryPack): number {
  // Lower fitError = better
  // Higher maturity = better
  // Clamp result to [-0.10, +0.20]
  
  const fitBoost = (1 - pack.fitError) * 0.10;  // up to +0.10
  const maturityBoost = pack.maturity * 0.08;    // up to +0.08
  
  // Compression bonus for triangles
  let compressionBonus = 0;
  if (pack.triangle && pack.triangle.compression < 0.8) {
    compressionBonus = (0.8 - pack.triangle.compression) * 0.05;  // up to +0.04
  }
  
  const totalBoost = fitBoost + maturityBoost + compressionBonus - 0.09;  // center around 0
  
  return Math.max(-0.10, Math.min(0.20, totalBoost));
}

/**
 * Extract geometry features for ML dataset
 */
export function extractGeometryFeatures(pack: GeometryPack): Record<string, number> {
  const features: Record<string, number> = {
    geom_fit_error: pack.fitError,
    geom_maturity: pack.maturity,
    geom_height_atr: pack.heightATR,
    geom_duration_bars: pack.durationBars,
    geom_breakout_energy: pack.breakoutEnergy || 0,
    geom_family_triangle: pack.family === 'TRIANGLE' ? 1 : 0,
    geom_family_channel: pack.family === 'CHANNEL' ? 1 : 0,
    geom_family_flag: pack.family === 'FLAG' ? 1 : 0,
    geom_family_reversal: pack.family === 'REVERSAL_CLASSIC' ? 1 : 0,
    geom_family_harmonic: pack.family === 'HARMONIC' ? 1 : 0,
  };

  // Triangle features
  if (pack.triangle) {
    features.geom_tri_slope_high = pack.triangle.slopeHigh;
    features.geom_tri_slope_low = pack.triangle.slopeLow;
    features.geom_tri_convergence = pack.triangle.convergenceRate;
    features.geom_tri_compression = pack.triangle.compression;
    features.geom_tri_touches = pack.triangle.touchesHigh + pack.triangle.touchesLow;
    features.geom_tri_apex_dist = pack.triangle.apexDistanceBars;
  }

  // Channel features
  if (pack.channel) {
    features.geom_chan_width = pack.channel.widthATR;
    features.geom_chan_slope = pack.channel.slopeMid;
    features.geom_chan_parallel_err = pack.channel.parallelismError;
    features.geom_chan_touches = pack.channel.touches;
  }

  // Flag features
  if (pack.flag) {
    features.geom_flag_pole = pack.flag.poleATR;
    features.geom_flag_retrace = pack.flag.retracePct;
    features.geom_flag_width = pack.flag.channelWidthATR;
    features.geom_flag_compression = pack.flag.consolidationCompression;
  }

  // Reversal features
  if (pack.reversal) {
    features.geom_rev_symmetry = pack.reversal.symmetryTimeRatio;
    features.geom_rev_neckline = pack.reversal.necklineSlope;
    features.geom_rev_height = pack.reversal.heightATR;
  }

  // Harmonic features
  if (pack.harmonic) {
    features.geom_harm_ab_xa = pack.harmonic.ratioAB_XA;
    features.geom_harm_bc_ab = pack.harmonic.ratioBC_AB;
    features.geom_harm_cd_bc = pack.harmonic.ratioCD_BC;
    features.geom_harm_error = pack.harmonic.ratioError;
  }

  return features;
}
