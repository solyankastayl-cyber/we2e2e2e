/**
 * Phase 5.2 B4 — Calibration Engine Types
 */

// ═══════════════════════════════════════════════════════════════
// Model Types
// ═══════════════════════════════════════════════════════════════

export type CalibrationModelType = 'ISOTONIC' | 'PLATT';

export interface CalibrationModelDoc {
  _id?: any;
  modelId: string;
  modelType: CalibrationModelType;
  version: string;
  
  trainedAt: Date;
  sampleSize: number;
  
  input: string;           // "probabilityRaw"
  output: string;          // "probabilityCalibrated"
  
  // Isotonic regression params (piecewise linear)
  params: {
    x: number[];           // Input breakpoints
    y: number[];           // Output values at breakpoints
  };
  
  // Metrics
  metrics: {
    ece: number;           // Expected Calibration Error
    brier: number;         // Brier Score
    reliability: ReliabilityBucket[];
  };
  
  // Config used for training
  config: {
    minSamples: number;
    excludeNoEntry: boolean;
    excludeTimeout: boolean;
  };
}

// ═══════════════════════════════════════════════════════════════
// Reliability Buckets
// ═══════════════════════════════════════════════════════════════

export interface ReliabilityBucket {
  range: string;           // "0.4-0.5"
  predictedWin: number;    // Average predicted probability
  actualWin: number;       // Actual win rate
  count: number;           // Number of samples
  gap: number;             // predicted - actual
}

// ═══════════════════════════════════════════════════════════════
// Training Request
// ═══════════════════════════════════════════════════════════════

export interface CalibrationTrainRequest {
  minSamples?: number;     // Default 5000
  excludeNoEntry?: boolean;
  excludeTimeout?: boolean;
  source?: 'backtest' | 'outcomes';  // Data source
}

// ═══════════════════════════════════════════════════════════════
// Calibration Result
// ═══════════════════════════════════════════════════════════════

export interface CalibrationResult {
  pRaw: number;
  pCalibrated: number;
  modelVersion: string;
  interpolated: boolean;
}

// ═══════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════

export const CALIBRATION_COLLECTION = 'ta_calibration_models';

export const DEFAULT_CALIBRATION_CONFIG = {
  minSamples: 5000,
  excludeNoEntry: true,
  excludeTimeout: false,
};
