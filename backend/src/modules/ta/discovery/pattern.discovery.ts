/**
 * P2.1 — Pattern Discovery Engine
 * 
 * Main engine for discovering new patterns through shape clustering.
 * Integrates with existing pattern registry.
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuid } from 'uuid';
import { 
  extractShape, 
  flattenShape, 
  downsampleShape,
  ShapeVector,
  ShapeConfig,
  DEFAULT_SHAPE_CONFIG,
  CandleInput
} from './shape.extractor.js';
import { 
  ShapeClusterEngine, 
  createShapeClusterEngine,
  ShapeSample,
  Cluster,
  ClusterResult,
  ClusterConfig,
  DEFAULT_CLUSTER_CONFIG
} from './shape.cluster.js';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface DiscoveryConfig {
  shape: ShapeConfig;
  cluster: ClusterConfig;
  minOccurrences: number;     // Min occurrences to register pattern
  minProfitFactor: number;    // Min PF to register pattern
  minWinRate: number;         // Min win rate to register
}

export const DEFAULT_DISCOVERY_CONFIG: DiscoveryConfig = {
  shape: DEFAULT_SHAPE_CONFIG,
  cluster: DEFAULT_CLUSTER_CONFIG,
  minOccurrences: 200,
  minProfitFactor: 1.2,
  minWinRate: 0.35,
};

export interface DiscoveredPattern {
  patternId: string;
  name: string;                // e.g., "DISCOVERED_017"
  clusterId: number;
  
  centroid: number[];
  meanShape: number[];
  variance: number[];
  
  occurrences: number;
  winRate: number;
  avgR: number;
  profitFactor: number;
  
  assets: string[];
  timeframes: string[];
  
  status: 'CANDIDATE' | 'REGISTERED' | 'DISABLED';
  registeredAt?: Date;
  updatedAt: Date;
  
  // Key points for detection
  keyFeatures: {
    compressionLevel: number;
    slopeDirection: 'UP' | 'DOWN' | 'FLAT';
    volatilityRatio: number;
    breakoutZone: { low: number; high: number };
  };
}

export interface DiscoverySession {
  sessionId: string;
  assets: string[];
  timeframes: string[];
  startDate: string;
  endDate: string;
  
  samplesProcessed: number;
  clustersFound: number;
  patternsRegistered: number;
  
  status: 'RUNNING' | 'DONE' | 'FAILED';
  startedAt: Date;
  finishedAt?: Date;
  error?: string;
}

// ═══════════════════════════════════════════════════════════════
// COLLECTIONS
// ═══════════════════════════════════════════════════════════════

const COLLECTION_CANDLES = 'ta_candles';
const COLLECTION_PATTERNS = 'ta_discovered_patterns';
const COLLECTION_SESSIONS = 'ta_discovery_sessions';
const COLLECTION_OUTCOMES = 'ta_outcomes_v3';

// ═══════════════════════════════════════════════════════════════
// DISCOVERY ENGINE
// ═══════════════════════════════════════════════════════════════

export class PatternDiscoveryEngine {
  private db: Db;
  private config: DiscoveryConfig;
  private clusterEngine: ShapeClusterEngine;
  private candlesCol: Collection;
  private patternsCol: Collection;
  private sessionsCol: Collection;
  private outcomesCol: Collection;
  
  constructor(db: Db, config: DiscoveryConfig = DEFAULT_DISCOVERY_CONFIG) {
    this.db = db;
    this.config = config;
    this.clusterEngine = createShapeClusterEngine(config.cluster);
    this.candlesCol = db.collection(COLLECTION_CANDLES);
    this.patternsCol = db.collection(COLLECTION_PATTERNS);
    this.sessionsCol = db.collection(COLLECTION_SESSIONS);
    this.outcomesCol = db.collection(COLLECTION_OUTCOMES);
  }
  
  /**
   * Run discovery session
   */
  async runDiscovery(params: {
    assets: string[];
    timeframes: string[];
    startDate: string;
    endDate: string;
  }): Promise<DiscoverySession> {
    const sessionId = uuid();
    const session: DiscoverySession = {
      sessionId,
      ...params,
      samplesProcessed: 0,
      clustersFound: 0,
      patternsRegistered: 0,
      status: 'RUNNING',
      startedAt: new Date(),
    };
    
    await this.sessionsCol.insertOne(session);
    
    console.log(`[Discovery] Starting session ${sessionId}`);
    
    try {
      // 1. Extract shapes from historical data
      const samples = await this.extractSamples(params);
      session.samplesProcessed = samples.length;
      
      console.log(`[Discovery] Extracted ${samples.length} shape samples`);
      
      if (samples.length < this.config.cluster.minClusterSize * 2) {
        throw new Error(`Not enough samples: ${samples.length}`);
      }
      
      // 2. Cluster shapes
      const clusterResult = this.clusterEngine.cluster(samples);
      session.clustersFound = clusterResult.totalClusters;
      
      console.log(`[Discovery] Found ${clusterResult.totalClusters} clusters`);
      
      // 3. Evaluate and register patterns
      const registeredCount = await this.evaluateAndRegister(clusterResult, samples);
      session.patternsRegistered = registeredCount;
      
      // 4. Update session
      session.status = 'DONE';
      session.finishedAt = new Date();
      
      await this.sessionsCol.updateOne(
        { sessionId },
        { $set: session }
      );
      
      console.log(`[Discovery] Session complete: ${registeredCount} patterns registered`);
      
      return session;
      
    } catch (error) {
      session.status = 'FAILED';
      session.error = (error as Error).message;
      session.finishedAt = new Date();
      
      await this.sessionsCol.updateOne(
        { sessionId },
        { $set: session }
      );
      
      throw error;
    }
  }
  
  /**
   * Extract shape samples from candles
   */
  private async extractSamples(params: {
    assets: string[];
    timeframes: string[];
    startDate: string;
    endDate: string;
  }): Promise<ShapeSample[]> {
    const samples: ShapeSample[] = [];
    const { windowSize, embeddingDim } = this.config.shape;
    
    const startTs = new Date(params.startDate).getTime();
    const endTs = new Date(params.endDate).getTime();
    
    for (const asset of params.assets) {
      for (const tf of params.timeframes) {
        // Load candles
        const candles = await this.candlesCol
          .find({
            asset,
            timeframe: tf,
            openTime: { $gte: startTs, $lte: endTs }
          })
          .sort({ openTime: 1 })
          .toArray() as any[];
        
        if (candles.length < windowSize * 2) continue;
        
        // Slide window and extract shapes
        const step = Math.max(5, Math.floor(windowSize / 10)); // Overlap
        
        for (let i = windowSize; i < candles.length - 50; i += step) {
          const window = candles.slice(i - windowSize, i);
          const candleInputs: CandleInput[] = window.map(c => ({
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
            volume: c.volume || 0,
          }));
          
          try {
            const shape = extractShape(candleInputs, this.config.shape);
            const flat = flattenShape(shape);
            const embedding = downsampleShape(flat, embeddingDim);
            
            // Get outcome if available
            const futureCandles = candles.slice(i, Math.min(i + 50, candles.length));
            const outcome = this.evaluateSimpleOutcome(
              candles[i - 1].close,
              futureCandles
            );
            
            samples.push({
              id: `${asset}_${tf}_${candles[i].openTime}`,
              embedding,
              asset,
              timeframe: tf,
              timestamp: candles[i].openTime,
              outcome,
            });
          } catch (err) {
            // Skip invalid windows
          }
        }
      }
    }
    
    return samples;
  }
  
  /**
   * Simple outcome evaluation for discovery
   */
  private evaluateSimpleOutcome(
    entryPrice: number,
    futureCandles: any[]
  ): { rMultiple: number; entryHit: boolean } | undefined {
    if (futureCandles.length < 10) return undefined;
    
    // Simple R calculation based on max favorable/adverse excursion
    let mfe = 0;
    let mae = 0;
    
    for (const c of futureCandles) {
      const upMove = (c.high - entryPrice) / entryPrice;
      const downMove = (entryPrice - c.low) / entryPrice;
      
      if (upMove > mfe) mfe = upMove;
      if (downMove > mae) mae = downMove;
    }
    
    // Assume risk = 2% (typical ATR-based stop)
    const risk = 0.02;
    const mfeR = mfe / risk;
    const maeR = mae / risk;
    
    // Simple R based on direction that had better excursion
    const rMultiple = mfeR > maeR ? mfeR * 0.5 : -maeR * 0.5;
    
    return {
      rMultiple,
      entryHit: true,
    };
  }
  
  /**
   * Evaluate clusters and register patterns
   */
  private async evaluateAndRegister(
    clusterResult: ClusterResult,
    samples: ShapeSample[]
  ): Promise<number> {
    const { minOccurrences, minProfitFactor, minWinRate } = this.config;
    let registered = 0;
    
    for (const cluster of clusterResult.clusters) {
      // Check minimum requirements
      if (cluster.size < minOccurrences) continue;
      if (cluster.profitFactor && cluster.profitFactor < minProfitFactor) continue;
      if (cluster.winRate && cluster.winRate < minWinRate) continue;
      
      // Get cluster samples
      const clusterSamples = samples.filter(s => cluster.samples.includes(s.id));
      
      // Extract key features
      const keyFeatures = this.extractKeyFeatures(clusterSamples, cluster);
      
      // Determine assets and timeframes
      const assets = [...new Set(clusterSamples.map(s => s.asset!).filter(Boolean))];
      const timeframes = [...new Set(clusterSamples.map(s => s.timeframe!).filter(Boolean))];
      
      // Create discovered pattern
      const pattern: DiscoveredPattern = {
        patternId: uuid(),
        name: `DISCOVERED_${String(cluster.clusterId).padStart(3, '0')}`,
        clusterId: cluster.clusterId,
        centroid: cluster.centroid,
        meanShape: cluster.centroid,
        variance: this.calculateVariance(clusterSamples, cluster.centroid),
        occurrences: cluster.size,
        winRate: cluster.winRate || 0,
        avgR: cluster.avgR || 0,
        profitFactor: cluster.profitFactor || 0,
        assets,
        timeframes,
        status: 'CANDIDATE',
        updatedAt: new Date(),
        keyFeatures,
      };
      
      // Save to database
      await this.patternsCol.updateOne(
        { name: pattern.name },
        { $set: pattern },
        { upsert: true }
      );
      
      registered++;
      console.log(`[Discovery] Registered pattern ${pattern.name}: n=${cluster.size}, PF=${cluster.profitFactor?.toFixed(2)}`);
    }
    
    return registered;
  }
  
  /**
   * Extract key features from cluster for detection
   */
  private extractKeyFeatures(
    samples: ShapeSample[],
    cluster: Cluster
  ): DiscoveredPattern['keyFeatures'] {
    // Analyze centroid to determine characteristics
    const centroid = cluster.centroid;
    const dim = centroid.length;
    
    // First half is price shape, analyze slope
    const priceHalf = centroid.slice(0, Math.floor(dim / 4));
    const firstPrice = priceHalf[0];
    const lastPrice = priceHalf[priceHalf.length - 1];
    const slope = lastPrice - firstPrice;
    
    // Compression from later features
    const compressionIdx = Math.floor(dim * 0.75);
    const compressionLevel = centroid[compressionIdx] || 0.5;
    
    // Volatility from HL range section
    const hlStart = Math.floor(dim / 4);
    const hlEnd = Math.floor(dim / 2);
    const hlRange = centroid.slice(hlStart, hlEnd);
    const avgHL = hlRange.reduce((a, b) => a + b, 0) / hlRange.length;
    
    return {
      compressionLevel: Math.max(0, Math.min(1, compressionLevel)),
      slopeDirection: slope > 0.1 ? 'UP' : slope < -0.1 ? 'DOWN' : 'FLAT',
      volatilityRatio: avgHL,
      breakoutZone: {
        low: Math.min(...priceHalf),
        high: Math.max(...priceHalf),
      },
    };
  }
  
  /**
   * Calculate variance for cluster
   */
  private calculateVariance(
    samples: ShapeSample[],
    centroid: number[]
  ): number[] {
    const variance = new Array(centroid.length).fill(0);
    
    for (const sample of samples) {
      for (let i = 0; i < centroid.length; i++) {
        const diff = sample.embedding[i] - centroid[i];
        variance[i] += diff * diff;
      }
    }
    
    for (let i = 0; i < variance.length; i++) {
      variance[i] = Math.sqrt(variance[i] / samples.length);
    }
    
    return variance;
  }
  
  /**
   * Get all discovered patterns
   */
  async getDiscoveredPatterns(status?: string): Promise<DiscoveredPattern[]> {
    const filter = status ? { status } : {};
    return this.patternsCol.find(filter).sort({ profitFactor: -1 }).toArray() as any;
  }
  
  /**
   * Register a candidate pattern
   */
  async registerPattern(patternId: string): Promise<boolean> {
    const result = await this.patternsCol.updateOne(
      { patternId },
      { 
        $set: { 
          status: 'REGISTERED',
          registeredAt: new Date(),
          updatedAt: new Date(),
        }
      }
    );
    return result.modifiedCount > 0;
  }
  
  /**
   * Detect discovered patterns in current market
   */
  async detectDiscoveredPatterns(
    candles: CandleInput[],
    asset: string,
    timeframe: string
  ): Promise<Array<{
    pattern: DiscoveredPattern;
    similarity: number;
    distance: number;
  }>> {
    if (candles.length < this.config.shape.windowSize) {
      return [];
    }
    
    // Extract current shape
    const shape = extractShape(candles, this.config.shape);
    const flat = flattenShape(shape);
    const embedding = downsampleShape(flat, this.config.shape.embeddingDim);
    
    // Load registered patterns
    const patterns = await this.getDiscoveredPatterns('REGISTERED');
    
    const results: Array<{
      pattern: DiscoveredPattern;
      similarity: number;
      distance: number;
    }> = [];
    
    for (const pattern of patterns) {
      // Check if pattern applies to this asset/timeframe
      if (pattern.assets.length > 0 && !pattern.assets.includes(asset)) continue;
      if (pattern.timeframes.length > 0 && !pattern.timeframes.includes(timeframe)) continue;
      
      // Calculate similarity
      const sample: ShapeSample = { id: 'current', embedding };
      const assignment = this.clusterEngine.assignToCluster(sample, [{
        clusterId: pattern.clusterId,
        centroid: pattern.centroid,
        samples: [],
        size: pattern.occurrences,
        density: 1,
        avgDistance: 0.1,
      }]);
      
      if (assignment) {
        results.push({
          pattern,
          similarity: 1 - assignment.distance,
          distance: assignment.distance,
        });
      }
    }
    
    return results.sort((a, b) => b.similarity - a.similarity);
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

export function createPatternDiscoveryEngine(
  db: Db,
  config?: Partial<DiscoveryConfig>
): PatternDiscoveryEngine {
  return new PatternDiscoveryEngine(db, {
    ...DEFAULT_DISCOVERY_CONFIG,
    ...config,
  });
}
