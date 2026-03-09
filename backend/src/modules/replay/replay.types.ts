/**
 * Phase 4.2 — Replay Engine Types
 * =================================
 * Types for decision replay and simulation
 */

export interface DecisionSnapshot {
  id: string;
  decisionId: string;
  symbol: string;
  timestamp: number;
  
  // Full context at decision time
  context: SnapshotContext;
  
  // The decision made
  decision: {
    signal: 'LONG' | 'SHORT' | 'NO_TRADE';
    score: number;
    confidence: number;
  };
  
  // Market state
  marketState: {
    price: number;
    regime: string;
    volatility: number;
    volume: number;
  };
}

export interface SnapshotContext {
  patternScore: number;
  patternType?: string;
  
  liquidityScore: number;
  liquiditySweep: boolean;
  
  regime: string;
  regimeStrength: number;
  
  scenarioProbability: number;
  scenarioType: string;
  
  memoryBoost: number;
  memoryMatches: number;
  memoryBias: string;
  
  graphBoost?: number;
  physicsScore?: number;
  
  riskMode: string;
  moduleWeights: Record<string, number>;
}

export interface ReplayResult {
  snapshotId: string;
  originalDecision: {
    signal: string;
    score: number;
  };
  replayedDecision: {
    signal: string;
    score: number;
  };
  changed: boolean;
  differences: ReplayDifference[];
  reason?: string;
}

export interface ReplayDifference {
  factor: string;
  original: number;
  replayed: number;
  delta: number;
}

export interface CompareResult {
  symbol: string;
  decisions: {
    id: string;
    timestamp: number;
    signal: string;
    score: number;
    outcome?: string;
  }[];
  stats: {
    total: number;
    consistency: number;  // How consistent were signals
    avgScore: number;
  };
}
