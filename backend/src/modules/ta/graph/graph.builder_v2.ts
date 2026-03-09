/**
 * Phase 8.6 — Graph Builder V2
 * 
 * Enhanced builder that pulls from:
 * - ta_patterns
 * - ta_scenarios  
 * - ta_outcomes_v3
 * 
 * Builds complete transition graph
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

const PATTERNS_COLLECTION = 'ta_patterns';
const SCENARIOS_COLLECTION = 'ta_scenarios';
const OUTCOMES_COLLECTION = 'ta_outcomes_v3';

/**
 * Fetch pattern events from ta_patterns
 */
async function fetchPatternEvents(
  db: Db,
  params: GraphBuildParams
): Promise<PatternEvent[]> {
  const collection = db.collection(PATTERNS_COLLECTION);
  
  const query: Record<string, any> = {};
  if (params.assets.length) {
    query.asset = { $in: params.assets };
  }
  if (params.timeframes.length) {
    query.timeframe = { $in: params.timeframes.map(tf => tf.toLowerCase()) };
  }

  const patterns = await collection
    .find(query)
    .sort({ anchorTs: 1, startIdx: 1 })
    .toArray();

  return patterns.map((p, idx) => ({
    eventId: p._id?.toString() || `pattern-${idx}`,
    nodeKey: {
      family: 'PATTERN',
      type: p.type || p.patternType || 'UNKNOWN',
      direction: p.direction || 'BOTH',
      regime: p.regime,
      vol: p.volRegime,
      tf: (p.timeframe || '1d').toLowerCase(),
    },
    anchorIdx: p.startIdx || p.anchorIdx || 0,
    anchorTs: p.startTs || p.anchorTs || 0,
    asset: p.asset,
    timeframe: (p.timeframe || '1d').toLowerCase(),
    score: p.score,
    confidence: p.confidence,
  }));
}

/**
 * Fetch structure events (BOS, CHOCH, etc.)
 */
async function fetchStructureEvents(
  db: Db,
  params: GraphBuildParams
): Promise<PatternEvent[]> {
  // Structure events are often stored in ta_patterns with specific types
  const collection = db.collection(PATTERNS_COLLECTION);
  
  const structureTypes = [
    'BOS_BULL', 'BOS_BEAR', 
    'CHOCH_BULL', 'CHOCH_BEAR',
    'TREND_UP', 'TREND_DOWN', 'RANGE_BOX'
  ];

  const query: Record<string, any> = {
    type: { $in: structureTypes }
  };
  if (params.assets.length) {
    query.asset = { $in: params.assets };
  }

  const structures = await collection
    .find(query)
    .sort({ anchorTs: 1 })
    .toArray();

  return structures.map((s, idx) => ({
    eventId: s._id?.toString() || `struct-${idx}`,
    nodeKey: {
      family: 'STRUCT',
      type: s.type,
      direction: s.direction || 'BOTH',
      regime: s.regime,
      tf: (s.timeframe || '1d').toLowerCase(),
    },
    anchorIdx: s.startIdx || s.anchorIdx || 0,
    anchorTs: s.startTs || s.anchorTs || 0,
    asset: s.asset,
    timeframe: (s.timeframe || '1d').toLowerCase(),
    score: s.score,
  }));
}

/**
 * Enhanced graph builder with full data integration
 */
export async function buildGraphV2(
  db: Db,
  params: GraphBuildParams = DEFAULT_GRAPH_PARAMS
): Promise<GraphRunAudit> {
  const storage = createGraphStorage(db);
  const runId = uuidv4();
  const builtAt = new Date();

  console.log(`[GraphBuilder] Starting V2 build ${runId}`);
  console.log(`[GraphBuilder] Params: assets=${params.assets.join(',')}, tfs=${params.timeframes.join(',')}`);

  // Fetch all events
  const patternEvents = await fetchPatternEvents(db, params);
  console.log(`[GraphBuilder] Loaded ${patternEvents.length} pattern events`);

  const structureEvents = await fetchStructureEvents(db, params);
  console.log(`[GraphBuilder] Loaded ${structureEvents.length} structure events`);

  // Combine all events
  const allEvents = [...patternEvents, ...structureEvents];
  
  if (!allEvents.length) {
    console.log('[GraphBuilder] No events found, creating empty graph');
    const audit: GraphRunAudit = {
      runId,
      builtAt,
      tf: params.timeframes.join(','),
      assets: params.assets,
      rowsUsed: 0,
      nodesCount: 0,
      edgesCount: 0,
      version: '8.6.2',
      notes: 'No events found',
    };
    await storage.saveRun(audit);
    return audit;
  }

  // Group by asset+tf
  const eventsByKey = new Map<string, PatternEvent[]>();
  for (const e of allEvents) {
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
  const edgeMap = new Map<string, {
    fromId: string;
    toId: string;
    tf: string;
    windowBars: number;
    count: number;
    deltaBarsList: number[];
  }>();
  
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
          if (deltaBars > window) break;

          const nodeIdB = hashNodeKey(eventB.nodeKey);
          
          // Ensure target node exists
          if (!nodeMap.has(nodeIdB)) {
            nodeMap.set(nodeIdB, {
              nodeId: nodeIdB,
              key: eventB.nodeKey,
              count: 0,
              firstSeenAt: builtAt,
              lastSeenAt: builtAt,
            });
          }
          
          const edgeId = hashEdge(nodeIdA, nodeIdB, eventA.nodeKey.tf, window);

          if (!edgeMap.has(edgeId)) {
            edgeMap.set(edgeId, {
              fromId: nodeIdA,
              toId: nodeIdB,
              tf: eventA.nodeKey.tf,
              windowBars: window,
              count: 0,
              deltaBarsList: [],
            });
          }
          const edge = edgeMap.get(edgeId)!;
          edge.count++;
          edge.deltaBarsList.push(deltaBars);
        }
      }
    }
  }

  // Compute final edges with lift
  const nodes = Array.from(nodeMap.values());
  const edges: GraphEdge[] = [];

  for (const [edgeId, acc] of edgeMap.entries()) {
    if (acc.count < params.minEdgeCount) continue;

    const fromNode = nodeMap.get(acc.fromId);
    const toNode = nodeMap.get(acc.toId);
    if (!fromNode || !toNode) continue;

    // P(B|A) = count(A->B) / count(A)
    const pToGivenFrom = fromNode.count > 0 ? acc.count / fromNode.count : 0;
    
    // P(B) = count(B) / total events
    const pTo = totalEvents > 0 ? toNode.count / totalEvents : 0;
    
    // lift = P(B|A) / P(B)
    const lift = pTo > 0 ? pToGivenFrom / pTo : 1;

    if (lift < params.liftMin) continue;

    // Calculate delta stats
    const sorted = acc.deltaBarsList.sort((a, b) => a - b);
    const avgDeltaBars = sorted.length > 0 
      ? sorted.reduce((a, b) => a + b, 0) / sorted.length 
      : 0;
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
  
  // Clear existing graph for these timeframes
  for (const tf of params.timeframes) {
    await storage.clearGraph(tf.toLowerCase());
  }
  
  await storage.bulkUpsertNodes(nodes);
  await storage.bulkUpsertEdges(edges);

  // Save audit
  const audit: GraphRunAudit = {
    runId,
    builtAt,
    tf: params.timeframes.join(','),
    assets: params.assets,
    rowsUsed: allEvents.length,
    nodesCount: nodes.length,
    edgesCount: edges.length,
    version: '8.6.2',
  };
  await storage.saveRun(audit);

  console.log(`[GraphBuilder] Complete: ${nodes.length} nodes, ${edges.length} edges`);
  return audit;
}

/**
 * Incremental graph update (add new events without full rebuild)
 */
export async function updateGraphIncremental(
  db: Db,
  newEvents: PatternEvent[],
  params: GraphBuildParams = DEFAULT_GRAPH_PARAMS
): Promise<{ nodesUpdated: number; edgesUpdated: number }> {
  const storage = createGraphStorage(db);
  
  let nodesUpdated = 0;
  let edgesUpdated = 0;

  for (const event of newEvents) {
    const nodeId = hashNodeKey(event.nodeKey);
    
    // Update or create node
    const existingNode = await storage.getNode(nodeId);
    if (existingNode) {
      existingNode.count++;
      existingNode.lastSeenAt = new Date();
      await storage.upsertNode(existingNode);
    } else {
      await storage.upsertNode({
        nodeId,
        key: event.nodeKey,
        count: 1,
        firstSeenAt: new Date(),
        lastSeenAt: new Date(),
      });
    }
    nodesUpdated++;
  }

  // Note: Full edge recalculation would require more context
  // For now, this just updates nodes

  return { nodesUpdated, edgesUpdated };
}

/**
 * Get graph statistics
 */
export async function getGraphStats(db: Db): Promise<{
  nodes: { total: number; byFamily: Record<string, number> };
  edges: { total: number; avgLift: number; maxLift: number };
  lastBuild: GraphRunAudit | null;
}> {
  const storage = createGraphStorage(db);
  
  const nodesCol = db.collection('ta_graph_nodes');
  const edgesCol = db.collection('ta_graph_edges');

  const nodesTotal = await nodesCol.countDocuments();
  const edgesTotal = await edgesCol.countDocuments();

  // Nodes by family
  const byFamilyPipeline = [
    { $group: { _id: '$key.family', count: { $sum: 1 } } },
  ];
  const byFamilyResults = await nodesCol.aggregate(byFamilyPipeline).toArray();
  const byFamily: Record<string, number> = {};
  for (const r of byFamilyResults) {
    byFamily[r._id] = r.count;
  }

  // Edge lift stats
  const liftPipeline = [
    { $group: { 
      _id: null, 
      avgLift: { $avg: '$lift' },
      maxLift: { $max: '$lift' },
    } },
  ];
  const liftResults = await edgesCol.aggregate(liftPipeline).toArray();
  const liftStats = liftResults[0] || { avgLift: 0, maxLift: 0 };

  const lastBuild = await storage.getLatestRun();

  return {
    nodes: { total: nodesTotal, byFamily },
    edges: { total: edgesTotal, avgLift: liftStats.avgLift, maxLift: liftStats.maxLift },
    lastBuild,
  };
}
