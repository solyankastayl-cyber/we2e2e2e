/**
 * Phase 8.6 — Graph Storage
 * 
 * MongoDB storage for graph nodes and edges
 */

import { Db, Collection } from 'mongodb';
import { 
  GraphNode, 
  GraphEdge, 
  GraphRunAudit, 
  NodeKey 
} from './graph.types.js';
import crypto from 'crypto';

const NODES_COLLECTION = 'ta_graph_nodes';
const EDGES_COLLECTION = 'ta_graph_edges';
const RUNS_COLLECTION = 'ta_graph_runs';

/**
 * Generate stable hash for NodeKey
 */
export function hashNodeKey(key: NodeKey): string {
  const str = `${key.family}:${key.type}:${key.direction || ''}:${key.regime || ''}:${key.vol || ''}:${key.tf}`;
  return crypto.createHash('md5').update(str).digest('hex').slice(0, 16);
}

/**
 * Generate stable hash for edge
 */
export function hashEdge(fromId: string, toId: string, tf: string, window: number): string {
  const str = `${fromId}:${toId}:${tf}:${window}`;
  return crypto.createHash('md5').update(str).digest('hex').slice(0, 16);
}

export interface GraphStorage {
  // Nodes
  upsertNode(node: GraphNode): Promise<void>;
  getNode(nodeId: string): Promise<GraphNode | null>;
  getNodesByTf(tf: string): Promise<GraphNode[]>;
  getNodesByFamily(family: string, tf: string): Promise<GraphNode[]>;
  
  // Edges
  upsertEdge(edge: GraphEdge): Promise<void>;
  getEdge(edgeId: string): Promise<GraphEdge | null>;
  getOutgoingEdges(fromId: string, tf: string, window?: number): Promise<GraphEdge[]>;
  getIncomingEdges(toId: string, tf: string, window?: number): Promise<GraphEdge[]>;
  getTopEdgesByLift(tf: string, limit?: number): Promise<GraphEdge[]>;
  
  // Runs
  saveRun(run: GraphRunAudit): Promise<void>;
  getLatestRun(tf?: string): Promise<GraphRunAudit | null>;
  getRuns(limit?: number): Promise<GraphRunAudit[]>;
  
  // Bulk operations
  bulkUpsertNodes(nodes: GraphNode[]): Promise<number>;
  bulkUpsertEdges(edges: GraphEdge[]): Promise<number>;
  clearGraph(tf?: string): Promise<void>;
}

export function createGraphStorage(db: Db): GraphStorage {
  const nodesCol: Collection = db.collection(NODES_COLLECTION);
  const edgesCol: Collection = db.collection(EDGES_COLLECTION);
  const runsCol: Collection = db.collection(RUNS_COLLECTION);

  return {
    // Nodes
    async upsertNode(node: GraphNode): Promise<void> {
      await nodesCol.updateOne(
        { _id: node.nodeId },
        { $set: node },
        { upsert: true }
      );
    },

    async getNode(nodeId: string): Promise<GraphNode | null> {
      const doc = await nodesCol.findOne({ _id: nodeId });
      if (!doc) return null;
      return {
        nodeId: doc._id as string,
        key: doc.key,
        count: doc.count,
        firstSeenAt: doc.firstSeenAt,
        lastSeenAt: doc.lastSeenAt,
      };
    },

    async getNodesByTf(tf: string): Promise<GraphNode[]> {
      const docs = await nodesCol.find({ 'key.tf': tf }).toArray();
      return docs.map(d => ({
        nodeId: d._id as string,
        key: d.key,
        count: d.count,
        firstSeenAt: d.firstSeenAt,
        lastSeenAt: d.lastSeenAt,
      }));
    },

    async getNodesByFamily(family: string, tf: string): Promise<GraphNode[]> {
      const docs = await nodesCol.find({ 'key.family': family, 'key.tf': tf }).toArray();
      return docs.map(d => ({
        nodeId: d._id as string,
        key: d.key,
        count: d.count,
        firstSeenAt: d.firstSeenAt,
        lastSeenAt: d.lastSeenAt,
      }));
    },

    // Edges
    async upsertEdge(edge: GraphEdge): Promise<void> {
      await edgesCol.updateOne(
        { _id: edge.edgeId },
        { $set: edge },
        { upsert: true }
      );
    },

    async getEdge(edgeId: string): Promise<GraphEdge | null> {
      const doc = await edgesCol.findOne({ _id: edgeId });
      if (!doc) return null;
      return {
        edgeId: doc._id as string,
        fromId: doc.fromId,
        toId: doc.toId,
        tf: doc.tf,
        windowBars: doc.windowBars,
        count: doc.count,
        pToGivenFrom: doc.pToGivenFrom,
        lift: doc.lift,
        avgDeltaBars: doc.avgDeltaBars,
        deltaBarsP50: doc.deltaBarsP50,
        deltaBarsP90: doc.deltaBarsP90,
        contexts: doc.contexts,
      };
    },

    async getOutgoingEdges(fromId: string, tf: string, window?: number): Promise<GraphEdge[]> {
      const query: any = { fromId, tf };
      if (window) query.windowBars = window;
      
      const docs = await edgesCol
        .find(query)
        .sort({ lift: -1, count: -1 })
        .toArray();
      
      return docs.map(d => ({
        edgeId: d._id as string,
        fromId: d.fromId,
        toId: d.toId,
        tf: d.tf,
        windowBars: d.windowBars,
        count: d.count,
        pToGivenFrom: d.pToGivenFrom,
        lift: d.lift,
        avgDeltaBars: d.avgDeltaBars,
        deltaBarsP50: d.deltaBarsP50,
        deltaBarsP90: d.deltaBarsP90,
        contexts: d.contexts,
      }));
    },

    async getIncomingEdges(toId: string, tf: string, window?: number): Promise<GraphEdge[]> {
      const query: any = { toId, tf };
      if (window) query.windowBars = window;
      
      const docs = await edgesCol
        .find(query)
        .sort({ lift: -1, count: -1 })
        .toArray();
      
      return docs.map(d => ({
        edgeId: d._id as string,
        fromId: d.fromId,
        toId: d.toId,
        tf: d.tf,
        windowBars: d.windowBars,
        count: d.count,
        pToGivenFrom: d.pToGivenFrom,
        lift: d.lift,
        avgDeltaBars: d.avgDeltaBars,
        deltaBarsP50: d.deltaBarsP50,
        deltaBarsP90: d.deltaBarsP90,
        contexts: d.contexts,
      }));
    },

    async getTopEdgesByLift(tf: string, limit = 50): Promise<GraphEdge[]> {
      const docs = await edgesCol
        .find({ tf })
        .sort({ lift: -1 })
        .limit(limit)
        .toArray();
      
      return docs.map(d => ({
        edgeId: d._id as string,
        fromId: d.fromId,
        toId: d.toId,
        tf: d.tf,
        windowBars: d.windowBars,
        count: d.count,
        pToGivenFrom: d.pToGivenFrom,
        lift: d.lift,
        avgDeltaBars: d.avgDeltaBars,
        deltaBarsP50: d.deltaBarsP50,
        deltaBarsP90: d.deltaBarsP90,
        contexts: d.contexts,
      }));
    },

    // Runs
    async saveRun(run: GraphRunAudit): Promise<void> {
      await runsCol.insertOne(run);
    },

    async getLatestRun(tf?: string): Promise<GraphRunAudit | null> {
      const query = tf ? { tf } : {};
      const doc = await runsCol
        .findOne(query, { sort: { builtAt: -1 } });
      if (!doc) return null;
      return {
        runId: doc.runId,
        builtAt: doc.builtAt,
        tf: doc.tf,
        assets: doc.assets,
        rowsUsed: doc.rowsUsed,
        nodesCount: doc.nodesCount,
        edgesCount: doc.edgesCount,
        version: doc.version,
        notes: doc.notes,
      };
    },

    async getRuns(limit = 20): Promise<GraphRunAudit[]> {
      const docs = await runsCol
        .find({})
        .sort({ builtAt: -1 })
        .limit(limit)
        .toArray();
      
      return docs.map(d => ({
        runId: d.runId,
        builtAt: d.builtAt,
        tf: d.tf,
        assets: d.assets,
        rowsUsed: d.rowsUsed,
        nodesCount: d.nodesCount,
        edgesCount: d.edgesCount,
        version: d.version,
        notes: d.notes,
      }));
    },

    // Bulk operations
    async bulkUpsertNodes(nodes: GraphNode[]): Promise<number> {
      if (!nodes.length) return 0;
      
      const ops = nodes.map(n => ({
        updateOne: {
          filter: { _id: n.nodeId },
          update: { $set: n },
          upsert: true,
        },
      }));
      
      const result = await nodesCol.bulkWrite(ops);
      return result.upsertedCount + result.modifiedCount;
    },

    async bulkUpsertEdges(edges: GraphEdge[]): Promise<number> {
      if (!edges.length) return 0;
      
      const ops = edges.map(e => ({
        updateOne: {
          filter: { _id: e.edgeId },
          update: { $set: e },
          upsert: true,
        },
      }));
      
      const result = await edgesCol.bulkWrite(ops);
      return result.upsertedCount + result.modifiedCount;
    },

    async clearGraph(tf?: string): Promise<void> {
      if (tf) {
        await nodesCol.deleteMany({ 'key.tf': tf });
        await edgesCol.deleteMany({ tf });
      } else {
        await nodesCol.deleteMany({});
        await edgesCol.deleteMany({});
      }
    },
  };
}

/**
 * Create indexes for graph collections
 */
export async function createGraphIndexes(db: Db): Promise<void> {
  const nodesCol = db.collection(NODES_COLLECTION);
  const edgesCol = db.collection(EDGES_COLLECTION);

  await nodesCol.createIndex({ 'key.tf': 1, 'key.family': 1 });
  await nodesCol.createIndex({ 'key.type': 1 });

  await edgesCol.createIndex({ fromId: 1, tf: 1, windowBars: 1, count: -1 });
  await edgesCol.createIndex({ toId: 1, tf: 1, windowBars: 1 });
  await edgesCol.createIndex({ tf: 1, lift: -1 });

  console.log('[GraphStorage] Indexes created');
}
