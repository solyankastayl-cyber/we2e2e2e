/**
 * MetaBrain Learning — Decision Engine Integration
 * 
 * Provides learning weights to Decision Engine for module boost adjustment
 */

import { AnalysisModule, ModuleWeight } from './module_attribution.types.js';
import { getCurrentWeights, getModuleWeight } from './module_controller.js';

// ═══════════════════════════════════════════════════════════════
// WEIGHT MAP SERVICE
// ═══════════════════════════════════════════════════════════════

export interface LearningWeightMap {
  pattern: number;
  liquidity: number;
  graph: number;
  fractal: number;
  physics: number;
  state: number;
  regime: number;
  scenario: number;
}

/**
 * Get all learning weights as a map for Decision Engine
 */
export async function getLearningWeightMap(regime?: string): Promise<LearningWeightMap> {
  const weights = await getCurrentWeights(regime);
  
  const weightMap: LearningWeightMap = {
    pattern: 1.0,
    liquidity: 1.0,
    graph: 1.0,
    fractal: 1.0,
    physics: 1.0,
    state: 1.0,
    regime: 1.0,
    scenario: 1.0
  };
  
  for (const w of weights) {
    const key = moduleToKey(w.module);
    if (key) {
      weightMap[key] = w.weight;
    }
  }
  
  return weightMap;
}

/**
 * Get single weight by module name
 */
export async function getLearningWeight(
  moduleName: 'pattern' | 'liquidity' | 'graph' | 'fractal' | 'physics' | 'state' | 'regime' | 'scenario',
  regime?: string
): Promise<number> {
  const module = keyToModule(moduleName);
  if (!module) return 1.0;
  return getModuleWeight(module, regime);
}

/**
 * Apply learning weights to boost values
 */
export function applyLearningWeights(
  boosts: {
    patternBoost?: number;
    liquidityBoost?: number;
    graphBoost?: number;
    fractalBoost?: number;
    physicsBoost?: number;
    stateBoost?: number;
    regimeBoost?: number;
    scenarioBoost?: number;
  },
  weights: LearningWeightMap
): {
  patternBoost: number;
  liquidityBoost: number;
  graphBoost: number;
  fractalBoost: number;
  physicsBoost: number;
  stateBoost: number;
  regimeBoost: number;
  scenarioBoost: number;
  combinedMultiplier: number;
} {
  const adjusted = {
    patternBoost: (boosts.patternBoost ?? 1) * weights.pattern,
    liquidityBoost: (boosts.liquidityBoost ?? 1) * weights.liquidity,
    graphBoost: (boosts.graphBoost ?? 1) * weights.graph,
    fractalBoost: (boosts.fractalBoost ?? 1) * weights.fractal,
    physicsBoost: (boosts.physicsBoost ?? 1) * weights.physics,
    stateBoost: (boosts.stateBoost ?? 1) * weights.state,
    regimeBoost: (boosts.regimeBoost ?? 1) * weights.regime,
    scenarioBoost: (boosts.scenarioBoost ?? 1) * weights.scenario,
    combinedMultiplier: 1.0
  };
  
  // Calculate combined multiplier
  adjusted.combinedMultiplier = 
    adjusted.patternBoost *
    adjusted.liquidityBoost *
    adjusted.graphBoost *
    adjusted.fractalBoost *
    adjusted.physicsBoost *
    adjusted.stateBoost *
    adjusted.regimeBoost *
    adjusted.scenarioBoost;
  
  return adjusted;
}

// ═══════════════════════════════════════════════════════════════
// HTTP API FOR DECISION ENGINE
// ═══════════════════════════════════════════════════════════════

/**
 * Fetch learning weights via HTTP (for cross-service calls)
 */
export async function fetchLearningWeights(regime?: string): Promise<LearningWeightMap | null> {
  try {
    const url = regime 
      ? `http://localhost:3001/api/ta/metabrain/learning/weights?regime=${regime}`
      : 'http://localhost:3001/api/ta/metabrain/learning/weights';
    
    const resp = await fetch(url);
    if (!resp.ok) return null;
    
    const data = await resp.json() as { weights: Array<{ module: string; weight: number }> };
    
    const weightMap: LearningWeightMap = {
      pattern: 1.0,
      liquidity: 1.0,
      graph: 1.0,
      fractal: 1.0,
      physics: 1.0,
      state: 1.0,
      regime: 1.0,
      scenario: 1.0
    };
    
    for (const w of data.weights) {
      const key = moduleToKey(w.module as AnalysisModule);
      if (key) {
        weightMap[key] = w.weight;
      }
    }
    
    return weightMap;
  } catch {
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function moduleToKey(module: AnalysisModule): keyof LearningWeightMap | null {
  const map: Record<AnalysisModule, keyof LearningWeightMap> = {
    'PATTERN': 'pattern',
    'LIQUIDITY': 'liquidity',
    'GRAPH': 'graph',
    'FRACTAL': 'fractal',
    'PHYSICS': 'physics',
    'STATE': 'state',
    'REGIME': 'regime',
    'SCENARIO': 'scenario'
  };
  return map[module] || null;
}

function keyToModule(key: string): AnalysisModule | null {
  const map: Record<string, AnalysisModule> = {
    'pattern': 'PATTERN',
    'liquidity': 'LIQUIDITY',
    'graph': 'GRAPH',
    'fractal': 'FRACTAL',
    'physics': 'PHYSICS',
    'state': 'STATE',
    'regime': 'REGIME',
    'scenario': 'SCENARIO'
  };
  return map[key] || null;
}
