/**
 * P1.4 — Time-based Split + Purging
 * 
 * Proper train/val/test split to avoid data leakage:
 * - Train: 2017-2022
 * - Validation: 2023
 * - Test: 2024
 * - Purge window: remove N bars around boundaries
 */

import { DatasetV4Config, DEFAULT_DATASET_V4_CONFIG, DatasetRowV4 } from './labels_v4.types.js';

export type SplitType = 'train' | 'val' | 'test' | 'purge';

export interface SplitResult {
  train: DatasetRowV4[];
  val: DatasetRowV4[];
  test: DatasetRowV4[];
  purged: DatasetRowV4[];
  stats: SplitStats;
}

export interface SplitStats {
  total: number;
  trainCount: number;
  valCount: number;
  testCount: number;
  purgedCount: number;
  trainPct: number;
  valPct: number;
  testPct: number;
}

/**
 * Determine split for a single row based on timestamp
 */
export function determineSplit(
  timestamp: Date,
  barIndex: number,  // for purge calculation
  config: DatasetV4Config = DEFAULT_DATASET_V4_CONFIG
): SplitType {
  const { trainEndDate, valEndDate, testEndDate, purgeWindowBars } = config.splitConfig;
  
  const ts = timestamp.getTime();
  const trainEnd = trainEndDate.getTime();
  const valEnd = valEndDate.getTime();
  const testEnd = testEndDate?.getTime() || Date.now();
  
  // Check if in purge window around boundaries
  // This is simplified - in production you'd calculate actual bar distances
  const msPerBar = getApproxMsPerBar('1d');  // Use 1d as baseline
  const purgeMs = purgeWindowBars * msPerBar;
  
  // Purge zones
  const isNearTrainEnd = Math.abs(ts - trainEnd) < purgeMs;
  const isNearValEnd = Math.abs(ts - valEnd) < purgeMs;
  
  if (isNearTrainEnd || isNearValEnd) {
    return 'purge';
  }
  
  // Assign to splits
  if (ts <= trainEnd) {
    return 'train';
  } else if (ts <= valEnd) {
    return 'val';
  } else if (ts <= testEnd) {
    return 'test';
  }
  
  return 'test';  // Future data goes to test
}

/**
 * Split dataset with purging
 */
export function splitDataset(
  rows: DatasetRowV4[],
  config: DatasetV4Config = DEFAULT_DATASET_V4_CONFIG
): SplitResult {
  const train: DatasetRowV4[] = [];
  const val: DatasetRowV4[] = [];
  const test: DatasetRowV4[] = [];
  const purged: DatasetRowV4[] = [];
  
  // Sort by timestamp
  const sorted = [...rows].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
  
  for (let i = 0; i < sorted.length; i++) {
    const row = sorted[i];
    const split = determineSplit(row.timestamp, i, config);
    
    row.split = split === 'purge' ? undefined : split;
    
    switch (split) {
      case 'train': train.push(row); break;
      case 'val': val.push(row); break;
      case 'test': test.push(row); break;
      case 'purge': purged.push(row); break;
    }
  }
  
  const total = rows.length;
  const nonPurged = total - purged.length;
  
  return {
    train,
    val,
    test,
    purged,
    stats: {
      total,
      trainCount: train.length,
      valCount: val.length,
      testCount: test.length,
      purgedCount: purged.length,
      trainPct: nonPurged > 0 ? train.length / nonPurged : 0,
      valPct: nonPurged > 0 ? val.length / nonPurged : 0,
      testPct: nonPurged > 0 ? test.length / nonPurged : 0,
    },
  };
}

/**
 * Approximate ms per bar for different timeframes
 */
function getApproxMsPerBar(tf: string): number {
  const tfLower = tf.toLowerCase();
  const hour = 3600 * 1000;
  const day = 24 * hour;
  
  if (tfLower.includes('1m')) return 60 * 1000;
  if (tfLower.includes('5m')) return 5 * 60 * 1000;
  if (tfLower.includes('15m')) return 15 * 60 * 1000;
  if (tfLower.includes('1h')) return hour;
  if (tfLower.includes('4h')) return 4 * hour;
  if (tfLower.includes('1d') || tfLower.includes('daily')) return day;
  if (tfLower.includes('1w')) return 7 * day;
  
  return day;  // default to daily
}

/**
 * Validate split doesn't have leakage
 */
export function validateSplit(result: SplitResult): {
  valid: boolean;
  issues: string[];
} {
  const issues: string[] = [];
  
  // Check chronological order
  const trainMaxTs = result.train.length > 0 
    ? Math.max(...result.train.map(r => r.timestamp.getTime()))
    : 0;
  const valMinTs = result.val.length > 0
    ? Math.min(...result.val.map(r => r.timestamp.getTime()))
    : Infinity;
  const valMaxTs = result.val.length > 0
    ? Math.max(...result.val.map(r => r.timestamp.getTime()))
    : 0;
  const testMinTs = result.test.length > 0
    ? Math.min(...result.test.map(r => r.timestamp.getTime()))
    : Infinity;
  
  if (trainMaxTs >= valMinTs) {
    issues.push('Train data overlaps with validation data (potential leakage)');
  }
  
  if (valMaxTs >= testMinTs) {
    issues.push('Validation data overlaps with test data (potential leakage)');
  }
  
  // Check reasonable split sizes
  if (result.stats.trainPct < 0.5) {
    issues.push('Train set is less than 50% of data');
  }
  
  if (result.stats.purgedCount > result.stats.total * 0.2) {
    issues.push('More than 20% of data was purged');
  }
  
  return {
    valid: issues.length === 0,
    issues,
  };
}

/**
 * Get split boundaries for display
 */
export function getSplitBoundaries(config: DatasetV4Config = DEFAULT_DATASET_V4_CONFIG): {
  trainStart: string;
  trainEnd: string;
  valStart: string;
  valEnd: string;
  testStart: string;
  testEnd: string;
  purgeWindow: number;
} {
  const { trainEndDate, valEndDate, testEndDate, purgeWindowBars } = config.splitConfig;
  
  return {
    trainStart: '2017-01-01',
    trainEnd: trainEndDate.toISOString().split('T')[0],
    valStart: new Date(trainEndDate.getTime() + 1).toISOString().split('T')[0],
    valEnd: valEndDate.toISOString().split('T')[0],
    testStart: new Date(valEndDate.getTime() + 1).toISOString().split('T')[0],
    testEnd: testEndDate?.toISOString().split('T')[0] || 'present',
    purgeWindow: purgeWindowBars,
  };
}
