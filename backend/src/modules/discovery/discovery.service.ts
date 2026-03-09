/**
 * Phase 9 — Strategy Discovery Engine: Service
 * 
 * Main service for strategy discovery
 */

import { Db } from 'mongodb';
import {
  SignalRecord,
  FeatureCombination,
  GeneratedStrategy,
  SetupCluster,
  DiscoveryResult,
  DiscoveryConfig,
  DEFAULT_DISCOVERY_CONFIG,
  AnyFeature
} from './discovery.types.js';
import { buildDataset, generateMockDataset } from './discovery.dataset.js';
import { analyzeFeatureCombinations, findTopCombinations, analyzeFeatures } from './discovery.analyzer.js';
import { generateStrategies, clusterStrategies } from './discovery.generator.js';

export interface DiscoveryService {
  /**
   * Run full discovery pipeline
   */
  runDiscovery(options?: {
    symbols?: string[];
    timeframes?: string[];
    useMockData?: boolean;
  }): Promise<DiscoveryResult>;
  
  /**
   * Get all generated strategies
   */
  getStrategies(status?: string): Promise<GeneratedStrategy[]>;
  
  /**
   * Get strategy by ID
   */
  getStrategy(id: string): Promise<GeneratedStrategy | null>;
  
  /**
   * Approve strategy
   */
  approveStrategy(id: string): Promise<boolean>;
  
  /**
   * Reject strategy
   */
  rejectStrategy(id: string): Promise<boolean>;
  
  /**
   * Get top feature combinations
   */
  getTopCombinations(limit?: number): Promise<FeatureCombination[]>;
  
  /**
   * Get strategy clusters
   */
  getClusters(): Promise<SetupCluster[]>;
  
  /**
   * Analyze single feature
   */
  getFeatureAnalysis(): Promise<Record<AnyFeature, { winRate: number; sampleSize: number; edge: number }>>;
  
  /**
   * Get discovery status
   */
  getStatus(): Promise<{
    enabled: boolean;
    datasetSize: number;
    strategiesGenerated: number;
    lastRun: number | null;
  }>;
  
  /**
   * Health check
   */
  health(): { enabled: boolean; version: string };
}

/**
 * Create Discovery Service
 */
export function createDiscoveryService(
  db: Db,
  config: DiscoveryConfig = DEFAULT_DISCOVERY_CONFIG
): DiscoveryService {
  // Collections
  const strategiesCol = db.collection('discovery_strategies');
  const combinationsCol = db.collection('discovery_combinations');
  const clustersCol = db.collection('discovery_clusters');
  const runsCol = db.collection('discovery_runs');
  
  // Cache
  let lastRun: DiscoveryResult | null = null;
  let cachedStrategies: GeneratedStrategy[] = [];
  let cachedCombinations: FeatureCombination[] = [];
  let cachedClusters: SetupCluster[] = [];
  let cachedDataset: SignalRecord[] = [];
  
  return {
    async runDiscovery(options = {}): Promise<DiscoveryResult> {
      const startedAt = Date.now();
      const { symbols = ['BTCUSDT', 'ETHUSDT'], timeframes = ['1h', '4h'], useMockData = true } = options;
      
      // Build or generate dataset
      let dataset: SignalRecord[];
      
      if (useMockData) {
        dataset = generateMockDataset(500);
      } else {
        dataset = await buildDataset(db, { symbols, timeframes, limit: 5000 });
        if (dataset.length < 100) {
          // Fallback to mock if not enough real data
          dataset = generateMockDataset(500);
        }
      }
      
      cachedDataset = dataset;
      
      // Analyze combinations
      const combinations = analyzeFeatureCombinations(dataset, config);
      cachedCombinations = combinations;
      
      // Store combinations
      if (combinations.length > 0) {
        await combinationsCol.deleteMany({});
        await combinationsCol.insertMany(
          combinations.map(c => ({ ...c, storedAt: new Date() }))
        ).catch(() => {});
      }
      
      // Generate strategies
      const strategies = generateStrategies(dataset, config);
      cachedStrategies = strategies;
      
      // Store strategies
      if (strategies.length > 0) {
        await strategiesCol.deleteMany({});
        await strategiesCol.insertMany(
          strategies.map(s => ({ ...s, storedAt: new Date() }))
        ).catch(() => {});
      }
      
      // Generate clusters
      const clusters = clusterStrategies(strategies);
      cachedClusters = clusters;
      
      // Store clusters
      if (clusters.length > 0) {
        await clustersCol.deleteMany({});
        await clustersCol.insertMany(
          clusters.map(c => ({ ...c, storedAt: new Date() }))
        ).catch(() => {});
      }
      
      // Build result
      const result: DiscoveryResult = {
        runId: `run_${Date.now()}`,
        startedAt,
        completedAt: Date.now(),
        datasetSize: dataset.length,
        symbolsAnalyzed: symbols,
        timeframesAnalyzed: timeframes,
        combinationsFound: combinations.length,
        combinationsWithEdge: combinations.filter(c => c.edge > 0.1).length,
        clustersFormed: clusters.length,
        strategiesGenerated: strategies.length,
        topCombinations: combinations.slice(0, 5),
        topStrategies: strategies.slice(0, 5),
        insights: generateInsights(strategies, combinations)
      };
      
      // Store run
      await runsCol.insertOne({ ...result, storedAt: new Date() }).catch(() => {});
      
      lastRun = result;
      
      return result;
    },
    
    async getStrategies(status?: string): Promise<GeneratedStrategy[]> {
      if (cachedStrategies.length === 0) {
        const stored = await strategiesCol
          .find(status ? { status } : {})
          .project({ _id: 0 })
          .toArray();
        cachedStrategies = stored as GeneratedStrategy[];
      }
      
      if (status) {
        return cachedStrategies.filter(s => s.status === status);
      }
      
      return cachedStrategies;
    },
    
    async getStrategy(id: string): Promise<GeneratedStrategy | null> {
      // Check cache
      const cached = cachedStrategies.find(s => s.id === id);
      if (cached) return cached;
      
      // Check DB
      const stored = await strategiesCol.findOne(
        { id },
        { projection: { _id: 0 } }
      );
      
      return stored as GeneratedStrategy | null;
    },
    
    async approveStrategy(id: string): Promise<boolean> {
      const result = await strategiesCol.updateOne(
        { id },
        { $set: { status: 'APPROVED', approvedAt: Date.now() } }
      );
      
      // Update cache
      const cached = cachedStrategies.find(s => s.id === id);
      if (cached) {
        cached.status = 'APPROVED';
        cached.approvedAt = Date.now();
      }
      
      return result.modifiedCount > 0;
    },
    
    async rejectStrategy(id: string): Promise<boolean> {
      const result = await strategiesCol.updateOne(
        { id },
        { $set: { status: 'REJECTED' } }
      );
      
      // Update cache
      const cached = cachedStrategies.find(s => s.id === id);
      if (cached) {
        cached.status = 'REJECTED';
      }
      
      return result.modifiedCount > 0;
    },
    
    async getTopCombinations(limit = 10): Promise<FeatureCombination[]> {
      if (cachedCombinations.length === 0) {
        const stored = await combinationsCol
          .find({})
          .sort({ edge: -1 })
          .limit(limit)
          .project({ _id: 0 })
          .toArray();
        cachedCombinations = stored as FeatureCombination[];
      }
      
      return cachedCombinations.slice(0, limit);
    },
    
    async getClusters(): Promise<SetupCluster[]> {
      if (cachedClusters.length === 0) {
        const stored = await clustersCol
          .find({})
          .project({ _id: 0 })
          .toArray();
        cachedClusters = stored as SetupCluster[];
      }
      
      return cachedClusters;
    },
    
    async getFeatureAnalysis(): Promise<Record<AnyFeature, { winRate: number; sampleSize: number; edge: number }>> {
      if (cachedDataset.length === 0) {
        cachedDataset = generateMockDataset(500);
      }
      
      return analyzeFeatures(cachedDataset);
    },
    
    async getStatus(): Promise<{
      enabled: boolean;
      datasetSize: number;
      strategiesGenerated: number;
      lastRun: number | null;
    }> {
      return {
        enabled: config.enabled,
        datasetSize: cachedDataset.length,
        strategiesGenerated: cachedStrategies.length,
        lastRun: lastRun?.completedAt || null
      };
    },
    
    health(): { enabled: boolean; version: string } {
      return {
        enabled: config.enabled,
        version: 'discovery_v1_phase9'
      };
    }
  };
}

/**
 * Generate insights from analysis
 */
function generateInsights(
  strategies: GeneratedStrategy[],
  combinations: FeatureCombination[]
): string[] {
  const insights: string[] = [];
  
  if (strategies.length === 0) {
    insights.push('No strategies discovered meeting threshold criteria');
    return insights;
  }
  
  // Top strategy insight
  const top = strategies[0];
  insights.push(`Top strategy: ${top.name} with ${(top.metrics.winRate * 100).toFixed(1)}% win rate`);
  
  // Most common features
  const featureCounts: Record<string, number> = {};
  for (const combo of combinations) {
    for (const f of combo.features) {
      featureCounts[f] = (featureCounts[f] || 0) + 1;
    }
  }
  
  const topFeatures = Object.entries(featureCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([f]) => f);
  
  if (topFeatures.length > 0) {
    insights.push(`Most effective features: ${topFeatures.join(', ')}`);
  }
  
  // Regime insights
  const approvedCount = strategies.filter(s => s.status === 'APPROVED').length;
  insights.push(`${approvedCount} strategies auto-approved, ${strategies.length - approvedCount} in testing`);
  
  // Best direction
  const longBetter = strategies.filter(s => s.rules.direction === 'LONG').length;
  const shortBetter = strategies.filter(s => s.rules.direction === 'SHORT').length;
  
  if (longBetter > shortBetter * 1.5) {
    insights.push('LONG setups showing stronger edge in current dataset');
  } else if (shortBetter > longBetter * 1.5) {
    insights.push('SHORT setups showing stronger edge in current dataset');
  }
  
  return insights;
}

// Singleton
let discoveryServiceInstance: DiscoveryService | null = null;

/**
 * Get or create discovery service
 */
export function getDiscoveryService(db: Db, config?: DiscoveryConfig): DiscoveryService {
  if (!discoveryServiceInstance) {
    discoveryServiceInstance = createDiscoveryService(db, config);
  }
  return discoveryServiceInstance;
}
