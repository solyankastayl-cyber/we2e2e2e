/**
 * Probability Types (P4.2)
 * 
 * Contracts for probability composition
 */

/**
 * Source breakdown showing contribution from each component
 */
export interface SourceBreakdown {
  ml: number;
  scenario: number;
  priors: number;
  stability: number;
}

/**
 * Input from ML model
 */
export interface MLProbabilityInput {
  pEntry: number;
  expectedR: number;
  confidence: number;
  modelId?: string;
}

/**
 * Input from Scenario/Monte Carlo
 */
export interface ScenarioProbabilityInput {
  pTarget: number;
  pStop: number;
  pTimeout: number;
  p10: number;
  p50: number;
  p90: number;
  paths?: number;
}

/**
 * Input from Pattern Priors
 */
export interface PriorsProbabilityInput {
  pEntry: number;
  winRate: number;
  profitFactor: number;
  sampleSize: number;
  patternId?: string;
}

/**
 * Input from Stability Engine
 */
export interface StabilityInput {
  multiplier: number;
  pf30: number;
  pf100: number;
  degrading: boolean;
}

/**
 * Weights for composition
 */
export interface CompositionWeights {
  ml: number;
  scenario: number;
  priors: number;
}

/**
 * ProbabilityPack - Final composed probability output
 */
export interface ProbabilityPack {
  // Core probabilities
  pEntry: number;
  pWin: number;
  pStop: number;
  pTimeout: number;
  
  // Expectations
  expectedR: number;
  EV: number;
  
  // Breakdown
  sourceBreakdown: SourceBreakdown;
  weights: CompositionWeights;
  
  // Method used
  compositionMethod: 'WEIGHTED_AVERAGE' | 'BAYESIAN' | 'ENSEMBLE' | 'FALLBACK';
  
  // Calibration
  calibrated: boolean;
  calibrationMethod?: string;
  
  // Confidence
  confidence: number;
}

/**
 * Input for composition
 */
export interface ComposeProbabilityInput {
  ml: MLProbabilityInput | null;
  scenario: ScenarioProbabilityInput | null;
  priors: PriorsProbabilityInput | null;
  stability: StabilityInput | null;
}

/**
 * Calibration record
 */
export interface CalibrationRecord {
  predicted: number;
  actual: number;
  timestamp: Date;
}

/**
 * Probability metrics for logging
 */
export interface ProbabilityMetrics {
  runId: string;
  asset: string;
  timeframe: string;
  pEntryPredicted: number;
  pWinPredicted: number;
  compositionMethod: string;
  weights: CompositionWeights;
  timestamp: Date;
}
