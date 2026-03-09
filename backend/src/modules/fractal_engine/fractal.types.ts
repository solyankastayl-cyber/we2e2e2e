/**
 * D2 — Fractal Engine Types
 * 
 * Analyzes market SHAPE, not just patterns
 * Converts price movement into vector signatures
 */

export interface FractalSignature {
  id: string;
  
  // Context
  asset: string;
  timeframe: string;
  
  // Time range
  startTs: number;
  endTs: number;
  startBarIndex: number;
  endBarIndex: number;
  
  // Shape vector (normalized returns)
  vector: number[];
  vectorLength: number;
  
  // Metadata
  volatility: number;      // ATR-normalized
  trendBias: number;       // -1 (bearish) to +1 (bullish)
  compression: number;     // 0 (expanded) to 1 (compressed)
  impulseStrength: number; // Strength of dominant move
  
  // Source
  source: 'live' | 'historical';
  createdAt: Date;
}

export interface FractalCluster {
  clusterId: string;
  
  // Cluster stats
  size: number;
  centroid: number[];
  
  // Member signatures
  memberIds: string[];
  
  // Aggregate metrics
  avgVolatility: number;
  avgTrendBias: number;
  avgCompression: number;
  
  // Created
  createdAt: Date;
  updatedAt: Date;
}

export interface FractalClusterStats {
  clusterId: string;
  
  // Sample size
  sampleSize: number;
  
  // Performance
  winRate: number;
  avgR: number;
  profitFactor: number;
  
  // Stability
  stability: number;      // Consistency over time
  recentPerformance: number;
  
  // Edge score
  edgeScore: number;
  
  // Timestamps
  calculatedAt: Date;
}

export interface DiscoveredFractalPattern {
  patternId: string;       // e.g. "FRACTAL_001"
  clusterId: string;
  
  // Stats
  sampleSize: number;
  winRate: number;
  avgR: number;
  profitFactor: number;
  edgeScore: number;
  
  // Shape
  centroid: number[];
  
  // Direction bias
  direction: 'BULL' | 'BEAR' | 'NEUTRAL';
  
  // Status
  status: 'ACTIVE' | 'WATCHLIST' | 'REJECTED' | 'DEPRECATED';
  
  // Discovery
  discoveredAt: Date;
  lastValidatedAt: Date;
}

export interface FractalMatch {
  patternId: string;
  clusterId: string;
  
  similarity: number;     // 0-1, cosine similarity
  
  // Expected performance
  winRate: number;
  avgR: number;
  edgeScore: number;
  
  // Direction
  direction: 'BULL' | 'BEAR' | 'NEUTRAL';
}

export interface FractalConfig {
  // Signature extraction
  signatureLength: number;      // Default: 32
  inputCandles: number;         // Default: 64
  smoothingPeriod: number;      // EMA period: 3
  
  // Clustering
  minClusterSize: number;       // Default: 50
  maxClusters: number;          // Default: 100
  similarityThreshold: number;  // Default: 0.75
  
  // Discovery thresholds
  minSampleSize: number;        // Default: 100
  minWinRate: number;           // Default: 0.55
  minProfitFactor: number;      // Default: 1.2
  minEdgeScore: number;         // Default: 0.1
  
  // Matching
  matchThreshold: number;       // Default: 0.8
}

export const DEFAULT_FRACTAL_CONFIG: FractalConfig = {
  signatureLength: 32,
  inputCandles: 64,
  smoothingPeriod: 3,
  
  minClusterSize: 50,
  maxClusters: 100,
  similarityThreshold: 0.75,
  
  minSampleSize: 100,
  minWinRate: 0.55,
  minProfitFactor: 1.2,
  minEdgeScore: 0.1,
  
  matchThreshold: 0.8,
};
