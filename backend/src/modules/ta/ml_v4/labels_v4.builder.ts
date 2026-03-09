/**
 * P1.3 — Labels V4 Builder
 * 
 * Converts OutcomeV3 to LabelsV4 for EV decomposition
 */

import { OutcomeV3 } from '../outcomes_v3/labels_v3.types.js';
import { 
  LabelsV4, 
  OutcomeClassV4, 
  DatasetV4Config, 
  DEFAULT_DATASET_V4_CONFIG 
} from './labels_v4.types.js';

/**
 * Build Labels V4 from Outcome V3
 */
export function buildLabelsV4(
  outcome: OutcomeV3,
  config: DatasetV4Config = DEFAULT_DATASET_V4_CONFIG
): LabelsV4 {
  // Entry hit
  const label_entry_hit: 0 | 1 = outcome.entryHit ? 1 : 0;
  
  // Cap R-multiple
  const rawR = outcome.rMultiple;
  const label_r_multiple = Math.max(
    config.rMultipleCap.min,
    Math.min(config.rMultipleCap.max, rawR)
  );
  
  // MFE/MAE (already in R units from V3)
  const label_mfe_r = Math.max(config.rMultipleCap.min, Math.min(config.rMultipleCap.max, outcome.mfeR));
  const label_mae_r = Math.max(config.rMultipleCap.min, Math.min(0, outcome.maeR));
  
  // Time to entry/exit
  const label_time_to_entry = outcome.timeToEntryBars;
  const label_time_to_exit = outcome.timeToOutcomeBars;
  
  // Outcome class
  const label_outcome_class = mapOutcomeClass(outcome);
  
  return {
    label_entry_hit,
    label_r_multiple,
    label_mfe_r,
    label_mae_r,
    label_time_to_entry,
    label_time_to_exit,
    label_outcome_class,
  };
}

/**
 * Map V3 outcome class to V4
 */
function mapOutcomeClass(outcome: OutcomeV3): OutcomeClassV4 {
  if (!outcome.entryHit) return 'NO_ENTRY';
  
  switch (outcome.class) {
    case 'WIN': return 'WIN';
    case 'LOSS': return 'LOSS';
    case 'PARTIAL': return 'PARTIAL';
    case 'TIMEOUT': return 'TIMEOUT';
    case 'NO_ENTRY': return 'NO_ENTRY';
    default: return 'TIMEOUT';
  }
}

/**
 * Calculate EV from predictions
 */
export function calculateEV(pEntry: number, rExpected: number): number {
  // EV = P(entry) × E[r|entry]
  // If entry not hit, R = 0
  // So EV = pEntry × rExpected + (1-pEntry) × 0 = pEntry × rExpected
  return pEntry * rExpected;
}

/**
 * Calculate full EV with risk adjustment
 * 
 * More sophisticated: accounts for partial outcomes
 */
export function calculateEVFull(
  pEntry: number,
  pWinGivenEntry: number,
  avgWinR: number,
  avgLossR: number
): number {
  // EV = P(entry) × [P(win|entry) × avgWinR + P(loss|entry) × avgLossR]
  // avgLossR is typically negative
  const pLossGivenEntry = 1 - pWinGivenEntry;
  return pEntry * (pWinGivenEntry * avgWinR + pLossGivenEntry * avgLossR);
}

/**
 * Batch convert outcomes to labels
 */
export function batchBuildLabelsV4(
  outcomes: OutcomeV3[],
  config: DatasetV4Config = DEFAULT_DATASET_V4_CONFIG
): LabelsV4[] {
  return outcomes.map(o => buildLabelsV4(o, config));
}

/**
 * Get label statistics
 */
export function getLabelStats(labels: LabelsV4[]): {
  total: number;
  entryRate: number;
  avgR: number;
  avgRGivenEntry: number;
  winRateGivenEntry: number;
  byClass: Record<OutcomeClassV4, number>;
} {
  const total = labels.length;
  if (total === 0) {
    return {
      total: 0,
      entryRate: 0,
      avgR: 0,
      avgRGivenEntry: 0,
      winRateGivenEntry: 0,
      byClass: { NO_ENTRY: 0, WIN: 0, PARTIAL: 0, LOSS: 0, TIMEOUT: 0 },
    };
  }
  
  const entries = labels.filter(l => l.label_entry_hit === 1);
  const entryRate = entries.length / total;
  
  const avgR = labels.reduce((sum, l) => sum + l.label_r_multiple, 0) / total;
  const avgRGivenEntry = entries.length > 0
    ? entries.reduce((sum, l) => sum + l.label_r_multiple, 0) / entries.length
    : 0;
  
  const wins = entries.filter(l => l.label_outcome_class === 'WIN');
  const winRateGivenEntry = entries.length > 0 ? wins.length / entries.length : 0;
  
  const byClass: Record<OutcomeClassV4, number> = {
    NO_ENTRY: 0, WIN: 0, PARTIAL: 0, LOSS: 0, TIMEOUT: 0,
  };
  for (const l of labels) {
    byClass[l.label_outcome_class]++;
  }
  
  return {
    total,
    entryRate,
    avgR,
    avgRGivenEntry,
    winRateGivenEntry,
    byClass,
  };
}
