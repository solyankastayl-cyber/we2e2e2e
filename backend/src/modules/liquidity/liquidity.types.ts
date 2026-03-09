/**
 * Liquidity Engine Types
 * 
 * Liquidity zones are areas where stop losses cluster:
 * - Equal Highs/Lows
 * - Swing Points
 * - Range boundaries
 * - Sweeps (stop hunts)
 */

export type LiquidityZoneType =
  | 'EQUAL_HIGHS'        // Multiple highs at same level
  | 'EQUAL_LOWS'         // Multiple lows at same level
  | 'SWEEP_UP'           // Price swept above then closed back
  | 'SWEEP_DOWN'         // Price swept below then closed back
  | 'RANGE_HIGH'         // Top of range/consolidation
  | 'RANGE_LOW'          // Bottom of range/consolidation
  | 'SWING_HIGH'         // Obvious swing high (stop cluster)
  | 'SWING_LOW'          // Obvious swing low (stop cluster)
  | 'ORDER_BLOCK_BULL'   // Bullish order block (demand zone)
  | 'ORDER_BLOCK_BEAR';  // Bearish order block (supply zone)

export interface LiquidityZone {
  type: LiquidityZoneType;
  price: number;
  priceRange: {
    low: number;
    high: number;
  };
  strength: number;       // 0-1, how significant
  touches: number;        // How many times tested
  swept: boolean;         // Has been swept?
  sweptAt?: number;       // Timestamp of sweep
  candleIndex: number;    // Index where formed
  timestamp: number;      // When formed
}

export interface SweepEvent {
  type: 'SWEEP_UP' | 'SWEEP_DOWN';
  zonePrice: number;
  wickHigh: number;
  wickLow: number;
  closePrice: number;
  candleIndex: number;
  timestamp: number;
  magnitude: number;      // How far past the zone
  recovered: boolean;     // Did price close back
}

export interface LiquidityAnalysis {
  asset: string;
  timeframe: string;
  timestamp: Date;
  
  // All detected zones
  zones: LiquidityZone[];
  
  // Recent sweep events
  sweeps: SweepEvent[];
  
  // Nearest zones to current price
  nearestResistance: LiquidityZone | null;
  nearestSupport: LiquidityZone | null;
  
  // Summary metrics
  metrics: {
    zonesAbove: number;
    zonesBelow: number;
    recentSweepUp: boolean;
    recentSweepDown: boolean;
    liquidityBias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    distanceToNearestZoneATR: number;
  };
}

export interface Candle {
  openTime: number;
  closeTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface LiquidityConfig {
  // Equal High/Low detection
  equalLevelTolerance: number;    // % tolerance for "equal" levels
  minEqualTouches: number;        // Minimum touches for equal level
  
  // Swing detection
  swingLookback: number;          // Bars to look back for swings
  swingStrengthBars: number;      // Bars on each side for valid swing
  
  // Sweep detection
  sweepRecoveryBars: number;      // Bars to close back after sweep
  sweepMinWickRatio: number;      // Min wick vs body ratio
  
  // Range detection
  rangeLookback: number;          // Bars for range detection
  rangeAtrMultiplier: number;     // Max range width in ATR
  
  // General
  maxZones: number;               // Max zones to track
  recentBarsForSweep: number;     // Bars to consider "recent" sweep
}

export const DEFAULT_LIQUIDITY_CONFIG: LiquidityConfig = {
  equalLevelTolerance: 0.002,     // 0.2% tolerance
  minEqualTouches: 2,
  swingLookback: 50,
  swingStrengthBars: 3,
  sweepRecoveryBars: 3,
  sweepMinWickRatio: 0.5,
  rangeLookback: 30,
  rangeAtrMultiplier: 3,
  maxZones: 20,
  recentBarsForSweep: 10,
};
