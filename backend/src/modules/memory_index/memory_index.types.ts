/**
 * ANN Memory Index — Types
 * 
 * Vector-based similarity search for market states
 */

// ═══════════════════════════════════════════════════════════════
// VECTOR TYPES
// ═══════════════════════════════════════════════════════════════

export interface MarketStateVector {
  id: string;
  asset: string;
  timeframe: string;
  timestamp: number;
  
  // 16-dimensional feature vector
  vector: number[];
  
  // Metadata
  regime: string;
  state: string;
  scenario?: string;
  outcome?: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  
  // Original values for interpretability
  features: {
    volatility: number;
    trend: number;
    liquidityImbalance: number;
    momentum: number;
    volumeProfile: number;
    pricePosition: number;
    regimeStrength: number;
    scenarioConfidence: number;
    patternSignature: number;
    treeUncertainty: number;
    memoryConfidence: number;
    edgeHealth: number;
    drawdown: number;
    rsi: number;
    macdSignal: number;
    atrNormalized: number;
  };
}

export interface SimilarityMatch {
  id: string;
  similarity: number;  // 0-1, higher = more similar
  distance: number;    // Euclidean distance
  vector: MarketStateVector;
}

export interface SearchResult {
  query: MarketStateVector;
  matches: SimilarityMatch[];
  searchTimeMs: number;
  totalIndexed: number;
}

// ═══════════════════════════════════════════════════════════════
// INDEX TYPES
// ═══════════════════════════════════════════════════════════════

export interface IndexStats {
  totalVectors: number;
  dimensions: number;
  avgSearchTimeMs: number;
  lastReindexAt?: Date;
  memoryUsageMB: number;
}

export interface IndexConfig {
  dimensions: number;
  maxVectors: number;
  efConstruction: number;  // HNSW parameter
  efSearch: number;        // HNSW parameter
  m: number;               // HNSW connections per layer
}

export const DEFAULT_INDEX_CONFIG: IndexConfig = {
  dimensions: 16,
  maxVectors: 1000000,
  efConstruction: 200,
  efSearch: 100,
  m: 16
};

// ═══════════════════════════════════════════════════════════════
// API TYPES
// ═══════════════════════════════════════════════════════════════

export interface SearchRequest {
  asset: string;
  timeframe: string;
  k: number;  // Number of neighbors
  
  // Optional filters
  regimeFilter?: string[];
  outcomeFilter?: ('BULLISH' | 'BEARISH' | 'NEUTRAL')[];
  minTimestamp?: number;
  maxTimestamp?: number;
}

export interface IndexResponse {
  success: boolean;
  data?: {
    stats: IndexStats;
    recentSearches: number;
  };
  error?: string;
}
