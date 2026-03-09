/**
 * P1.2 — Module Gating Engine
 * 
 * Computes gating decisions for analysis modules based on:
 * - Weight performance (from learning weights)
 * - Outcome impact (from attribution)
 * - Degradation streaks
 * 
 * Gate states:
 * - ACTIVE: Module operates normally
 * - SOFT_GATED: Module boost reduced by 30%
 * - HARD_GATED: Module boost set to 1.0 (no effect)
 */

import {
  ModuleGate,
  ModuleGateStatus,
  ModuleGatingInput,
  GatingDecision,
  GatingRules,
  GatingSummary,
  GateApplicationResult,
  DEFAULT_GATING_RULES
} from './learning.gating.types.js';
import { AnalysisModule, ALL_MODULES } from './module_attribution.types.js';

// ═══════════════════════════════════════════════════════════════
// GATING SCORE CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate gating score
 * Higher score = more likely to be gated
 * 
 * Formula:
 * gateScore = (-avgOutcomeImpact * 0.5) + ((1 - weight) * 0.3) + (degradationStreak / 10 * 0.2)
 */
export function calculateGatingScore(
  input: ModuleGatingInput,
  rules: GatingRules = DEFAULT_GATING_RULES
): number {
  // Impact component: negative impact increases score
  const impactComponent = -input.avgOutcomeImpact * rules.impactWeight;
  
  // Weight deviation component: lower weight increases score
  const weightDeviation = Math.max(0, 1 - input.weight);
  const weightComponent = weightDeviation * rules.weightDevWeight;
  
  // Degradation streak component
  const streakFactor = Math.min(input.degradationStreak / 10, 1);
  const streakComponent = streakFactor * rules.streakWeight;
  
  const score = impactComponent + weightComponent + streakComponent;
  
  return Math.max(0, Math.min(1, score));
}

// ═══════════════════════════════════════════════════════════════
// GATING DECISION LOGIC
// ═══════════════════════════════════════════════════════════════

/**
 * Determine gate status based on input
 */
export function determineGateStatus(
  input: ModuleGatingInput,
  rules: GatingRules = DEFAULT_GATING_RULES
): GatingDecision {
  const score = calculateGatingScore(input, rules);
  
  // Not enough samples - stay active
  if (input.sampleSize < rules.minSampleForSoftGate) {
    return {
      module: input.module,
      regime: input.regime,
      status: 'ACTIVE',
      reason: `Insufficient sample size (${input.sampleSize} < ${rules.minSampleForSoftGate})`,
      score,
      statusChanged: false
    };
  }
  
  // Check for HARD_GATED conditions
  const shouldHardGate = 
    input.sampleSize >= rules.minSampleForHardGate &&
    input.weight < rules.hardGateWeightThreshold &&
    input.avgOutcomeImpact < rules.hardGateImpactThreshold &&
    input.degradationStreak >= rules.minDegradationStreakForHardGate;
  
  if (shouldHardGate) {
    return {
      module: input.module,
      regime: input.regime,
      status: 'HARD_GATED',
      reason: `Persistent negative contribution: weight=${input.weight.toFixed(2)}, impact=${input.avgOutcomeImpact.toFixed(3)}, streak=${input.degradationStreak}`,
      score,
      statusChanged: false
    };
  }
  
  // Check for SOFT_GATED conditions
  const shouldSoftGate =
    input.sampleSize >= rules.minSampleForSoftGate &&
    (input.weight < rules.softGateWeightThreshold || 
     input.avgOutcomeImpact < rules.softGateImpactThreshold);
  
  if (shouldSoftGate) {
    return {
      module: input.module,
      regime: input.regime,
      status: 'SOFT_GATED',
      reason: `Weak negative contribution: weight=${input.weight.toFixed(2)}, impact=${input.avgOutcomeImpact.toFixed(3)}`,
      score,
      statusChanged: false
    };
  }
  
  // Default: ACTIVE
  return {
    module: input.module,
    regime: input.regime,
    status: 'ACTIVE',
    reason: 'Normal performance',
    score,
    statusChanged: false
  };
}

/**
 * Compute gates for all modules
 */
export function computeModuleGates(
  inputs: ModuleGatingInput[],
  currentGates: Map<string, ModuleGate>,
  rules: GatingRules = DEFAULT_GATING_RULES
): ModuleGate[] {
  const gates: ModuleGate[] = [];
  const now = Date.now();
  
  for (const input of inputs) {
    const key = input.regime ? `${input.module}:${input.regime}` : input.module;
    const currentGate = currentGates.get(key);
    
    const decision = determineGateStatus(input, rules);
    
    // Check if status changed
    decision.statusChanged = currentGate ? currentGate.status !== decision.status : decision.status !== 'ACTIVE';
    
    gates.push({
      module: input.module,
      regime: input.regime,
      status: decision.status,
      reason: decision.reason,
      score: decision.score,
      sampleSize: input.sampleSize,
      avgOutcomeImpact: input.avgOutcomeImpact,
      weight: input.weight,
      gatedUntil: decision.status === 'HARD_GATED' 
        ? now + (rules.hardGateDurationDays * 24 * 60 * 60 * 1000)
        : undefined,
      updatedAt: now,
      createdAt: currentGate?.createdAt ?? now
    });
  }
  
  return gates;
}

// ═══════════════════════════════════════════════════════════════
// GATE APPLICATION
// ═══════════════════════════════════════════════════════════════

/**
 * Apply gate to module boost
 * 
 * ACTIVE: boost × weight (normal)
 * SOFT_GATED: boost × weight × 0.7
 * HARD_GATED: 1.0 (no effect)
 */
export function applyModuleGate(
  moduleName: AnalysisModule,
  baseBoost: number,
  learnedWeight: number,
  gate: ModuleGate | undefined
): GateApplicationResult {
  const status = gate?.status ?? 'ACTIVE';
  
  let multiplier: number;
  let gatedBoost: number;
  
  switch (status) {
    case 'ACTIVE':
      multiplier = learnedWeight;
      gatedBoost = baseBoost * multiplier;
      break;
      
    case 'SOFT_GATED':
      multiplier = learnedWeight * 0.7;
      gatedBoost = baseBoost * multiplier;
      break;
      
    case 'HARD_GATED':
      multiplier = 1.0;
      gatedBoost = 1.0;  // Module has no effect
      break;
      
    default:
      multiplier = learnedWeight;
      gatedBoost = baseBoost * multiplier;
  }
  
  return {
    module: moduleName,
    originalBoost: baseBoost,
    gatedBoost: Math.round(gatedBoost * 1000) / 1000,
    gateApplied: status !== 'ACTIVE',
    gateStatus: status,
    multiplier: Math.round(multiplier * 1000) / 1000
  };
}

/**
 * Apply gates to all module boosts
 */
export function applyAllModuleGates(
  boosts: Map<AnalysisModule, number>,
  weights: Map<AnalysisModule, number>,
  gates: Map<string, ModuleGate>,
  regime?: string
): Map<AnalysisModule, GateApplicationResult> {
  const results = new Map<AnalysisModule, GateApplicationResult>();
  
  for (const [module, boost] of boosts) {
    const key = regime ? `${module}:${regime}` : module;
    const gate = gates.get(key) || gates.get(module);
    const weight = weights.get(module) ?? 1.0;
    
    results.set(module, applyModuleGate(module, boost, weight, gate));
  }
  
  return results;
}

// ═══════════════════════════════════════════════════════════════
// GATING SUMMARY
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate gating summary
 */
export function calculateGatingSummary(gates: ModuleGate[]): GatingSummary {
  const active = gates.filter(g => g.status === 'ACTIVE').length;
  const softGated = gates.filter(g => g.status === 'SOFT_GATED').length;
  const hardGated = gates.filter(g => g.status === 'HARD_GATED').length;
  
  const gatedModules = gates
    .filter(g => g.status !== 'ACTIVE')
    .map(g => g.module);
  
  // Gate pressure: how much the system has constrained itself
  // 0 = all active, 1 = all hard gated
  const totalModules = gates.length;
  const gatePressure = totalModules > 0
    ? (softGated * 0.3 + hardGated * 1.0) / totalModules
    : 0;
  
  return {
    totalModules,
    activeModules: active,
    softGatedModules: softGated,
    hardGatedModules: hardGated,
    gatedModulesList: gatedModules,
    gatePressure: Math.round(gatePressure * 100) / 100
  };
}

// ═══════════════════════════════════════════════════════════════
// GOVERNANCE CHECKS
// ═══════════════════════════════════════════════════════════════

/**
 * Check if gating change is allowed by governance rules
 */
export function isGatingChangeAllowed(
  currentGates: ModuleGate[],
  proposedGate: ModuleGate,
  recentChanges: number,
  rules: GatingRules = DEFAULT_GATING_RULES
): { allowed: boolean; reason: string } {
  // Check max gate changes per day
  if (recentChanges >= rules.maxGateChangesPerDay) {
    return {
      allowed: false,
      reason: `Max daily gate changes reached (${rules.maxGateChangesPerDay})`
    };
  }
  
  // Check max hard-gated modules
  if (proposedGate.status === 'HARD_GATED') {
    const currentHardGated = currentGates.filter(g => 
      g.status === 'HARD_GATED' && g.module !== proposedGate.module
    ).length;
    
    if (currentHardGated >= rules.maxHardGatedModules) {
      return {
        allowed: false,
        reason: `Max hard-gated modules reached (${rules.maxHardGatedModules})`
      };
    }
  }
  
  return { allowed: true, reason: 'Change allowed' };
}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════

/**
 * Get default gates (all active)
 */
export function getDefaultGates(): ModuleGate[] {
  const now = Date.now();
  
  return ALL_MODULES.map(module => ({
    module,
    status: 'ACTIVE' as ModuleGateStatus,
    reason: 'Default active state',
    score: 0,
    sampleSize: 0,
    avgOutcomeImpact: 0,
    weight: 1.0,
    updatedAt: now,
    createdAt: now
  }));
}

/**
 * Check if a module is gated
 */
export function isModuleGated(
  module: AnalysisModule,
  gates: Map<string, ModuleGate>,
  regime?: string
): boolean {
  const key = regime ? `${module}:${regime}` : module;
  const gate = gates.get(key) || gates.get(module);
  
  return gate?.status !== 'ACTIVE';
}

/**
 * Get gate status for module
 */
export function getModuleGateStatus(
  module: AnalysisModule,
  gates: Map<string, ModuleGate>,
  regime?: string
): ModuleGateStatus {
  const key = regime ? `${module}:${regime}` : module;
  const gate = gates.get(key) || gates.get(module);
  
  return gate?.status ?? 'ACTIVE';
}
