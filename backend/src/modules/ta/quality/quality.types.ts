/**
 * P2.0 — Quality Types
 */

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

export interface QualityRebuildConfig {
  assets: string[];
  timeframes: string[];
  regimes: Regime[];
  fromTs?: number;
  toTs?: number;
  halfLifeDays?: number;
  minN?: number;
}

export interface QualityQueryParams {
  patternType?: string;
  asset?: string;
  tf?: string;
  regime?: Regime;
  limit?: number;
}
