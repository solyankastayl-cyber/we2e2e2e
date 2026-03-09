/**
 * MetaBrain v1 — Types
 * 
 * Global policy layer for system control
 */

// ═══════════════════════════════════════════════════════════════
// RISK MODES
// ═══════════════════════════════════════════════════════════════

export type MetaRiskMode = 'CONSERVATIVE' | 'NORMAL' | 'AGGRESSIVE';

export const RISK_MODE_CONFIG: Record<MetaRiskMode, {
  baseRiskPct: number;
  confidenceThreshold: number;
  strategyMultiplier: number;
  riskMultiplier: number;
  description: string;
}> = {
  CONSERVATIVE: {
    baseRiskPct: 0.3,
    confidenceThreshold: 0.65,
    strategyMultiplier: 0.8,
    riskMultiplier: 0.6,
    description: 'Reduced risk exposure during unfavorable conditions'
  },
  NORMAL: {
    baseRiskPct: 0.5,
    confidenceThreshold: 0.55,
    strategyMultiplier: 1.0,
    riskMultiplier: 1.0,
    description: 'Standard operating mode'
  },
  AGGRESSIVE: {
    baseRiskPct: 1.0,
    confidenceThreshold: 0.50,
    strategyMultiplier: 1.2,
    riskMultiplier: 1.3,
    description: 'Enhanced position sizing during favorable conditions'
  }
};

// ═══════════════════════════════════════════════════════════════
// META BRAIN CONTEXT
// ═══════════════════════════════════════════════════════════════

export type VolatilityLevel = 'LOW' | 'NORMAL' | 'HIGH' | 'EXTREME';

export interface MetaBrainContext {
  // From Regime Intelligence
  regime: string;
  regimeConfidence: number;
  
  // From State Machine
  state: string;
  
  // From Physics Engine
  volatility: VolatilityLevel;
  volatilityValue: number;
  
  // From Execution Portfolio
  drawdownPct: number;
  portfolioRiskPct: number;
  openPositions: number;
  
  // From Edge Intelligence
  edgeHealth: number;  // 0-1, based on recent edge stats
  
  // From Strategy Builder
  bestStrategyScore: number;
  activeStrategiesCount: number;
  
  // From Governance
  governanceFrozen: boolean;
  
  // Derived
  marketCondition: 'FAVORABLE' | 'NEUTRAL' | 'UNFAVORABLE';
  
  // Timestamp
  computedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// META BRAIN DECISION
// ═══════════════════════════════════════════════════════════════

export interface MetaBrainDecision {
  // Core decision
  riskMode: MetaRiskMode;
  
  // Thresholds
  confidenceThreshold: number;
  scenarioProbabilityThreshold: number;
  
  // Multipliers for downstream modules
  strategyMultiplier: number;
  riskMultiplier: number;
  
  // Reasons
  reason: string[];
  
  // Applied limits
  effectiveBaseRisk: number;
  
  // Status
  isOverride: boolean;
  overrideReason?: string;
  
  // Timestamp
  decidedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// META BRAIN ACTION LOG
// ═══════════════════════════════════════════════════════════════

export interface MetaBrainAction {
  actionId: string;
  timestamp: Date;
  
  // Action type
  actionType: 'SET_RISK_MODE' | 'UPDATE_THRESHOLD' | 'ADJUST_MULTIPLIER' | 'STRATEGY_CONTROL' | 'SYSTEM_PAUSE';
  
  // Before/After
  from: any;
  to: any;
  
  // Context
  contextSnapshot: Partial<MetaBrainContext>;
  
  // Reason
  reason: string[];
}

// ═══════════════════════════════════════════════════════════════
// META BRAIN STATE
// ═══════════════════════════════════════════════════════════════

export interface MetaBrainState {
  // Current state
  currentRiskMode: MetaRiskMode;
  currentDecision: MetaBrainDecision;
  currentContext: MetaBrainContext;
  
  // History
  riskModeHistory: Array<{ mode: MetaRiskMode; at: Date; reason: string[] }>;
  
  // Counters
  totalDecisions: number;
  modeChangesToday: number;
  
  // Health
  systemHealth: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
  
  // Updated
  updatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

export interface MetaBrainConfig {
  // Thresholds for CONSERVATIVE
  conservativeDrawdownThreshold: number;
  conservativeEdgeHealthThreshold: number;
  
  // Thresholds for AGGRESSIVE
  aggressiveDrawdownThreshold: number;
  aggressiveEdgeHealthThreshold: number;
  aggressiveStrategyScoreThreshold: number;
  
  // Rate limits
  maxModeChangesPerDay: number;
  minTimeBetweenChanges: number;  // minutes
  
  // Default values
  defaultRiskMode: MetaRiskMode;
}

export const DEFAULT_METABRAIN_CONFIG: MetaBrainConfig = {
  conservativeDrawdownThreshold: 0.08,
  conservativeEdgeHealthThreshold: 0.35,
  aggressiveDrawdownThreshold: 0.03,
  aggressiveEdgeHealthThreshold: 0.65,
  aggressiveStrategyScoreThreshold: 1.2,
  maxModeChangesPerDay: 3,
  minTimeBetweenChanges: 60,
  defaultRiskMode: 'NORMAL'
};
