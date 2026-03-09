/**
 * P1.2 — Module Gating Types
 * 
 * Types for MetaBrain v2.2 Module Gating system
 * Allows system to soft-gate or hard-gate underperforming modules
 */

import { AnalysisModule } from './module_attribution.types.js';

// ═══════════════════════════════════════════════════════════════
// GATE STATUS
// ═══════════════════════════════════════════════════════════════

export type ModuleGateStatus = 'ACTIVE' | 'SOFT_GATED' | 'HARD_GATED';

// ═══════════════════════════════════════════════════════════════
// GATE TYPES
// ═══════════════════════════════════════════════════════════════

export interface ModuleGate {
  module: AnalysisModule;
  regime?: string;
  
  status: ModuleGateStatus;
  reason: string;
  
  // Scoring data
  score: number;           // Gating score (higher = more likely to gate)
  sampleSize: number;
  avgOutcomeImpact: number;
  weight: number;
  
  // Timing
  gatedUntil?: number;     // Unix timestamp
  updatedAt: number;
  createdAt: number;
}

export interface ModuleGateHistory {
  module: AnalysisModule;
  regime?: string;
  
  previousStatus: ModuleGateStatus;
  newStatus: ModuleGateStatus;
  
  reason: string;
  score: number;
  
  changedAt: Date;
  changedBy: 'AUTO' | 'MANUAL' | 'GOVERNANCE';
}

// ═══════════════════════════════════════════════════════════════
// GATING INPUT/OUTPUT
// ═══════════════════════════════════════════════════════════════

export interface ModuleGatingInput {
  module: AnalysisModule;
  weight: number;
  sampleSize: number;
  avgOutcomeImpact: number;
  degradationStreak: number;
  regime?: string;
}

export interface GatingDecision {
  module: AnalysisModule;
  regime?: string;
  
  status: ModuleGateStatus;
  reason: string;
  score: number;
  
  previousStatus?: ModuleGateStatus;
  statusChanged: boolean;
}

// ═══════════════════════════════════════════════════════════════
// GATING RULES
// ═══════════════════════════════════════════════════════════════

export interface GatingRules {
  // Sample requirements
  minSampleForSoftGate: number;
  minSampleForHardGate: number;
  
  // Thresholds
  softGateWeightThreshold: number;
  hardGateWeightThreshold: number;
  softGateImpactThreshold: number;
  hardGateImpactThreshold: number;
  
  // Degradation streak
  minDegradationStreakForHardGate: number;
  
  // Governance limits
  maxHardGatedModules: number;
  maxGateChangesPerDay: number;
  hardGateDurationDays: number;
  
  // Score calculation weights
  impactWeight: number;
  weightDevWeight: number;
  streakWeight: number;
}

export const DEFAULT_GATING_RULES: GatingRules = {
  // Sample requirements
  minSampleForSoftGate: 200,
  minSampleForHardGate: 500,
  
  // Thresholds
  softGateWeightThreshold: 0.90,
  hardGateWeightThreshold: 0.80,
  softGateImpactThreshold: 0,      // Negative impact triggers soft gate
  hardGateImpactThreshold: -0.05,  // Significantly negative impact
  
  // Degradation streak
  minDegradationStreakForHardGate: 3,
  
  // Governance limits
  maxHardGatedModules: 3,
  maxGateChangesPerDay: 1,
  hardGateDurationDays: 14,
  
  // Score calculation weights
  impactWeight: 0.5,
  weightDevWeight: 0.3,
  streakWeight: 0.2
};

// ═══════════════════════════════════════════════════════════════
// GATING SUMMARY
// ═══════════════════════════════════════════════════════════════

export interface GatingSummary {
  totalModules: number;
  activeModules: number;
  softGatedModules: number;
  hardGatedModules: number;
  
  gatedModulesList: AnalysisModule[];
  
  gatePressure: number;  // 0-1, how much system has "constrained itself"
  
  lastRebuildAt?: Date;
  nextScheduledRebuild?: Date;
}

// ═══════════════════════════════════════════════════════════════
// GATE APPLICATION
// ═══════════════════════════════════════════════════════════════

export interface GateApplicationResult {
  module: AnalysisModule;
  originalBoost: number;
  gatedBoost: number;
  gateApplied: boolean;
  gateStatus: ModuleGateStatus;
  multiplier: number;
}

// ═══════════════════════════════════════════════════════════════
// API TYPES
// ═══════════════════════════════════════════════════════════════

export interface GatesResponse {
  success: boolean;
  data?: {
    gates: ModuleGate[];
    summary: GatingSummary;
  };
  error?: string;
}

export interface GateRebuildResponse {
  success: boolean;
  data?: {
    modulesProcessed: number;
    statusChanges: number;
    newGates: ModuleGate[];
    rebuiltAt: Date;
  };
  error?: string;
}

export interface GateOverrideRequest {
  module: AnalysisModule;
  regime?: string;
  status: ModuleGateStatus;
  reason: string;
  durationDays?: number;
}

export interface GateOverrideResponse {
  success: boolean;
  data?: {
    gate: ModuleGate;
    previousStatus: ModuleGateStatus;
  };
  error?: string;
}
