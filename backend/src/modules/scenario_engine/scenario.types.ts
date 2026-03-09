/**
 * Phase 6 — Scenario Engine Types
 * 
 * Market behavior scenarios, not just price paths
 */

// ═══════════════════════════════════════════════════════════════
// STATE TRANSITIONS
// ═══════════════════════════════════════════════════════════════

export type MarketBehaviorState = 
  | 'COMPRESSION'
  | 'BREAKOUT'
  | 'FALSE_BREAKOUT'
  | 'RETEST'
  | 'EXPANSION'
  | 'LIQUIDITY_SWEEP'
  | 'REVERSAL'
  | 'RANGE'
  | 'EXHAUSTION'
  | 'CONTINUATION';

export type ScenarioDirection = 'BULL' | 'BEAR' | 'NEUTRAL';

// ═══════════════════════════════════════════════════════════════
// SCENARIO TYPES
// ═══════════════════════════════════════════════════════════════

export interface MarketScenario {
  scenarioId: string;
  asset: string;
  timeframe: string;
  
  // Direction and outcome
  direction: ScenarioDirection;
  probability: number;
  
  // Expected move
  expectedMoveATR: number;
  
  // Event path (state sequence)
  path: MarketBehaviorState[];
  
  // Key events
  events: string[];
  
  // Market states traversed
  states: MarketBehaviorState[];
  
  // Confidence in scenario
  confidence: number;
  
  // Scenario score for ranking
  score: number;
  
  // Timestamps
  generatedAt: Date;
  expiresAt?: Date;
}

// ═══════════════════════════════════════════════════════════════
// TRANSITION PROBABILITIES
// ═══════════════════════════════════════════════════════════════

export interface StateTransition {
  from: MarketBehaviorState;
  to: MarketBehaviorState;
  baseProbability: number;
  conditionMultipliers: {
    highEnergy?: number;
    liquiditySweep?: number;
    trendAlignment?: number;
    volumeSpike?: number;
  };
}

export const STATE_TRANSITIONS: StateTransition[] = [
  // From COMPRESSION
  { from: 'COMPRESSION', to: 'BREAKOUT', baseProbability: 0.45, 
    conditionMultipliers: { highEnergy: 1.3, trendAlignment: 1.2 } },
  { from: 'COMPRESSION', to: 'FALSE_BREAKOUT', baseProbability: 0.25,
    conditionMultipliers: { liquiditySweep: 1.4 } },
  { from: 'COMPRESSION', to: 'RANGE', baseProbability: 0.30,
    conditionMultipliers: {} },
  
  // From BREAKOUT
  { from: 'BREAKOUT', to: 'RETEST', baseProbability: 0.40,
    conditionMultipliers: { trendAlignment: 1.2 } },
  { from: 'BREAKOUT', to: 'EXPANSION', baseProbability: 0.35,
    conditionMultipliers: { volumeSpike: 1.3, highEnergy: 1.2 } },
  { from: 'BREAKOUT', to: 'FALSE_BREAKOUT', baseProbability: 0.25,
    conditionMultipliers: { liquiditySweep: 1.5 } },
  
  // From FALSE_BREAKOUT  
  { from: 'FALSE_BREAKOUT', to: 'RANGE', baseProbability: 0.40,
    conditionMultipliers: {} },
  { from: 'FALSE_BREAKOUT', to: 'REVERSAL', baseProbability: 0.35,
    conditionMultipliers: { liquiditySweep: 1.3 } },
  { from: 'FALSE_BREAKOUT', to: 'COMPRESSION', baseProbability: 0.25,
    conditionMultipliers: {} },
  
  // From RETEST
  { from: 'RETEST', to: 'EXPANSION', baseProbability: 0.55,
    conditionMultipliers: { trendAlignment: 1.3, highEnergy: 1.2 } },
  { from: 'RETEST', to: 'REVERSAL', baseProbability: 0.25,
    conditionMultipliers: { liquiditySweep: 1.4 } },
  { from: 'RETEST', to: 'RANGE', baseProbability: 0.20,
    conditionMultipliers: {} },
  
  // From EXPANSION
  { from: 'EXPANSION', to: 'EXHAUSTION', baseProbability: 0.35,
    conditionMultipliers: {} },
  { from: 'EXPANSION', to: 'CONTINUATION', baseProbability: 0.40,
    conditionMultipliers: { trendAlignment: 1.3 } },
  { from: 'EXPANSION', to: 'RETEST', baseProbability: 0.25,
    conditionMultipliers: {} },
  
  // From LIQUIDITY_SWEEP
  { from: 'LIQUIDITY_SWEEP', to: 'REVERSAL', baseProbability: 0.50,
    conditionMultipliers: {} },
  { from: 'LIQUIDITY_SWEEP', to: 'CONTINUATION', baseProbability: 0.30,
    conditionMultipliers: { trendAlignment: 1.3 } },
  { from: 'LIQUIDITY_SWEEP', to: 'RANGE', baseProbability: 0.20,
    conditionMultipliers: {} },
  
  // From REVERSAL
  { from: 'REVERSAL', to: 'EXPANSION', baseProbability: 0.40,
    conditionMultipliers: { volumeSpike: 1.3 } },
  { from: 'REVERSAL', to: 'FALSE_BREAKOUT', baseProbability: 0.30,
    conditionMultipliers: {} },
  { from: 'REVERSAL', to: 'RANGE', baseProbability: 0.30,
    conditionMultipliers: {} },
  
  // From EXHAUSTION
  { from: 'EXHAUSTION', to: 'REVERSAL', baseProbability: 0.45,
    conditionMultipliers: { liquiditySweep: 1.3 } },
  { from: 'EXHAUSTION', to: 'RANGE', baseProbability: 0.35,
    conditionMultipliers: {} },
  { from: 'EXHAUSTION', to: 'CONTINUATION', baseProbability: 0.20,
    conditionMultipliers: { trendAlignment: 1.5 } },
];

// ═══════════════════════════════════════════════════════════════
// SCENARIO TEMPLATES
// ═══════════════════════════════════════════════════════════════

export interface ScenarioTemplate {
  name: string;
  direction: ScenarioDirection;
  path: MarketBehaviorState[];
  baseProb: number;
  description: string;
}

export const SCENARIO_TEMPLATES: ScenarioTemplate[] = [
  // Bullish scenarios
  {
    name: 'CLASSIC_BREAKOUT',
    direction: 'BULL',
    path: ['COMPRESSION', 'BREAKOUT', 'RETEST', 'EXPANSION'],
    baseProb: 0.15,
    description: 'Classic bullish breakout with retest confirmation'
  },
  {
    name: 'DIRECT_EXPANSION',
    direction: 'BULL', 
    path: ['COMPRESSION', 'BREAKOUT', 'EXPANSION'],
    baseProb: 0.12,
    description: 'Strong breakout without retest'
  },
  {
    name: 'SWEEP_REVERSAL_BULL',
    direction: 'BULL',
    path: ['COMPRESSION', 'FALSE_BREAKOUT', 'LIQUIDITY_SWEEP', 'REVERSAL', 'EXPANSION'],
    baseProb: 0.08,
    description: 'Bear trap leading to bullish reversal'
  },
  
  // Bearish scenarios
  {
    name: 'CLASSIC_BREAKDOWN',
    direction: 'BEAR',
    path: ['COMPRESSION', 'BREAKOUT', 'RETEST', 'EXPANSION'],
    baseProb: 0.15,
    description: 'Classic bearish breakdown with retest'
  },
  {
    name: 'EXHAUSTION_REVERSAL',
    direction: 'BEAR',
    path: ['EXPANSION', 'EXHAUSTION', 'REVERSAL', 'EXPANSION'],
    baseProb: 0.10,
    description: 'Bull exhaustion leading to reversal'
  },
  {
    name: 'SWEEP_REVERSAL_BEAR',
    direction: 'BEAR',
    path: ['COMPRESSION', 'FALSE_BREAKOUT', 'LIQUIDITY_SWEEP', 'REVERSAL', 'EXPANSION'],
    baseProb: 0.08,
    description: 'Bull trap leading to bearish reversal'
  },
  
  // Neutral scenarios
  {
    name: 'RANGE_CONTINUATION',
    direction: 'NEUTRAL',
    path: ['COMPRESSION', 'FALSE_BREAKOUT', 'RANGE'],
    baseProb: 0.18,
    description: 'Failed breakout returning to range'
  },
  {
    name: 'EXTENDED_RANGE',
    direction: 'NEUTRAL',
    path: ['COMPRESSION', 'RANGE', 'COMPRESSION'],
    baseProb: 0.14,
    description: 'Continued ranging behavior'
  }
];

// ═══════════════════════════════════════════════════════════════
// SIMULATION INPUT/OUTPUT
// ═══════════════════════════════════════════════════════════════

export interface ScenarioSimulationInput {
  asset: string;
  timeframe: string;
  currentState: MarketBehaviorState;
  
  // From intelligence layers
  physicsState?: string;
  energyScore?: number;
  releaseProbability?: number;
  exhaustionScore?: number;
  
  liquidityBias?: number;
  recentSweepUp?: boolean;
  recentSweepDown?: boolean;
  
  trendDirection?: 'BULL' | 'BEAR' | 'NEUTRAL';
  trendStrength?: number;
  
  volumeProfile?: number;
  atrRatio?: number;
}

export interface ScenarioSimulationResult {
  asset: string;
  timeframe: string;
  timestamp: Date;
  
  // Top 3 scenarios
  scenarios: MarketScenario[];
  
  // Primary scenario (highest probability)
  primaryScenario: MarketScenario;
  
  // Alternative scenario
  alternativeScenario?: MarketScenario;
  
  // Risk scenario (worst case)
  riskScenario?: MarketScenario;
  
  // Aggregate probabilities
  bullishProbability: number;
  bearishProbability: number;
  neutralProbability: number;
  
  // Decision support
  recommendedAction: 'LONG' | 'SHORT' | 'WAIT' | 'REDUCE';
  actionConfidence: number;
}

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

export interface ScenarioEngineConfig {
  maxPathDepth: number;
  minScenarioProbability: number;
  topScenariosCount: number;
  scenarioExpiryBars: number;
  useHistoricalTransitions: boolean;
}

export const DEFAULT_SCENARIO_CONFIG: ScenarioEngineConfig = {
  maxPathDepth: 5,
  minScenarioProbability: 0.05,
  topScenariosCount: 3,
  scenarioExpiryBars: 20,
  useHistoricalTransitions: true
};
