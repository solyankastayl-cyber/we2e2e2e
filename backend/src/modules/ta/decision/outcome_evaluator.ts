/**
 * P1.6 — Outcome Evaluator V4
 * 
 * Evaluates trade outcomes without lookahead:
 * - Entry hit only if price touched entry AFTER signal
 * - R-multiple calculated only after entry
 * - Proper timeout handling
 */

export interface OutcomeV4 {
  entryHit: boolean;
  barsToEntry: number;
  barsToExit: number;
  
  rMultiple: number;
  mfeR: number;        // Max Favorable Excursion in R
  maeR: number;        // Max Adverse Excursion in R (negative)
  
  exitReason: 'STOP' | 'TARGET1' | 'TARGET2' | 'TIMEOUT' | 'TIMEOUT_PARTIAL' | 'NO_ENTRY';
  exitPrice: number;
  exitIdx: number;
}

export interface TradeSetup {
  direction: 'LONG' | 'SHORT';
  entry: number;
  stop: number;
  target1: number;
  target2?: number;
  signalIdx: number;      // Bar index when signal was generated
  timeoutBars: number;    // Max bars to wait for entry/exit
}

export interface CandleBar {
  high: number;
  low: number;
  close: number;
}

/**
 * Evaluate trade outcome from forward candles
 * NO LOOKAHEAD: uses only candles after signalIdx
 */
export function evaluateOutcome(
  setup: TradeSetup,
  forwardCandles: CandleBar[]  // Candles starting from signalIdx
): OutcomeV4 {
  const { direction, entry, stop, target1, target2, signalIdx, timeoutBars } = setup;
  
  // Risk calculation
  const risk = Math.abs(entry - stop);
  if (risk <= 0) {
    return noEntry('Invalid risk');
  }

  // Step 1: Find entry hit
  let entryIdx = -1;
  for (let i = 0; i < Math.min(forwardCandles.length, timeoutBars); i++) {
    const candle = forwardCandles[i];
    
    if (direction === 'LONG') {
      // For LONG, entry hit when price goes UP to entry level
      if (candle.high >= entry) {
        entryIdx = i;
        break;
      }
    } else {
      // For SHORT, entry hit when price goes DOWN to entry level
      if (candle.low <= entry) {
        entryIdx = i;
        break;
      }
    }
  }

  // No entry hit
  if (entryIdx === -1) {
    return {
      entryHit: false,
      barsToEntry: timeoutBars,
      barsToExit: timeoutBars,
      rMultiple: 0,
      mfeR: 0,
      maeR: 0,
      exitReason: 'NO_ENTRY',
      exitPrice: forwardCandles[forwardCandles.length - 1]?.close || entry,
      exitIdx: timeoutBars,
    };
  }

  // Step 2: Track position after entry
  let mfe = 0;  // Max favorable excursion (price move in our direction)
  let mae = 0;  // Max adverse excursion (price move against us)
  let exitIdx = -1;
  let exitPrice = entry;
  let exitReason: OutcomeV4['exitReason'] = 'TIMEOUT';

  const maxIdx = Math.min(forwardCandles.length, entryIdx + timeoutBars);
  
  for (let i = entryIdx; i < maxIdx; i++) {
    const candle = forwardCandles[i];
    
    if (direction === 'LONG') {
      // Track MFE/MAE
      const favorable = candle.high - entry;
      const adverse = entry - candle.low;
      
      if (favorable > mfe) mfe = favorable;
      if (adverse > mae) mae = adverse;
      
      // Check stop hit (priority over target - conservative)
      if (candle.low <= stop) {
        exitIdx = i;
        exitPrice = stop;
        exitReason = 'STOP';
        break;
      }
      
      // Check target2 first (if exists)
      if (target2 && candle.high >= target2) {
        exitIdx = i;
        exitPrice = target2;
        exitReason = 'TARGET2';
        break;
      }
      
      // Check target1
      if (candle.high >= target1) {
        exitIdx = i;
        exitPrice = target1;
        exitReason = 'TARGET1';
        break;
      }
      
    } else {
      // SHORT direction
      const favorable = entry - candle.low;
      const adverse = candle.high - entry;
      
      if (favorable > mfe) mfe = favorable;
      if (adverse > mae) mae = adverse;
      
      // Check stop hit
      if (candle.high >= stop) {
        exitIdx = i;
        exitPrice = stop;
        exitReason = 'STOP';
        break;
      }
      
      // Check target2
      if (target2 && candle.low <= target2) {
        exitIdx = i;
        exitPrice = target2;
        exitReason = 'TARGET2';
        break;
      }
      
      // Check target1
      if (candle.low <= target1) {
        exitIdx = i;
        exitPrice = target1;
        exitReason = 'TARGET1';
        break;
      }
    }
  }

  // Timeout - use last close
  if (exitIdx === -1) {
    exitIdx = maxIdx - 1;
    exitPrice = forwardCandles[exitIdx]?.close || entry;
    
    // Check if partial profit
    const unrealizedR = direction === 'LONG'
      ? (exitPrice - entry) / risk
      : (entry - exitPrice) / risk;
    
    exitReason = unrealizedR > 0.3 ? 'TIMEOUT_PARTIAL' : 'TIMEOUT';
  }

  // Calculate R-multiples
  const rMultiple = direction === 'LONG'
    ? (exitPrice - entry) / risk
    : (entry - exitPrice) / risk;
  
  const mfeR = mfe / risk;
  const maeR = -mae / risk;  // Negative for adverse

  return {
    entryHit: true,
    barsToEntry: entryIdx,
    barsToExit: exitIdx - entryIdx,
    rMultiple,
    mfeR,
    maeR,
    exitReason,
    exitPrice,
    exitIdx,
  };
}

function noEntry(reason: string): OutcomeV4 {
  return {
    entryHit: false,
    barsToEntry: 0,
    barsToExit: 0,
    rMultiple: 0,
    mfeR: 0,
    maeR: 0,
    exitReason: 'NO_ENTRY',
    exitPrice: 0,
    exitIdx: 0,
  };
}

/**
 * Test cases for outcome evaluator
 */
export function runOutcomeTests(): { passed: number; failed: number; results: string[] } {
  const results: string[] = [];
  let passed = 0;
  let failed = 0;

  // Test 1: NO_ENTRY
  const test1 = evaluateOutcome(
    { direction: 'LONG', entry: 100, stop: 95, target1: 110, signalIdx: 0, timeoutBars: 10 },
    Array(10).fill({ high: 99, low: 97, close: 98 })  // Never reaches entry
  );
  if (test1.exitReason === 'NO_ENTRY' && !test1.entryHit) {
    results.push('✅ Test 1 (NO_ENTRY): PASSED');
    passed++;
  } else {
    results.push('❌ Test 1 (NO_ENTRY): FAILED');
    failed++;
  }

  // Test 2: STOP hit
  const test2 = evaluateOutcome(
    { direction: 'LONG', entry: 100, stop: 95, target1: 110, signalIdx: 0, timeoutBars: 10 },
    [
      { high: 101, low: 99, close: 100 },   // Entry hit
      { high: 100, low: 94, close: 95 },    // Stop hit
    ]
  );
  if (test2.exitReason === 'STOP' && test2.entryHit && test2.rMultiple === -1) {
    results.push('✅ Test 2 (STOP): PASSED');
    passed++;
  } else {
    results.push(`❌ Test 2 (STOP): FAILED (reason=${test2.exitReason}, r=${test2.rMultiple})`);
    failed++;
  }

  // Test 3: TARGET1 hit
  const test3 = evaluateOutcome(
    { direction: 'LONG', entry: 100, stop: 95, target1: 110, signalIdx: 0, timeoutBars: 10 },
    [
      { high: 101, low: 99, close: 100 },   // Entry hit
      { high: 105, low: 100, close: 104 },  // Moving up
      { high: 111, low: 108, close: 110 },  // Target1 hit
    ]
  );
  if (test3.exitReason === 'TARGET1' && test3.entryHit && test3.rMultiple === 2) {
    results.push('✅ Test 3 (TARGET1): PASSED');
    passed++;
  } else {
    results.push(`❌ Test 3 (TARGET1): FAILED (reason=${test3.exitReason}, r=${test3.rMultiple})`);
    failed++;
  }

  // Test 4: TARGET2 hit
  const test4 = evaluateOutcome(
    { direction: 'LONG', entry: 100, stop: 95, target1: 110, target2: 120, signalIdx: 0, timeoutBars: 10 },
    [
      { high: 101, low: 99, close: 100 },   // Entry hit
      { high: 109, low: 100, close: 108 },  // Moving up but not at target1
      { high: 122, low: 115, close: 121 },  // Both targets hit on same candle, target2 wins
    ]
  );
  if (test4.exitReason === 'TARGET2' && test4.rMultiple === 4) {
    results.push('✅ Test 4 (TARGET2): PASSED');
    passed++;
  } else {
    results.push(`❌ Test 4 (TARGET2): FAILED (reason=${test4.exitReason}, r=${test4.rMultiple})`);
    failed++;
  }

  // Test 5: TIMEOUT_PARTIAL
  const test5 = evaluateOutcome(
    { direction: 'LONG', entry: 100, stop: 95, target1: 110, signalIdx: 0, timeoutBars: 5 },
    [
      { high: 101, low: 99, close: 100 },
      { high: 103, low: 100, close: 102 },
      { high: 104, low: 101, close: 103 },
      { high: 103, low: 101, close: 102 },
      { high: 102, low: 100, close: 101 },  // Timeout at small profit
    ]
  );
  if (test5.entryHit && test5.rMultiple > 0 && (test5.exitReason === 'TIMEOUT' || test5.exitReason === 'TIMEOUT_PARTIAL')) {
    results.push('✅ Test 5 (TIMEOUT_PARTIAL): PASSED');
    passed++;
  } else {
    results.push(`❌ Test 5 (TIMEOUT_PARTIAL): FAILED (reason=${test5.exitReason}, r=${test5.rMultiple})`);
    failed++;
  }

  return { passed, failed, results };
}

// ═══════════════════════════════════════════════════════════════
// SIMPLIFIED OUTCOME EVALUATOR FOR BATCH SIMULATION
// ═══════════════════════════════════════════════════════════════

export interface OutcomeInput {
  entry: number;
  stop: number;
  target1: number;
  target2?: number;
  direction: 'LONG' | 'SHORT';
  entryTs: number;
  futureCandles: Array<{
    ts: number;
    open: number;
    high: number;
    low: number;
    close: number;
  }>;
  maxBars: number;
}

export interface OutcomeResult {
  entryHit: boolean;
  rMultiple: number;
  mfeR: number;
  maeR: number;
  exitReason: string;
  closeTs: number;
  barsInTrade: number;
}

/**
 * Simplified outcome evaluation for batch simulation
 */
export function evaluateOutcomeSimple(input: OutcomeInput): OutcomeResult {
  const { entry, stop, target1, target2, direction, entryTs, futureCandles, maxBars } = input;
  
  const risk = Math.abs(entry - stop);
  if (risk <= 0) {
    return {
      entryHit: false,
      rMultiple: 0,
      mfeR: 0,
      maeR: 0,
      exitReason: 'INVALID_RISK',
      closeTs: entryTs,
      barsInTrade: 0,
    };
  }
  
  // Find entry
  let entryIdx = -1;
  for (let i = 0; i < Math.min(futureCandles.length, maxBars); i++) {
    const c = futureCandles[i];
    
    if (direction === 'LONG') {
      if (c.high >= entry) {
        entryIdx = i;
        break;
      }
    } else {
      if (c.low <= entry) {
        entryIdx = i;
        break;
      }
    }
  }
  
  if (entryIdx === -1) {
    return {
      entryHit: false,
      rMultiple: 0,
      mfeR: 0,
      maeR: 0,
      exitReason: 'NO_ENTRY',
      closeTs: futureCandles[futureCandles.length - 1]?.ts || entryTs,
      barsInTrade: 0,
    };
  }
  
  // Track position
  let mfe = 0;
  let mae = 0;
  let exitIdx = -1;
  let exitPrice = entry;
  let exitReason = 'TIMEOUT';
  
  const endIdx = Math.min(futureCandles.length, entryIdx + maxBars);
  
  for (let i = entryIdx; i < endIdx; i++) {
    const c = futureCandles[i];
    
    if (direction === 'LONG') {
      const favorable = c.high - entry;
      const adverse = entry - c.low;
      if (favorable > mfe) mfe = favorable;
      if (adverse > mae) mae = adverse;
      
      if (c.low <= stop) {
        exitIdx = i;
        exitPrice = stop;
        exitReason = 'STOP';
        break;
      }
      
      if (target2 && c.high >= target2) {
        exitIdx = i;
        exitPrice = target2;
        exitReason = 'T2';
        break;
      }
      
      if (c.high >= target1) {
        exitIdx = i;
        exitPrice = target1;
        exitReason = 'T1';
        break;
      }
    } else {
      const favorable = entry - c.low;
      const adverse = c.high - entry;
      if (favorable > mfe) mfe = favorable;
      if (adverse > mae) mae = adverse;
      
      if (c.high >= stop) {
        exitIdx = i;
        exitPrice = stop;
        exitReason = 'STOP';
        break;
      }
      
      if (target2 && c.low <= target2) {
        exitIdx = i;
        exitPrice = target2;
        exitReason = 'T2';
        break;
      }
      
      if (c.low <= target1) {
        exitIdx = i;
        exitPrice = target1;
        exitReason = 'T1';
        break;
      }
    }
  }
  
  if (exitIdx === -1) {
    exitIdx = endIdx - 1;
    exitPrice = futureCandles[exitIdx]?.close || entry;
  }
  
  const rMultiple = direction === 'LONG'
    ? (exitPrice - entry) / risk
    : (entry - exitPrice) / risk;
  
  return {
    entryHit: true,
    rMultiple,
    mfeR: mfe / risk,
    maeR: -mae / risk,
    exitReason,
    closeTs: futureCandles[exitIdx]?.ts || entryTs,
    barsInTrade: exitIdx - entryIdx,
  };
}
