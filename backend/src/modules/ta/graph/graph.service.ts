/**
 * Phase 8.6 — Graph Boost Service
 * 
 * Computes conditional probability boost for scenarios
 * based on historical pattern transitions
 */

import { Db } from 'mongodb';
import {
  GraphBoostResult,
  GraphBoostReason,
  GraphConfig,
  DEFAULT_GRAPH_CONFIG,
  NodeKey,
} from './graph.types.js';
import { createGraphStorage, hashNodeKey, GraphStorage } from './graph.storage.js';

export interface GraphBoostService {
  computeBoost(params: BoostParams): Promise<GraphBoostResult>;
  getNodeInfo(type: string, tf: string): Promise<NodeInfo | null>;
  getTopTransitions(type: string, tf: string, limit?: number): Promise<TransitionInfo[]>;
}

export interface BoostParams {
  // Current scenario pattern
  patternType: string;
  direction: string;
  timeframe: string;
  
  // Recent events (last N bars)
  recentEvents: Array<{
    type: string;
    direction: string;
    barsAgo: number;  // how many bars ago this occurred
  }>;
  
  // Context
  regime?: string;
  vol?: string;
}

export interface NodeInfo {
  nodeId: string;
  type: string;
  count: number;
  topOutgoing: Array<{
    toType: string;
    lift: number;
    count: number;
  }>;
}

export interface TransitionInfo {
  fromType: string;
  toType: string;
  lift: number;
  count: number;
  avgBars: number;
}

export function createGraphBoostService(db: Db, config: GraphConfig = DEFAULT_GRAPH_CONFIG): GraphBoostService {
  const storage = createGraphStorage(db);

  return {
    async computeBoost(params: BoostParams): Promise<GraphBoostResult> {
      if (!config.enabled) {
        return {
          graphBoostFactor: 1.0,
          graphReasons: [],
          supportingEdges: 0,
          confidence: 0,
        };
      }

      const targetNodeKey: NodeKey = {
        family: 'PATTERN',
        type: params.patternType,
        direction: params.direction,
        tf: params.timeframe,
      };
      const targetNodeId = hashNodeKey(targetNodeKey);

      // Find edges from recent events to target pattern
      const reasons: GraphBoostReason[] = [];
      let totalBoostRaw = 0;
      let totalWeight = 0;

      for (const recent of params.recentEvents) {
        const fromNodeKey: NodeKey = {
          family: 'PATTERN',
          type: recent.type,
          direction: recent.direction,
          tf: params.timeframe,
        };
        const fromNodeId = hashNodeKey(fromNodeKey);

        // Get edges from this recent event
        for (const window of config.windows) {
          if (recent.barsAgo > window) continue;

          const edges = await storage.getOutgoingEdges(fromNodeId, params.timeframe, window);
          
          // Find edge to target
          const edge = edges.find(e => e.toId === targetNodeId);
          if (!edge) continue;

          // Calculate weight based on recency
          const recencyWeight = 1 - (recent.barsAgo / window);  // closer = higher
          const reliabilityWeight = Math.min(edge.count / 100, 1);  // more data = more reliable
          const weight = recencyWeight * reliabilityWeight;

          // Accumulate boost
          const contribution = weight * Math.log(edge.lift);
          totalBoostRaw += contribution;
          totalWeight += weight;

          reasons.push({
            fromType: recent.type,
            toType: params.patternType,
            lift: edge.lift,
            deltaBars: recent.barsAgo,
            weight,
          });
        }
      }

      // Clamp and convert to factor
      const clampedBoost = Math.max(
        Math.log(config.boostClamp.min),
        Math.min(Math.log(config.boostClamp.max), totalBoostRaw)
      );
      const graphBoostFactor = Math.exp(clampedBoost);

      // Sort reasons by weight and limit
      reasons.sort((a, b) => b.weight - a.weight);
      const topReasons = reasons.slice(0, config.maxReasons);

      return {
        graphBoostFactor,
        graphReasons: topReasons,
        supportingEdges: reasons.length,
        confidence: totalWeight > 0 ? Math.min(totalWeight, 1) : 0,
      };
    },

    async getNodeInfo(type: string, tf: string): Promise<NodeInfo | null> {
      const nodeKey: NodeKey = {
        family: 'PATTERN',
        type,
        direction: 'BOTH',
        tf,
      };
      const nodeId = hashNodeKey(nodeKey);
      
      const node = await storage.getNode(nodeId);
      if (!node) return null;

      const outgoing = await storage.getOutgoingEdges(nodeId, tf);
      
      return {
        nodeId,
        type,
        count: node.count,
        topOutgoing: outgoing.slice(0, 10).map(e => ({
          toType: e.toId,  // Would need to lookup node to get type
          lift: e.lift,
          count: e.count,
        })),
      };
    },

    async getTopTransitions(type: string, tf: string, limit = 10): Promise<TransitionInfo[]> {
      const nodeKey: NodeKey = {
        family: 'PATTERN',
        type,
        direction: 'BOTH',
        tf,
      };
      const nodeId = hashNodeKey(nodeKey);
      
      const edges = await storage.getOutgoingEdges(nodeId, tf);
      
      return edges.slice(0, limit).map(e => ({
        fromType: type,
        toType: e.toId,
        lift: e.lift,
        count: e.count,
        avgBars: e.avgDeltaBars,
      }));
    },
  };
}
