/**
 * Unified Outcome Evaluator (O3)
 * 
 * Единый источник истины для оценки outcomes.
 * Используется:
 * - симулятором (online)
 * - batch backfill job (offline)
 * - backtest harness
 * 
 * С версионированием: labelVersion: "v3" | "v4"
 */

import { Db } from 'mongodb';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export type LabelVersion = 'v3' | 'v4';
export type OutcomeClass = 'WIN' | 'LOSS' | 'PARTIAL' | 'TIMEOUT' | 'NO_ENTRY';

export interface EvaluationInput {
  // Identity
  runId: string;
  scenarioId: string;
  asset: string;
  timeframe: string;
  
  // Trade plan
  entry: number;
  stop: number;
  target1: number;
  target2?: number;
  
  // Decision context
  decisionIdx: number;
  decisionTs?: number;
  
  // Forward candles for evaluation
  candles: {
    openTime: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }[];
  
  // Config
  timeoutBars?: number;  // Default: 40
}

export interface EvaluationResult {
  // Identity
  runId: string;
  scenarioId: string;
  asset: string;
  timeframe: string;
  
  // Version
  labelVersion: LabelVersion;
  
  // Outcome
  class: OutcomeClass;
  direction: 'LONG' | 'SHORT';
  
  // Entry/Exit
  entryPlanned: boolean;
  entryHit: boolean;
  entryIdx?: number;
  entryTs?: number;
  exitIdx?: number;
  exitTs?: number;
  exitPrice?: number;
  
  // R Metrics
  rMultiple: number;
  mfeR: number;   // Max Favorable Excursion in R
  maeR: number;   // Max Adverse Excursion in R (negative)
  
  // Timing
  timeToEntryBars: number;
  timeToOutcomeBars: number;
  
  // Trade plan (for reference)
  entry: number;
  stop: number;
  target1: number;
  target2?: number;
  risk: number;
  
  // Meta
  reason: string;
  evaluatedAt: string;
}

export interface EvaluationThresholds {
  winMfeR: number;      // MFE threshold for WIN (default: 1.5)
  partialMfeR: number;  // MFE threshold for PARTIAL (default: 0.5)
  lossMaeR: number;     // MAE threshold for LOSS (negative, default: -0.8)
}

const DEFAULT_THRESHOLDS: EvaluationThresholds = {
  winMfeR: 1.5,
  partialMfeR: 0.5,
  lossMaeR: -0.8,
};

// ═══════════════════════════════════════════════════════════════
// Core Evaluation Logic
// ═══════════════════════════════════════════════════════════════

/**
 * Find entry hit in candles
 */
function findEntryHit(
  input: EvaluationInput,
  isLong: boolean
): { idx: number; ts?: number } | null {
  const { entry, decisionIdx, candles, timeoutBars = 40 } = input;
  
  for (let i = decisionIdx; i < candles.length && (i - decisionIdx) <= timeoutBars; i++) {
    const candle = candles[i];
    if (isLong) {
      if (candle.high >= entry) {
        return { idx: i, ts: candle.openTime };
      }
    } else {
      if (candle.low <= entry) {
        return { idx: i, ts: candle.openTime };
      }
    }
  }
  return null;
}

/**
 * Walk path after entry to find MFE/MAE and exit
 */
function walkPath(
  input: EvaluationInput,
  entryIdx: number,
  isLong: boolean,
  risk: number
): {
  mfe: number;
  mae: number;
  hitStop: boolean;
  hitT1: boolean;
  exitIdx: number;
  exitPrice: number;
  exitTs?: number;
} {
  const { entry, stop, target1, candles, decisionIdx, timeoutBars = 40 } = input;
  
  let mfe = 0;
  let mae = 0;
  let hitStop = false;
  let hitT1 = false;
  let exitIdx = entryIdx;
  let exitPrice = entry;
  let exitTs: number | undefined;
  
  for (let i = entryIdx; i < candles.length && (i - decisionIdx) <= timeoutBars; i++) {
    const candle = candles[i];
    const { high, low, close, openTime } = candle;
    
    // Calculate excursions
    const favorable = isLong ? (high - entry) : (entry - low);
    const adverse = isLong ? (entry - low) : (high - entry);
    
    if (favorable > mfe) mfe = favorable;
    if (adverse > mae) mae = adverse;
    
    // Check stop hit
    if (isLong && low <= stop) {
      hitStop = true;
      exitIdx = i;
      exitPrice = stop;
      exitTs = openTime;
      break;
    } else if (!isLong && high >= stop) {
      hitStop = true;
      exitIdx = i;
      exitPrice = stop;
      exitTs = openTime;
      break;
    }
    
    // Check target1 hit
    if (!hitT1 && target1) {
      if (isLong && high >= target1) {
        hitT1 = true;
        exitIdx = i;
        exitPrice = target1;
        exitTs = openTime;
        break;
      } else if (!isLong && low <= target1) {
        hitT1 = true;
        exitIdx = i;
        exitPrice = target1;
        exitTs = openTime;
        break;
      }
    }
    
    // Update exit to last candle close if no explicit exit
    exitIdx = i;
    exitPrice = close;
    exitTs = openTime;
  }
  
  return { mfe, mae, hitStop, hitT1, exitIdx, exitPrice, exitTs };
}

/**
 * Classify outcome based on metrics
 */
function classifyOutcome(
  hitStop: boolean,
  hitT1: boolean,
  mfeR: number,
  maeR: number,
  rMultiple: number,
  thresholds: EvaluationThresholds
): OutcomeClass {
  // LOSS: stop hit or MAE too deep
  if (hitStop || maeR <= thresholds.lossMaeR) return 'LOSS';
  
  // WIN: target hit or MFE reached win threshold
  if (hitT1 || mfeR >= thresholds.winMfeR) return 'WIN';
  
  // PARTIAL: some favorable movement but not win
  if (mfeR >= thresholds.partialMfeR || rMultiple > 0.2) return 'PARTIAL';
  
  // TIMEOUT: minimal movement
  return 'TIMEOUT';
}

// ═══════════════════════════════════════════════════════════════
// Main Evaluation Function
// ═══════════════════════════════════════════════════════════════

/**
 * Unified outcome evaluation function
 * 
 * @param input - Evaluation input with trade plan and candles
 * @param version - Label version (v3 or v4)
 * @param thresholds - Classification thresholds
 */
export function evaluatePathAndLabel(
  input: EvaluationInput,
  version: LabelVersion = 'v3',
  thresholds: EvaluationThresholds = DEFAULT_THRESHOLDS
): EvaluationResult {
  const evaluatedAt = new Date().toISOString();
  const { runId, scenarioId, asset, timeframe, entry, stop, target1, target2, candles, decisionIdx, timeoutBars = 40 } = input;
  
  const risk = Math.abs(entry - stop);
  const isLong = entry >= stop;
  const direction: 'LONG' | 'SHORT' = isLong ? 'LONG' : 'SHORT';
  
  // Base result for invalid inputs
  const baseResult = (cls: OutcomeClass, reason: string): EvaluationResult => ({
    runId,
    scenarioId,
    asset,
    timeframe,
    labelVersion: version,
    class: cls,
    direction,
    entryPlanned: true,
    entryHit: false,
    rMultiple: 0,
    mfeR: 0,
    maeR: 0,
    timeToEntryBars: timeoutBars,
    timeToOutcomeBars: timeoutBars,
    entry,
    stop,
    target1,
    target2,
    risk,
    reason,
    evaluatedAt,
  });
  
  // Validate risk
  if (!Number.isFinite(risk) || risk <= 0) {
    return baseResult('TIMEOUT', 'invalid_risk');
  }
  
  // Validate candles
  if (!candles || candles.length === 0) {
    return baseResult('TIMEOUT', 'no_forward_candles');
  }
  
  // 1. Find entry hit
  const entryHit = findEntryHit(input, isLong);
  if (!entryHit) {
    return {
      ...baseResult('NO_ENTRY', 'entry_not_hit'),
      entryHit: false,
    };
  }
  
  // 2. Walk path after entry
  const path = walkPath(input, entryHit.idx, isLong, risk);
  
  // 3. Calculate R metrics
  const mfeR = path.mfe / risk;
  const maeR = -path.mae / risk;  // negative for adverse
  const realizedMove = isLong 
    ? (path.exitPrice - entry) 
    : (entry - path.exitPrice);
  const rMultiple = realizedMove / risk;
  
  // 4. Classify
  const outcomeClass = classifyOutcome(
    path.hitStop, 
    path.hitT1, 
    mfeR, 
    maeR, 
    rMultiple, 
    thresholds
  );
  
  // 5. Determine reason
  let reason = 'timeout';
  if (outcomeClass === 'WIN') reason = path.hitT1 ? 'target_hit' : 'mfe_reached';
  else if (outcomeClass === 'LOSS') reason = path.hitStop ? 'stop_hit' : 'mae_exceeded';
  else if (outcomeClass === 'PARTIAL') reason = 'partial_move';
  
  return {
    runId,
    scenarioId,
    asset,
    timeframe,
    labelVersion: version,
    class: outcomeClass,
    direction,
    entryPlanned: true,
    entryHit: true,
    entryIdx: entryHit.idx,
    entryTs: entryHit.ts,
    exitIdx: path.exitIdx,
    exitTs: path.exitTs,
    exitPrice: path.exitPrice,
    rMultiple,
    mfeR,
    maeR,
    timeToEntryBars: entryHit.idx - decisionIdx,
    timeToOutcomeBars: path.exitIdx - decisionIdx,
    entry,
    stop,
    target1,
    target2,
    risk,
    reason,
    evaluatedAt,
  };
}

/**
 * Batch evaluation
 */
export function evaluatePathAndLabelBatch(
  inputs: EvaluationInput[],
  version: LabelVersion = 'v3',
  thresholds: EvaluationThresholds = DEFAULT_THRESHOLDS
): EvaluationResult[] {
  return inputs.map(input => evaluatePathAndLabel(input, version, thresholds));
}

// ═══════════════════════════════════════════════════════════════
// Export for backwards compatibility
// ═══════════════════════════════════════════════════════════════

export { DEFAULT_THRESHOLDS };
