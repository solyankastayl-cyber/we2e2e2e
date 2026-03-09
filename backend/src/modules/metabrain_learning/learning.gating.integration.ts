/**
 * P1.2 — Module Gating Integration
 * 
 * Integrates module gating with Decision Engine
 * Provides gated weights for score calculation
 */

import { AnalysisModule, ALL_MODULES } from './module_attribution.types.js';
import { LearningWeightMap } from './learning.integration.js';
import {
  ModuleGate,
  ModuleGateStatus,
  GateApplicationResult,
  GatingSummary
} from './learning.gating.types.js';
import {
  applyModuleGate,
  calculateGatingSummary,
  getModuleGateStatus,
  isModuleGated
} from './learning.gating.js';
import {
  getModuleGatesMap,
  getAllModuleGates
} from './learning.gating.storage.js';

// ═══════════════════════════════════════════════════════════════
// GATED WEIGHT MAP
// ═══════════════════════════════════════════════════════════════

export interface GatedWeightMap {
  pattern: number;
  liquidity: number;
  graph: number;
  fractal: number;
  physics: number;
  state: number;
  regime: number;
  scenario: number;
  
  // Gate info
  gatesApplied: boolean;
  gatedModules: AnalysisModule[];
}

/**
 * Apply gates to learning weights
 */
export function applyGatesToWeights(
  weights: LearningWeightMap,
  gates: Map<string, ModuleGate>,
  regime?: string
): GatedWeightMap {
  const moduleMap: Record<keyof LearningWeightMap, AnalysisModule> = {
    pattern: 'PATTERN',
    liquidity: 'LIQUIDITY',
    graph: 'GRAPH',
    fractal: 'FRACTAL',
    physics: 'PHYSICS',
    state: 'STATE',
    regime: 'REGIME',
    scenario: 'SCENARIO'
  };
  
  const gatedModules: AnalysisModule[] = [];
  const result: GatedWeightMap = {
    pattern: weights.pattern,
    liquidity: weights.liquidity,
    graph: weights.graph,
    fractal: weights.fractal,
    physics: weights.physics,
    state: weights.state,
    regime: weights.regime,
    scenario: weights.scenario,
    gatesApplied: false,
    gatedModules: []
  };
  
  for (const [key, module] of Object.entries(moduleMap)) {
    const gateKey = regime ? `${module}:${regime}` : module;
    const gate = gates.get(gateKey) || gates.get(module);
    
    if (gate && gate.status !== 'ACTIVE') {
      gatedModules.push(module);
      
      const weightKey = key as keyof LearningWeightMap;
      
      if (gate.status === 'SOFT_GATED') {
        // Reduce by 30%
        result[weightKey] = weights[weightKey] * 0.7;
      } else if (gate.status === 'HARD_GATED') {
        // Set to 1.0 (no effect)
        result[weightKey] = 1.0;
      }
    }
  }
  
  result.gatesApplied = gatedModules.length > 0;
  result.gatedModules = gatedModules;
  
  return result;
}

/**
 * Get gated weights from storage
 */
export async function getGatedWeights(
  weights: LearningWeightMap,
  regime?: string
): Promise<GatedWeightMap> {
  const gates = await getModuleGatesMap(regime);
  return applyGatesToWeights(weights, gates, regime);
}

// ═══════════════════════════════════════════════════════════════
// DECISION ENGINE INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Apply gating to a single boost
 * Used in Decision Engine for each module boost
 */
export function applyGateToBoost(
  module: AnalysisModule,
  boost: number,
  weight: number,
  gates: Map<string, ModuleGate>,
  regime?: string
): { gatedBoost: number; gateStatus: ModuleGateStatus; applied: boolean } {
  const gateKey = regime ? `${module}:${regime}` : module;
  const gate = gates.get(gateKey) || gates.get(module);
  
  const result = applyModuleGate(module, boost, weight, gate);
  
  return {
    gatedBoost: result.gatedBoost,
    gateStatus: result.gateStatus,
    applied: result.gateApplied
  };
}

/**
 * Get all gate statuses for explain API
 */
export async function getGateStatusesForExplain(
  regime?: string
): Promise<Record<string, { status: ModuleGateStatus; reason: string }>> {
  const gates = await getAllModuleGates(regime);
  const result: Record<string, { status: ModuleGateStatus; reason: string }> = {};
  
  for (const gate of gates) {
    if (gate.status !== 'ACTIVE') {
      result[gate.module] = {
        status: gate.status,
        reason: gate.reason
      };
    }
  }
  
  return result;
}

// ═══════════════════════════════════════════════════════════════
// HTTP FETCH
// ═══════════════════════════════════════════════════════════════

/**
 * Fetch gates via HTTP (for cross-service calls)
 */
export async function fetchModuleGates(regime?: string): Promise<ModuleGate[] | null> {
  try {
    const url = regime
      ? `http://localhost:8001/api/ta/metabrain/learning/gates?regime=${regime}`
      : 'http://localhost:8001/api/ta/metabrain/learning/gates';
    
    const resp = await fetch(url);
    if (!resp.ok) return null;
    
    const data = await resp.json() as { data?: { gates: ModuleGate[] } };
    return data.data?.gates ?? null;
  } catch {
    return null;
  }
}

/**
 * Fetch gating summary
 */
export async function fetchGatingSummary(regime?: string): Promise<GatingSummary | null> {
  try {
    const url = regime
      ? `http://localhost:8001/api/ta/metabrain/learning/gates?regime=${regime}`
      : 'http://localhost:8001/api/ta/metabrain/learning/gates';
    
    const resp = await fetch(url);
    if (!resp.ok) return null;
    
    const data = await resp.json() as { data?: { summary: GatingSummary } };
    return data.data?.summary ?? null;
  } catch {
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
// METABRAIN INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get gating pressure for MetaBrain policy
 */
export async function getGatingPressure(regime?: string): Promise<{
  pressure: number;
  hardGatedCount: number;
  shouldReduceRisk: boolean;
}> {
  const gates = await getAllModuleGates(regime);
  const summary = calculateGatingSummary(gates);
  
  return {
    pressure: summary.gatePressure,
    hardGatedCount: summary.hardGatedModules,
    shouldReduceRisk: summary.hardGatedModules >= 2 || summary.gatePressure > 0.3
  };
}

// ═══════════════════════════════════════════════════════════════
// DIGITAL TWIN INTEGRATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get gated modules list for Digital Twin state
 */
export async function getGatedModulesForTwin(regime?: string): Promise<{
  gatedModules: AnalysisModule[];
  gatePressure: number;
}> {
  const gates = await getAllModuleGates(regime);
  const summary = calculateGatingSummary(gates);
  
  return {
    gatedModules: summary.gatedModulesList,
    gatePressure: summary.gatePressure
  };
}
