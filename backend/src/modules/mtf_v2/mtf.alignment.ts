/**
 * Phase 6.5 — MTF Alignment Engine
 * 
 * Computes alignment between timeframes and calculates mtfBoost factor
 * 
 * 4 Key Checks:
 * 1. Regime alignment — higher TF regime supports setup
 * 2. Structure alignment — higher TF structure aligns
 * 3. Scenario alignment — higher TF scenario supports
 * 4. Momentum alignment — lower TF momentum confirms
 */

import { 
  MTFState, 
  MTFAlignmentInput, 
  MTFConfig, 
  DEFAULT_MTF_CONFIG,
  Bias 
} from './mtf.types.js';
import { MTFContext } from './mtf.context.js';

/**
 * Check if higher TF regime supports the setup direction
 */
function checkRegimeAlignment(
  higherRegime: string,
  anchorDirection: 'LONG' | 'SHORT'
): boolean {
  // TREND_UP supports LONG, TREND_DOWN supports SHORT
  // RANGE is neutral (supports both)
  // TRANSITION is weak support
  
  if (anchorDirection === 'LONG') {
    return higherRegime === 'TREND_UP' || higherRegime === 'RANGE';
  }
  if (anchorDirection === 'SHORT') {
    return higherRegime === 'TREND_DOWN' || higherRegime === 'RANGE';
  }
  return true;
}

/**
 * Check if higher TF structure aligns with anchor direction
 */
function checkStructureAlignment(
  higherStructure: string,
  anchorDirection: 'LONG' | 'SHORT'
): boolean {
  if (anchorDirection === 'LONG') {
    return higherStructure === 'BULLISH' || higherStructure === 'NEUTRAL';
  }
  if (anchorDirection === 'SHORT') {
    return higherStructure === 'BEARISH' || higherStructure === 'NEUTRAL';
  }
  return true;
}

/**
 * Check if higher TF scenario supports anchor scenario
 */
function checkScenarioAlignment(
  higherScenarioDirection: string | undefined,
  anchorDirection: 'LONG' | 'SHORT'
): boolean {
  if (!higherScenarioDirection) return true;  // No scenario = neutral
  
  const higherDir = higherScenarioDirection.toUpperCase();
  
  if (anchorDirection === 'LONG') {
    return higherDir === 'LONG' || higherDir === 'BULL' || higherDir === 'BULLISH';
  }
  if (anchorDirection === 'SHORT') {
    return higherDir === 'SHORT' || higherDir === 'BEAR' || higherDir === 'BEARISH';
  }
  return true;
}

/**
 * Check if lower TF momentum confirms entry
 */
function checkMomentumAlignment(
  lowerMomentumBias: Bias,
  anchorDirection: 'LONG' | 'SHORT'
): boolean {
  if (anchorDirection === 'LONG') {
    return lowerMomentumBias === 'BULL' || lowerMomentumBias === 'NEUTRAL';
  }
  if (anchorDirection === 'SHORT') {
    return lowerMomentumBias === 'BEAR' || lowerMomentumBias === 'NEUTRAL';
  }
  return true;
}

/**
 * Check if higher TF is actively conflicting (opposite direction)
 */
function checkHigherConflict(
  higherBias: Bias,
  anchorDirection: 'LONG' | 'SHORT'
): boolean {
  if (higherBias === 'NEUTRAL') return false;
  
  if (anchorDirection === 'LONG' && higherBias === 'BEAR') return true;
  if (anchorDirection === 'SHORT' && higherBias === 'BULL') return true;
  
  return false;
}

/**
 * Check if higher TF bias aligns with anchor direction
 */
function checkHigherBiasAlignment(
  higherBias: Bias,
  anchorDirection: 'LONG' | 'SHORT'
): boolean {
  if (higherBias === 'NEUTRAL') return true;  // Neutral doesn't oppose
  
  if (anchorDirection === 'LONG' && higherBias === 'BULL') return true;
  if (anchorDirection === 'SHORT' && higherBias === 'BEAR') return true;
  
  return false;
}

/**
 * Calculate MTF Boost factor
 * 
 * Formula:
 * - higherBias aligned: +0.06
 * - regime aligned: +0.05
 * - structure aligned: +0.05
 * - scenario aligned: +0.04
 * - lower momentum aligned: +0.04
 * - higher conflict: -0.10
 * 
 * Clamped to [0.88, 1.15]
 */
export function calculateMTFBoost(
  input: MTFAlignmentInput,
  config: MTFConfig = DEFAULT_MTF_CONFIG
): number {
  let boost = 1.0;
  
  if (input.higherBiasAligned) {
    boost += config.weights.higherBiasAligned;
  }
  
  if (input.regimeAligned) {
    boost += config.weights.regimeAligned;
  }
  
  if (input.structureAligned) {
    boost += config.weights.structureAligned;
  }
  
  if (input.scenarioAligned) {
    boost += config.weights.scenarioAligned;
  }
  
  if (input.lowerMomentumAligned) {
    boost += config.weights.lowerMomentumAligned;
  }
  
  if (input.higherConflict) {
    boost += config.weights.higherConflict;  // Negative value
  }
  
  // Clamp to bounds
  return Math.max(config.boostMin, Math.min(config.boostMax, boost));
}

/**
 * Calculate execution adjustment based on alignment strength
 */
export function calculateExecutionAdjustment(
  alignmentCount: number,  // How many of the 4 checks passed
  higherConflict: boolean,
  config: MTFConfig = DEFAULT_MTF_CONFIG
): number {
  if (higherConflict) {
    return config.executionConflict;  // 0.85
  }
  
  if (alignmentCount >= 3) {
    return config.executionStrong;  // 1.00
  }
  
  return config.executionMixed;  // 0.92
}

/**
 * Generate human-readable notes about alignment
 */
function generateNotes(
  higherBiasAligned: boolean,
  regimeAligned: boolean,
  structureAligned: boolean,
  scenarioAligned: boolean,
  momentumAligned: boolean,
  higherConflict: boolean,
  higherTf: string,
  lowerTf: string
): string[] {
  const notes: string[] = [];
  
  if (higherBiasAligned) {
    notes.push(`Higher timeframe (${higherTf}) trend supports current setup`);
  }
  
  if (regimeAligned) {
    notes.push(`${higherTf} regime aligns with entry direction`);
  } else {
    notes.push(`Warning: ${higherTf} regime does not support direction`);
  }
  
  if (structureAligned) {
    notes.push(`${higherTf} structure confirms direction`);
  }
  
  if (scenarioAligned) {
    notes.push(`${higherTf} scenario supports current setup`);
  } else {
    notes.push(`${higherTf} scenario partially conflicts`);
  }
  
  if (momentumAligned) {
    notes.push(`Lower timeframe (${lowerTf}) momentum confirms entry`);
  } else {
    notes.push(`Warning: ${lowerTf} momentum is weak or opposing`);
  }
  
  if (higherConflict) {
    notes.push(`CONFLICT: ${higherTf} is opposing current direction!`);
  }
  
  return notes;
}

/**
 * Compute full MTF State from context
 */
export function computeMTFState(
  ctx: MTFContext,
  config: MTFConfig = DEFAULT_MTF_CONFIG
): MTFState {
  const anchorDirection = ctx.anchor.direction;
  
  // Skip if anchor direction is WAIT
  if (anchorDirection === 'WAIT') {
    return {
      symbol: ctx.symbol,
      anchorTf: ctx.anchorTf,
      higherTf: ctx.higherTf,
      lowerTf: ctx.lowerTf,
      higherBias: ctx.higher.bias,
      higherRegime: ctx.higher.regime,
      higherStructure: ctx.higher.structure,
      higherScenarioBias: ctx.higher.topScenario?.direction,
      lowerMomentum: ctx.lower.momentum?.overallBias || 'NEUTRAL',
      lowerStructure: ctx.lower.structure,
      regimeAligned: true,
      structureAligned: true,
      scenarioAligned: true,
      momentumAligned: true,
      higherConflict: false,
      mtfBoost: 1.0,
      mtfExecutionAdjustment: 1.0,
      notes: ['No active direction - MTF check skipped'],
      computedAt: Date.now()
    };
  }
  
  // Perform 4 key checks
  const higherBiasAligned = checkHigherBiasAlignment(ctx.higher.bias, anchorDirection);
  const regimeAligned = checkRegimeAlignment(ctx.higher.regime, anchorDirection);
  const structureAligned = checkStructureAlignment(ctx.higher.structure, anchorDirection);
  const scenarioAligned = checkScenarioAlignment(
    ctx.higher.topScenario?.direction,
    anchorDirection
  );
  const momentumAligned = checkMomentumAlignment(
    ctx.lower.momentum?.overallBias || 'NEUTRAL',
    anchorDirection
  );
  const higherConflict = checkHigherConflict(ctx.higher.bias, anchorDirection);
  
  // Calculate boost
  const alignmentInput: MTFAlignmentInput = {
    anchorDirection,
    higherBiasAligned,
    regimeAligned,
    structureAligned,
    scenarioAligned,
    lowerMomentumAligned: momentumAligned,
    higherConflict
  };
  
  const mtfBoost = calculateMTFBoost(alignmentInput, config);
  
  // Count alignments for execution adjustment
  const alignmentCount = [regimeAligned, structureAligned, scenarioAligned, momentumAligned]
    .filter(Boolean).length;
  
  const mtfExecutionAdjustment = calculateExecutionAdjustment(
    alignmentCount,
    higherConflict,
    config
  );
  
  // Generate notes
  const notes = generateNotes(
    higherBiasAligned,
    regimeAligned,
    structureAligned,
    scenarioAligned,
    momentumAligned,
    higherConflict,
    ctx.higherTf,
    ctx.lowerTf
  );
  
  return {
    symbol: ctx.symbol,
    anchorTf: ctx.anchorTf,
    higherTf: ctx.higherTf,
    lowerTf: ctx.lowerTf,
    higherBias: ctx.higher.bias,
    higherRegime: ctx.higher.regime,
    higherStructure: ctx.higher.structure,
    higherScenarioBias: ctx.higher.topScenario?.direction,
    lowerMomentum: ctx.lower.momentum?.overallBias || 'NEUTRAL',
    lowerStructure: ctx.lower.structure,
    regimeAligned,
    structureAligned,
    scenarioAligned,
    momentumAligned,
    higherConflict,
    mtfBoost,
    mtfExecutionAdjustment,
    notes,
    computedAt: Date.now()
  };
}

/**
 * Quick check if MTF supports a direction
 */
export function mtfSupportsDirection(
  higherBias: Bias,
  higherRegime: string,
  lowerMomentum: Bias,
  direction: 'LONG' | 'SHORT'
): { supports: boolean; boost: number; reason: string } {
  const higherAligned = checkHigherBiasAlignment(higherBias, direction);
  const regimeAligned = checkRegimeAlignment(higherRegime, direction);
  const momentumAligned = checkMomentumAlignment(lowerMomentum, direction);
  const conflict = checkHigherConflict(higherBias, direction);
  
  const boost = calculateMTFBoost({
    anchorDirection: direction,
    higherBiasAligned: higherAligned,
    regimeAligned,
    structureAligned: true,  // Assume true for quick check
    scenarioAligned: true,
    lowerMomentumAligned: momentumAligned,
    higherConflict: conflict
  });
  
  const supports = !conflict && (higherAligned || regimeAligned);
  
  let reason = '';
  if (conflict) {
    reason = 'Higher TF conflict';
  } else if (supports) {
    reason = 'MTF aligned';
  } else {
    reason = 'Weak MTF support';
  }
  
  return { supports, boost, reason };
}
