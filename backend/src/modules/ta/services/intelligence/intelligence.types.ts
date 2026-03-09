/**
 * Intelligence Types (P4.1)
 * 
 * Core contract for IntelligencePack - the unified output of TA Engine
 */

/**
 * Bias direction
 */
export type Bias = 'LONG' | 'SHORT' | 'WAIT';

/**
 * Probability source
 */
export type ProbabilitySource = 'ML' | 'SCENARIO' | 'CALIBRATED' | 'FALLBACK';

/**
 * Top scenario summary
 */
export interface TopScenario {
  id: string;
  type: string;           // Pattern type: TRIANGLE_ASC, CHANNEL_UP, etc.
  score: number;          // Combined score [0-1]
  probability: number;    // Win probability [0-1]
  ev: number;             // Expected value
  riskReward: number;     // R:R ratio
}

/**
 * Probability breakdown
 */
export interface ProbabilitySet {
  pEntry: number;         // Probability to take this entry
  pWin: number;           // Probability of hitting target
  pStop: number;          // Probability of hitting stop
  pTimeout: number;       // Probability of timeout/scratch
}

/**
 * Expectation values
 */
export interface Expectation {
  expectedR: number;      // Expected R multiple
  expectedEV: number;     // Expected value (prob-weighted)
}

/**
 * Signal aggregates
 */
export interface SignalSummary {
  bullish: number;        // Count of bullish signals
  bearish: number;        // Count of bearish signals
  neutral: number;        // Count of neutral signals
  conflictCount: number;  // Number of conflicting signals
  netBias: number;        // Net signal (-1 to +1)
}

/**
 * R/Price projection bands
 */
export interface Projection {
  // R percentiles
  r_p10: number;
  r_p50: number;
  r_p90: number;
  
  // Price projections (if priceNow available)
  price_p10?: number;
  price_p50?: number;
  price_p90?: number;
  priceNow?: number;
}

/**
 * Component references (audit linkage)
 */
export interface IntelligenceComponents {
  patternsRunId?: string;
  regimeRunId?: string;
  geometryRunId?: string;
  gatesRunId?: string;
  graphRunId?: string;
  mlRunId?: string;
  stabilityRunId?: string;
  scenarioRunId?: string;
}

/**
 * Metadata
 */
export interface IntelligenceMeta {
  modelEntry?: string;        // Entry model ID
  modelR?: string;            // R model ID
  featureSchema?: string;     // Feature schema version
  calibrationVersion?: string;
  probabilitySource: ProbabilitySource;
  engineVersion: string;
}

/**
 * IntelligencePack - The unified output
 */
export interface IntelligencePack {
  // Identity
  runId: string;
  asset: string;
  timeframe: string;
  asOfTs: number;           // Timestamp of analysis
  
  // Core decision
  topBias: Bias;
  topScenario: TopScenario | null;
  
  // Probabilities
  probability: ProbabilitySet;
  
  // Expectations
  expectation: Expectation;
  
  // Signals
  signals: SignalSummary;
  
  // Projections
  projection: Projection;
  
  // Confidence (composite score)
  confidence: number;       // [0-1]
  
  // Components (audit trail links)
  components: IntelligenceComponents;
  
  // Meta
  meta: IntelligenceMeta;
  
  // Timestamps
  createdAt: Date;
}

/**
 * Input for intelligence computation
 */
export interface IntelligenceRequest {
  asset: string;
  timeframe: string;
  provider?: 'binance' | 'mongo' | 'mock' | 'replay';
  asOfTs?: number;
}

/**
 * Health status
 */
export interface IntelligenceHealth {
  status: 'OK' | 'DEGRADED' | 'ERROR';
  checks: {
    mongo: boolean;
    decisionEngine: boolean;
    modelRegistry: boolean;
    calibration: boolean;
    stability: boolean;
  };
  message?: string;
}
