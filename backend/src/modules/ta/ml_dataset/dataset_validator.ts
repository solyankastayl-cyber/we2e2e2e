/**
 * Dataset Validator Job
 * 
 * Validates ML dataset for:
 * - Missing features
 * - NaN values
 * - Distribution drift
 */

import { Db } from 'mongodb';

export interface DatasetStats {
  totalRows: number;
  validRows: number;
  invalidRows: number;
  missingFeatures: Record<string, number>;
  nanCounts: Record<string, number>;
  distributionStats: Record<string, { mean: number; std: number; min: number; max: number }>;
  schemaHash?: string;
  timestamp: Date;
}

const REQUIRED_FEATURES = [
  'score', 'confidence', 'risk_reward', 'gate_score',
  'geom_fit_error', 'geom_maturity', 'geom_compression', 'geom_symmetry',
  'graph_boost_factor', 'graph_lift', 'graph_conditional_prob',
  'pattern_strength', 'pattern_duration', 'volatility', 'atr_ratio',
  'regime_trend_up', 'regime_trend_down', 'regime_range'
];

export class DatasetValidator {
  private db: Db;
  private collectionName = 'ta_ml_rows_v4';
  private statsCollectionName = 'ta_dataset_stats';

  constructor(db: Db) {
    this.db = db;
  }

  async ensureIndexes(): Promise<void> {
    await this.db.collection(this.statsCollectionName).createIndex(
      { timestamp: -1 }
    );
  }

  /**
   * Run full dataset validation
   */
  async validate(): Promise<DatasetStats> {
    const collection = this.db.collection(this.collectionName);
    
    const missingFeatures: Record<string, number> = {};
    const nanCounts: Record<string, number> = {};
    const featureValues: Record<string, number[]> = {};

    // Initialize
    for (const f of REQUIRED_FEATURES) {
      missingFeatures[f] = 0;
      nanCounts[f] = 0;
      featureValues[f] = [];
    }

    // Scan all rows
    const cursor = collection.find({});
    let totalRows = 0;
    let validRows = 0;
    let invalidRows = 0;

    while (await cursor.hasNext()) {
      const row = await cursor.next();
      if (!row) continue;
      
      totalRows++;
      let isValid = true;

      for (const f of REQUIRED_FEATURES) {
        const value = row[f];
        
        if (value === undefined || value === null) {
          missingFeatures[f]++;
          isValid = false;
        } else if (typeof value === 'number' && isNaN(value)) {
          nanCounts[f]++;
          isValid = false;
        } else if (typeof value === 'number') {
          featureValues[f].push(value);
        }
      }

      if (isValid) validRows++;
      else invalidRows++;
    }

    // Calculate distribution stats
    const distributionStats: Record<string, { mean: number; std: number; min: number; max: number }> = {};
    
    for (const f of REQUIRED_FEATURES) {
      const values = featureValues[f];
      if (values.length === 0) {
        distributionStats[f] = { mean: 0, std: 0, min: 0, max: 0 };
        continue;
      }

      const mean = values.reduce((a, b) => a + b, 0) / values.length;
      const variance = values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length;
      const std = Math.sqrt(variance);
      const min = Math.min(...values);
      const max = Math.max(...values);

      distributionStats[f] = { mean, std, min, max };
    }

    // Generate schema hash
    const schemaHash = this.generateSchemaHash();

    const stats: DatasetStats = {
      totalRows,
      validRows,
      invalidRows,
      missingFeatures,
      nanCounts,
      distributionStats,
      schemaHash,
      timestamp: new Date()
    };

    // Save stats
    await this.db.collection(this.statsCollectionName).insertOne(stats);

    return stats;
  }

  /**
   * Get latest stats
   */
  async getLatestStats(): Promise<DatasetStats | null> {
    const stats = await this.db.collection(this.statsCollectionName)
      .findOne({}, { sort: { timestamp: -1 } });
    return stats as DatasetStats | null;
  }

  /**
   * Check for drift against baseline
   */
  async checkDrift(threshold = 0.5): Promise<{
    hasDrift: boolean;
    driftFeatures: string[];
    details: Record<string, { baseline: number; current: number; drift: number }>;
  }> {
    // Get baseline (first stats)
    const baseline = await this.db.collection(this.statsCollectionName)
      .findOne({}, { sort: { timestamp: 1 } }) as DatasetStats | null;
    
    if (!baseline) {
      return { hasDrift: false, driftFeatures: [], details: {} };
    }

    // Get current stats
    const current = await this.getLatestStats();
    if (!current) {
      return { hasDrift: false, driftFeatures: [], details: {} };
    }

    const driftFeatures: string[] = [];
    const details: Record<string, { baseline: number; current: number; drift: number }> = {};

    for (const f of REQUIRED_FEATURES) {
      const baselineMean = baseline.distributionStats[f]?.mean || 0;
      const currentMean = current.distributionStats[f]?.mean || 0;
      const baselineStd = baseline.distributionStats[f]?.std || 1;

      const drift = Math.abs(currentMean - baselineMean) / (baselineStd || 1);

      details[f] = {
        baseline: baselineMean,
        current: currentMean,
        drift
      };

      if (drift > threshold) {
        driftFeatures.push(f);
      }
    }

    return {
      hasDrift: driftFeatures.length > 0,
      driftFeatures,
      details
    };
  }

  private generateSchemaHash(): string {
    // Simple hash based on feature names
    const featureStr = REQUIRED_FEATURES.sort().join(',');
    let hash = 0;
    for (let i = 0; i < featureStr.length; i++) {
      const char = featureStr.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return `v1.0.0-${Math.abs(hash).toString(16).substring(0, 8)}`;
  }
}

// Singleton
let validatorInstance: DatasetValidator | null = null;

export function getDatasetValidator(db: Db): DatasetValidator {
  if (!validatorInstance) {
    validatorInstance = new DatasetValidator(db);
  }
  return validatorInstance;
}
