/**
 * P2.1 — Shape Clustering Engine
 * 
 * Clusters similar market shapes using DBSCAN-like algorithm.
 * Discovers new patterns not in classical TA.
 */

import { shapeDistance, shapeSimilarity } from './shape.extractor.js';

export interface ClusterConfig {
  minClusterSize: number;   // Minimum samples for valid cluster
  epsilon: number;          // Distance threshold for neighbors
  metric: 'euclidean' | 'cosine';
}

export const DEFAULT_CLUSTER_CONFIG: ClusterConfig = {
  minClusterSize: 50,
  epsilon: 0.3,
  metric: 'euclidean',
};

export interface ShapeSample {
  id: string;
  embedding: number[];
  asset?: string;
  timeframe?: string;
  timestamp?: number;
  outcome?: {
    rMultiple: number;
    entryHit: boolean;
  };
}

export interface Cluster {
  clusterId: number;
  centroid: number[];
  samples: string[];       // Sample IDs
  size: number;
  density: number;
  avgDistance: number;
  
  // Performance metrics (if outcomes available)
  winRate?: number;
  avgR?: number;
  profitFactor?: number;
}

export interface ClusterResult {
  clusters: Cluster[];
  noise: string[];         // Samples that didn't fit any cluster
  totalSamples: number;
  totalClusters: number;
}

/**
 * Simple DBSCAN-like clustering
 */
export class ShapeClusterEngine {
  private config: ClusterConfig;
  
  constructor(config: ClusterConfig = DEFAULT_CLUSTER_CONFIG) {
    this.config = config;
  }
  
  /**
   * Cluster shapes using density-based algorithm
   */
  cluster(samples: ShapeSample[]): ClusterResult {
    const { minClusterSize, epsilon, metric } = this.config;
    
    if (samples.length < minClusterSize) {
      return {
        clusters: [],
        noise: samples.map(s => s.id),
        totalSamples: samples.length,
        totalClusters: 0,
      };
    }
    
    const distanceFn = metric === 'euclidean' 
      ? shapeDistance 
      : (a: number[], b: number[]) => 1 - shapeSimilarity(a, b);
    
    // Compute distance matrix (for smaller datasets)
    // For large datasets, use approximate methods
    const visited = new Set<number>();
    const clusterLabels = new Array(samples.length).fill(-1);
    let currentCluster = 0;
    
    for (let i = 0; i < samples.length; i++) {
      if (visited.has(i)) continue;
      
      // Find neighbors
      const neighbors = this.findNeighbors(samples, i, epsilon, distanceFn);
      
      if (neighbors.length < minClusterSize) {
        // Mark as noise
        continue;
      }
      
      // Start new cluster
      visited.add(i);
      clusterLabels[i] = currentCluster;
      
      // Expand cluster
      const seedSet = [...neighbors];
      let j = 0;
      
      while (j < seedSet.length) {
        const idx = seedSet[j];
        
        if (!visited.has(idx)) {
          visited.add(idx);
          const newNeighbors = this.findNeighbors(samples, idx, epsilon, distanceFn);
          
          if (newNeighbors.length >= minClusterSize) {
            seedSet.push(...newNeighbors.filter(n => !seedSet.includes(n)));
          }
        }
        
        if (clusterLabels[idx] === -1) {
          clusterLabels[idx] = currentCluster;
        }
        
        j++;
      }
      
      currentCluster++;
    }
    
    // Build cluster objects
    const clusters = this.buildClusters(samples, clusterLabels, currentCluster, distanceFn);
    const noise = samples
      .filter((_, i) => clusterLabels[i] === -1)
      .map(s => s.id);
    
    return {
      clusters,
      noise,
      totalSamples: samples.length,
      totalClusters: clusters.length,
    };
  }
  
  /**
   * Find neighbors within epsilon distance
   */
  private findNeighbors(
    samples: ShapeSample[],
    idx: number,
    epsilon: number,
    distanceFn: (a: number[], b: number[]) => number
  ): number[] {
    const neighbors: number[] = [];
    const sample = samples[idx];
    
    for (let i = 0; i < samples.length; i++) {
      if (i === idx) continue;
      
      const dist = distanceFn(sample.embedding, samples[i].embedding);
      if (dist <= epsilon) {
        neighbors.push(i);
      }
    }
    
    return neighbors;
  }
  
  /**
   * Build cluster objects from labels
   */
  private buildClusters(
    samples: ShapeSample[],
    labels: number[],
    numClusters: number,
    distanceFn: (a: number[], b: number[]) => number
  ): Cluster[] {
    const clusters: Cluster[] = [];
    
    for (let c = 0; c < numClusters; c++) {
      const clusterSamples = samples.filter((_, i) => labels[i] === c);
      
      if (clusterSamples.length === 0) continue;
      
      // Compute centroid
      const dim = clusterSamples[0].embedding.length;
      const centroid = new Array(dim).fill(0);
      
      for (const sample of clusterSamples) {
        for (let d = 0; d < dim; d++) {
          centroid[d] += sample.embedding[d];
        }
      }
      
      for (let d = 0; d < dim; d++) {
        centroid[d] /= clusterSamples.length;
      }
      
      // Compute average distance to centroid
      let totalDist = 0;
      for (const sample of clusterSamples) {
        totalDist += distanceFn(sample.embedding, centroid);
      }
      const avgDistance = totalDist / clusterSamples.length;
      
      // Compute performance metrics if outcomes available
      const withOutcomes = clusterSamples.filter(s => s.outcome);
      let winRate: number | undefined;
      let avgR: number | undefined;
      let profitFactor: number | undefined;
      
      if (withOutcomes.length > 0) {
        const wins = withOutcomes.filter(s => s.outcome!.rMultiple > 0);
        winRate = wins.length / withOutcomes.length;
        avgR = withOutcomes.reduce((sum, s) => sum + s.outcome!.rMultiple, 0) / withOutcomes.length;
        
        const grossProfit = wins.reduce((sum, s) => sum + s.outcome!.rMultiple, 0);
        const grossLoss = Math.abs(
          withOutcomes.filter(s => s.outcome!.rMultiple < 0)
            .reduce((sum, s) => sum + s.outcome!.rMultiple, 0)
        );
        profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? 999 : 0;
      }
      
      clusters.push({
        clusterId: c,
        centroid,
        samples: clusterSamples.map(s => s.id),
        size: clusterSamples.length,
        density: 1 / (avgDistance + 0.001),
        avgDistance,
        winRate,
        avgR,
        profitFactor,
      });
    }
    
    return clusters.sort((a, b) => b.size - a.size);
  }
  
  /**
   * Assign a new sample to closest cluster
   */
  assignToCluster(
    sample: ShapeSample,
    clusters: Cluster[]
  ): { clusterId: number; distance: number } | null {
    if (clusters.length === 0) return null;
    
    const distanceFn = this.config.metric === 'euclidean' 
      ? shapeDistance 
      : (a: number[], b: number[]) => 1 - shapeSimilarity(a, b);
    
    let bestCluster = -1;
    let bestDistance = Infinity;
    
    for (const cluster of clusters) {
      const dist = distanceFn(sample.embedding, cluster.centroid);
      if (dist < bestDistance) {
        bestDistance = dist;
        bestCluster = cluster.clusterId;
      }
    }
    
    if (bestDistance <= this.config.epsilon * 2) {
      return { clusterId: bestCluster, distance: bestDistance };
    }
    
    return null;
  }
}

export function createShapeClusterEngine(config?: Partial<ClusterConfig>): ShapeClusterEngine {
  return new ShapeClusterEngine({
    ...DEFAULT_CLUSTER_CONFIG,
    ...config,
  });
}
