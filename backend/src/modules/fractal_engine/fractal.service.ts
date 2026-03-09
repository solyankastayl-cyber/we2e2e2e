/**
 * D2 — Fractal Engine Service
 * 
 * Main service for fractal analysis:
 * - Signature extraction from candles
 * - Clustering and discovery
 * - Matching current market to discovered patterns
 */

import { Db } from 'mongodb';
import { 
  FractalSignature, 
  FractalCluster, 
  DiscoveredFractalPattern,
  FractalMatch,
  FractalConfig,
  DEFAULT_FRACTAL_CONFIG,
} from './fractal.types.js';
import { extractFractalSignature, cosineSimilarity } from './fractal.signature.js';
import { clusterSignatures, evaluateCluster, discoverPatterns } from './fractal.discovery.js';
import { FractalStorage } from './fractal.storage.js';

export class FractalService {
  private db: Db;
  private storage: FractalStorage;
  private config: FractalConfig;

  constructor(db: Db, config?: Partial<FractalConfig>) {
    this.db = db;
    this.storage = new FractalStorage(db);
    this.config = { ...DEFAULT_FRACTAL_CONFIG, ...config };
  }

  async ensureIndexes(): Promise<void> {
    await this.storage.ensureIndexes();
  }

  // ═══════════════════════════════════════════════════════════════
  // Signature Extraction
  // ═══════════════════════════════════════════════════════════════

  /**
   * Extract and save signature for asset/timeframe
   */
  async extractSignature(
    asset: string,
    timeframe: string
  ): Promise<FractalSignature | null> {
    // Fetch candles
    const candles = await this.fetchCandles(asset, timeframe, this.config.inputCandles);
    
    if (candles.length < this.config.inputCandles) {
      return null;
    }
    
    // Extract signature
    const signature = extractFractalSignature(candles, asset, timeframe, this.config);
    
    if (signature) {
      await this.storage.saveSignature(signature);
    }
    
    return signature;
  }

  /**
   * Build historical signatures from stored candles
   */
  async buildHistoricalSignatures(
    asset: string,
    timeframe: string,
    maxSignatures: number = 500
  ): Promise<number> {
    const candles = await this.fetchCandles(asset, timeframe, 2000);
    
    if (candles.length < this.config.inputCandles) {
      return 0;
    }
    
    const signatures: FractalSignature[] = [];
    const step = Math.max(1, Math.floor((candles.length - this.config.inputCandles) / maxSignatures));
    
    for (let i = 0; i < candles.length - this.config.inputCandles; i += step) {
      const window = candles.slice(i, i + this.config.inputCandles);
      const sig = extractFractalSignature(window, asset, timeframe, this.config);
      
      if (sig) {
        sig.source = 'historical';
        sig.endTs = window[window.length - 1].openTime;
        signatures.push(sig);
      }
    }
    
    return await this.storage.saveSignatures(signatures);
  }

  // ═══════════════════════════════════════════════════════════════
  // Discovery
  // ═══════════════════════════════════════════════════════════════

  /**
   * Rebuild clusters and discover patterns
   */
  async rebuildDiscovery(): Promise<{
    signaturesUsed: number;
    clustersCreated: number;
    patternsDiscovered: number;
  }> {
    // Get all signatures
    const signatures = await this.storage.getAllSignatures(5000);
    
    if (signatures.length < this.config.minClusterSize) {
      return { signaturesUsed: 0, clustersCreated: 0, patternsDiscovered: 0 };
    }
    
    // Clear old clusters
    await this.storage.clearClusters();
    
    // Cluster signatures
    const clusters = clusterSignatures(signatures, this.config);
    await this.storage.saveClusters(clusters);
    
    // Evaluate clusters (mock outcomes for now)
    const mockOutcomes = signatures.map(s => ({
      signatureId: s.id,
      win: Math.random() > 0.45, // Slightly bullish bias
      rMultiple: (Math.random() - 0.4) * 2,
    }));
    
    const stats = clusters.map(c => evaluateCluster(c, mockOutcomes));
    for (const s of stats) {
      await this.storage.saveClusterStats(s);
    }
    
    // Discover patterns
    const discovered = discoverPatterns(clusters, stats, this.config);
    for (const p of discovered) {
      await this.storage.saveDiscoveredPattern(p);
    }
    
    return {
      signaturesUsed: signatures.length,
      clustersCreated: clusters.length,
      patternsDiscovered: discovered.length,
    };
  }

  // ═══════════════════════════════════════════════════════════════
  // Matching
  // ═══════════════════════════════════════════════════════════════

  /**
   * Match current market to discovered fractals
   */
  async matchCurrent(
    asset: string,
    timeframe: string,
    topN: number = 5
  ): Promise<FractalMatch[]> {
    // Get current signature
    const currentSig = await this.extractSignature(asset, timeframe);
    if (!currentSig) return [];
    
    // Get active discovered patterns
    const discovered = await this.storage.getActiveDiscoveredPatterns();
    if (discovered.length === 0) return [];
    
    // Calculate similarity to each pattern
    const matches: FractalMatch[] = [];
    
    for (const pattern of discovered) {
      const similarity = cosineSimilarity(currentSig.vector, pattern.centroid);
      
      if (similarity >= this.config.matchThreshold) {
        matches.push({
          patternId: pattern.patternId,
          clusterId: pattern.clusterId,
          similarity,
          winRate: pattern.winRate,
          avgR: pattern.avgR,
          edgeScore: pattern.edgeScore,
          direction: pattern.direction,
        });
      }
    }
    
    // Sort by similarity and take top N
    return matches
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, topN);
  }

  /**
   * Get fractal boost for decision engine
   */
  async getFractalBoost(
    asset: string,
    timeframe: string,
    patternDirection: 'BULL' | 'BEAR'
  ): Promise<{ boost: number; matches: FractalMatch[] }> {
    const matches = await this.matchCurrent(asset, timeframe, 3);
    
    if (matches.length === 0) {
      return { boost: 1.0, matches: [] };
    }
    
    // Calculate boost from matches
    let totalBoost = 0;
    let totalWeight = 0;
    
    for (const match of matches) {
      // Direction alignment
      const aligned = 
        (patternDirection === 'BULL' && match.direction === 'BULL') ||
        (patternDirection === 'BEAR' && match.direction === 'BEAR') ||
        match.direction === 'NEUTRAL';
      
      if (aligned) {
        const weight = match.similarity * match.edgeScore;
        totalBoost += (1 + match.edgeScore) * weight;
        totalWeight += weight;
      }
    }
    
    const boost = totalWeight > 0 
      ? Math.min(1.3, Math.max(0.8, totalBoost / totalWeight))
      : 1.0;
    
    return { boost, matches };
  }

  // ═══════════════════════════════════════════════════════════════
  // Stats
  // ═══════════════════════════════════════════════════════════════

  async getStats(): Promise<{
    totalSignatures: number;
    totalClusters: number;
    discoveredPatterns: number;
    activePatterns: number;
  }> {
    return {
      totalSignatures: await this.storage.countSignatures(),
      totalClusters: await this.storage.countClusters(),
      discoveredPatterns: await this.storage.countDiscoveredPatterns(),
      activePatterns: await this.storage.countActivePatterns(),
    };
  }

  async getClusters(): Promise<FractalCluster[]> {
    return this.storage.getClusters();
  }

  async getDiscoveredPatterns(): Promise<DiscoveredFractalPattern[]> {
    return this.storage.getDiscoveredPatterns();
  }

  // ═══════════════════════════════════════════════════════════════
  // Helpers
  // ═══════════════════════════════════════════════════════════════

  private async fetchCandles(
    symbol: string,
    interval: string,
    limit: number
  ): Promise<any[]> {
    // Try archive candles first
    const docs = await this.db.collection('candles_binance')
      .find({ symbol, interval })
      .sort({ openTime: -1 })
      .limit(limit)
      .toArray();
    
    if (docs.length > 0) {
      return docs.reverse();
    }
    
    // Fallback to ta_candles
    const taDocs = await this.db.collection('ta_candles')
      .find({ asset: symbol, timeframe: interval })
      .sort({ openTime: -1 })
      .limit(limit)
      .toArray();
    
    return taDocs.reverse();
  }
}
