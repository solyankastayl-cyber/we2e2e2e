/**
 * Edge Buckets (P5.0.4)
 * 
 * Bucketization logic for edge dimensions
 */

/**
 * ML probability buckets
 */
export function getMlBucket(prob: number | undefined | null): string {
  if (prob === undefined || prob === null) return 'UNKNOWN';
  if (prob < 0.4) return 'LOW';
  if (prob < 0.55) return 'MED_LOW';
  if (prob < 0.7) return 'MED_HIGH';
  return 'HIGH';
}

/**
 * Stability multiplier buckets
 */
export function getStabilityBucket(multiplier: number | undefined | null): string {
  if (multiplier === undefined || multiplier === null) return 'UNKNOWN';
  if (multiplier < 0.9) return 'LOW';
  if (multiplier <= 1.1) return 'MED';
  return 'HIGH';
}

/**
 * Pattern maturity buckets (0-1)
 */
export function getMaturityBucket(maturity: number | undefined | null): string {
  if (maturity === undefined || maturity === null) return 'UNKNOWN';
  if (maturity < 0.4) return 'EARLY';
  if (maturity < 0.7) return 'MID';
  return 'LATE';
}

/**
 * Fit error buckets (lower is better)
 */
export function getFitErrorBucket(fitError: number | undefined | null): string {
  if (fitError === undefined || fitError === null) return 'UNKNOWN';
  if (fitError < 0.05) return 'TIGHT';
  if (fitError < 0.15) return 'MED';
  return 'LOOSE';
}

/**
 * Compression buckets (0-1)
 */
export function getCompressionBucket(compression: number | undefined | null): string {
  if (compression === undefined || compression === null) return 'UNKNOWN';
  if (compression < 0.4) return 'LOW';
  if (compression < 0.7) return 'MED';
  return 'HIGH';
}

/**
 * R-multiple buckets
 */
export function getRBucket(r: number): string {
  if (r < -2) return 'LARGE_LOSS';
  if (r < -1) return 'LOSS';
  if (r < 0) return 'SMALL_LOSS';
  if (r < 1) return 'SMALL_WIN';
  if (r < 2) return 'WIN';
  return 'LARGE_WIN';
}

/**
 * Regime normalization
 */
export function normalizeRegime(regime: string | undefined | null): string {
  if (!regime) return 'UNKNOWN';
  const upper = regime.toUpperCase();
  
  if (upper.includes('UP') || upper.includes('BULL')) return 'TREND_UP';
  if (upper.includes('DOWN') || upper.includes('BEAR')) return 'TREND_DOWN';
  if (upper.includes('RANGE') || upper.includes('SIDEWAYS')) return 'RANGE';
  
  return regime.toUpperCase();
}

/**
 * Vol regime normalization
 */
export function normalizeVolRegime(volRegime: string | undefined | null): string {
  if (!volRegime) return 'UNKNOWN';
  const upper = volRegime.toUpperCase();
  
  if (upper.includes('LOW')) return 'LOW';
  if (upper.includes('HIGH')) return 'HIGH';
  if (upper.includes('MED')) return 'MED';
  
  return 'MED';
}

/**
 * Apply all buckets to edge row
 */
export function applyBuckets(row: {
  mlProb?: number;
  stabilityMultiplier?: number;
  geometry?: {
    fitError?: number;
    maturity?: number;
    compression?: number;
  };
}): {
  mlBucket: string;
  stabilityBucket: string;
  maturityBucket: string;
  fitErrorBucket: string;
  compressionBucket: string;
} {
  return {
    mlBucket: getMlBucket(row.mlProb),
    stabilityBucket: getStabilityBucket(row.stabilityMultiplier),
    maturityBucket: getMaturityBucket(row.geometry?.maturity),
    fitErrorBucket: getFitErrorBucket(row.geometry?.fitError),
    compressionBucket: getCompressionBucket(row.geometry?.compression)
  };
}
