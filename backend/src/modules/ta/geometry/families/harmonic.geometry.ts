/**
 * P1.2 — Harmonic Geometry (COMMIT 5)
 * ABCD, Gartley, Bat, Butterfly, Crab, etc.
 */

import { GeometryInput, HarmonicGeometry } from './geometry.types.js';

// Ideal Fibonacci ratios for common harmonics
const IDEAL_RATIOS: Record<string, { AB_XA: number; BC_AB: number; CD_BC: number; AD_XA: number }> = {
  GARTLEY: { AB_XA: 0.618, BC_AB: 0.618, CD_BC: 1.272, AD_XA: 0.786 },
  BAT: { AB_XA: 0.5, BC_AB: 0.5, CD_BC: 2.0, AD_XA: 0.886 },
  BUTTERFLY: { AB_XA: 0.786, BC_AB: 0.618, CD_BC: 1.618, AD_XA: 1.272 },
  CRAB: { AB_XA: 0.618, BC_AB: 0.618, CD_BC: 2.618, AD_XA: 1.618 },
  SHARK: { AB_XA: 0.618, BC_AB: 1.272, CD_BC: 1.618, AD_XA: 0.886 },
  CYPHER: { AB_XA: 0.618, BC_AB: 1.414, CD_BC: 1.272, AD_XA: 0.786 },
  ABCD: { AB_XA: 1.0, BC_AB: 0.618, CD_BC: 1.272, AD_XA: 1.0 },
};

/**
 * Compute harmonic pattern geometry
 */
export function computeHarmonicGeometry(input: GeometryInput): HarmonicGeometry | null {
  const { pointX, pointA, pointB, pointC, pointD, patternType } = input;
  
  if (pointX === undefined || pointA === undefined || 
      pointB === undefined || pointC === undefined || pointD === undefined) {
    return null;
  }

  // Calculate legs
  const XA = Math.abs(pointA - pointX);
  const AB = Math.abs(pointB - pointA);
  const BC = Math.abs(pointC - pointB);
  const CD = Math.abs(pointD - pointC);
  const AD = Math.abs(pointD - pointA);

  // Calculate ratios (guard against division by zero)
  const ratioAB_XA = XA > 0 ? AB / XA : 0;
  const ratioBC_AB = AB > 0 ? BC / AB : 0;
  const ratioCD_BC = BC > 0 ? CD / BC : 0;
  const ratioAD_XA = XA > 0 ? AD / XA : 0;

  // Find ideal ratios for this pattern type
  const upper = patternType.toUpperCase();
  let idealRatios = IDEAL_RATIOS.GARTLEY;  // default
  
  for (const [name, ratios] of Object.entries(IDEAL_RATIOS)) {
    if (upper.includes(name)) {
      idealRatios = ratios;
      break;
    }
  }

  // Calculate ratio error
  const errors = [
    Math.abs(ratioAB_XA - idealRatios.AB_XA) / idealRatios.AB_XA,
    Math.abs(ratioBC_AB - idealRatios.BC_AB) / idealRatios.BC_AB,
    Math.abs(ratioCD_BC - idealRatios.CD_BC) / idealRatios.CD_BC,
    Math.abs(ratioAD_XA - idealRatios.AD_XA) / idealRatios.AD_XA,
  ];
  const ratioError = Math.min(errors.reduce((a, b) => a + b, 0) / 4, 1);

  return {
    ratioAB_XA,
    ratioBC_AB,
    ratioCD_BC,
    ratioAD_XA,
    ratioError,
  };
}

export function harmonicMaturity(geom: HarmonicGeometry): number {
  // Harmonic is "mature" when D point is formed with good ratios
  // Lower ratio error = higher maturity
  return Math.max(0, 1 - geom.ratioError);
}

export function harmonicFitError(geom: HarmonicGeometry): number {
  // Fit error is the ratio error
  return geom.ratioError;
}
