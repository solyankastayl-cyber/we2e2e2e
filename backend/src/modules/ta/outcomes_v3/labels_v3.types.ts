/**
 * Phase 8.3 + O3 — Labels v3 Types
 * 
 * Multiclass outcomes + R-regression targets
 * Replaces binary WIN/LOSS with:
 * - LOSS, PARTIAL, WIN, TIMEOUT, NO_ENTRY
 * - rMultiple, mfeR, maeR regression targets
 * 
 * O3: Added labelVersion for unified evaluation
 */

export type OutcomeClassV3 = 'LOSS' | 'PARTIAL' | 'WIN' | 'TIMEOUT' | 'NO_ENTRY';
export type LabelVersion = 'v3' | 'v4';

export interface OutcomeV3 {
  runId: string;
  scenarioId: string;
  asset: string;
  timeframe: string;

  // O3: Label versioning
  labelVersion?: LabelVersion;

  entryPlanned: boolean;
  entryHit: boolean;
  entryIdx?: number;

  exitIdx?: number;
  class: OutcomeClassV3;

  // Regression targets (in R units)
  rMultiple: number;       // final realized R (>=1.5 win, <=-1 loss, between partial)
  mfeR: number;            // max favorable excursion / risk
  maeR: number;            // max adverse excursion / risk

  // Times
  timeToEntryBars: number;     // bars until entry or timeout window
  timeToOutcomeBars: number;   // bars until exit/timeout

  // Meta
  direction: 'LONG' | 'SHORT';
  reason?: string;
  createdAt: string;
  
  // Trade plan snapshot
  entry: number;
  stop: number;
  target1: number;
  target2?: number;
  risk: number;  // abs(entry - stop)
}

export interface EvalInputsV3 {
  runId: string;
  scenarioId: string;
  asset: string;
  timeframe: string;

  // Trade plan
  entry: number;
  stop: number;
  t1: number;
  t2?: number;

  entryType: 'MARKET' | 'BREAKOUT' | 'TRIGGER';
  timeoutBars: number;  // max bars to wait

  // Candles forward starting from decision candle inclusive
  closes: number[];
  highs: number[];
  lows: number[];
  timestamps?: number[];

  // Index within forward arrays where decision was made
  // forward[0] = decision bar
  decisionIdx: number;
}

/**
 * Classification thresholds
 */
export interface ClassificationThresholds {
  winMfeR: number;      // mfeR >= this => WIN (default 1.5)
  lossMaeR: number;     // maeR <= this => LOSS (default -1.0)
  partialMfeR: number;  // mfeR >= this for PARTIAL (default 0.3)
  timeoutMaeR: number;  // maeR > this for TIMEOUT (default -0.5)
}

export const DEFAULT_THRESHOLDS: ClassificationThresholds = {
  winMfeR: 1.5,
  lossMaeR: -1.0,
  partialMfeR: 0.3,
  timeoutMaeR: -0.5,
};

/**
 * Outcome stats aggregation
 */
export interface OutcomeV3Stats {
  total: number;
  byClass: Record<OutcomeClassV3, number>;
  avgRMultiple: number;
  avgMfeR: number;
  avgMaeR: number;
  avgTimeToEntry: number;
  avgTimeToOutcome: number;
  winRate: number;
  profitFactor: number;
}
