/**
 * P1.3 — Labels V4 Types (EV Decomposition)
 * 
 * Split prediction into:
 * 1. P(entry) - probability of entry hit
 * 2. E[r|entry] - expected R-multiple given entry
 * 
 * EV = P(entry) × E[r|entry]
 */

export interface LabelsV4 {
  // Entry prediction
  label_entry_hit: 0 | 1;           // 1 if entry was hit, 0 otherwise
  label_entry_probability?: number;  // predicted P(entry)
  
  // R-multiple regression targets
  label_r_multiple: number;          // realized R (capped)
  label_mfe_r: number;               // max favorable excursion in R
  label_mae_r: number;               // max adverse excursion in R
  
  // Time targets
  label_time_to_entry: number;       // bars until entry (or timeout)
  label_time_to_exit: number;        // bars until exit
  
  // Derived
  label_ev?: number;                 // P(entry) × E[r|entry]
  
  // Classification helpers
  label_outcome_class: OutcomeClassV4;
}

export type OutcomeClassV4 = 
  | 'NO_ENTRY'      // Entry never hit
  | 'WIN'           // R >= 1.5
  | 'PARTIAL'       // 0 < R < 1.5
  | 'LOSS'          // R <= -1
  | 'TIMEOUT';      // Entry hit but no clear outcome

export interface DatasetRowV4 {
  rowId: string;
  scenarioId: string;
  asset: string;
  timeframe: string;
  timestamp: Date;
  
  // Features
  features: Record<string, number>;
  
  // Labels V4
  labels: LabelsV4;
  
  // Metadata
  regime?: string;
  split?: 'train' | 'val' | 'test';
  featureSchemaVersion: string;
}

export interface DatasetV4Config {
  // R-multiple capping
  rMultipleCap: { min: number; max: number };  // [-2, +4] typical
  
  // Time-based split
  splitConfig: {
    trainEndDate: Date;      // 2022-12-31
    valEndDate: Date;        // 2023-12-31
    testEndDate?: Date;      // 2024-12-31
    purgeWindowBars: number; // 30-60 bars
  };
  
  // Feature schema
  featureSchemaVersion: string;
}

export const DEFAULT_DATASET_V4_CONFIG: DatasetV4Config = {
  rMultipleCap: { min: -2, max: 4 },
  splitConfig: {
    trainEndDate: new Date('2022-12-31'),
    valEndDate: new Date('2023-12-31'),
    testEndDate: new Date('2024-12-31'),
    purgeWindowBars: 30,
  },
  featureSchemaVersion: '4.0',
};

/**
 * EV calculation
 */
export interface EVPrediction {
  pEntry: number;        // P(entry)
  rExpected: number;     // E[r|entry]
  ev: number;            // EV = pEntry × rExpected
  confidence: number;    // model confidence
  regime?: string;
}

/**
 * Model performance metrics
 */
export interface ModelMetricsV4 {
  // Entry model
  entryAuc: number;
  entryAccuracy: number;
  entryPrecision: number;
  entryRecall: number;
  
  // R regression model
  rRmse: number;
  rMae: number;
  rR2: number;
  
  // Combined EV metrics
  evCorrelation: number;
  profitFactor: number;
}
