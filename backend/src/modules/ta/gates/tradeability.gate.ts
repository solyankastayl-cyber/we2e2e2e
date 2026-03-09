/**
 * P1.1 — Tradeability Gate Implementation
 * 
 * Filter scenarios that shouldn't be traded
 * Increases signal quality by removing noise
 */

import {
  TradeabilityResult,
  GateReason,
  GateConfig,
  GateInput,
  DEFAULT_GATE_CONFIG,
} from './tradeability.types.js';

/**
 * Check if scenario passes all tradeability gates
 */
export function isTradeableScenario(
  input: GateInput,
  config: GateConfig = DEFAULT_GATE_CONFIG
): TradeabilityResult {
  if (!config.enabled) {
    return {
      ok: true,
      gateScore: 1,
      reasons: [],
      passingGates: ['DISABLED'],
      failingGates: [],
    };
  }

  const reasons: GateReason[] = [];
  const passingGates: string[] = [];
  const failingGates: string[] = [];
  let score = 1;

  const { price, atr, entry, stop, target1, direction } = input;

  // Validate inputs
  if (!price || !atr || atr <= 0) {
    return {
      ok: false,
      gateScore: 0,
      reasons: ['INVALID_STOP'],
      passingGates: [],
      failingGates: ['INVALID_INPUTS'],
    };
  }

  // Gate 1: Risk/Reward ratio
  const risk = Math.abs(entry - stop);
  const reward = Math.abs(target1 - entry);
  const rr = risk > 0 ? reward / risk : 0;

  if (rr < config.minRR) {
    reasons.push('RR_TOO_LOW');
    failingGates.push('RR');
    score -= 0.25;
  } else {
    passingGates.push('RR');
  }

  // Gate 2: Entry distance
  const entryDistance = Math.abs(price - entry);
  const entryDistanceATR = entryDistance / atr;

  if (entryDistanceATR > config.maxEntryDistanceATR) {
    reasons.push('ENTRY_TOO_FAR');
    failingGates.push('ENTRY_DISTANCE');
    score -= 0.25;
  } else {
    passingGates.push('ENTRY_DISTANCE');
  }

  // Gate 3: Volatility filter - too high
  const volatility = atr / price;

  if (volatility > config.maxVolatility) {
    reasons.push('EXTREME_VOL');
    failingGates.push('VOL_HIGH');
    score -= 0.2;
  } else {
    passingGates.push('VOL_HIGH');
  }

  // Gate 4: Volatility filter - too low
  if (volatility < config.minVolatility) {
    reasons.push('LOW_VOL');
    failingGates.push('VOL_LOW');
    score -= 0.2;
  } else {
    passingGates.push('VOL_LOW');
  }

  // Gate 5: Pattern maturity (touches)
  if (input.touches !== undefined && input.touches < config.minTouches) {
    reasons.push('PATTERN_TOO_EARLY');
    failingGates.push('TOUCHES');
    score -= 0.2;
  } else if (input.touches !== undefined) {
    passingGates.push('TOUCHES');
  }

  // Gate 6: Apex distance (for triangles/wedges)
  if (input.apexDistanceBars !== undefined && input.patternLengthBars !== undefined) {
    const apexPct = input.patternLengthBars > 0 
      ? input.apexDistanceBars / input.patternLengthBars 
      : 1;
    
    if (apexPct > config.maxApexDistancePct) {
      reasons.push('APEX_TOO_FAR');
      failingGates.push('APEX');
      score -= 0.15;
    } else {
      passingGates.push('APEX');
    }
  }

  // Gate 7: Compression (optional)
  if (config.minCompression && input.compression !== undefined) {
    if (input.compression > 1.5) {  // Not compressed enough
      reasons.push('NO_COMPRESSION');
      failingGates.push('COMPRESSION');
      score -= 0.15;
    } else {
      passingGates.push('COMPRESSION');
    }
  }

  // Gate 8: Stop/Target validity
  if (!stop || stop <= 0) {
    reasons.push('INVALID_STOP');
    failingGates.push('STOP');
    score -= 0.3;
  } else {
    passingGates.push('STOP');
  }

  if (!target1 || target1 <= 0) {
    reasons.push('INVALID_TARGET');
    failingGates.push('TARGET');
    score -= 0.3;
  } else {
    passingGates.push('TARGET');
  }

  // Ensure score is in valid range
  score = Math.max(0, Math.min(1, score));

  return {
    ok: score >= config.minPassScore,
    gateScore: score,
    reasons,
    passingGates,
    failingGates,
  };
}

/**
 * Batch check multiple scenarios
 */
export function filterTradeableScenarios<T extends GateInput>(
  scenarios: T[],
  config: GateConfig = DEFAULT_GATE_CONFIG
): { passed: T[]; rejected: T[]; stats: GateStats } {
  const passed: T[] = [];
  const rejected: T[] = [];
  const reasonCounts: Record<string, number> = {};

  for (const scenario of scenarios) {
    const result = isTradeableScenario(scenario, config);
    
    if (result.ok) {
      passed.push(scenario);
    } else {
      rejected.push(scenario);
      for (const reason of result.reasons) {
        reasonCounts[reason] = (reasonCounts[reason] || 0) + 1;
      }
    }
  }

  return {
    passed,
    rejected,
    stats: {
      total: scenarios.length,
      passed: passed.length,
      rejected: rejected.length,
      passRate: scenarios.length > 0 ? passed.length / scenarios.length : 0,
      rejectionReasons: reasonCounts,
    },
  };
}

export interface GateStats {
  total: number;
  passed: number;
  rejected: number;
  passRate: number;
  rejectionReasons: Record<string, number>;
}
