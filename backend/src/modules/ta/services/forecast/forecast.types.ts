/**
 * Forecast Types (P4.4)
 * 
 * Contracts for forecast engine
 */

/**
 * Single point on forecast path
 */
export interface ForecastPoint {
  t: number;        // Unix timestamp or bar offset
  price: number;
}

/**
 * Bands point with percentiles
 */
export interface ForecastBandsPoint {
  t: number;
  p10: number;
  p50: number;
  p90: number;
}

/**
 * Event types
 */
export type ForecastEventKind = 
  | 'BREAKOUT'
  | 'RETEST'
  | 'LEVEL_TOUCH'
  | 'TARGET_HIT'
  | 'STOP_HIT'
  | 'TIMEOUT'
  | 'REGIME_SHIFT'
  | 'MIDLINE_TOUCH';

/**
 * Forecast event
 */
export interface ForecastEvent {
  kind: ForecastEventKind;
  t: number;
  price: number;
  confidence: number;
  barOffset: number;
  meta?: Record<string, any>;
}

/**
 * Source weights used in forecast
 */
export interface ForecastSources {
  projectorWeight: number;
  scenarioWeight: number;
  stabilityWeight: number;
  mlWeight: number;
}

/**
 * Forecast statistics
 */
export interface ForecastStats {
  expectedReturnPct: number;
  expectedVolPct: number;
  maxDrawdownPct: number;
  probUp: number;
  probDown: number;
  horizonBars: number;
}

/**
 * Projection metadata
 */
export interface ProjectionMeta {
  patternType?: string;
  breakoutLevel?: number;
  measuredMove?: number;
  projectionConfidence: number;
  method: 'PATTERN_PROJECTOR' | 'SCENARIO_MC' | 'BLENDED' | 'FALLBACK';
}

/**
 * Complete Forecast Pack
 */
export interface ForecastPack {
  runId: string;
  decisionRunId?: string;
  intelligenceRunId?: string;
  
  asset: string;
  tf: string;
  
  nowTs: number;
  priceNow: number;
  
  horizonBars: number;
  
  // Main forecast path (expected)
  path: ForecastPoint[];
  
  // Probability bands
  bands: ForecastBandsPoint[];
  
  // Events
  events: ForecastEvent[];
  
  // Sources
  sources: ForecastSources;
  
  // Statistics
  stats: ForecastStats;
  
  // Projection metadata
  projection: ProjectionMeta;
  
  // Timestamps
  createdAt: Date;
}

/**
 * Input for forecast computation
 */
export interface ForecastComputeInput {
  asset: string;
  timeframe: string;
  
  // From decision/intelligence
  priceNow: number;
  target?: number;
  stop?: number;
  bias?: 'LONG' | 'SHORT' | 'WAIT';
  
  // Pattern info
  patternType?: string;
  breakoutLevel?: number;
  measuredMove?: number;
  
  // Scenario bands
  scenarioBands?: {
    p10: number;
    p50: number;
    p90: number;
  };
  
  // Volatility
  atrPct?: number;
  
  // Stability
  stabilityMultiplier?: number;
}

/**
 * Horizon bars by timeframe
 */
export const HORIZON_BARS: Record<string, number> = {
  '1m': 60,
  '5m': 60,
  '15m': 56,
  '30m': 48,
  '1h': 48,
  '4h': 42,
  '1d': 30,
  '1w': 26,
  '1M': 18
};

/**
 * Get horizon bars for timeframe
 */
export function getHorizonBars(tf: string): number {
  return HORIZON_BARS[tf.toLowerCase()] || 30;
}
