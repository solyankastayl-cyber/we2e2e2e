/**
 * Edge Attribution Types (P5.0.1)
 * 
 * Core contracts for edge analysis
 */

/**
 * Dimensions for edge attribution
 */
export type EdgeDimension = 
  | 'pattern'
  | 'family'
  | 'regime'
  | 'geometry'
  | 'ml_bucket'
  | 'stability_bucket'
  | 'timeframe'
  | 'asset';

/**
 * Outcome classification
 */
export type OutcomeClass = 
  | 'WIN'
  | 'LOSS'
  | 'PARTIAL'
  | 'TIMEOUT'
  | 'NO_ENTRY'
  | 'UNKNOWN';

/**
 * Single edge row (per-trade data)
 */
export interface EdgeRow {
  // Identity
  runId: string;
  decisionRunId?: string;
  outcomeId?: string;
  
  // Asset/Time
  asset: string;
  timeframe: string;
  ts: number;
  closedAt?: number;
  
  // Pattern info
  patternTypes: string[];
  primaryPatternType: string;
  patternFamily: string;
  
  // Market context
  regime: string;
  volRegime: string;
  
  // Predictions
  pEntry: number;
  expectedR: number;
  ev: number;  // pEntry * expectedR
  
  // Realized outcome
  realizedR: number;
  mfeR: number;   // Max Favorable Excursion
  maeR: number;   // Max Adverse Excursion
  outcomeClass: OutcomeClass;
  
  // ML info
  mlProb?: number;
  mlStage?: string;
  probabilitySource: string;
  
  // Stability
  stabilityMultiplier: number;
  
  // Geometry
  geometry: {
    fitError: number;
    maturity: number;
    compression: number;
    symmetry?: number;
  };
  
  // Buckets (computed)
  mlBucket?: string;
  stabilityBucket?: string;
  maturityBucket?: string;
  fitErrorBucket?: string;
  compressionBucket?: string;
}

/**
 * Aggregated edge statistics
 */
export interface EdgeAggregate {
  dimension: EdgeDimension;
  key: string;
  
  // Sample
  sampleSize: number;
  winCount: number;
  lossCount: number;
  partialCount: number;
  timeoutCount: number;
  
  // Win rate
  winRate: number;
  winRateShrunk: number;
  
  // R metrics
  avgR: number;
  avgRShrunk: number;
  medianR: number;
  p10R: number;
  p50R: number;
  p90R: number;
  
  // EV metrics
  avgEV: number;
  edge: number;           // avgR - avgEV
  edgeShrunk: number;
  
  // Performance
  profitFactor: number;
  maxDrawdownR: number;
  sharpeR: number;
  evCorrelation: number;
  
  // Composite score
  edgeScore: number;
  
  // Timestamp
  updatedAt: Date;
}

/**
 * Edge rebuild request
 */
export interface EdgeRebuildRequest {
  from?: Date;
  to?: Date;
  assets?: string[];
  timeframes?: string[];
  force?: boolean;
}

/**
 * Edge rebuild result
 */
export interface EdgeRebuildResult {
  edgeRunId: string;
  status: 'SUCCESS' | 'FAILED' | 'PARTIAL';
  rowsProcessed: number;
  aggregatesCreated: number;
  duration: number;
  errors?: string[];
}

/**
 * Edge run record
 */
export interface EdgeRun {
  runId: string;
  params: EdgeRebuildRequest;
  startedAt: Date;
  finishedAt?: Date;
  status: 'RUNNING' | 'SUCCESS' | 'FAILED';
  rowsProcessed: number;
  aggregatesCreated: number;
  globalBaseline?: GlobalBaseline;
}

/**
 * Global baseline for shrinkage
 */
export interface GlobalBaseline {
  totalSamples: number;
  globalWinRate: number;
  globalAvgR: number;
  globalAvgEV: number;
  globalPF: number;
}

/**
 * Edge health status
 */
export interface EdgeHealth {
  ok: boolean;
  outcomesCount: number;
  decisionsCount: number;
  hasRequiredFields: boolean;
  missingFields: string[];
  lastOutcomeTs?: number;
}

/**
 * Pattern family mapping
 */
export const PATTERN_FAMILIES: Record<string, string> = {
  // Triangles
  'TRIANGLE_ASC': 'TRIANGLES',
  'TRIANGLE_DESC': 'TRIANGLES',
  'TRIANGLE_SYM': 'TRIANGLES',
  'ASC_TRIANGLE': 'TRIANGLES',
  'DESC_TRIANGLE': 'TRIANGLES',
  
  // Channels
  'CHANNEL_UP': 'CHANNELS',
  'CHANNEL_DOWN': 'CHANNELS',
  'CHANNEL_HORIZ': 'CHANNELS',
  
  // Flags
  'FLAG_BULL': 'FLAGS',
  'FLAG_BEAR': 'FLAGS',
  'PENNANT': 'FLAGS',
  
  // Reversals
  'HS_TOP': 'REVERSALS',
  'HS_BOTTOM': 'REVERSALS',
  'IHS': 'REVERSALS',
  'DOUBLE_TOP': 'REVERSALS',
  'DOUBLE_BOTTOM': 'REVERSALS',
  
  // Harmonics
  'HARMONIC_GARTLEY': 'HARMONICS',
  'HARMONIC_BAT': 'HARMONICS',
  'HARMONIC_BUTTERFLY': 'HARMONICS',
  'HARMONIC_CRAB': 'HARMONICS',
  
  // Structure
  'BOS_BULL': 'STRUCTURE',
  'BOS_BEAR': 'STRUCTURE',
  'CHOCH_BULL': 'STRUCTURE',
  'CHOCH_BEAR': 'STRUCTURE',
  
  // Candles
  'CANDLE_ENGULF_BULL': 'CANDLES',
  'CANDLE_ENGULF_BEAR': 'CANDLES',
  'CANDLE_HAMMER': 'CANDLES',
  'CANDLE_STAR': 'CANDLES',
  
  // Divergences
  'RSI_DIV_BULL': 'DIVERGENCES',
  'RSI_DIV_BEAR': 'DIVERGENCES',
  'MACD_DIV_BULL': 'DIVERGENCES',
  'MACD_DIV_BEAR': 'DIVERGENCES',
};

/**
 * Get pattern family
 */
export function getPatternFamily(patternType: string): string {
  const upper = patternType.toUpperCase();
  
  // Check direct mapping
  if (PATTERN_FAMILIES[upper]) {
    return PATTERN_FAMILIES[upper];
  }
  
  // Infer from name
  if (upper.includes('TRIANGLE')) return 'TRIANGLES';
  if (upper.includes('CHANNEL')) return 'CHANNELS';
  if (upper.includes('FLAG') || upper.includes('PENNANT')) return 'FLAGS';
  if (upper.includes('HS') || upper.includes('HEAD') || upper.includes('DOUBLE') || upper.includes('TRIPLE')) return 'REVERSALS';
  if (upper.includes('HARMONIC') || upper.includes('GARTLEY') || upper.includes('BAT')) return 'HARMONICS';
  if (upper.includes('BOS') || upper.includes('CHOCH')) return 'STRUCTURE';
  if (upper.includes('CANDLE') || upper.includes('ENGULF') || upper.includes('HAMMER')) return 'CANDLES';
  if (upper.includes('DIV')) return 'DIVERGENCES';
  if (upper.includes('WEDGE')) return 'WEDGES';
  if (upper.includes('GAP')) return 'GAPS';
  
  return 'OTHER';
}
