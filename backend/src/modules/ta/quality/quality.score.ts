/**
 * P2.0 — Pattern Quality Scoring Engine
 * 
 * Automatically evaluates pattern quality based on historical performance:
 * - winRate, avgR, profitFactor
 * - calibration (ECE, Brier)
 * - stability across time windows
 * - decay weighting
 * 
 * Produces qualityScore (0..1) and multiplier (0.6..1.4)
 */

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type Regime = 'TREND_UP' | 'TREND_DOWN' | 'RANGE' | 'TRANSITION';

export interface QualityKey {
  patternType: string;
  asset: string;
  tf: string;
  regime: Regime;
}

export interface PatternQualityDoc extends QualityKey {
  n: number;
  
  winRate: number;
  avgR: number;
  profitFactor: number;
  maxDrawdownR: number;
  
  ece: number;
  brier: number;
  
  stability: number;
  decayHalfLifeDays: number;
  
  qualityScore: number;   // 0..1
  multiplier: number;     // 0.6..1.4
  
  updatedAt: string;
}

// ═══════════════════════════════════════════════════════════════
// NORMALIZATION FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

// Win rate: 25% -> 60%
function normWinRate(w: number): number {
  return clamp01((w - 0.25) / (0.60 - 0.25));
}

// Profit factor: 1.0 -> 2.0
function normPF(pf: number): number {
  return clamp01((pf - 1.0) / (2.0 - 1.0));
}

// Average R: 0 -> 0.8
function normAvgR(r: number): number {
  return clamp01((r - 0.0) / (0.8 - 0.0));
}

// ECE: 0 -> 0.15 (lower is better)
function normECE(e: number): number {
  return clamp01(e / 0.15);
}

// Stability: already 0..1
function normStability(s: number): number {
  return clamp01(s);
}

// ═══════════════════════════════════════════════════════════════
// QUALITY SCORE CALCULATION
// ═══════════════════════════════════════════════════════════════

export interface MetricsForQuality {
  winRate: number;
  profitFactor: number;
  avgR: number;
  ece: number;
  stability: number;
}

export interface QualityScoreResult {
  qualityScore: number;
  multiplier: number;
}

/**
 * Compute quality score from metrics
 * 
 * Formula:
 * qualityScore = 0.35*winRate + 0.25*PF + 0.20*avgR + 0.10*(1-ECE) + 0.10*stability
 * 
 * multiplier = clamp(0.7 + 0.8*qualityScore, 0.6, 1.4)
 */
export function computeQualityScore(m: MetricsForQuality): QualityScoreResult {
  const wr = normWinRate(m.winRate);
  const pf = normPF(m.profitFactor);
  const ar = normAvgR(m.avgR);
  const ece = 1 - normECE(m.ece);
  const st = normStability(m.stability);
  
  const qualityScore =
    0.35 * wr +
    0.25 * pf +
    0.20 * ar +
    0.10 * ece +
    0.10 * st;
  
  const multiplierRaw = 0.7 + 0.8 * qualityScore;
  const multiplier = Math.max(0.6, Math.min(1.4, multiplierRaw));
  
  return { qualityScore, multiplier };
}

// ═══════════════════════════════════════════════════════════════
// DECAY WEIGHT
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate decay weight for a trade based on age
 * 
 * w = exp(-ageDays / halfLifeDays)
 */
export function decayWeight(ageDays: number, halfLifeDays: number = 120): number {
  return Math.exp(-ageDays / halfLifeDays);
}

// ═══════════════════════════════════════════════════════════════
// STABILITY CALCULATION
// ═══════════════════════════════════════════════════════════════

export interface WindowMetrics {
  windowDays: number;
  winRate: number;
  avgR: number;
}

/**
 * Calculate stability from rolling window metrics
 * 
 * Measures how consistent winRate is across windows:
 * - last 30d
 * - last 90d
 * - last 180d
 * 
 * stability = 1 - stdWinRate / 0.15
 */
export function calculateStability(windows: WindowMetrics[]): number {
  if (windows.length < 2) return 0.5;
  
  const winRates = windows.map(w => w.winRate);
  const mean = winRates.reduce((a, b) => a + b, 0) / winRates.length;
  const variance = winRates.reduce((sum, wr) => sum + Math.pow(wr - mean, 2), 0) / winRates.length;
  const std = Math.sqrt(variance);
  
  // Convert to 0..1 where lower std = higher stability
  const stability = clamp01(1 - std / 0.15);
  
  return stability;
}
