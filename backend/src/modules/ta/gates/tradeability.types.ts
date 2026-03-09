/**
 * P1.1 — Tradeability Gate Types
 * 
 * Gate layer to filter out scenarios that shouldn't be traded
 * Reduces noise, increases signal quality
 */

export interface TradeabilityResult {
  ok: boolean;
  gateScore: number;       // 0-1, higher is better
  reasons: GateReason[];
  passingGates: string[];
  failingGates: string[];
}

export type GateReason = 
  | 'RR_TOO_LOW'
  | 'ENTRY_TOO_FAR'
  | 'EXTREME_VOL'
  | 'LOW_VOL'
  | 'PATTERN_TOO_EARLY'
  | 'APEX_TOO_FAR'
  | 'NO_COMPRESSION'
  | 'INVALID_STOP'
  | 'INVALID_TARGET';

export interface GateConfig {
  enabled: boolean;
  
  // Risk/Reward
  minRR: number;              // minimum risk/reward ratio (default 1.2)
  
  // Entry feasibility
  maxEntryDistanceATR: number; // max distance to entry in ATR units (default 0.8)
  
  // Volatility filters
  maxVolatility: number;      // ATR/price max (default 0.08)
  minVolatility: number;      // ATR/price min (default 0.002)
  
  // Pattern maturity
  minTouches: number;         // minimum touches for pattern (default 3)
  maxApexDistancePct: number; // max distance to apex as % of pattern (default 0.7)
  
  // Compression
  minCompression: boolean;    // require compression before breakout
  
  // Score threshold
  minPassScore: number;       // minimum score to pass (default 0.5)
}

export const DEFAULT_GATE_CONFIG: GateConfig = {
  enabled: true,
  minRR: 1.2,
  maxEntryDistanceATR: 0.8,
  maxVolatility: 0.08,
  minVolatility: 0.002,
  minTouches: 3,
  maxApexDistancePct: 0.7,
  minCompression: false,
  minPassScore: 0.5,
};

export interface GateInput {
  // Scenario data
  entry: number;
  stop: number;
  target1: number;
  target2?: number;
  direction: 'LONG' | 'SHORT';
  patternType: string;
  
  // Pattern metadata
  touches?: number;
  apexDistanceBars?: number;
  patternLengthBars?: number;
  
  // Market context
  price: number;
  atr: number;
  
  // Optional compression indicator
  compression?: number;  // std(range)/ATR, lower = more compressed
}
