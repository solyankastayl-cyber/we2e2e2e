/**
 * Phase 8.3 — Labels v3 Evaluator
 * 
 * Pure function to evaluate OutcomeV3 from forward candles
 * No lookahead bias: decision made only after candles appear
 */

import { 
  OutcomeV3, 
  OutcomeClassV3, 
  EvalInputsV3,
  ClassificationThresholds,
  DEFAULT_THRESHOLDS 
} from './labels_v3.types.js';

/**
 * Find entry hit index in candles
 */
function findEntry(inp: EvalInputsV3): number {
  const long = inp.entry >= inp.stop;
  
  for (let i = inp.decisionIdx; i < inp.closes.length && (i - inp.decisionIdx) <= inp.timeoutBars; i++) {
    if (long) {
      if (inp.highs[i] >= inp.entry) return i;
    } else {
      if (inp.lows[i] <= inp.entry) return i;
    }
  }
  return -1;
}

/**
 * Classify outcome based on metrics
 */
function classify(
  x: { hitStop: boolean; hitT1: boolean; mfeR: number; maeR: number; rMultiple: number },
  thresholds: ClassificationThresholds
): OutcomeClassV3 {
  // LOSS: stop hit or MAE too deep
  if (x.hitStop || x.maeR <= thresholds.lossMaeR) return 'LOSS';
  
  // WIN: target hit or MFE reached win threshold
  if (x.hitT1 || x.mfeR >= thresholds.winMfeR) return 'WIN';

  // PARTIAL: some favorable movement but not win
  if (x.mfeR >= thresholds.partialMfeR || x.rMultiple > 0.2) return 'PARTIAL';
  
  // TIMEOUT: minimal movement
  return 'TIMEOUT';
}

/**
 * Evaluate OutcomeV3 from inputs
 */
export function evaluateOutcomeV3(
  inp: EvalInputsV3, 
  thresholds: ClassificationThresholds = DEFAULT_THRESHOLDS
): OutcomeV3 {
  const createdAt = new Date().toISOString();
  const risk = Math.abs(inp.entry - inp.stop);
  const direction: 'LONG' | 'SHORT' = inp.entry >= inp.stop ? 'LONG' : 'SHORT';

  // Base outcome for invalid inputs
  const base = (cls: OutcomeClassV3, reason: string): OutcomeV3 => ({
    runId: inp.runId,
    scenarioId: inp.scenarioId,
    asset: inp.asset,
    timeframe: inp.timeframe,
    entryPlanned: true,
    entryHit: false,
    class: cls,
    rMultiple: 0,
    mfeR: 0,
    maeR: 0,
    timeToEntryBars: inp.timeoutBars,
    timeToOutcomeBars: inp.timeoutBars,
    direction,
    reason,
    createdAt,
    entry: inp.entry,
    stop: inp.stop,
    target1: inp.t1,
    target2: inp.t2,
    risk,
  });

  // Validate risk
  if (!Number.isFinite(risk) || risk <= 0) {
    return base('TIMEOUT', 'invalid_risk');
  }

  // Validate candles
  if (!inp.closes.length || !inp.highs.length || !inp.lows.length) {
    return base('TIMEOUT', 'no_forward_candles');
  }

  // 1) Find entry hit
  const entryIdx = findEntry(inp);
  if (entryIdx === -1) {
    return {
      ...base('NO_ENTRY', 'entry_not_hit'),
      entryHit: false,
      timeToEntryBars: inp.timeoutBars,
    };
  }

  // 2) Walk forward after entry: track MFE/MAE and stop/targets hits
  let mfe = 0;  // max favorable (abs)
  let mae = 0;  // max adverse (abs)
  let hitStop = false;
  let hitT1 = false;
  let exitIdx = -1;
  let exitPrice = inp.closes[entryIdx];

  for (let i = entryIdx; i < inp.closes.length && (i - inp.decisionIdx) <= inp.timeoutBars; i++) {
    const hi = inp.highs[i];
    const lo = inp.lows[i];

    // Calculate favorable/adverse excursions
    const favorable = direction === 'LONG' ? (hi - inp.entry) : (inp.entry - lo);
    const adverse = direction === 'LONG' ? (inp.entry - lo) : (hi - inp.entry);

    if (favorable > mfe) mfe = favorable;
    if (adverse > mae) mae = adverse;

    // Check stop hit
    if (direction === 'LONG') {
      if (lo <= inp.stop) {
        hitStop = true;
        exitIdx = i;
        exitPrice = inp.stop;
        break;
      }
    } else {
      if (hi >= inp.stop) {
        hitStop = true;
        exitIdx = i;
        exitPrice = inp.stop;
        break;
      }
    }

    // Check target1 hit
    if (!hitT1 && inp.t1 !== undefined) {
      if (direction === 'LONG') {
        if (hi >= inp.t1) {
          hitT1 = true;
          exitIdx = i;
          exitPrice = inp.t1;
          break;
        }
      } else {
        if (lo <= inp.t1) {
          hitT1 = true;
          exitIdx = i;
          exitPrice = inp.t1;
          break;
        }
      }
    }
  }

  // Calculate R metrics
  const mfeR = mfe / risk;
  const maeR = -mae / risk;  // negative for adverse

  // Realized rMultiple
  if (exitIdx === -1) {
    exitIdx = Math.min(inp.closes.length - 1, inp.decisionIdx + inp.timeoutBars);
    exitPrice = inp.closes[exitIdx];
  }

  const realizedMove = direction === 'LONG' 
    ? (exitPrice - inp.entry) 
    : (inp.entry - exitPrice);
  const rMultiple = realizedMove / risk;

  // Classify
  const cls = classify({ hitStop, hitT1, mfeR, maeR, rMultiple }, thresholds);

  return {
    runId: inp.runId,
    scenarioId: inp.scenarioId,
    asset: inp.asset,
    timeframe: inp.timeframe,
    entryPlanned: true,
    entryHit: true,
    entryIdx,
    exitIdx,
    class: cls,
    rMultiple,
    mfeR,
    maeR,
    timeToEntryBars: entryIdx - inp.decisionIdx,
    timeToOutcomeBars: exitIdx - inp.decisionIdx,
    direction,
    reason: cls === 'WIN' ? 't1_or_mfe' : cls === 'LOSS' ? 'stop_or_mae' : 'timeout',
    createdAt,
    entry: inp.entry,
    stop: inp.stop,
    target1: inp.t1,
    target2: inp.t2,
    risk,
  };
}

/**
 * Batch evaluate multiple outcomes
 */
export function evaluateOutcomesV3Batch(
  inputs: EvalInputsV3[],
  thresholds: ClassificationThresholds = DEFAULT_THRESHOLDS
): OutcomeV3[] {
  return inputs.map(inp => evaluateOutcomeV3(inp, thresholds));
}
