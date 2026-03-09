/**
 * Phase 8.6 — Core Calibration Loop Types
 * 
 * Filter configuration for improving edge:
 * - Volatility Filter: ATR > SMA(ATR) * 0.8
 * - Trend Alignment: Trade only in EMA50/EMA200 direction
 * - Volume Breakout: volume > SMA(volume) * 1.4
 * - ATR-based TP/SL: SL = 1.5 * ATR, TP = 2.5 * ATR
 * - Disabled Strategies: LIQUIDITY_SWEEP, RANGE_REVERSAL
 */

export interface CalibrationFilterConfig {
  enabled: boolean;
  
  // Volatility Filter
  volatilityFilter: {
    enabled: boolean;
    atrMultiplier: number;  // Default: 0.8
    atrPeriod: number;      // Default: 14
    smaPeriod: number;      // Default: 14
  };
  
  // Trend Alignment Filter
  trendAlignment: {
    enabled: boolean;
    emaShortPeriod: number;   // Default: 50
    emaLongPeriod: number;    // Default: 200
    requireBothAligned: boolean;  // If true, both EMAs must align
  };
  
  // Volume Breakout Filter
  volumeBreakout: {
    enabled: boolean;
    volumeMultiplier: number;  // Default: 1.4
    smaPeriod: number;         // Default: 20
  };
  
  // ATR-based TP/SL
  atrRiskManagement: {
    enabled: boolean;
    stopLossATR: number;    // Default: 1.5
    takeProfitATR: number;  // Default: 2.5
  };
  
  // Disabled Strategies
  disabledStrategies: string[];
}

export const DEFAULT_CALIBRATION_FILTER_CONFIG: CalibrationFilterConfig = {
  enabled: true,
  
  volatilityFilter: {
    enabled: true,
    atrMultiplier: 0.8,
    atrPeriod: 14,
    smaPeriod: 14,
  },
  
  trendAlignment: {
    enabled: true,
    emaShortPeriod: 50,
    emaLongPeriod: 200,
    requireBothAligned: false,  // Only EMA50 direction required
  },
  
  volumeBreakout: {
    enabled: true,
    volumeMultiplier: 1.4,
    smaPeriod: 20,
  },
  
  atrRiskManagement: {
    enabled: true,
    stopLossATR: 1.5,
    takeProfitATR: 2.5,
  },
  
  disabledStrategies: [
    'LIQUIDITY_SWEEP',
    'LIQUIDITY_SWEEP_HIGH',
    'LIQUIDITY_SWEEP_LOW',
    'RANGE_REVERSAL',
  ],
};

export interface CalibrationFilterInput {
  // Candle data
  candles: CandleWithVolume[];
  
  // Current trade direction
  direction: 'LONG' | 'SHORT';
  
  // Pattern/strategy type
  patternType: string;
  
  // Current entry price
  entry: number;
  
  // Optional pre-calculated values
  atr?: number;
  ema50?: number;
  ema200?: number;
  volumeSMA?: number;
}

export interface CandleWithVolume {
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface CalibrationFilterResult {
  passed: boolean;
  score: number;           // 0-1, higher is better
  
  // Individual filter results
  volatilityPassed: boolean;
  trendAlignmentPassed: boolean;
  volumeBreakoutPassed: boolean;
  strategyEnabled: boolean;
  
  // Computed values
  computedValues: {
    atr: number;
    atrSMA: number;
    volatilityRatio: number;
    ema50: number;
    ema200: number;
    trendDirection: 'UP' | 'DOWN' | 'NEUTRAL';
    currentVolume: number;
    volumeSMA: number;
    volumeRatio: number;
  };
  
  // Adjusted TP/SL
  adjustedLevels: {
    stopLoss: number;
    takeProfit: number;
    riskReward: number;
  };
  
  // Rejection reasons
  rejectionReasons: string[];
}

export type CalibrationFilterReason =
  | 'LOW_VOLATILITY'
  | 'TREND_MISALIGNED'
  | 'LOW_VOLUME'
  | 'STRATEGY_DISABLED';
