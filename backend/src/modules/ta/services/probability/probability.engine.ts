/**
 * Probability Engine (P4.2)
 * 
 * Main composition engine that combines ML + Scenario + Priors + Stability
 * into final probability and EV
 */

import type {
  ProbabilityPack,
  ComposeProbabilityInput,
  SourceBreakdown,
  CompositionWeights
} from './probability.types.js';
import { calculateWeights, applyStabilityDamping } from './probability.weights.js';
import { isotonicAdjust } from './probability.calibration.js';

/**
 * Normalize probability to [0, 1]
 */
function clampProb(p: number): number {
  return Math.max(0, Math.min(1, p));
}

/**
 * Main probability composition function
 */
export function composeProbability(input: ComposeProbabilityInput): ProbabilityPack {
  const { ml, scenario, priors, stability } = input;
  
  // Calculate base weights
  let weights = calculateWeights(ml, scenario, priors);
  
  // Apply stability damping if needed
  const stabilityMultiplier = stability?.multiplier ?? 1.0;
  if (stability && stability.degrading) {
    weights = applyStabilityDamping(weights, stabilityMultiplier);
  }
  
  // Extract raw probabilities
  const pEntryML = ml?.pEntry ?? 0.5;
  const pEntryScenario = scenario?.pTarget ?? 0.5;
  const pEntryPriors = priors?.pEntry ?? priors?.winRate ?? 0.5;
  
  // === Compose pEntry ===
  let pEntry = 
    weights.ml * pEntryML +
    weights.scenario * pEntryScenario +
    weights.priors * pEntryPriors;
  
  // Apply isotonic shrinkage (light calibration)
  pEntry = isotonicAdjust(pEntry, 0.05);
  
  // === Compose pWin ===
  let pWin: number;
  if (scenario) {
    // Blend scenario pTarget with ML
    pWin = scenario.pTarget * 0.6 + (ml?.pEntry ?? 0.5) * 0.4;
  } else {
    pWin = pEntry * 0.9; // Slightly lower than entry
  }
  pWin = clampProb(pWin);
  
  // === pStop and pTimeout ===
  let pStop = scenario?.pStop ?? 0.3;
  let pTimeout = scenario?.pTimeout ?? (1 - pWin - pStop);
  
  // Normalize to sum to 1
  const pTotal = pWin + pStop + pTimeout;
  if (pTotal > 0 && Math.abs(pTotal - 1) > 0.01) {
    pWin /= pTotal;
    pStop /= pTotal;
    pTimeout /= pTotal;
  }
  
  // === Expected R ===
  let expectedR: number;
  if (ml && ml.expectedR !== undefined) {
    expectedR = ml.expectedR * 0.7;
    
    if (scenario) {
      expectedR += scenario.p50 * 0.3;
    }
  } else if (scenario) {
    expectedR = scenario.p50;
  } else {
    expectedR = 1.5; // Default
  }
  
  // Apply stability multiplier
  expectedR *= stabilityMultiplier;
  
  // === Final EV ===
  const EV = pEntry * expectedR;
  
  // === Source breakdown ===
  const sourceBreakdown: SourceBreakdown = {
    ml: ml ? pEntryML * weights.ml : 0,
    scenario: scenario ? pEntryScenario * weights.scenario : 0,
    priors: priors ? pEntryPriors * weights.priors : 0,
    stability: stabilityMultiplier
  };
  
  // === Confidence ===
  let confidence = 0.5;
  
  // Higher confidence if multiple sources agree
  const sources = [
    ml ? pEntryML : null,
    scenario ? pEntryScenario : null,
    priors ? pEntryPriors : null
  ].filter(p => p !== null) as number[];
  
  if (sources.length >= 2) {
    // Calculate variance
    const mean = sources.reduce((a, b) => a + b, 0) / sources.length;
    const variance = sources.reduce((sum, p) => sum + Math.pow(p - mean, 2), 0) / sources.length;
    
    // Lower variance = higher confidence
    confidence = Math.max(0.3, 1 - Math.sqrt(variance) * 2);
  }
  
  // Boost confidence if we have all sources
  if (ml && scenario && priors) {
    confidence = Math.min(0.9, confidence + 0.1);
  }
  
  // === Composition method ===
  let compositionMethod: ProbabilityPack['compositionMethod'] = 'WEIGHTED_AVERAGE';
  if (!ml && !scenario && !priors) {
    compositionMethod = 'FALLBACK';
  }
  
  return {
    pEntry: clampProb(pEntry),
    pWin: clampProb(pWin),
    pStop: clampProb(pStop),
    pTimeout: clampProb(pTimeout),
    expectedR,
    EV,
    sourceBreakdown,
    weights,
    compositionMethod,
    calibrated: true,
    calibrationMethod: 'isotonic_shrinkage',
    confidence: clampProb(confidence)
  };
}

/**
 * Debug version with full breakdown
 */
export function composeProbabilityDebug(input: ComposeProbabilityInput): {
  pack: ProbabilityPack;
  debug: {
    rawInputs: {
      ml: { pEntry: number; expectedR: number } | null;
      scenario: { pTarget: number; p50: number } | null;
      priors: { pEntry: number; winRate: number } | null;
      stability: { multiplier: number } | null;
    };
    intermediateWeights: CompositionWeights;
    finalWeights: CompositionWeights;
    preCalibration: { pEntry: number };
    postCalibration: { pEntry: number };
  };
} {
  const { ml, scenario, priors, stability } = input;
  
  const intermediateWeights = calculateWeights(ml, scenario, priors);
  const finalWeights = stability?.degrading 
    ? applyStabilityDamping(intermediateWeights, stability.multiplier)
    : intermediateWeights;
  
  // Raw pEntry before calibration
  const rawPEntry = 
    finalWeights.ml * (ml?.pEntry ?? 0.5) +
    finalWeights.scenario * (scenario?.pTarget ?? 0.5) +
    finalWeights.priors * (priors?.pEntry ?? priors?.winRate ?? 0.5);
  
  const pack = composeProbability(input);
  
  return {
    pack,
    debug: {
      rawInputs: {
        ml: ml ? { pEntry: ml.pEntry, expectedR: ml.expectedR } : null,
        scenario: scenario ? { pTarget: scenario.pTarget, p50: scenario.p50 } : null,
        priors: priors ? { pEntry: priors.pEntry, winRate: priors.winRate } : null,
        stability: stability ? { multiplier: stability.multiplier } : null
      },
      intermediateWeights,
      finalWeights,
      preCalibration: { pEntry: rawPEntry },
      postCalibration: { pEntry: pack.pEntry }
    }
  };
}
