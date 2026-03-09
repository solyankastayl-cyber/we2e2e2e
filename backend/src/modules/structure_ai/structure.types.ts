/**
 * Phase 7 — Market Structure AI Layer
 * 
 * Transforms raw indicators into market events and event chains
 * 
 * Events: LIQUIDITY_SWEEP, COMPRESSION, BREAKOUT, RETEST, 
 *         EXPANSION, ACCUMULATION, DISTRIBUTION
 * 
 * Event Chain: SWEEP → COMPRESSION → BREAKOUT → EXPANSION
 */

// ==============================================
// Market Event Types
// ==============================================

export type MarketEventType = 
  | 'LIQUIDITY_SWEEP'
  | 'COMPRESSION'
  | 'BREAKOUT'
  | 'RETEST'
  | 'EXPANSION'
  | 'ACCUMULATION'
  | 'DISTRIBUTION'
  | 'TREND_CONTINUATION'
  | 'REVERSAL'
  | 'FAKE_BREAKOUT'
  | 'RANGE_BOUND'
  | 'VOLATILITY_SPIKE'
  | 'EXHAUSTION';

export type EventDirection = 'UP' | 'DOWN' | 'NEUTRAL';

export type StructureType = 
  | 'SWEEP_REVERSAL'
  | 'COMPRESSION_BREAKOUT'
  | 'ACCUMULATION_BREAKOUT'
  | 'DISTRIBUTION_BREAKDOWN'
  | 'TREND_CONTINUATION'
  | 'RANGE_EXPANSION'
  | 'FALSE_BREAKOUT_REVERSAL'
  | 'EXHAUSTION_REVERSAL';

// ==============================================
// Core Types
// ==============================================

/**
 * Single market event
 */
export interface MarketEvent {
  id: string;
  type: MarketEventType;
  direction: EventDirection;
  
  // Event quality
  probability: number;   // 0-1
  strength: number;      // 0-1
  confidence: number;    // 0-1
  
  // Context
  priceLevel?: number;
  priceRange?: { low: number; high: number };
  volume?: number;
  timestamp: number;
  
  // Related data
  triggerIndicators: string[];  // What triggered this event
  relatedPatterns?: string[];
  
  // Duration
  startCandle: number;
  endCandle?: number;
  duration?: number;
  
  // Notes
  notes: string[];
}

/**
 * Event chain - sequence of events
 */
export interface EventChain {
  id: string;
  events: MarketEventType[];
  currentIndex: number;
  
  // Chain progress
  completed: MarketEventType[];
  expected: MarketEventType[];
  
  // Chain quality
  probability: number;
  strength: number;
  
  // Direction
  direction: EventDirection;
}

/**
 * Market structure state
 */
export interface StructureState {
  symbol: string;
  timeframe: string;
  
  // Current structure type
  structure: StructureType;
  structureConfidence: number;
  
  // Current events
  currentEvents: MarketEvent[];
  
  // Active chain
  activeChain?: EventChain;
  
  // Expected next events
  expectedNext: MarketEventType[];
  expectedProbability: number;
  
  // Overall state
  bias: EventDirection;
  momentum: 'STRONG' | 'MODERATE' | 'WEAK';
  
  // Narrative
  narrative: string;
  
  // Metadata
  computedAt: number;
}

/**
 * Structure analysis input
 */
export interface StructureInput {
  symbol: string;
  timeframe: string;
  
  // Indicators
  rsi: { value: number; divergence?: 'BULL' | 'BEAR' | null };
  macd: { histogram: number; signal: number; crossover?: 'BULL' | 'BEAR' | null };
  volume: { current: number; average: number; spike: boolean };
  atr: { value: number; percentile: number };
  
  // Structure data
  equalHighs: boolean;
  equalLows: boolean;
  higherHigh: boolean;
  higherLow: boolean;
  lowerHigh: boolean;
  lowerLow: boolean;
  
  // Liquidity
  liquidityCluster?: { price: number; strength: number; swept: boolean };
  liquiditySweep?: { direction: 'UP' | 'DOWN'; price: number };
  
  // Patterns
  compression: boolean;
  compressionCandles?: number;
  breakout?: { direction: 'UP' | 'DOWN'; confirmed: boolean };
  
  // Market regime
  regime: 'TREND_UP' | 'TREND_DOWN' | 'RANGE' | 'TRANSITION';
  volRegime: 'LOW' | 'NORMAL' | 'HIGH' | 'EXTREME';
}

// ==============================================
// Event Chain Templates
// ==============================================

/**
 * Standard event chains
 */
export const EVENT_CHAINS: Record<string, MarketEventType[]> = {
  // Classic sweep reversal
  SWEEP_REVERSAL: ['LIQUIDITY_SWEEP', 'COMPRESSION', 'BREAKOUT', 'EXPANSION'],
  
  // Accumulation breakout
  ACCUMULATION: ['ACCUMULATION', 'COMPRESSION', 'BREAKOUT', 'EXPANSION'],
  
  // Distribution breakdown
  DISTRIBUTION: ['DISTRIBUTION', 'COMPRESSION', 'BREAKOUT', 'EXPANSION'],
  
  // Trend continuation
  TREND_CONTINUATION: ['RETEST', 'COMPRESSION', 'BREAKOUT', 'EXPANSION'],
  
  // Range expansion
  RANGE_EXPANSION: ['RANGE_BOUND', 'COMPRESSION', 'BREAKOUT', 'EXPANSION'],
  
  // False breakout reversal
  FALSE_BREAKOUT: ['BREAKOUT', 'FAKE_BREAKOUT', 'REVERSAL', 'EXPANSION'],
  
  // Exhaustion reversal
  EXHAUSTION: ['EXPANSION', 'EXHAUSTION', 'COMPRESSION', 'REVERSAL']
};

/**
 * Event probability transitions
 * P(next_event | current_event)
 */
export const EVENT_TRANSITIONS: Record<MarketEventType, Record<MarketEventType, number>> = {
  'LIQUIDITY_SWEEP': {
    'COMPRESSION': 0.65,
    'BREAKOUT': 0.15,
    'REVERSAL': 0.10,
    'RANGE_BOUND': 0.10
  } as any,
  
  'COMPRESSION': {
    'BREAKOUT': 0.55,
    'FAKE_BREAKOUT': 0.15,
    'RANGE_BOUND': 0.20,
    'EXHAUSTION': 0.10
  } as any,
  
  'BREAKOUT': {
    'EXPANSION': 0.50,
    'RETEST': 0.25,
    'FAKE_BREAKOUT': 0.15,
    'COMPRESSION': 0.10
  } as any,
  
  'RETEST': {
    'BREAKOUT': 0.45,
    'EXPANSION': 0.30,
    'COMPRESSION': 0.15,
    'REVERSAL': 0.10
  } as any,
  
  'EXPANSION': {
    'TREND_CONTINUATION': 0.35,
    'EXHAUSTION': 0.25,
    'COMPRESSION': 0.25,
    'RETEST': 0.15
  } as any,
  
  'ACCUMULATION': {
    'COMPRESSION': 0.50,
    'BREAKOUT': 0.30,
    'RANGE_BOUND': 0.20
  } as any,
  
  'DISTRIBUTION': {
    'COMPRESSION': 0.50,
    'BREAKOUT': 0.30,
    'RANGE_BOUND': 0.20
  } as any,
  
  'FAKE_BREAKOUT': {
    'REVERSAL': 0.60,
    'COMPRESSION': 0.25,
    'RANGE_BOUND': 0.15
  } as any,
  
  'REVERSAL': {
    'EXPANSION': 0.45,
    'COMPRESSION': 0.30,
    'RETEST': 0.25
  } as any,
  
  'EXHAUSTION': {
    'REVERSAL': 0.50,
    'COMPRESSION': 0.30,
    'RANGE_BOUND': 0.20
  } as any,
  
  'RANGE_BOUND': {
    'COMPRESSION': 0.40,
    'BREAKOUT': 0.30,
    'ACCUMULATION': 0.15,
    'DISTRIBUTION': 0.15
  } as any,
  
  'VOLATILITY_SPIKE': {
    'EXPANSION': 0.40,
    'EXHAUSTION': 0.30,
    'REVERSAL': 0.20,
    'COMPRESSION': 0.10
  } as any,
  
  'TREND_CONTINUATION': {
    'EXPANSION': 0.40,
    'RETEST': 0.30,
    'COMPRESSION': 0.20,
    'EXHAUSTION': 0.10
  } as any
};

// ==============================================
// Configuration
// ==============================================

export interface StructureAIConfig {
  enabled: boolean;
  
  // Detection thresholds
  thresholds: {
    compressionCandles: number;        // Min candles for compression
    volumeSpikeMultiplier: number;     // Volume spike threshold
    sweepDepthPercent: number;         // Liquidity sweep depth
    breakoutStrength: number;          // Min breakout strength
    exhaustionRsiThreshold: number;    // RSI for exhaustion
  };
  
  // Event probabilities
  minEventProbability: number;
  minChainProbability: number;
  
  // Cache TTL
  cacheTTLSeconds: number;
}

export const DEFAULT_STRUCTURE_CONFIG: StructureAIConfig = {
  enabled: true,
  
  thresholds: {
    compressionCandles: 5,
    volumeSpikeMultiplier: 1.8,
    sweepDepthPercent: 0.3,
    breakoutStrength: 0.6,
    exhaustionRsiThreshold: 75
  },
  
  minEventProbability: 0.4,
  minChainProbability: 0.35,
  
  cacheTTLSeconds: 300
};

// ==============================================
// API Response Types
// ==============================================

export interface StructureEventsResponse {
  symbol: string;
  timeframe: string;
  events: MarketEvent[];
  count: number;
  timestamp: number;
}

export interface StructureStateResponse {
  symbol: string;
  timeframe: string;
  structure: StructureType;
  events: MarketEventType[];
  expectedNext: MarketEventType[];
  probability: number;
  bias: EventDirection;
  narrative: string;
  computedAt: number;
}

export interface StructureNarrativeResponse {
  symbol: string;
  timeframe: string;
  narrative: string;
  events: string[];
  expectedNext: string[];
  confidence: number;
}
