/**
 * Phase 9 — Regime Intelligence Engine Types
 * 
 * Market regime classification and transitions
 */

// ═══════════════════════════════════════════════════════════════
// MARKET REGIMES
// ═══════════════════════════════════════════════════════════════

export type MarketRegime = 
  | 'TREND_EXPANSION'
  | 'TREND_CONTINUATION'
  | 'RANGE_ROTATION'
  | 'COMPRESSION'
  | 'BREAKOUT_PREP'
  | 'VOLATILITY_EXPANSION'
  | 'LIQUIDITY_HUNT'
  | 'ACCUMULATION'
  | 'DISTRIBUTION';

export const REGIME_DESCRIPTIONS: Record<MarketRegime, string> = {
  'TREND_EXPANSION': 'Strong directional move with increasing volatility',
  'TREND_CONTINUATION': 'Steady directional move, low volatility',
  'RANGE_ROTATION': 'Price oscillating between support and resistance',
  'COMPRESSION': 'Decreasing volatility, building energy',
  'BREAKOUT_PREP': 'Compression near key level, ready for breakout',
  'VOLATILITY_EXPANSION': 'Sudden increase in volatility without clear direction',
  'LIQUIDITY_HUNT': 'Price sweeping liquidity zones',
  'ACCUMULATION': 'Institutional buying in range',
  'DISTRIBUTION': 'Institutional selling in range'
};

// ═══════════════════════════════════════════════════════════════
// REGIME FEATURES
// ═══════════════════════════════════════════════════════════════

export interface RegimeFeatures {
  // Trend
  trendStrength: number;    // ADX-like (0-1)
  trendDirection: number;   // -1 to 1 (bear to bull)
  
  // Volatility
  volatility: number;       // ATR / mean ATR
  volatilityTrend: number;  // Change in ATR (-1 to 1)
  
  // Compression
  compression: number;      // Bollinger width ratio
  compressionTrend: number; // Change in compression
  
  // Range
  rangeScore: number;       // HH/HL structure quality
  rangeWidth: number;       // Range as % of price
  
  // Liquidity
  liquidityActivity: number; // Sweep frequency
  liquidityBias: number;     // -1 (sweeping lows) to 1 (sweeping highs)
  
  // Momentum
  momentum: number;         // MACD slope normalized
  momentumDivergence: number; // Price vs momentum divergence
  
  // Volume
  volumeProfile: number;    // Current vs average volume
  volumeTrend: number;      // Volume trend
}

// ═══════════════════════════════════════════════════════════════
// REGIME DETECTION RESULT
// ═══════════════════════════════════════════════════════════════

export interface RegimeDetectionResult {
  regime: MarketRegime;
  confidence: number;
  
  // Sub-scores
  scores: {
    trendScore: number;
    rangeScore: number;
    compressionScore: number;
    volatilityScore: number;
    liquidityScore: number;
  };
  
  // Features used
  features: RegimeFeatures;
  
  // Probabilities for all regimes
  probabilities: Record<MarketRegime, number>;
  
  // Time
  detectedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// REGIME HISTORY
// ═══════════════════════════════════════════════════════════════

export interface RegimeHistoryRecord {
  asset: string;
  timeframe: string;
  timestamp: Date;
  regime: MarketRegime;
  confidence: number;
  features: RegimeFeatures;
  duration?: number;  // Bars in this regime
}

// ═══════════════════════════════════════════════════════════════
// REGIME TRANSITIONS
// ═══════════════════════════════════════════════════════════════

export interface RegimeTransition {
  from: MarketRegime;
  to: MarketRegime;
  probability: number;
  avgDuration: number;  // Avg bars before transition
  sampleSize: number;
}

export const BASE_REGIME_TRANSITIONS: Array<Omit<RegimeTransition, 'sampleSize' | 'avgDuration'>> = [
  // From COMPRESSION
  { from: 'COMPRESSION', to: 'BREAKOUT_PREP', probability: 0.35 },
  { from: 'COMPRESSION', to: 'TREND_EXPANSION', probability: 0.25 },
  { from: 'COMPRESSION', to: 'RANGE_ROTATION', probability: 0.25 },
  { from: 'COMPRESSION', to: 'VOLATILITY_EXPANSION', probability: 0.15 },
  
  // From BREAKOUT_PREP
  { from: 'BREAKOUT_PREP', to: 'TREND_EXPANSION', probability: 0.50 },
  { from: 'BREAKOUT_PREP', to: 'COMPRESSION', probability: 0.25 },
  { from: 'BREAKOUT_PREP', to: 'LIQUIDITY_HUNT', probability: 0.25 },
  
  // From TREND_EXPANSION
  { from: 'TREND_EXPANSION', to: 'TREND_CONTINUATION', probability: 0.40 },
  { from: 'TREND_EXPANSION', to: 'DISTRIBUTION', probability: 0.25 },
  { from: 'TREND_EXPANSION', to: 'COMPRESSION', probability: 0.20 },
  { from: 'TREND_EXPANSION', to: 'VOLATILITY_EXPANSION', probability: 0.15 },
  
  // From TREND_CONTINUATION
  { from: 'TREND_CONTINUATION', to: 'TREND_EXPANSION', probability: 0.35 },
  { from: 'TREND_CONTINUATION', to: 'COMPRESSION', probability: 0.30 },
  { from: 'TREND_CONTINUATION', to: 'DISTRIBUTION', probability: 0.20 },
  { from: 'TREND_CONTINUATION', to: 'RANGE_ROTATION', probability: 0.15 },
  
  // From RANGE_ROTATION
  { from: 'RANGE_ROTATION', to: 'BREAKOUT_PREP', probability: 0.30 },
  { from: 'RANGE_ROTATION', to: 'ACCUMULATION', probability: 0.25 },
  { from: 'RANGE_ROTATION', to: 'DISTRIBUTION', probability: 0.25 },
  { from: 'RANGE_ROTATION', to: 'COMPRESSION', probability: 0.20 },
  
  // From ACCUMULATION
  { from: 'ACCUMULATION', to: 'BREAKOUT_PREP', probability: 0.45 },
  { from: 'ACCUMULATION', to: 'TREND_EXPANSION', probability: 0.30 },
  { from: 'ACCUMULATION', to: 'RANGE_ROTATION', probability: 0.25 },
  
  // From DISTRIBUTION
  { from: 'DISTRIBUTION', to: 'TREND_EXPANSION', probability: 0.35 },  // Bear trend
  { from: 'DISTRIBUTION', to: 'RANGE_ROTATION', probability: 0.35 },
  { from: 'DISTRIBUTION', to: 'COMPRESSION', probability: 0.30 },
  
  // From LIQUIDITY_HUNT
  { from: 'LIQUIDITY_HUNT', to: 'TREND_EXPANSION', probability: 0.45 },
  { from: 'LIQUIDITY_HUNT', to: 'RANGE_ROTATION', probability: 0.30 },
  { from: 'LIQUIDITY_HUNT', to: 'COMPRESSION', probability: 0.25 },
  
  // From VOLATILITY_EXPANSION
  { from: 'VOLATILITY_EXPANSION', to: 'TREND_EXPANSION', probability: 0.35 },
  { from: 'VOLATILITY_EXPANSION', to: 'COMPRESSION', probability: 0.35 },
  { from: 'VOLATILITY_EXPANSION', to: 'RANGE_ROTATION', probability: 0.30 }
];

// ═══════════════════════════════════════════════════════════════
// REGIME BOOST
// ═══════════════════════════════════════════════════════════════

export interface RegimeBoost {
  regime: MarketRegime;
  pattern: string;
  boost: number;  // Multiplier
  sampleSize: number;
}

// Default boosts per pattern family in each regime
export const REGIME_PATTERN_BOOSTS: Record<MarketRegime, Record<string, number>> = {
  'TREND_EXPANSION': {
    'FLAG': 1.25,
    'TRIANGLE': 1.15,
    'BREAKOUT': 1.30,
    'REVERSAL': 0.70
  },
  'TREND_CONTINUATION': {
    'FLAG': 1.30,
    'TRIANGLE': 1.20,
    'CHANNEL': 1.15,
    'REVERSAL': 0.75
  },
  'RANGE_ROTATION': {
    'REVERSAL': 1.25,
    'DOUBLE': 1.30,
    'HARMONIC': 1.20,
    'BREAKOUT': 0.70
  },
  'COMPRESSION': {
    'TRIANGLE': 1.35,
    'FLAG': 1.15,
    'CHANNEL': 1.10,
    'BREAKOUT': 0.90
  },
  'BREAKOUT_PREP': {
    'TRIANGLE': 1.40,
    'BREAKOUT': 1.35,
    'FLAG': 1.20,
    'REVERSAL': 0.80
  },
  'VOLATILITY_EXPANSION': {
    'BREAKOUT': 0.80,
    'REVERSAL': 1.10,
    'FLAG': 0.75,
    'TRIANGLE': 0.80
  },
  'LIQUIDITY_HUNT': {
    'SWEEP': 1.40,
    'REVERSAL': 1.30,
    'DOUBLE': 1.25,
    'BREAKOUT': 0.85
  },
  'ACCUMULATION': {
    'DOUBLE': 1.25,
    'HARMONIC': 1.20,
    'TRIANGLE': 1.15,
    'FLAG': 1.10
  },
  'DISTRIBUTION': {
    'DOUBLE': 1.25,
    'REVERSAL': 1.20,
    'HARMONIC': 1.15,
    'FLAG': 1.10
  }
};

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

export interface RegimeConfig {
  lookbackBars: number;
  minConfidence: number;
  smoothingFactor: number;  // EMA for regime persistence
  transitionThreshold: number;  // Min diff to switch regimes
}

export const DEFAULT_REGIME_CONFIG: RegimeConfig = {
  lookbackBars: 100,
  minConfidence: 0.5,
  smoothingFactor: 0.3,
  transitionThreshold: 0.15
};
