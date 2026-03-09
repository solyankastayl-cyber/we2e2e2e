/**
 * Probability Calibration (P4.2)
 * 
 * Calibration methods for ML probabilities
 * Uses Platt scaling approximation
 */

import { Db } from 'mongodb';

export interface CalibrationParams {
  a: number;  // Slope
  b: number;  // Intercept
}

/**
 * Default calibration params (identity)
 */
const DEFAULT_PARAMS: CalibrationParams = { a: 1, b: 0 };

/**
 * Apply Platt scaling
 * Transforms raw probability using sigmoid: 1 / (1 + exp(-(a*p + b)))
 */
export function plattScale(p: number, params: CalibrationParams): number {
  const z = params.a * p + params.b;
  return 1 / (1 + Math.exp(-z));
}

/**
 * Simple isotonic-like adjustment
 * Pulls extreme probabilities toward center
 */
export function isotonicAdjust(p: number, shrinkage: number = 0.1): number {
  // Pull toward 0.5
  const adjusted = p + shrinkage * (0.5 - p);
  return Math.max(0.01, Math.min(0.99, adjusted));
}

/**
 * Calibration Engine
 */
export class CalibrationEngine {
  private db: Db;
  private collectionName = 'ta_calibration_params';
  private historyCollection = 'ta_calibration_history';
  
  constructor(db: Db) {
    this.db = db;
  }

  async ensureIndexes(): Promise<void> {
    await this.db.collection(this.collectionName).createIndex({ modelId: 1 }, { unique: true });
    await this.db.collection(this.historyCollection).createIndex({ timestamp: -1 });
  }

  /**
   * Get calibration params for a model
   */
  async getParams(modelId: string): Promise<CalibrationParams> {
    const doc = await this.db.collection(this.collectionName)
      .findOne({ modelId });
    
    if (doc) {
      return { a: doc.a, b: doc.b };
    }
    
    return DEFAULT_PARAMS;
  }

  /**
   * Calibrate probability
   */
  async calibrate(p: number, modelId?: string): Promise<{ calibrated: number; method: string }> {
    if (!modelId) {
      // Use simple shrinkage
      return {
        calibrated: isotonicAdjust(p, 0.1),
        method: 'isotonic_shrinkage'
      };
    }
    
    const params = await this.getParams(modelId);
    
    if (params.a === 1 && params.b === 0) {
      // No calibration params, use shrinkage
      return {
        calibrated: isotonicAdjust(p, 0.1),
        method: 'isotonic_shrinkage'
      };
    }
    
    return {
      calibrated: plattScale(p, params),
      method: 'platt_scaling'
    };
  }

  /**
   * Update calibration params from outcomes
   * Simple online update using exponential moving average
   */
  async updateFromOutcome(
    modelId: string,
    predicted: number,
    actual: number
  ): Promise<void> {
    // Log to history
    await this.db.collection(this.historyCollection).insertOne({
      modelId,
      predicted,
      actual,
      timestamp: new Date()
    });

    // Get recent history
    const history = await this.db.collection(this.historyCollection)
      .find({ modelId })
      .sort({ timestamp: -1 })
      .limit(500)
      .toArray();

    if (history.length < 50) {
      // Not enough data to calibrate
      return;
    }

    // Simple Platt scaling estimation
    // Using logistic regression approximation
    const predictions = history.map(h => h.predicted);
    const actuals = history.map(h => h.actual);

    // Mean and variance
    const meanP = predictions.reduce((a, b) => a + b, 0) / predictions.length;
    const meanA = actuals.reduce((a, b) => a + b, 0) / actuals.length;
    
    // Covariance and variance
    let cov = 0;
    let varP = 0;
    for (let i = 0; i < predictions.length; i++) {
      cov += (predictions[i] - meanP) * (actuals[i] - meanA);
      varP += Math.pow(predictions[i] - meanP, 2);
    }
    
    // Linear regression slope
    const a = varP > 0 ? cov / varP : 1;
    const b = meanA - a * meanP;

    // Update params
    await this.db.collection(this.collectionName).updateOne(
      { modelId },
      { $set: { a, b, updatedAt: new Date() } },
      { upsert: true }
    );
  }
}

// Singleton
let calibrationEngine: CalibrationEngine | null = null;

export function getCalibrationEngine(db: Db): CalibrationEngine {
  if (!calibrationEngine) {
    calibrationEngine = new CalibrationEngine(db);
  }
  return calibrationEngine;
}
