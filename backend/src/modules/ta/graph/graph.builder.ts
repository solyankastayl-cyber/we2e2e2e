/**
 * Phase 8.6 — Graph Builder
 * 
 * Builds transition graph from pattern/event history
 * Deterministic and idempotent
 */

import { Db } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';
import {
  NodeKey,
  GraphNode,
  GraphEdge,
  GraphRunAudit,
  GraphBuildParams,
  PatternEvent,
  DEFAULT_GRAPH_PARAMS,
} from './graph.types.js';
import { 
  createGraphStorage, 
  hashNodeKey, 
  hashEdge,
  GraphStorage 
} from './graph.storage.js';

interface EdgeAccumulator {
  count: number;
  deltaBarsList: number[];
}

/**
 * Build graph from pattern events
 */
export async function buildGraph(
  db: Db,
  events: PatternEvent[],
  params: GraphBuildParams = DEFAULT_GRAPH_PARAMS
): Promise<GraphRunAudit> {
  const storage = createGraphStorage(db);
  const runId = uuidv4();
  const builtAt = new Date();

  console.log(`[GraphBuilder] Starting build: ${events.length} events`);

  // Group events by asset+tf and sort by anchorIdx
  const eventsByKey = new Map<string, PatternEvent[]>();
  for (const e of events) {
    const key = `${e.asset}:${e.timeframe}`;
    if (!eventsByKey.has(key)) {
      eventsByKey.set(key, []);
    }
    eventsByKey.get(key)!.push(e);
  }

  // Sort each group by anchorIdx
  for (const group of eventsByKey.values()) {
    group.sort((a, b) => a.anchorIdx - b.anchorIdx);
  }

  // Build nodes and edges
  const nodeMap = new Map<string, GraphNode>();
  const edgeMap = new Map<string, EdgeAccumulator>();
  let totalEvents = 0;

  for (const [key, groupEvents] of eventsByKey.entries()) {
    for (let i = 0; i < groupEvents.length; i++) {
      const eventA = groupEvents[i];
      const nodeIdA = hashNodeKey(eventA.nodeKey);

      // Ensure node exists
      if (!nodeMap.has(nodeIdA)) {
        nodeMap.set(nodeIdA, {
          nodeId: nodeIdA,
          key: eventA.nodeKey,
          count: 0,
          firstSeenAt: builtAt,
          lastSeenAt: builtAt,
        });
      }
      const nodeA = nodeMap.get(nodeIdA)!;
      nodeA.count++;
      nodeA.lastSeenAt = builtAt;
      totalEvents++;

      // Look for events B within window
      for (const window of params.windowBars) {
        for (let j = i + 1; j < groupEvents.length; j++) {
          const eventB = groupEvents[j];
          const deltaBars = eventB.anchorIdx - eventA.anchorIdx;

          if (deltaBars <= 0) continue;
          if (deltaBars > window) break;  // events sorted, can break

          const nodeIdB = hashNodeKey(eventB.nodeKey);
          const edgeId = hashEdge(nodeIdA, nodeIdB, eventA.nodeKey.tf, window);

          if (!edgeMap.has(edgeId)) {
            edgeMap.set(edgeId, { count: 0, deltaBarsList: [] });
          }
          const edge = edgeMap.get(edgeId)!;
          edge.count++;
          edge.deltaBarsList.push(deltaBars);
        }
      }
    }
  }

  // Compute probabilities and lift
  const nodes = Array.from(nodeMap.values());
  const edges: GraphEdge[] = [];

  for (const [edgeId, acc] of edgeMap.entries()) {
    if (acc.count < params.minEdgeCount) continue;

    // Parse edge ID to get from/to/tf/window
    const parts = edgeId.split(':');  // Won't work - edgeId is hash
    // Need to track full edge info

    // Actually we need to reconstruct from the accumulator
    // Let me fix this approach
  }

  // Better approach: store full edge info during accumulation
  console.log(`[GraphBuilder] Built ${nodes.length} nodes, calculating edges...`);

  // Rebuild with full edge tracking
  const fullEdgeMap = new Map<string, {
    fromId: string;
    toId: string;
    tf: string;
    windowBars: number;
    count: number;
    deltaBarsList: number[];
  }>();

  for (const [key, groupEvents] of eventsByKey.entries()) {
    for (let i = 0; i < groupEvents.length; i++) {
      const eventA = groupEvents[i];
      const nodeIdA = hashNodeKey(eventA.nodeKey);

      for (const window of params.windowBars) {
        for (let j = i + 1; j < groupEvents.length; j++) {
          const eventB = groupEvents[j];
          const deltaBars = eventB.anchorIdx - eventA.anchorIdx;

          if (deltaBars <= 0) continue;
          if (deltaBars > window) break;

          const nodeIdB = hashNodeKey(eventB.nodeKey);
          const edgeId = hashEdge(nodeIdA, nodeIdB, eventA.nodeKey.tf, window);

          if (!fullEdgeMap.has(edgeId)) {
            fullEdgeMap.set(edgeId, {
              fromId: nodeIdA,
              toId: nodeIdB,
              tf: eventA.nodeKey.tf,
              windowBars: window,
              count: 0,
              deltaBarsList: [],
            });
          }
          const edge = fullEdgeMap.get(edgeId)!;
          edge.count++;
          edge.deltaBarsList.push(deltaBars);
        }
      }
    }
  }

  // Compute final edges with lift
  for (const [edgeId, acc] of fullEdgeMap.entries()) {
    if (acc.count < params.minEdgeCount) continue;

    const fromNode = nodeMap.get(acc.fromId);
    const toNode = nodeMap.get(acc.toId);
    if (!fromNode || !toNode) continue;

    // P(B|A) = count(A->B) / count(A)
    const pToGivenFrom = acc.count / fromNode.count;
    
    // P(B) = count(B) / total events
    const pTo = toNode.count / totalEvents;
    
    // lift = P(B|A) / P(B)
    const lift = pTo > 0 ? pToGivenFrom / pTo : 1;

    if (lift < params.liftMin) continue;

    // Calculate delta stats
    const sorted = acc.deltaBarsList.sort((a, b) => a - b);
    const avgDeltaBars = sorted.reduce((a, b) => a + b, 0) / sorted.length;
    const p50Idx = Math.floor(sorted.length * 0.5);
    const p90Idx = Math.floor(sorted.length * 0.9);

    edges.push({
      edgeId,
      fromId: acc.fromId,
      toId: acc.toId,
      tf: acc.tf,
      windowBars: acc.windowBars,
      count: acc.count,
      pToGivenFrom,
      lift,
      avgDeltaBars,
      deltaBarsP50: sorted[p50Idx] || avgDeltaBars,
      deltaBarsP90: sorted[p90Idx] || avgDeltaBars,
    });
  }

  // Save to storage
  console.log(`[GraphBuilder] Saving ${nodes.length} nodes, ${edges.length} edges`);
  await storage.bulkUpsertNodes(nodes);
  await storage.bulkUpsertEdges(edges);

  // Save audit
  const audit: GraphRunAudit = {
    runId,
    builtAt,
    tf: params.timeframes.join(','),
    assets: params.assets,
    rowsUsed: events.length,
    nodesCount: nodes.length,
    edgesCount: edges.length,
    version: '8.6.1',
  };
  await storage.saveRun(audit);

  console.log(`[GraphBuilder] Complete: ${nodes.length} nodes, ${edges.length} edges`);
  return audit;
}

/**
 * Convert pattern records to events for graph building
 */
export function patternsToEvents(
  patterns: Array<{
    type: string;
    direction: string;
    asset: string;
    timeframe: string;
    startIdx: number;
    score?: number;
    confidence?: number;
    regime?: string;
    vol?: string;
  }>
): PatternEvent[] {
  return patterns.map((p, idx) => ({
    eventId: `${p.asset}-${p.timeframe}-${p.startIdx}-${idx}`,
    nodeKey: {
      family: 'PATTERN',
      type: p.type,
      direction: p.direction,
      regime: p.regime,
      vol: p.vol,
      tf: p.timeframe,
    },
    anchorIdx: p.startIdx,
    anchorTs: 0,  // Would need actual timestamp
    asset: p.asset,
    timeframe: p.timeframe,
    score: p.score,
    confidence: p.confidence,
  }));
}
