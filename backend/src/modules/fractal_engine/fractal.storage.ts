/**
 * D2 — Fractal Storage
 * 
 * MongoDB storage for fractal signatures, clusters, and discovered patterns
 */

import { Db, Collection } from 'mongodb';
import { 
  FractalSignature, 
  FractalCluster, 
  FractalClusterStats,
  DiscoveredFractalPattern,
} from './fractal.types.js';

const SIGNATURES_COLLECTION = 'ta_fractal_signatures';
const CLUSTERS_COLLECTION = 'ta_fractal_clusters';
const STATS_COLLECTION = 'ta_fractal_cluster_stats';
const DISCOVERED_COLLECTION = 'ta_discovered_fractals';

export class FractalStorage {
  private db: Db;
  private signatures: Collection;
  private clusters: Collection;
  private stats: Collection;
  private discovered: Collection;

  constructor(db: Db) {
    this.db = db;
    this.signatures = db.collection(SIGNATURES_COLLECTION);
    this.clusters = db.collection(CLUSTERS_COLLECTION);
    this.stats = db.collection(STATS_COLLECTION);
    this.discovered = db.collection(DISCOVERED_COLLECTION);
  }

  async ensureIndexes(): Promise<void> {
    // Signatures
    await this.signatures.createIndex({ asset: 1, timeframe: 1, endTs: -1 });
    await this.signatures.createIndex({ id: 1 }, { unique: true });
    
    // Clusters
    await this.clusters.createIndex({ clusterId: 1 }, { unique: true });
    
    // Stats
    await this.stats.createIndex({ clusterId: 1 });
    await this.stats.createIndex({ edgeScore: -1 });
    
    // Discovered
    await this.discovered.createIndex({ patternId: 1 }, { unique: true });
    await this.discovered.createIndex({ status: 1 });
    await this.discovered.createIndex({ edgeScore: -1 });
    
    console.log('[FractalStorage] Indexes ensured');
  }

  // ═══════════════════════════════════════════════════════════════
  // Signatures
  // ═══════════════════════════════════════════════════════════════

  async saveSignature(signature: FractalSignature): Promise<boolean> {
    try {
      await this.signatures.updateOne(
        { id: signature.id },
        { $set: signature },
        { upsert: true }
      );
      return true;
    } catch (e) {
      return false;
    }
  }

  async saveSignatures(signatures: FractalSignature[]): Promise<number> {
    let saved = 0;
    for (const sig of signatures) {
      if (await this.saveSignature(sig)) saved++;
    }
    return saved;
  }

  async getSignatures(
    asset: string,
    timeframe: string,
    limit: number = 500
  ): Promise<FractalSignature[]> {
    const docs = await this.signatures
      .find({ asset, timeframe })
      .sort({ endTs: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(d => {
      const { _id, ...sig } = d as any;
      return sig;
    });
  }

  async getAllSignatures(limit: number = 5000): Promise<FractalSignature[]> {
    const docs = await this.signatures
      .find({})
      .sort({ endTs: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(d => {
      const { _id, ...sig } = d as any;
      return sig;
    });
  }

  async getSignatureById(id: string): Promise<FractalSignature | null> {
    const doc = await this.signatures.findOne({ id });
    if (!doc) return null;
    
    const { _id, ...sig } = doc as any;
    return sig;
  }

  async countSignatures(): Promise<number> {
    return this.signatures.countDocuments();
  }

  // ═══════════════════════════════════════════════════════════════
  // Clusters
  // ═══════════════════════════════════════════════════════════════

  async saveCluster(cluster: FractalCluster): Promise<boolean> {
    try {
      await this.clusters.updateOne(
        { clusterId: cluster.clusterId },
        { $set: cluster },
        { upsert: true }
      );
      return true;
    } catch (e) {
      return false;
    }
  }

  async saveClusters(clusters: FractalCluster[]): Promise<number> {
    let saved = 0;
    for (const cluster of clusters) {
      if (await this.saveCluster(cluster)) saved++;
    }
    return saved;
  }

  async getClusters(limit: number = 100): Promise<FractalCluster[]> {
    const docs = await this.clusters
      .find({})
      .limit(limit)
      .toArray();
    
    return docs.map(d => {
      const { _id, ...cluster } = d as any;
      return cluster;
    });
  }

  async getClusterById(clusterId: string): Promise<FractalCluster | null> {
    const doc = await this.clusters.findOne({ clusterId });
    if (!doc) return null;
    
    const { _id, ...cluster } = doc as any;
    return cluster;
  }

  async countClusters(): Promise<number> {
    return this.clusters.countDocuments();
  }

  async clearClusters(): Promise<number> {
    const result = await this.clusters.deleteMany({});
    return result.deletedCount;
  }

  // ═══════════════════════════════════════════════════════════════
  // Cluster Stats
  // ═══════════════════════════════════════════════════════════════

  async saveClusterStats(stats: FractalClusterStats): Promise<boolean> {
    try {
      await this.stats.updateOne(
        { clusterId: stats.clusterId },
        { $set: stats },
        { upsert: true }
      );
      return true;
    } catch (e) {
      return false;
    }
  }

  async getClusterStats(clusterId: string): Promise<FractalClusterStats | null> {
    const doc = await this.stats.findOne({ clusterId });
    if (!doc) return null;
    
    const { _id, ...stats } = doc as any;
    return stats;
  }

  async getTopClusterStats(limit: number = 20): Promise<FractalClusterStats[]> {
    const docs = await this.stats
      .find({})
      .sort({ edgeScore: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(d => {
      const { _id, ...stats } = d as any;
      return stats;
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // Discovered Patterns
  // ═══════════════════════════════════════════════════════════════

  async saveDiscoveredPattern(pattern: DiscoveredFractalPattern): Promise<boolean> {
    try {
      await this.discovered.updateOne(
        { patternId: pattern.patternId },
        { $set: pattern },
        { upsert: true }
      );
      return true;
    } catch (e) {
      return false;
    }
  }

  async getDiscoveredPatterns(status?: string): Promise<DiscoveredFractalPattern[]> {
    const query = status ? { status } : {};
    const docs = await this.discovered
      .find(query)
      .sort({ edgeScore: -1 })
      .toArray();
    
    return docs.map(d => {
      const { _id, ...pattern } = d as any;
      return pattern;
    });
  }

  async getActiveDiscoveredPatterns(): Promise<DiscoveredFractalPattern[]> {
    return this.getDiscoveredPatterns('ACTIVE');
  }

  async getDiscoveredPatternById(patternId: string): Promise<DiscoveredFractalPattern | null> {
    const doc = await this.discovered.findOne({ patternId });
    if (!doc) return null;
    
    const { _id, ...pattern } = doc as any;
    return pattern;
  }

  async countDiscoveredPatterns(): Promise<number> {
    return this.discovered.countDocuments();
  }

  async countActivePatterns(): Promise<number> {
    return this.discovered.countDocuments({ status: 'ACTIVE' });
  }
}
