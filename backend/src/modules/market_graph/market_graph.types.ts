/**
 * G1 — Market Structure Graph Types
 * 
 * Represents market as a sequence of events (not just patterns)
 * Events: pattern detected, breakout, retest, sweep, expansion, failure
 */

export type MarketEventType =
  | 'PATTERN_DETECTED'
  | 'BREAKOUT'
  | 'BREAKDOWN'
  | 'RETEST'
  | 'LIQUIDITY_SWEEP_UP'
  | 'LIQUIDITY_SWEEP_DOWN'
  | 'EXPANSION'
  | 'COMPRESSION'
  | 'FAILURE'
  | 'TARGET_HIT'
  | 'STOP_HIT'
  | 'REVERSAL_ATTEMPT'
  | 'CONTINUATION';

export interface MarketEvent {
  id?: string;
  
  // Context
  runId: string;
  asset: string;
  timeframe: string;
  
  // Timing
  ts: number;
  barIndex: number;
  
  // Event data
  type: MarketEventType;
  direction?: 'BULL' | 'BEAR' | 'NEUTRAL';
  
  // Associated pattern (if any)
  patternType?: string;
  patternId?: string;
  
  // Price info
  price?: number;
  priceHigh?: number;
  priceLow?: number;
  
  // Strength/confidence
  strength?: number;
  confidence?: number;
  
  // Metadata
  meta?: Record<string, any>;
  
  // Timestamps
  createdAt?: Date;
}

export interface EventTransition {
  from: MarketEventType;
  fromPattern?: string;
  
  to: MarketEventType;
  toPattern?: string;
  
  // Statistics
  count: number;
  probability: number;
  avgBarsBetween: number;
  
  // Performance
  avgWinRate?: number;
  avgPF?: number;
  avgR?: number;
}

export interface EventChain {
  events: MarketEvent[];
  
  // Chain metadata
  asset: string;
  timeframe: string;
  startTs: number;
  endTs: number;
  
  // Outcome
  outcome?: 'WIN' | 'LOSS' | 'PENDING';
  rMultiple?: number;
}

export interface GraphStats {
  totalEvents: number;
  eventsByType: Record<MarketEventType, number>;
  transitionsCount: number;
  
  // Top transitions
  topTransitions: EventTransition[];
  
  // Chains
  avgChainLength: number;
  winningChains: number;
  losingChains: number;
}

export interface GraphBoostResult {
  score: number;
  confidence: number;
  boost: number;
  
  currentChain: MarketEvent[];
  matchedTransitions: EventTransition[];
  
  // Forecast
  predictedNext?: {
    event: MarketEventType;
    probability: number;
    avgBarsAhead: number;
  }[];
  
  bestPath?: MarketEventType[];
}
