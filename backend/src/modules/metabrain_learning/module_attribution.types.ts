/**
 * MetaBrain v2.1 — Module Attribution Types
 * 
 * Learning layer for analyzing which modules contribute to performance
 */

// ═══════════════════════════════════════════════════════════════
// MODULE TYPES
// ═══════════════════════════════════════════════════════════════

export type AnalysisModule =
  | 'PATTERN'
  | 'LIQUIDITY'
  | 'GRAPH'
  | 'FRACTAL'
  | 'PHYSICS'
  | 'STATE'
  | 'REGIME'
  | 'SCENARIO';

export const ALL_MODULES: AnalysisModule[] = [
  'PATTERN',
  'LIQUIDITY',
  'GRAPH',
  'FRACTAL',
  'PHYSICS',
  'STATE',
  'REGIME',
  'SCENARIO'
];

// ═══════════════════════════════════════════════════════════════
// MODULE CONTRIBUTION
// ═══════════════════════════════════════════════════════════════

export interface ModuleContribution {
  module: AnalysisModule;
  
  // Performance metrics
  winRate: number;
  avgR: number;
  profitFactor: number;
  sharpe: number;
  
  // Sample
  sampleSize: number;
  confidence: number;
  
  // Edge score (0-3 scale)
  edgeScore: number;
  
  // Impact direction
  impact: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  
  // Calculated at
  calculatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// MODULE ATTRIBUTION RESULT
// ═══════════════════════════════════════════════════════════════

export interface ModuleAttributionResult {
  // Context
  asset?: string;
  timeframe?: string;
  regime?: string;
  
  // Global baseline
  baseline: {
    winRate: number;
    avgR: number;
    profitFactor: number;
    totalTrades: number;
  };
  
  // Per-module contributions
  modules: ModuleContribution[];
  
  // Rankings
  topModules: AnalysisModule[];
  weakModules: AnalysisModule[];
  
  // Meta
  calculatedAt: Date;
  dataWindowDays: number;
}

// ═══════════════════════════════════════════════════════════════
// MODULE WEIGHT
// ═══════════════════════════════════════════════════════════════

export interface ModuleWeight {
  module: AnalysisModule;
  
  // Weight (0.4 - 1.6)
  weight: number;
  rawWeight: number;
  
  // Confidence in weight
  confidence: number;
  
  // Based on
  basedOnSample: number;
  basedOnEdgeScore: number;
  
  // Regime-specific (optional)
  regime?: string;
  
  // Updated
  updatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// WEIGHT HISTORY
// ═══════════════════════════════════════════════════════════════

export interface ModuleWeightHistory {
  module: AnalysisModule;
  weight: number;
  regime?: string;
  reason: string;
  changedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// LEARNING CONFIG
// ═══════════════════════════════════════════════════════════════

export interface LearningConfig {
  // Minimum sample size for attribution
  minSampleSize: number;
  
  // Shrinkage toward 1.0
  shrinkageStrength: number;
  
  // Weight bounds
  minWeight: number;
  maxWeight: number;
  
  // Max weight change per day
  maxDailyChange: number;
  
  // Data window
  dataWindowDays: number;
  
  // Regime-specific learning
  regimeSpecificLearning: boolean;
}

export const DEFAULT_LEARNING_CONFIG: LearningConfig = {
  minSampleSize: 50,
  shrinkageStrength: 0.5,
  minWeight: 0.4,
  maxWeight: 1.6,
  maxDailyChange: 0.05,
  dataWindowDays: 180,
  regimeSpecificLearning: false
};

// ═══════════════════════════════════════════════════════════════
// ATTRIBUTION SOURCE DATA
// ═══════════════════════════════════════════════════════════════

export interface AttributionTradeRecord {
  tradeId: string;
  asset: string;
  timeframe: string;
  
  // Result
  resultR: number;
  outcome: 'WIN' | 'LOSS' | 'BREAKEVEN';
  
  // Module activations (which modules were active/high for this trade)
  moduleActivations: {
    module: AnalysisModule;
    value: string;  // e.g., pattern name, state name
    boost: number;  // The boost/score this module gave
  }[];
  
  // Context
  regime?: string;
  
  // Timestamp
  entryTime: Date;
}
