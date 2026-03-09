/**
 * P1.4 — MetaBrain v2.3 Regime Learning Integration
 */

import { AnalysisModule, ALL_MODULES } from '../metabrain_learning/module_attribution.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import { RegimeModuleWeight, RegimeWeightMap } from './regime.learning.types.js';
import {
  getRegimeWeight as getRegimeWeightFn,
  applyRegimeWeight,
  getDefaultRegimeWeightMap
} from './regime.learning.js';
import {
  getRegimeWeights as getRegimeWeightsFromStorage,
  getAllRegimeWeights,
  getRegimeWeightMaps
} from './regime.learning.storage.js';

// ═══════════════════════════════════════════════════════════════
// FETCH REGIME WEIGHTS
// ═══════════════════════════════════════════════════════════════

/**
 * Fetch regime weights via HTTP
 */
export async function fetchRegimeWeights(regime: MarketRegime): Promise<RegimeModuleWeight[] | null> {
  try {
    const url = `http://localhost:8001/api/ta/metabrain/regime/weights?regime=${regime}`;
    const resp = await fetch(url);
    
    if (!resp.ok) return null;
    
    const data = await resp.json() as { data?: { weights: RegimeModuleWeight[] } };
    return data.data?.weights ?? null;
  } catch {
    return null;
  }
}

/**
 * Fetch regime weight map
 */
export async function fetchRegimeWeightMap(regime: MarketRegime): Promise<RegimeWeightMap | null> {
  try {
    const url = `http://localhost:8001/api/ta/metabrain/regime/weights?regime=${regime}`;
    const resp = await fetch(url);
    
    if (!resp.ok) return null;
    
    const data = await resp.json() as { data?: { regime: MarketRegime; weights: RegimeModuleWeight[] } };
    
    if (!data.data) return null;
    
    // Build weight map
    const weights: Record<AnalysisModule, number> = {} as Record<AnalysisModule, number>;
    let totalConfidence = 0;
    let totalSamples = 0;
    
    for (const module of ALL_MODULES) {
      weights[module] = 1.0;
    }
    
    for (const w of data.data.weights) {
      weights[w.module] = w.weight;
      totalConfidence += w.confidence;
      totalSamples += w.sampleSize;
    }
    
    const count = data.data.weights.length;
    
    return {
      regime,
      weights,
      avgConfidence: count > 0 ? totalConfidence / count : 0,
      totalSamples
    };
  } catch {
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
// DECISION ENGINE INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get regime weight for a module
 */
export async function getModuleRegimeWeight(
  module: AnalysisModule,
  regime: MarketRegime
): Promise<number> {
  const weights = await getRegimeWeightsFromStorage(regime);
  return getRegimeWeightFn(module, regime, weights);
}

/**
 * Apply regime weight to decision boost
 */
export async function applyRegimeWeightToBoost(
  module: AnalysisModule,
  boost: number,
  moduleWeight: number,
  regime: MarketRegime
): Promise<{ adjustedBoost: number; regimeWeight: number; applied: boolean }> {
  const regimeWeight = await getModuleRegimeWeight(module, regime);
  
  if (regimeWeight === 1.0) {
    return {
      adjustedBoost: boost * moduleWeight,
      regimeWeight: 1.0,
      applied: false
    };
  }
  
  return {
    adjustedBoost: applyRegimeWeight(boost, moduleWeight, regimeWeight),
    regimeWeight,
    applied: true
  };
}

// ═══════════════════════════════════════════════════════════════
// GATING INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Check if module should be soft-gated based on regime weight
 */
export async function shouldSoftGateByRegime(
  module: AnalysisModule,
  regime: MarketRegime
): Promise<{ shouldGate: boolean; weight: number; reason: string }> {
  const weight = await getModuleRegimeWeight(module, regime);
  
  if (weight < 0.80) {
    return {
      shouldGate: true,
      weight,
      reason: `Regime weight ${weight.toFixed(2)} below threshold for ${regime}`
    };
  }
  
  return {
    shouldGate: false,
    weight,
    reason: 'Regime weight within acceptable range'
  };
}

/**
 * Check if module should be hard-gated based on regime weight
 */
export async function shouldHardGateByRegime(
  module: AnalysisModule,
  regime: MarketRegime
): Promise<{ shouldGate: boolean; weight: number; reason: string }> {
  const weight = await getModuleRegimeWeight(module, regime);
  
  if (weight < 0.70) {
    return {
      shouldGate: true,
      weight,
      reason: `Regime weight ${weight.toFixed(2)} critically low for ${regime}`
    };
  }
  
  return {
    shouldGate: false,
    weight,
    reason: 'Regime weight above critical threshold'
  };
}

// ═══════════════════════════════════════════════════════════════
// EXPLAIN API INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get regime weights for explain API
 */
export async function getRegimeWeightsForExplain(
  regime: MarketRegime
): Promise<Record<string, number>> {
  const weights = await getRegimeWeightsFromStorage(regime);
  const result: Record<string, number> = {};
  
  for (const module of ALL_MODULES) {
    result[module] = getRegimeWeightFn(module, regime, weights);
  }
  
  return result;
}

// ═══════════════════════════════════════════════════════════════
// FULL INTEGRATION HELPER
// ═══════════════════════════════════════════════════════════════

/**
 * Get complete regime learning state
 */
export async function getRegimeLearningState(regime: MarketRegime): Promise<{
  weights: RegimeModuleWeight[];
  weightMap: Record<AnalysisModule, number>;
  avgConfidence: number;
  modulesWithData: number;
}> {
  const weights = await getRegimeWeightsFromStorage(regime);
  
  const weightMap: Record<AnalysisModule, number> = {} as Record<AnalysisModule, number>;
  let totalConfidence = 0;
  let modulesWithData = 0;
  
  for (const module of ALL_MODULES) {
    weightMap[module] = 1.0;
  }
  
  for (const w of weights) {
    weightMap[w.module] = w.weight;
    if (w.confidence > 0) {
      totalConfidence += w.confidence;
      modulesWithData++;
    }
  }
  
  return {
    weights,
    weightMap,
    avgConfidence: modulesWithData > 0 ? totalConfidence / modulesWithData : 0,
    modulesWithData
  };
}
