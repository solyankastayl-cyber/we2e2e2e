/**
 * Phase 6 — Indicators Types
 * ===========================
 * RSI, Volume Profile, Open Interest, Macro
 */

// ═══════════════════════════════════════════════════════════════
// RSI / MOMENTUM
// ═══════════════════════════════════════════════════════════════

export interface RSIResult {
  value: number;              // 0-100
  signal: 'OVERBOUGHT' | 'OVERSOLD' | 'NEUTRAL';
  divergence?: RSIDivergence;
  trend: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  strength: number;           // 0-1
}

export interface RSIDivergence {
  type: 'BULLISH' | 'BEARISH' | 'HIDDEN_BULLISH' | 'HIDDEN_BEARISH';
  confidence: number;
  priceAction: 'HIGHER_HIGH' | 'LOWER_LOW' | 'HIGHER_LOW' | 'LOWER_HIGH';
  rsiAction: 'HIGHER_HIGH' | 'LOWER_LOW' | 'HIGHER_LOW' | 'LOWER_HIGH';
}

export interface MomentumState {
  rsi: RSIResult;
  macd?: MACDResult;
  stochastic?: StochasticResult;
  composite: number;          // 0-1, combined momentum score
  bias: 'LONG' | 'SHORT' | 'NEUTRAL';
}

export interface MACDResult {
  macd: number;
  signal: number;
  histogram: number;
  crossover: 'BULLISH' | 'BEARISH' | 'NONE';
}

export interface StochasticResult {
  k: number;
  d: number;
  signal: 'OVERBOUGHT' | 'OVERSOLD' | 'NEUTRAL';
}

// ═══════════════════════════════════════════════════════════════
// VOLUME PROFILE
// ═══════════════════════════════════════════════════════════════

export interface VolumeProfileLevel {
  price: number;
  volume: number;
  percentage: number;         // % of total volume
  type: 'POC' | 'VAH' | 'VAL' | 'HVN' | 'LVN' | 'NORMAL';
}

export interface VolumeProfileResult {
  poc: number;                // Point of Control (highest volume price)
  vah: number;                // Value Area High (70% of volume)
  val: number;                // Value Area Low
  valueAreaVolume: number;    // % of volume in VA
  
  levels: VolumeProfileLevel[];
  
  hvn: number[];              // High Volume Nodes
  lvn: number[];              // Low Volume Nodes
  
  currentPricePosition: 'ABOVE_VA' | 'BELOW_VA' | 'IN_VA' | 'AT_POC';
  
  support: number[];          // Volume-based support
  resistance: number[];       // Volume-based resistance
}

// ═══════════════════════════════════════════════════════════════
// OPEN INTEREST / POSITIONING
// ═══════════════════════════════════════════════════════════════

export interface OpenInterestData {
  current: number;
  change24h: number;
  changePct24h: number;
  
  longRatio: number;          // % of longs
  shortRatio: number;         // % of shorts
  
  fundingRate: number;        // Current funding rate
  fundingTrend: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';
  
  liquidationLevels: LiquidationLevel[];
}

export interface LiquidationLevel {
  price: number;
  side: 'LONG' | 'SHORT';
  volume: number;             // Estimated liquidation volume
  leverage: number;           // Average leverage at this level
}

export interface PositioningState {
  oi: OpenInterestData;
  
  sentiment: 'EXTREMELY_BULLISH' | 'BULLISH' | 'NEUTRAL' | 'BEARISH' | 'EXTREMELY_BEARISH';
  crowdedSide: 'LONG' | 'SHORT' | 'BALANCED';
  
  contrarian: boolean;        // True if positioning suggests contrarian trade
  
  nextLiquidationZone: {
    price: number;
    side: 'LONG' | 'SHORT';
    distance: number;         // % from current price
  } | null;
}

// ═══════════════════════════════════════════════════════════════
// MACRO
// ═══════════════════════════════════════════════════════════════

export interface MacroData {
  fearGreedIndex: {
    value: number;            // 0-100
    classification: 'EXTREME_FEAR' | 'FEAR' | 'NEUTRAL' | 'GREED' | 'EXTREME_GREED';
    change24h: number;
  };
  
  btcDominance: {
    value: number;            // % (e.g., 52.3)
    change7d: number;
    trend: 'RISING' | 'FALLING' | 'STABLE';
  };
  
  altDominance: {
    value: number;            // % (100 - BTC.D - stables)
    change7d: number;
    trend: 'RISING' | 'FALLING' | 'STABLE';
  };
  
  totalMarketCap: number;
  totalMarketCapChange24h: number;
}

export interface MacroBoost {
  fearGreedFactor: number;    // 0.8 - 1.2
  dominanceFactor: number;    // 0.9 - 1.1
  combined: number;           // Final multiplier
  
  signal: 'RISK_ON' | 'RISK_OFF' | 'NEUTRAL';
  
  notes: string[];
}

// ═══════════════════════════════════════════════════════════════
// COMBINED INDICATOR STATE
// ═══════════════════════════════════════════════════════════════

export interface IndicatorState {
  symbol: string;
  timeframe: string;
  
  momentum: MomentumState;
  volumeProfile: VolumeProfileResult;
  positioning: PositioningState;
  macro: MacroBoost;
  
  // Combined boosts for decision engine
  boosts: {
    momentum: number;         // 0.7 - 1.3
    volume: number;           // 0.8 - 1.2
    positioning: number;      // 0.7 - 1.3
    macro: number;            // 0.8 - 1.2
  };
  
  compositeBoost: number;     // Product of all boosts
  
  lastUpdated: number;
}
