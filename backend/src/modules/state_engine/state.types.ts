/**
 * D4 — State Transition Engine Types
 * 
 * Models market as a state machine:
 * BALANCE → COMPRESSION → BREAKOUT_ATTEMPT → EXPANSION → EXHAUSTION → REVERSAL_ATTEMPT
 */

export type MarketStateNode =
  | 'BALANCE'
  | 'COMPRESSION'
  | 'BREAKOUT_ATTEMPT'
  | 'EXPANSION'
  | 'EXHAUSTION'
  | 'REVERSAL_ATTEMPT';

export interface StateTransition {
  from: MarketStateNode;
  to: MarketStateNode;
  probability: number;
  avgBarsToTransition: number;
  count: number;
}

export interface StateTransitionResult {
  asset: string;
  timeframe: string;
  timestamp: Date;
  
  // Current state
  currentState: MarketStateNode;
  stateConfidence: number;
  stateEnteredAt?: Date;
  barsInState: number;
  
  // Next state probabilities
  nextStateProbabilities: Array<{
    state: MarketStateNode;
    probability: number;
    avgBarsAhead: number;
  }>;
  
  // Most likely path
  likelyPath: MarketStateNode[];
  pathProbability: number;
  
  // State boost for decision engine
  stateBoost: number;
  
  // Reasoning
  stateReason: string;
}

export interface StateEngineConfig {
  // Thresholds for state detection
  compressionThreshold: number;        // Energy score for compression (default: 0.5)
  breakoutThreshold: number;           // Release probability for breakout (default: 0.6)
  expansionThreshold: number;          // ATR spike for expansion (default: 1.3)
  exhaustionThreshold: number;         // Exhaustion score for exhaustion (default: 0.6)
  reversalThreshold: number;           // Reversal signal threshold (default: 0.5)
  
  // Transition constraints
  minBarsForTransition: number;        // Min bars before transition allowed (default: 3)
  maxBarsInState: number;              // Max bars before forced transition (default: 50)
}

export const DEFAULT_STATE_CONFIG: StateEngineConfig = {
  compressionThreshold: 0.5,
  breakoutThreshold: 0.6,
  expansionThreshold: 1.3,
  exhaustionThreshold: 0.6,
  reversalThreshold: 0.5,
  minBarsForTransition: 3,
  maxBarsInState: 50,
};

// Allowed state transitions (state machine graph)
export const ALLOWED_TRANSITIONS: Record<MarketStateNode, MarketStateNode[]> = {
  BALANCE: ['COMPRESSION', 'BREAKOUT_ATTEMPT'],
  COMPRESSION: ['BREAKOUT_ATTEMPT', 'BALANCE'],
  BREAKOUT_ATTEMPT: ['EXPANSION', 'BALANCE', 'REVERSAL_ATTEMPT'],
  EXPANSION: ['EXHAUSTION', 'BALANCE'],
  EXHAUSTION: ['REVERSAL_ATTEMPT', 'BALANCE'],
  REVERSAL_ATTEMPT: ['EXPANSION', 'COMPRESSION', 'BALANCE'],
};
