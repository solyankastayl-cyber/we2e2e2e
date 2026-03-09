/**
 * Phase 7.5 — Incremental Engine
 * 
 * Dependency-based incremental computation engine.
 * Only recalculates changed parts of the pipeline.
 * 
 * Dependency Graph:
 * candles → TA, momentum, volume_profile
 * TA → liquidity, scenario
 * scenario + memory → decision
 * 
 * Expected optimization:
 * CPU -70%, Latency -60%
 */

// ==============================================
// Node Types (Pipeline Components)
// ==============================================

export type NodeId = 
  | 'candles'
  | 'indicators'
  | 'ta'
  | 'momentum'
  | 'volume_profile'
  | 'liquidity'
  | 'structure_ai'
  | 'mtf'
  | 'scenario'
  | 'memory'
  | 'decision'
  | 'strategy'
  | 'portfolio'
  | 'execution'
  | 'metabrain'
  | 'macro';

export type NodeStatus = 'CLEAN' | 'DIRTY' | 'COMPUTING' | 'ERROR';

// ==============================================
// Core Types
// ==============================================

/**
 * Dependency graph node
 */
export interface DependencyNode {
  id: NodeId;
  
  // Dependencies
  dependsOn: NodeId[];
  
  // Reverse dependencies (what depends on this node)
  dependents: NodeId[];
  
  // Status
  status: NodeStatus;
  
  // Last computation
  lastComputed: number;
  computeDuration: number;  // ms
  
  // Version for cache invalidation
  version: number;
  
  // Cached result
  cachedResult?: any;
  cacheExpiry?: number;
}

/**
 * Dependency graph
 */
export interface DependencyGraph {
  nodes: Map<NodeId, DependencyNode>;
  
  // Topological order for computation
  computationOrder: NodeId[];
  
  // Stats
  lastFullCompute: number;
  incrementalSaves: number;  // CPU saved
}

/**
 * Computation result
 */
export interface ComputationResult {
  nodeId: NodeId;
  success: boolean;
  duration: number;
  version: number;
  result?: any;
  error?: string;
}

/**
 * Incremental update
 */
export interface IncrementalUpdate {
  triggeredBy: NodeId;
  nodesComputed: NodeId[];
  nodesSkipped: NodeId[];
  totalDuration: number;
  savedDuration: number;  // Estimated time saved vs full recompute
  timestamp: number;
}

/**
 * Engine configuration
 */
export interface IncrementalConfig {
  enabled: boolean;
  
  // Cache settings
  defaultCacheTTL: number;  // ms
  maxCacheSize: number;     // nodes
  
  // Performance
  parallelCompute: boolean;
  maxParallelNodes: number;
  
  // Monitoring
  trackMetrics: boolean;
  metricsRetention: number;  // hours
}

export const DEFAULT_INCREMENTAL_CONFIG: IncrementalConfig = {
  enabled: true,
  defaultCacheTTL: 60000,  // 1 min
  maxCacheSize: 100,
  parallelCompute: true,
  maxParallelNodes: 4,
  trackMetrics: true,
  metricsRetention: 24
};

// ==============================================
// Dependency Definitions
// ==============================================

/**
 * Static dependency graph definition
 * 
 * Format: nodeId → list of nodes it depends on
 */
export const DEPENDENCY_MAP: Record<NodeId, NodeId[]> = {
  // Root nodes (no dependencies)
  'candles': [],
  'macro': [],
  
  // First level (depends on candles)
  'indicators': ['candles'],
  'ta': ['candles'],
  'momentum': ['candles'],
  'volume_profile': ['candles'],
  
  // Second level
  'liquidity': ['ta', 'volume_profile'],
  'structure_ai': ['ta', 'liquidity', 'momentum'],
  'mtf': ['ta', 'indicators'],
  
  // Third level
  'scenario': ['ta', 'liquidity', 'structure_ai', 'mtf'],
  
  // Fourth level
  'memory': ['scenario'],
  
  // Fifth level
  'decision': ['scenario', 'memory', 'mtf', 'structure_ai'],
  
  // Sixth level
  'strategy': ['decision'],
  'portfolio': ['decision'],
  
  // Seventh level
  'execution': ['decision', 'strategy', 'portfolio'],
  
  // Top level
  'metabrain': ['decision', 'execution', 'portfolio', 'macro']
};

/**
 * Node computation cost estimates (ms)
 */
export const NODE_COSTS: Record<NodeId, number> = {
  'candles': 10,
  'macro': 50,
  'indicators': 30,
  'ta': 100,
  'momentum': 20,
  'volume_profile': 40,
  'liquidity': 50,
  'structure_ai': 80,
  'mtf': 60,
  'scenario': 120,
  'memory': 40,
  'decision': 150,
  'strategy': 30,
  'portfolio': 40,
  'execution': 25,
  'metabrain': 60
};

/**
 * Which nodes need recomputation on new candle
 */
export const CANDLE_TRIGGERED_NODES: NodeId[] = [
  'candles',
  'indicators',
  'ta',
  'momentum',
  'volume_profile',
  'liquidity',
  'structure_ai',
  'mtf',
  'scenario',
  'decision'
];

/**
 * Nodes that DON'T need recomputation on new candle
 */
export const CANDLE_SKIPPED_NODES: NodeId[] = [
  'macro',
  'memory',
  'strategy',
  'portfolio',
  'metabrain'
];

// ==============================================
// Engine Statistics
// ==============================================

export interface EngineStats {
  totalComputations: number;
  incrementalComputations: number;
  fullComputations: number;
  
  // Savings
  totalTimeSaved: number;      // ms
  avgTimeSavedPerUpdate: number;
  
  // Performance
  avgIncrementalDuration: number;
  avgFullDuration: number;
  
  // Cache
  cacheHits: number;
  cacheMisses: number;
  cacheHitRate: number;
  
  // Node stats
  nodeComputeCounts: Record<NodeId, number>;
  nodeAvgDurations: Record<NodeId, number>;
}

// ==============================================
// API Types
// ==============================================

export interface IncrementalStatusResponse {
  enabled: boolean;
  version: string;
  graph: {
    nodeCount: number;
    edges: number;
  };
  stats: EngineStats;
  lastUpdate: number;
}

export interface ComputeRequest {
  symbol: string;
  timeframe: string;
  trigger: NodeId;
  forceFullRecompute?: boolean;
}

export interface ComputeResponse {
  symbol: string;
  timeframe: string;
  mode: 'incremental' | 'full';
  nodesComputed: NodeId[];
  nodesSkipped: NodeId[];
  totalDuration: number;
  savedDuration: number;
  results: Record<NodeId, any>;
}
