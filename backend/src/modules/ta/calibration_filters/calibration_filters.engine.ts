/**
 * Phase 8.6 — Core Calibration Loop Engine
 * 
 * Implements calibration filters for improving trading edge:
 * 1. Volatility Filter: ATR > SMA(ATR) * 0.8
 * 2. Trend Alignment: Trade only in EMA50/EMA200 direction
 * 3. Volume Breakout: volume > SMA(volume) * 1.4
 * 4. ATR-based TP/SL: SL = 1.5 * ATR, TP = 2.5 * ATR
 * 5. Disabled Strategies: LIQUIDITY_SWEEP, RANGE_REVERSAL
 */

import {
  CalibrationFilterConfig,
  CalibrationFilterInput,
  CalibrationFilterResult,
  CandleWithVolume,
  DEFAULT_CALIBRATION_FILTER_CONFIG,
} from './calibration_filters.types.js';

// ═══════════════════════════════════════════════════════════════
// Core Indicator Functions
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate ATR (Average True Range)
 */
function calculateATR(candles: CandleWithVolume[], period: number): number {
  if (candles.length < period + 1) return 0;

  let atr = 0;
  const startIdx = candles.length - period;

  for (let i = startIdx; i < candles.length; i++) {
    const high = candles[i].high;
    const low = candles[i].low;
    const prevClose = i > 0 ? candles[i - 1].close : candles[i].open;
    const tr = Math.max(
      high - low,
      Math.abs(high - prevClose),
      Math.abs(low - prevClose)
    );
    atr += tr;
  }

  return atr / period;
}

/**
 * Calculate ATR series for SMA calculation
 */
function calculateATRSeries(candles: CandleWithVolume[], atrPeriod: number): number[] {
  const atrSeries: number[] = [];

  for (let i = atrPeriod; i < candles.length; i++) {
    const slice = candles.slice(0, i + 1);
    const atr = calculateATR(slice, atrPeriod);
    atrSeries.push(atr);
  }

  return atrSeries;
}

/**
 * Calculate SMA (Simple Moving Average)
 */
function calculateSMA(values: number[], period: number): number {
  if (values.length < period) return values.length > 0 ? values[values.length - 1] : 0;

  const slice = values.slice(-period);
  return slice.reduce((sum, v) => sum + v, 0) / period;
}

/**
 * Calculate EMA (Exponential Moving Average)
 */
function calculateEMA(candles: CandleWithVolume[], period: number): number {
  if (candles.length === 0) return 0;
  if (candles.length < period) {
    // Return SMA if not enough data
    return candles.reduce((sum, c) => sum + c.close, 0) / candles.length;
  }

  const multiplier = 2 / (period + 1);
  
  // Seed with SMA
  let ema = candles.slice(0, period).reduce((sum, c) => sum + c.close, 0) / period;

  // Apply EMA from period onwards
  for (let i = period; i < candles.length; i++) {
    ema = (candles[i].close - ema) * multiplier + ema;
  }

  return ema;
}

/**
 * Calculate volume SMA
 */
function calculateVolumeSMA(candles: CandleWithVolume[], period: number): number {
  if (candles.length < period) {
    return candles.reduce((sum, c) => sum + c.volume, 0) / candles.length;
  }

  const recentVolumes = candles.slice(-period).map(c => c.volume);
  return recentVolumes.reduce((sum, v) => sum + v, 0) / period;
}

// ═══════════════════════════════════════════════════════════════
// Main Filter Engine
// ═══════════════════════════════════════════════════════════════

/**
 * Apply Phase 8.6 calibration filters
 */
export function applyCalibrationFilters(
  input: CalibrationFilterInput,
  config: CalibrationFilterConfig = DEFAULT_CALIBRATION_FILTER_CONFIG
): CalibrationFilterResult {
  const { candles, direction, patternType, entry } = input;
  const rejectionReasons: string[] = [];
  let score = 1.0;

  // Check if strategy is disabled
  const strategyEnabled = !config.disabledStrategies.includes(patternType);
  if (!strategyEnabled) {
    rejectionReasons.push('STRATEGY_DISABLED');
    score -= 1.0;  // Immediate fail
  }

  // Calculate indicators
  const atrPeriod = config.volatilityFilter.atrPeriod;
  const atr = input.atr ?? calculateATR(candles, atrPeriod);

  // ATR series for SMA calculation
  const atrSeries = calculateATRSeries(candles, atrPeriod);
  const atrSMA = calculateSMA(atrSeries, config.volatilityFilter.smaPeriod);

  // EMA calculations
  const ema50 = input.ema50 ?? calculateEMA(candles, config.trendAlignment.emaShortPeriod);
  const ema200 = input.ema200 ?? calculateEMA(candles, config.trendAlignment.emaLongPeriod);
  const currentPrice = candles.length > 0 ? candles[candles.length - 1].close : entry;

  // Volume calculations
  const currentVolume = candles.length > 0 ? candles[candles.length - 1].volume : 0;
  const volumeSMA = input.volumeSMA ?? calculateVolumeSMA(candles, config.volumeBreakout.smaPeriod);

  // ═══════════════════════════════════════════════════════════════
  // Filter 1: Volatility Filter — ATR > SMA(ATR) * 0.8
  // ═══════════════════════════════════════════════════════════════
  const volatilityThreshold = atrSMA * config.volatilityFilter.atrMultiplier;
  const volatilityRatio = atrSMA > 0 ? atr / atrSMA : 1;
  const volatilityPassed = !config.volatilityFilter.enabled || 
                           atr > volatilityThreshold;

  if (config.volatilityFilter.enabled && !volatilityPassed) {
    rejectionReasons.push('LOW_VOLATILITY');
    score -= 0.3;
  }

  // ═══════════════════════════════════════════════════════════════
  // Filter 2: Trend Alignment — Trade in direction of EMA50/EMA200
  // ═══════════════════════════════════════════════════════════════
  const trendDirection = determineTrendDirection(currentPrice, ema50, ema200);
  let trendAlignmentPassed = !config.trendAlignment.enabled;

  if (config.trendAlignment.enabled) {
    if (config.trendAlignment.requireBothAligned) {
      // Both EMAs must align with trade direction
      const shortAligned = (direction === 'LONG' && currentPrice > ema50) ||
                          (direction === 'SHORT' && currentPrice < ema50);
      const longAligned = (direction === 'LONG' && currentPrice > ema200) ||
                         (direction === 'SHORT' && currentPrice < ema200);
      trendAlignmentPassed = shortAligned && longAligned;
    } else {
      // Only EMA50 direction required
      trendAlignmentPassed = (direction === 'LONG' && trendDirection === 'UP') ||
                             (direction === 'SHORT' && trendDirection === 'DOWN');
    }
  }

  if (config.trendAlignment.enabled && !trendAlignmentPassed) {
    rejectionReasons.push('TREND_MISALIGNED');
    score -= 0.3;
  }

  // ═══════════════════════════════════════════════════════════════
  // Filter 3: Volume Breakout — volume > SMA(volume) * 1.4
  // ═══════════════════════════════════════════════════════════════
  const volumeThreshold = volumeSMA * config.volumeBreakout.volumeMultiplier;
  const volumeRatio = volumeSMA > 0 ? currentVolume / volumeSMA : 1;
  const volumeBreakoutPassed = !config.volumeBreakout.enabled ||
                               currentVolume > volumeThreshold;

  if (config.volumeBreakout.enabled && !volumeBreakoutPassed) {
    rejectionReasons.push('LOW_VOLUME');
    score -= 0.2;
  }

  // ═══════════════════════════════════════════════════════════════
  // ATR-based TP/SL
  // ═══════════════════════════════════════════════════════════════
  let stopLoss: number;
  let takeProfit: number;

  if (config.atrRiskManagement.enabled && atr > 0) {
    const slDistance = atr * config.atrRiskManagement.stopLossATR;
    const tpDistance = atr * config.atrRiskManagement.takeProfitATR;

    if (direction === 'LONG') {
      stopLoss = entry - slDistance;
      takeProfit = entry + tpDistance;
    } else {
      stopLoss = entry + slDistance;
      takeProfit = entry - tpDistance;
    }
  } else {
    // Fallback: use entry ± 2%
    const fallback = entry * 0.02;
    if (direction === 'LONG') {
      stopLoss = entry - fallback;
      takeProfit = entry + fallback * 2;
    } else {
      stopLoss = entry + fallback;
      takeProfit = entry - fallback * 2;
    }
  }

  const risk = Math.abs(entry - stopLoss);
  const reward = Math.abs(takeProfit - entry);
  const riskReward = risk > 0 ? reward / risk : 0;

  // ═══════════════════════════════════════════════════════════════
  // Final Result
  // ═══════════════════════════════════════════════════════════════
  const passed = strategyEnabled && 
                 (score >= 0.5 || !config.enabled) &&
                 (volatilityPassed || !config.volatilityFilter.enabled) &&
                 (trendAlignmentPassed || !config.trendAlignment.enabled) &&
                 (volumeBreakoutPassed || !config.volumeBreakout.enabled);

  return {
    passed,
    score: Math.max(0, Math.min(1, score)),
    
    volatilityPassed,
    trendAlignmentPassed,
    volumeBreakoutPassed,
    strategyEnabled,
    
    computedValues: {
      atr,
      atrSMA,
      volatilityRatio,
      ema50,
      ema200,
      trendDirection,
      currentVolume,
      volumeSMA,
      volumeRatio,
    },
    
    adjustedLevels: {
      stopLoss,
      takeProfit,
      riskReward,
    },
    
    rejectionReasons,
  };
}

/**
 * Determine trend direction based on price and EMAs
 */
function determineTrendDirection(
  price: number, 
  ema50: number, 
  ema200: number
): 'UP' | 'DOWN' | 'NEUTRAL' {
  // Price above both EMAs = UP trend
  if (price > ema50 && price > ema200) return 'UP';
  
  // Price below both EMAs = DOWN trend
  if (price < ema50 && price < ema200) return 'DOWN';
  
  // Mixed = use EMA50 as primary signal
  if (price > ema50) return 'UP';
  if (price < ema50) return 'DOWN';
  
  return 'NEUTRAL';
}

// ═══════════════════════════════════════════════════════════════
// Utility Functions
// ═══════════════════════════════════════════════════════════════

/**
 * Check if strategy/pattern is disabled
 */
export function isStrategyDisabled(
  patternType: string,
  config: CalibrationFilterConfig = DEFAULT_CALIBRATION_FILTER_CONFIG
): boolean {
  return config.disabledStrategies.includes(patternType);
}

/**
 * Get calibration-adjusted TP/SL levels
 */
export function getAdjustedLevels(
  entry: number,
  direction: 'LONG' | 'SHORT',
  atr: number,
  config: CalibrationFilterConfig = DEFAULT_CALIBRATION_FILTER_CONFIG
): { stopLoss: number; takeProfit: number; riskReward: number } {
  const slDistance = atr * config.atrRiskManagement.stopLossATR;
  const tpDistance = atr * config.atrRiskManagement.takeProfitATR;

  let stopLoss: number;
  let takeProfit: number;

  if (direction === 'LONG') {
    stopLoss = entry - slDistance;
    takeProfit = entry + tpDistance;
  } else {
    stopLoss = entry + slDistance;
    takeProfit = entry - tpDistance;
  }

  const risk = Math.abs(entry - stopLoss);
  const reward = Math.abs(takeProfit - entry);
  const riskReward = risk > 0 ? reward / risk : 0;

  return { stopLoss, takeProfit, riskReward };
}

/**
 * Batch filter scenarios
 */
export function filterScenarios<T extends { patternType: string; direction: 'LONG' | 'SHORT'; entry: number }>(
  scenarios: T[],
  candles: CandleWithVolume[],
  config: CalibrationFilterConfig = DEFAULT_CALIBRATION_FILTER_CONFIG
): {
  passed: T[];
  rejected: T[];
  results: Map<T, CalibrationFilterResult>;
  stats: {
    total: number;
    passed: number;
    rejected: number;
    byReason: Record<string, number>;
  };
} {
  const passed: T[] = [];
  const rejected: T[] = [];
  const results = new Map<T, CalibrationFilterResult>();
  const byReason: Record<string, number> = {};

  for (const scenario of scenarios) {
    const result = applyCalibrationFilters({
      candles,
      direction: scenario.direction,
      patternType: scenario.patternType,
      entry: scenario.entry,
    }, config);

    results.set(scenario, result);

    if (result.passed) {
      passed.push(scenario);
    } else {
      rejected.push(scenario);
      for (const reason of result.rejectionReasons) {
        byReason[reason] = (byReason[reason] || 0) + 1;
      }
    }
  }

  return {
    passed,
    rejected,
    results,
    stats: {
      total: scenarios.length,
      passed: passed.length,
      rejected: rejected.length,
      byReason,
    },
  };
}
