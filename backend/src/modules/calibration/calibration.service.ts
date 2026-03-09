/**
 * Phase 5.2 B4 — Calibration Service (Runtime)
 * 
 * Applies trained calibration model to raw probabilities
 */

import { Db } from 'mongodb';
import {
  CalibrationModelDoc,
  CalibrationResult,
} from './calibration.types.js';
import { getCalibrationStorage, CalibrationStorage } from './calibration.train.js';

// ═══════════════════════════════════════════════════════════════
// Calibration Service
// ═══════════════════════════════════════════════════════════════

export class CalibrationService {
  private db: Db;
  private storage: CalibrationStorage;
  private cachedModel: CalibrationModelDoc | null = null;
  private cacheTime: number = 0;
  private cacheTTL: number = 60000;  // 1 minute

  constructor(db: Db) {
    this.db = db;
    this.storage = getCalibrationStorage(db);
  }

  /**
   * Calibrate a raw probability
   */
  async calibrate(pRaw: number): Promise<CalibrationResult> {
    // Ensure model is loaded
    const model = await this.getModel();

    if (!model) {
      // No model - return raw probability
      return {
        pRaw,
        pCalibrated: pRaw,
        modelVersion: 'NONE',
        interpolated: false,
      };
    }

    // Apply calibration
    const pCalibrated = this.applyModel(pRaw, model);

    return {
      pRaw,
      pCalibrated,
      modelVersion: model.version,
      interpolated: true,
    };
  }

  /**
   * Calibrate multiple probabilities
   */
  async calibrateBatch(pRaws: number[]): Promise<CalibrationResult[]> {
    const model = await this.getModel();

    if (!model) {
      return pRaws.map(pRaw => ({
        pRaw,
        pCalibrated: pRaw,
        modelVersion: 'NONE',
        interpolated: false,
      }));
    }

    return pRaws.map(pRaw => ({
      pRaw,
      pCalibrated: this.applyModel(pRaw, model),
      modelVersion: model.version,
      interpolated: true,
    }));
  }

  /**
   * Get current model status
   */
  async getStatus(): Promise<{
    hasModel: boolean;
    version?: string;
    trainedAt?: Date;
    sampleSize?: number;
    ece?: number;
    brier?: number;
  }> {
    const model = await this.getModel();

    if (!model) {
      return { hasModel: false };
    }

    return {
      hasModel: true,
      version: model.version,
      trainedAt: model.trainedAt,
      sampleSize: model.sampleSize,
      ece: model.metrics.ece,
      brier: model.metrics.brier,
    };
  }

  /**
   * Get reliability buckets from current model
   */
  async getReliability(): Promise<any[]> {
    const model = await this.getModel();
    return model?.metrics.reliability || [];
  }

  /**
   * Clear cache to force reload
   */
  clearCache(): void {
    this.cachedModel = null;
    this.cacheTime = 0;
  }

  // ─────────────────────────────────────────────────────────────
  // Private Methods
  // ─────────────────────────────────────────────────────────────

  private async getModel(): Promise<CalibrationModelDoc | null> {
    const now = Date.now();

    // Check cache
    if (this.cachedModel && (now - this.cacheTime) < this.cacheTTL) {
      return this.cachedModel;
    }

    // Load from storage
    this.cachedModel = await this.storage.getLatestModel();
    this.cacheTime = now;

    return this.cachedModel;
  }

  /**
   * Apply isotonic regression model (piecewise linear interpolation)
   */
  private applyModel(pRaw: number, model: CalibrationModelDoc): number {
    const { x, y } = model.params;

    if (x.length === 0) return pRaw;

    // Clamp to [0, 1]
    pRaw = Math.max(0, Math.min(1, pRaw));

    // Find interpolation segment
    if (pRaw <= x[0]) return y[0];
    if (pRaw >= x[x.length - 1]) return y[y.length - 1];

    // Binary search for segment
    let left = 0;
    let right = x.length - 1;

    while (left < right - 1) {
      const mid = Math.floor((left + right) / 2);
      if (x[mid] <= pRaw) {
        left = mid;
      } else {
        right = mid;
      }
    }

    // Linear interpolation
    const x0 = x[left];
    const x1 = x[right];
    const y0 = y[left];
    const y1 = y[right];

    if (x1 === x0) return y0;

    const t = (pRaw - x0) / (x1 - x0);
    const pCalibrated = y0 + t * (y1 - y0);

    // Ensure monotonicity and bounds
    return Math.max(0, Math.min(1, pCalibrated));
  }
}

// ═══════════════════════════════════════════════════════════════
// Singleton
// ═══════════════════════════════════════════════════════════════

let serviceInstance: CalibrationService | null = null;

export function getCalibrationService(db: Db): CalibrationService {
  if (!serviceInstance) {
    serviceInstance = new CalibrationService(db);
  }
  return serviceInstance;
}
