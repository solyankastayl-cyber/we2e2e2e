/**
 * P1.3 — MM3 Memory-conditioned MetaBrain Policies Types
 * 
 * Types for Memory-conditioned policies that affect
 * MetaBrain decisions based on historical analogs
 */

import { ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// MEMORY CONTEXT (Extended from MM1-MM2)
// ═══════════════════════════════════════════════════════════════

export interface MemoryContext {
  confidence: number;
  matches: number;
  
  bias: 'BULL' | 'BEAR' | 'NEUTRAL';
  
  // Extended fields for policy decisions
  historicalWinRate?: number;
  avgMoveATR?: number;
  avgBarsToResolution?: number;
  
  // Consistency metrics
  directionConsistency?: number;  // How consistent were historical outcomes
  scenarioConsistency?: number;   // How often same scenario resolved
}

// ═══════════════════════════════════════════════════════════════
// MEMORY POLICY OUTPUT
// ═══════════════════════════════════════════════════════════════

export interface MemoryPolicy {
  // Risk multiplier (affects MetaBrain riskMode)
  riskMultiplier: number;
  
  // Confidence adjustment (affects Decision Engine)
  confidenceAdjustment: number;
  
  // Signal approval threshold adjustment
  signalApprovalThreshold: number;
  
  // Policy strength (0-1)
  policyStrength: number;
  
  // Human-readable reason
  policyReason: string;
  
  // Bias alignment adjustment
  biasAlignment?: {
    aligned: boolean;
    multiplier: number;
    description: string;
  };
}

// ═══════════════════════════════════════════════════════════════
// MEMORY POLICY RULES
// ═══════════════════════════════════════════════════════════════

export type MemoryStrength = 'STRONG' | 'MODERATE' | 'WEAK' | 'NONE';

export interface MemoryPolicyRules {
  // Strong memory thresholds
  strongMinMatches: number;
  strongMinConfidence: number;
  
  // Moderate memory thresholds
  moderateMinMatches: number;
  moderateMinConfidence: number;
  
  // Weak memory thresholds
  weakMinMatches: number;
  weakMinConfidence: number;
  
  // Risk multipliers by strength
  strongRiskMultiplier: number;
  moderateRiskMultiplier: number;
  weakRiskMultiplier: number;
  
  // Confidence adjustments
  strongConfidenceAdjustment: number;
  moderateConfidenceAdjustment: number;
  weakConfidenceAdjustment: number;
  
  // Signal threshold adjustments
  strongThresholdAdjustment: number;
  moderateThresholdAdjustment: number;
  weakThresholdAdjustment: number;
  
  // Bias alignment multipliers
  sameDirectionMultiplier: number;
  oppositeDirectionMultiplier: number;
}

export const DEFAULT_MEMORY_POLICY_RULES: MemoryPolicyRules = {
  // Strong memory: 25+ matches, 65%+ confidence
  strongMinMatches: 25,
  strongMinConfidence: 0.65,
  
  // Moderate memory: 10+ matches, 50%+ confidence
  moderateMinMatches: 10,
  moderateMinConfidence: 0.50,
  
  // Weak memory: <10 matches or <50% confidence
  weakMinMatches: 5,
  weakMinConfidence: 0.35,
  
  // Risk multipliers
  strongRiskMultiplier: 1.10,
  moderateRiskMultiplier: 1.00,
  weakRiskMultiplier: 0.90,
  
  // Confidence adjustments
  strongConfidenceAdjustment: 0.05,
  moderateConfidenceAdjustment: 0.00,
  weakConfidenceAdjustment: -0.05,
  
  // Signal threshold adjustments (negative = lower threshold = easier to trigger)
  strongThresholdAdjustment: -0.03,
  moderateThresholdAdjustment: 0.00,
  weakThresholdAdjustment: 0.03,
  
  // Bias alignment
  sameDirectionMultiplier: 1.05,
  oppositeDirectionMultiplier: 0.90
};

// ═══════════════════════════════════════════════════════════════
// POLICY APPLICATION
// ═══════════════════════════════════════════════════════════════

export interface MemoryPolicyApplication {
  // Original values
  originalConfidence: number;
  originalRiskMultiplier: number;
  
  // Adjusted values
  adjustedConfidence: number;
  adjustedRiskMultiplier: number;
  
  // Policy info
  memoryStrength: MemoryStrength;
  policyApplied: boolean;
  policyDetails: MemoryPolicy;
}

// ═══════════════════════════════════════════════════════════════
// STORAGE TYPES
// ═══════════════════════════════════════════════════════════════

export interface MemoryPolicyRecord {
  asset: string;
  timeframe: string;
  ts: number;
  
  context: MemoryContext;
  policy: MemoryPolicy;
  strength: MemoryStrength;
  
  // Metadata
  createdAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// API TYPES
// ═══════════════════════════════════════════════════════════════

export interface MemoryPolicyResponse {
  success: boolean;
  data?: {
    context: MemoryContext;
    policy: MemoryPolicy;
    strength: MemoryStrength;
  };
  error?: string;
}

export interface MemoryPolicyRecomputeResponse {
  success: boolean;
  data?: {
    asset: string;
    timeframe: string;
    policy: MemoryPolicy;
    recomputedAt: Date;
  };
  error?: string;
}
