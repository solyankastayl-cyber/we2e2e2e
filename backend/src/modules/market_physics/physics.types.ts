/**
 * D3 — Market Physics Engine Types
 * 
 * Models market as energy system:
 * - Compression (energy building)
 * - Pressure (directional force)
 * - Release (energy discharge)
 * - Expansion (movement phase)
 * - Exhaustion (energy depleted)
 */

export type PhysicsState = 
  | 'COMPRESSION'
  | 'PRESSURE'
  | 'RELEASE'
  | 'EXPANSION'
  | 'EXHAUSTION'
  | 'NEUTRAL';

export interface MarketPhysicsResult {
  asset: string;
  timeframe: string;
  timestamp: Date;
  
  // Individual scores (0-1)
  compressionScore: number;
  pressureScore: number;
  energyScore: number;
  releaseProbability: number;
  exhaustionScore: number;
  
  // Derived state
  physicsState: PhysicsState;
  stateConfidence: number;
  
  // Direction bias from physics
  directionBias: 'BULL' | 'BEAR' | 'NEUTRAL';
  
  // Boost for decision engine
  physicsBoost: number;
  
  // Detailed metrics
  metrics: {
    atrRatio: number;          // Recent ATR / Historical ATR
    rangeContraction: number;  // Range narrowing measure
    bollingerWidth: number;    // BB squeeze indicator
    levelTests: number;        // Number of level tests
    trendPersistence: number;  // Trend continuation strength
    volumeProfile: number;     // Volume relative to average
  };
}

export interface PhysicsConfig {
  // Compression detection
  compressionATRPeriod: number;        // ATR lookback (default: 14)
  compressionThreshold: number;        // ATR ratio below this = compression (default: 0.7)
  bollingerPeriod: number;             // BB period (default: 20)
  bollingerSqueezeFactor: number;      // BB width squeeze threshold (default: 0.5)
  
  // Pressure detection
  levelTestLookback: number;           // Bars to look for level tests (default: 20)
  minLevelTests: number;               // Min tests for pressure (default: 3)
  trendPersistenceThreshold: number;   // Trend strength threshold (default: 0.6)
  
  // Energy calculation
  energyWeights: {
    compression: number;   // default: 0.35
    pressure: number;      // default: 0.25
    liquidity: number;     // default: 0.25
    momentum: number;      // default: 0.15
  };
  
  // Release detection
  releaseATRSpike: number;             // ATR increase for release (default: 1.5)
  releaseVolumeSpike: number;          // Volume increase for release (default: 1.5)
  
  // Exhaustion detection
  exhaustionLookback: number;          // Bars after release to check (default: 10)
  momentumDecayThreshold: number;      // Momentum decline threshold (default: 0.3)
}

export const DEFAULT_PHYSICS_CONFIG: PhysicsConfig = {
  compressionATRPeriod: 14,
  compressionThreshold: 0.7,
  bollingerPeriod: 20,
  bollingerSqueezeFactor: 0.5,
  
  levelTestLookback: 20,
  minLevelTests: 3,
  trendPersistenceThreshold: 0.6,
  
  energyWeights: {
    compression: 0.35,
    pressure: 0.25,
    liquidity: 0.25,
    momentum: 0.15,
  },
  
  releaseATRSpike: 1.5,
  releaseVolumeSpike: 1.5,
  
  exhaustionLookback: 10,
  momentumDecayThreshold: 0.3,
};
