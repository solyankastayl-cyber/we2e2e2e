/**
 * D2.2 — Fractal Clustering & Discovery
 * 
 * Groups similar signatures and discovers patterns with edge
 */

import { 
  FractalSignature, 
  FractalCluster, 
  FractalClusterStats,
  DiscoveredFractalPattern,
  FractalConfig,
  DEFAULT_FRACTAL_CONFIG,
} from './fractal.types.js';
import { cosineSimilarity } from './fractal.signature.js';
import { v4 as uuidv4 } from 'uuid';

/**
 * Simple K-means clustering for fractal signatures
 */
export function clusterSignatures(
  signatures: FractalSignature[],
  config: FractalConfig = DEFAULT_FRACTAL_CONFIG
): FractalCluster[] {
  if (signatures.length < config.minClusterSize) {
    return [];
  }
  
  const k = Math.min(config.maxClusters, Math.floor(signatures.length / config.minClusterSize));
  if (k < 1) return [];
  
  // Initialize centroids randomly
  const shuffled = [...signatures].sort(() => Math.random() - 0.5);
  let centroids: number[][] = shuffled.slice(0, k).map(s => [...s.vector]);
  
  // K-means iterations
  const maxIterations = 50;
  let assignments: number[] = new Array(signatures.length).fill(-1);
  
  for (let iter = 0; iter < maxIterations; iter++) {
    const newAssignments: number[] = [];
    
    // Assign each signature to nearest centroid
    for (const sig of signatures) {
      let bestCluster = 0;
      let bestSimilarity = -1;
      
      for (let c = 0; c < centroids.length; c++) {
        const sim = cosineSimilarity(sig.vector, centroids[c]);
        if (sim > bestSimilarity) {
          bestSimilarity = sim;
          bestCluster = c;
        }
      }
      
      newAssignments.push(bestCluster);
    }
    
    // Check convergence
    const changed = newAssignments.some((a, i) => a !== assignments[i]);
    assignments = newAssignments;
    
    if (!changed) break;
    
    // Update centroids
    const newCentroids: number[][] = centroids.map(() => 
      new Array(config.signatureLength).fill(0)
    );
    const counts: number[] = new Array(k).fill(0);
    
    for (let i = 0; i < signatures.length; i++) {
      const c = assignments[i];
      counts[c]++;
      for (let j = 0; j < config.signatureLength; j++) {
        newCentroids[c][j] += signatures[i].vector[j];
      }
    }
    
    // Normalize centroids
    for (let c = 0; c < k; c++) {
      if (counts[c] > 0) {
        for (let j = 0; j < config.signatureLength; j++) {
          newCentroids[c][j] /= counts[c];
        }
      }
    }
    
    centroids = newCentroids;
  }
  
  // Build cluster objects
  const clusters: FractalCluster[] = [];
  
  for (let c = 0; c < k; c++) {
    const memberIds = signatures
      .filter((_, i) => assignments[i] === c)
      .map(s => s.id);
    
    if (memberIds.length >= config.minClusterSize) {
      const members = signatures.filter((_, i) => assignments[i] === c);
      
      clusters.push({
        clusterId: `cluster_${uuidv4().slice(0, 8)}`,
        size: memberIds.length,
        centroid: centroids[c],
        memberIds,
        avgVolatility: members.reduce((s, m) => s + m.volatility, 0) / members.length,
        avgTrendBias: members.reduce((s, m) => s + m.trendBias, 0) / members.length,
        avgCompression: members.reduce((s, m) => s + m.compression, 0) / members.length,
        createdAt: new Date(),
        updatedAt: new Date(),
      });
    }
  }
  
  return clusters;
}

/**
 * Evaluate cluster performance (mock - needs backtest data)
 */
export function evaluateCluster(
  cluster: FractalCluster,
  outcomes: Array<{ signatureId: string; win: boolean; rMultiple: number }>
): FractalClusterStats {
  const memberOutcomes = outcomes.filter(o => 
    cluster.memberIds.includes(o.signatureId)
  );
  
  if (memberOutcomes.length === 0) {
    return {
      clusterId: cluster.clusterId,
      sampleSize: 0,
      winRate: 0.5,
      avgR: 0,
      profitFactor: 1,
      stability: 0,
      recentPerformance: 0.5,
      edgeScore: 0,
      calculatedAt: new Date(),
    };
  }
  
  const wins = memberOutcomes.filter(o => o.win).length;
  const winRate = wins / memberOutcomes.length;
  
  const avgR = memberOutcomes.reduce((s, o) => s + o.rMultiple, 0) / memberOutcomes.length;
  
  const sumWins = memberOutcomes.filter(o => o.rMultiple > 0).reduce((s, o) => s + o.rMultiple, 0);
  const sumLosses = Math.abs(memberOutcomes.filter(o => o.rMultiple < 0).reduce((s, o) => s + o.rMultiple, 0));
  const profitFactor = sumLosses > 0 ? sumWins / sumLosses : sumWins > 0 ? 2 : 1;
  
  // Stability: consistency of results
  const stability = winRate > 0.5 ? (winRate - 0.5) * 2 : 0;
  
  // Edge score
  const edgeScore = (winRate - 0.5) * 2 * Math.min(1, memberOutcomes.length / 100);
  
  return {
    clusterId: cluster.clusterId,
    sampleSize: memberOutcomes.length,
    winRate,
    avgR,
    profitFactor,
    stability,
    recentPerformance: winRate,
    edgeScore,
    calculatedAt: new Date(),
  };
}

/**
 * Discover patterns from clusters meeting criteria
 */
export function discoverPatterns(
  clusters: FractalCluster[],
  stats: FractalClusterStats[],
  config: FractalConfig = DEFAULT_FRACTAL_CONFIG
): DiscoveredFractalPattern[] {
  const discovered: DiscoveredFractalPattern[] = [];
  let patternNum = 1;
  
  for (const cluster of clusters) {
    const clusterStats = stats.find(s => s.clusterId === cluster.clusterId);
    if (!clusterStats) continue;
    
    // Check discovery criteria
    const meetsMinSample = clusterStats.sampleSize >= config.minSampleSize;
    const meetsWinRate = clusterStats.winRate >= config.minWinRate;
    const meetsPF = clusterStats.profitFactor >= config.minProfitFactor;
    const meetsEdge = clusterStats.edgeScore >= config.minEdgeScore;
    
    let status: 'ACTIVE' | 'WATCHLIST' | 'REJECTED' = 'REJECTED';
    
    if (meetsMinSample && meetsWinRate && meetsPF && meetsEdge) {
      status = 'ACTIVE';
    } else if (meetsWinRate && meetsPF) {
      status = 'WATCHLIST';
    }
    
    if (status !== 'REJECTED') {
      // Determine direction from trend bias
      const direction: 'BULL' | 'BEAR' | 'NEUTRAL' = 
        cluster.avgTrendBias > 0.2 ? 'BULL' :
        cluster.avgTrendBias < -0.2 ? 'BEAR' : 'NEUTRAL';
      
      discovered.push({
        patternId: `FRACTAL_${String(patternNum++).padStart(3, '0')}`,
        clusterId: cluster.clusterId,
        sampleSize: clusterStats.sampleSize,
        winRate: clusterStats.winRate,
        avgR: clusterStats.avgR,
        profitFactor: clusterStats.profitFactor,
        edgeScore: clusterStats.edgeScore,
        centroid: cluster.centroid,
        direction,
        status,
        discoveredAt: new Date(),
        lastValidatedAt: new Date(),
      });
    }
  }
  
  return discovered;
}
