/**
 * ANN Memory Index — Vector Engine
 * 
 * In-memory vector index with approximate nearest neighbor search
 * Uses simple brute-force for now, can be upgraded to HNSW/FAISS
 */

import {
  MarketStateVector,
  SimilarityMatch,
  SearchResult,
  IndexStats,
  IndexConfig,
  DEFAULT_INDEX_CONFIG
} from './memory_index.types.js';

// ═══════════════════════════════════════════════════════════════
// VECTOR OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate Euclidean distance between two vectors
 */
export function euclideanDistance(a: number[], b: number[]): number {
  if (a.length !== b.length) {
    throw new Error('Vectors must have same dimensions');
  }
  
  let sum = 0;
  for (let i = 0; i < a.length; i++) {
    const diff = a[i] - b[i];
    sum += diff * diff;
  }
  
  return Math.sqrt(sum);
}

/**
 * Calculate cosine similarity between two vectors
 */
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) {
    throw new Error('Vectors must have same dimensions');
  }
  
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  
  if (normA === 0 || normB === 0) return 0;
  
  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

/**
 * Normalize vector to unit length
 */
export function normalizeVector(v: number[]): number[] {
  const norm = Math.sqrt(v.reduce((sum, x) => sum + x * x, 0));
  if (norm === 0) return v;
  return v.map(x => x / norm);
}

// ═══════════════════════════════════════════════════════════════
// VECTOR INDEX
// ═══════════════════════════════════════════════════════════════

class VectorIndex {
  private vectors: Map<string, MarketStateVector> = new Map();
  private config: IndexConfig;
  private searchCount = 0;
  private totalSearchTimeMs = 0;
  private lastReindexAt?: Date;

  constructor(config: IndexConfig = DEFAULT_INDEX_CONFIG) {
    this.config = config;
  }

  // ─────────────────────────────────────────────────────────────
  // INDEX OPERATIONS
  // ─────────────────────────────────────────────────────────────

  /**
   * Add vector to index
   */
  add(vector: MarketStateVector): void {
    if (vector.vector.length !== this.config.dimensions) {
      throw new Error(`Vector must have ${this.config.dimensions} dimensions`);
    }
    
    if (this.vectors.size >= this.config.maxVectors) {
      // Remove oldest vector
      const oldest = Array.from(this.vectors.values())
        .sort((a, b) => a.timestamp - b.timestamp)[0];
      if (oldest) {
        this.vectors.delete(oldest.id);
      }
    }
    
    this.vectors.set(vector.id, vector);
  }

  /**
   * Add multiple vectors
   */
  addBatch(vectors: MarketStateVector[]): number {
    let added = 0;
    for (const v of vectors) {
      try {
        this.add(v);
        added++;
      } catch {
        // Skip invalid vectors
      }
    }
    return added;
  }

  /**
   * Remove vector from index
   */
  remove(id: string): boolean {
    return this.vectors.delete(id);
  }

  /**
   * Clear all vectors
   */
  clear(): void {
    this.vectors.clear();
    this.lastReindexAt = new Date();
  }

  // ─────────────────────────────────────────────────────────────
  // SEARCH OPERATIONS
  // ─────────────────────────────────────────────────────────────

  /**
   * Search for k nearest neighbors
   */
  search(
    queryVector: number[],
    k: number = 10,
    filter?: {
      regimes?: string[];
      outcomes?: string[];
      minTimestamp?: number;
      maxTimestamp?: number;
    }
  ): SearchResult {
    const startTime = performance.now();
    
    // Filter vectors
    let candidates = Array.from(this.vectors.values());
    
    if (filter?.regimes && filter.regimes.length > 0) {
      candidates = candidates.filter(v => filter.regimes!.includes(v.regime));
    }
    
    if (filter?.outcomes && filter.outcomes.length > 0) {
      candidates = candidates.filter(v => v.outcome && filter.outcomes!.includes(v.outcome));
    }
    
    if (filter?.minTimestamp) {
      candidates = candidates.filter(v => v.timestamp >= filter.minTimestamp!);
    }
    
    if (filter?.maxTimestamp) {
      candidates = candidates.filter(v => v.timestamp <= filter.maxTimestamp!);
    }
    
    // Calculate distances
    const distances: { vector: MarketStateVector; distance: number }[] = [];
    
    for (const candidate of candidates) {
      const distance = euclideanDistance(queryVector, candidate.vector);
      distances.push({ vector: candidate, distance });
    }
    
    // Sort by distance
    distances.sort((a, b) => a.distance - b.distance);
    
    // Take top k
    const matches: SimilarityMatch[] = distances.slice(0, k).map(d => ({
      id: d.vector.id,
      similarity: 1 / (1 + d.distance),  // Convert distance to similarity
      distance: d.distance,
      vector: d.vector
    }));
    
    const searchTimeMs = performance.now() - startTime;
    this.searchCount++;
    this.totalSearchTimeMs += searchTimeMs;
    
    return {
      query: {
        id: 'query',
        asset: '',
        timeframe: '',
        timestamp: Date.now(),
        vector: queryVector,
        regime: '',
        state: '',
        features: {} as any
      },
      matches,
      searchTimeMs: Math.round(searchTimeMs * 100) / 100,
      totalIndexed: this.vectors.size
    };
  }

  /**
   * Search by vector ID
   */
  searchById(id: string, k: number = 10): SearchResult | null {
    const vector = this.vectors.get(id);
    if (!vector) return null;
    
    return this.search(vector.vector, k + 1);  // +1 to exclude self
  }

  // ─────────────────────────────────────────────────────────────
  // STATS & INFO
  // ─────────────────────────────────────────────────────────────

  /**
   * Get index statistics
   */
  getStats(): IndexStats {
    // Rough memory estimate
    const bytesPerVector = this.config.dimensions * 8 + 500; // float64 + metadata
    const memoryUsageMB = (this.vectors.size * bytesPerVector) / (1024 * 1024);
    
    return {
      totalVectors: this.vectors.size,
      dimensions: this.config.dimensions,
      avgSearchTimeMs: this.searchCount > 0 
        ? Math.round((this.totalSearchTimeMs / this.searchCount) * 100) / 100
        : 0,
      lastReindexAt: this.lastReindexAt,
      memoryUsageMB: Math.round(memoryUsageMB * 100) / 100
    };
  }

  /**
   * Get vector by ID
   */
  get(id: string): MarketStateVector | undefined {
    return this.vectors.get(id);
  }

  /**
   * Get all vectors for an asset
   */
  getByAsset(asset: string): MarketStateVector[] {
    return Array.from(this.vectors.values()).filter(v => v.asset === asset);
  }

  /**
   * Get count
   */
  size(): number {
    return this.vectors.size;
  }
}

// Singleton instance
export const vectorIndex = new VectorIndex();

// ═══════════════════════════════════════════════════════════════
// FEATURE EXTRACTION
// ═══════════════════════════════════════════════════════════════

/**
 * Create feature vector from market state
 */
export function createFeatureVector(features: {
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
}): number[] {
  return [
    features.volatility,
    features.trend,
    features.liquidityImbalance,
    features.momentum,
    features.volumeProfile,
    features.pricePosition,
    features.regimeStrength,
    features.scenarioConfidence,
    features.patternSignature,
    features.treeUncertainty,
    features.memoryConfidence,
    features.edgeHealth,
    features.drawdown,
    features.rsi,
    features.macdSignal,
    features.atrNormalized
  ];
}

/**
 * Create MarketStateVector from raw data
 */
export function createMarketStateVector(
  id: string,
  asset: string,
  timeframe: string,
  timestamp: number,
  features: MarketStateVector['features'],
  regime: string,
  state: string,
  scenario?: string,
  outcome?: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
): MarketStateVector {
  return {
    id,
    asset,
    timeframe,
    timestamp,
    vector: createFeatureVector(features),
    regime,
    state,
    scenario,
    outcome,
    features
  };
}
