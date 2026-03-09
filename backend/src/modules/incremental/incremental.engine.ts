/**
 * Phase 7.5 — Incremental Engine: Core Engine
 * 
 * Main incremental computation engine
 */

import {
  NodeId,
  DependencyGraph,
  ComputationResult,
  IncrementalUpdate,
  EngineStats,
  IncrementalConfig,
  DEFAULT_INCREMENTAL_CONFIG,
  CANDLE_TRIGGERED_NODES,
  CANDLE_SKIPPED_NODES,
  NODE_COSTS
} from './incremental.types.js';

import {
  buildDependencyGraph,
  markDirty,
  markClean,
  getNodesToCompute,
  getCleanNodes,
  canCompute,
  estimateTimeSaved,
  getGraphStats
} from './incremental.graph.js';

/**
 * Incremental computation engine
 */
export class IncrementalEngine {
  private graph: DependencyGraph;
  private config: IncrementalConfig;
  private stats: EngineStats;
  
  // Node computation functions
  private computeFunctions: Map<NodeId, (ctx: any) => Promise<any>>;
  
  // Context (current market data)
  private context: Map<string, any>;  // key = symbol:tf
  
  constructor(config: IncrementalConfig = DEFAULT_INCREMENTAL_CONFIG) {
    this.config = config;
    this.graph = buildDependencyGraph();
    this.computeFunctions = new Map();
    this.context = new Map();
    
    this.stats = {
      totalComputations: 0,
      incrementalComputations: 0,
      fullComputations: 0,
      totalTimeSaved: 0,
      avgTimeSavedPerUpdate: 0,
      avgIncrementalDuration: 0,
      avgFullDuration: 0,
      cacheHits: 0,
      cacheMisses: 0,
      cacheHitRate: 0,
      nodeComputeCounts: {} as Record<NodeId, number>,
      nodeAvgDurations: {} as Record<NodeId, number>
    };
  }
  
  /**
   * Register computation function for a node
   */
  registerCompute(nodeId: NodeId, fn: (ctx: any) => Promise<any>): void {
    this.computeFunctions.set(nodeId, fn);
  }
  
  /**
   * Trigger update from a node (e.g., new candle)
   */
  async triggerUpdate(
    symbol: string,
    timeframe: string,
    trigger: NodeId,
    forceFullRecompute: boolean = false
  ): Promise<IncrementalUpdate> {
    const startTime = Date.now();
    const contextKey = `${symbol}:${timeframe}`;
    
    // Get or create context
    if (!this.context.has(contextKey)) {
      this.context.set(contextKey, { symbol, timeframe });
    }
    const ctx = this.context.get(contextKey);
    
    let nodesToCompute: NodeId[];
    let nodesToSkip: NodeId[];
    
    if (forceFullRecompute) {
      // Full recompute - all nodes
      nodesToCompute = this.graph.computationOrder;
      nodesToSkip = [];
      this.stats.fullComputations++;
    } else {
      // Incremental - only dirty nodes
      markDirty(this.graph, trigger);
      nodesToCompute = getNodesToCompute(this.graph);
      nodesToSkip = getCleanNodes(this.graph);
      this.stats.incrementalComputations++;
    }
    
    // Special case: candle trigger
    if (trigger === 'candles' && !forceFullRecompute) {
      // Use predefined set of nodes to compute
      nodesToCompute = CANDLE_TRIGGERED_NODES;
      nodesToSkip = CANDLE_SKIPPED_NODES;
      
      // Mark candle-triggered nodes as dirty
      for (const nodeId of nodesToCompute) {
        const node = this.graph.nodes.get(nodeId);
        if (node) node.status = 'DIRTY';
      }
    }
    
    // Compute nodes
    const computedNodes: NodeId[] = [];
    
    for (const nodeId of nodesToCompute) {
      // Check if we can compute (all deps ready)
      if (!canCompute(this.graph, nodeId) && !forceFullRecompute) {
        continue;
      }
      
      // Get computation function
      const computeFn = this.computeFunctions.get(nodeId);
      
      const nodeStart = Date.now();
      let result: any;
      
      if (computeFn) {
        try {
          result = await computeFn(ctx);
        } catch (error) {
          result = { error: String(error) };
        }
      } else {
        // Mock computation
        result = this.mockCompute(nodeId, ctx);
        await this.delay(NODE_COSTS[nodeId] * 0.1);  // Simulate some work
      }
      
      const nodeDuration = Date.now() - nodeStart;
      
      // Store result in context
      ctx[nodeId] = result;
      
      // Mark as clean
      markClean(this.graph, nodeId, result, nodeDuration);
      
      computedNodes.push(nodeId);
      
      // Update node stats
      this.updateNodeStats(nodeId, nodeDuration);
    }
    
    const totalDuration = Date.now() - startTime;
    const savedDuration = estimateTimeSaved(this.graph, computedNodes, nodesToSkip);
    
    // Update stats
    this.stats.totalComputations++;
    this.stats.totalTimeSaved += savedDuration;
    this.stats.avgTimeSavedPerUpdate = 
      this.stats.totalTimeSaved / this.stats.incrementalComputations || 0;
    
    if (forceFullRecompute) {
      this.stats.avgFullDuration = 
        (this.stats.avgFullDuration + totalDuration) / 2;
    } else {
      this.stats.avgIncrementalDuration = 
        (this.stats.avgIncrementalDuration + totalDuration) / 2;
    }
    
    this.graph.incrementalSaves += savedDuration;
    
    return {
      triggeredBy: trigger,
      nodesComputed: computedNodes,
      nodesSkipped: nodesToSkip,
      totalDuration,
      savedDuration,
      timestamp: Date.now()
    };
  }
  
  /**
   * Mock computation for nodes without registered functions
   */
  private mockCompute(nodeId: NodeId, ctx: any): any {
    return {
      nodeId,
      symbol: ctx.symbol,
      timeframe: ctx.timeframe,
      computed: true,
      timestamp: Date.now()
    };
  }
  
  /**
   * Update node statistics
   */
  private updateNodeStats(nodeId: NodeId, duration: number): void {
    if (!this.stats.nodeComputeCounts[nodeId]) {
      this.stats.nodeComputeCounts[nodeId] = 0;
      this.stats.nodeAvgDurations[nodeId] = 0;
    }
    
    this.stats.nodeComputeCounts[nodeId]++;
    this.stats.nodeAvgDurations[nodeId] = 
      (this.stats.nodeAvgDurations[nodeId] + duration) / 2;
  }
  
  /**
   * Get current context for symbol/timeframe
   */
  getContext(symbol: string, timeframe: string): any {
    return this.context.get(`${symbol}:${timeframe}`) || null;
  }
  
  /**
   * Get cached result for a node
   */
  getCachedResult(symbol: string, timeframe: string, nodeId: NodeId): any {
    const ctx = this.getContext(symbol, timeframe);
    if (!ctx) return null;
    return ctx[nodeId] || null;
  }
  
  /**
   * Get engine statistics
   */
  getStats(): EngineStats {
    this.updateCacheStats();
    return { ...this.stats };
  }
  
  /**
   * Update cache statistics
   */
  private updateCacheStats(): void {
    const total = this.stats.cacheHits + this.stats.cacheMisses;
    this.stats.cacheHitRate = total > 0 ? this.stats.cacheHits / total : 0;
  }
  
  /**
   * Get graph information
   */
  getGraphInfo(): {
    nodeCount: number;
    edges: number;
    computationOrder: NodeId[];
  } {
    const stats = getGraphStats(this.graph);
    return {
      nodeCount: stats.nodeCount,
      edges: stats.edgeCount,
      computationOrder: this.graph.computationOrder
    };
  }
  
  /**
   * Reset engine state
   */
  reset(): void {
    this.graph = buildDependencyGraph();
    this.context.clear();
    
    // Reset stats
    this.stats = {
      totalComputations: 0,
      incrementalComputations: 0,
      fullComputations: 0,
      totalTimeSaved: 0,
      avgTimeSavedPerUpdate: 0,
      avgIncrementalDuration: 0,
      avgFullDuration: 0,
      cacheHits: 0,
      cacheMisses: 0,
      cacheHitRate: 0,
      nodeComputeCounts: {} as Record<NodeId, number>,
      nodeAvgDurations: {} as Record<NodeId, number>
    };
  }
  
  /**
   * Health check
   */
  health(): { enabled: boolean; version: string; nodeCount: number } {
    return {
      enabled: this.config.enabled,
      version: 'incremental_v1_phase7.5',
      nodeCount: this.graph.nodes.size
    };
  }
  
  /**
   * Simple delay helper
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Singleton instance
let engineInstance: IncrementalEngine | null = null;

/**
 * Get or create engine instance
 */
export function getIncrementalEngine(config?: IncrementalConfig): IncrementalEngine {
  if (!engineInstance) {
    engineInstance = new IncrementalEngine(config);
  }
  return engineInstance;
}
