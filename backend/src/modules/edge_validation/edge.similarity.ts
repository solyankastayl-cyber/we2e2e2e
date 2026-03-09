/**
 * Phase 9.5 — Edge Validation: Similarity Analyzer
 */

import {
  SimilarityAnalysis,
  EdgeValidationConfig,
  DEFAULT_EDGE_CONFIG
} from './edge.types.js';

/**
 * Calculate feature overlap between two strategies
 */
export function calculateFeatureOverlap(
  features1: string[],
  features2: string[]
): number {
  const set1 = new Set(features1);
  const set2 = new Set(features2);
  
  const intersection = features1.filter(f => set2.has(f)).length;
  const union = new Set([...features1, ...features2]).size;
  
  return union > 0 ? intersection / union : 0;
}

/**
 * Analyze similarity with other strategies
 */
export function analyzeSimilarity(
  strategyId: string,
  strategyFeatures: string[],
  allStrategies: { id: string; features: string[] }[],
  config: EdgeValidationConfig = DEFAULT_EDGE_CONFIG
): SimilarityAnalysis {
  const similarStrategies: SimilarityAnalysis['similarStrategies'] = [];
  
  for (const other of allStrategies) {
    if (other.id === strategyId) continue;
    
    const similarity = calculateFeatureOverlap(strategyFeatures, other.features);
    
    if (similarity >= 0.3) {  // Only track if somewhat similar
      // Estimate co-occurrence (simplified - assume proportional to similarity)
      const cooccurrence = similarity * 0.8 + Math.random() * 0.2;
      
      similarStrategies.push({
        id: other.id,
        similarity,
        cooccurrence
      });
    }
  }
  
  // Sort by similarity
  similarStrategies.sort((a, b) => b.similarity - a.similarity);
  
  // Calculate penalty
  const maxSimilarity = similarStrategies.length > 0 ? similarStrategies[0].similarity : 0;
  
  let similarityPenalty = 0;
  
  if (maxSimilarity >= config.similarityThreshold) {
    // Strong penalty for very similar strategies
    similarityPenalty = Math.min(
      config.maxSimilarityPenalty,
      (maxSimilarity - config.similarityThreshold) * 2 + 0.1
    );
  } else if (maxSimilarity >= 0.5) {
    // Mild penalty for moderately similar
    similarityPenalty = (maxSimilarity - 0.5) * 0.5;
  }
  
  // Check if redundant (should be filtered)
  const isRedundant = maxSimilarity >= 0.9;
  
  return {
    strategyId,
    similarStrategies: similarStrategies.slice(0, 5),  // Top 5
    maxSimilarity,
    similarityPenalty,
    isRedundant
  };
}

/**
 * Filter redundant strategies from a list
 */
export function filterRedundantStrategies(
  strategies: { id: string; features: string[]; confidence: number }[]
): { id: string; features: string[]; confidence: number }[] {
  const filtered: typeof strategies = [];
  
  // Sort by confidence (keep higher confidence strategies)
  const sorted = [...strategies].sort((a, b) => b.confidence - a.confidence);
  
  for (const strategy of sorted) {
    // Check if too similar to any already selected
    let isSimilar = false;
    
    for (const selected of filtered) {
      const overlap = calculateFeatureOverlap(strategy.features, selected.features);
      if (overlap >= 0.85) {
        isSimilar = true;
        break;
      }
    }
    
    if (!isSimilar) {
      filtered.push(strategy);
    }
  }
  
  return filtered;
}

/**
 * Calculate cluster similarity for a group of strategies
 */
export function analyzeClusterSimilarity(
  strategies: { id: string; features: string[] }[]
): {
  avgSimilarity: number;
  clusters: { strategies: string[]; coreFeatures: string[] }[];
} {
  if (strategies.length < 2) {
    return { avgSimilarity: 0, clusters: [] };
  }
  
  // Calculate pairwise similarities
  let totalSimilarity = 0;
  let pairs = 0;
  
  for (let i = 0; i < strategies.length; i++) {
    for (let j = i + 1; j < strategies.length; j++) {
      totalSimilarity += calculateFeatureOverlap(
        strategies[i].features,
        strategies[j].features
      );
      pairs++;
    }
  }
  
  const avgSimilarity = pairs > 0 ? totalSimilarity / pairs : 0;
  
  // Simple clustering (group highly similar strategies)
  const clusters: { strategies: string[]; coreFeatures: string[] }[] = [];
  const used = new Set<string>();
  
  for (const strategy of strategies) {
    if (used.has(strategy.id)) continue;
    
    const cluster = [strategy.id];
    used.add(strategy.id);
    
    for (const other of strategies) {
      if (used.has(other.id)) continue;
      
      const sim = calculateFeatureOverlap(strategy.features, other.features);
      if (sim >= 0.6) {
        cluster.push(other.id);
        used.add(other.id);
      }
    }
    
    if (cluster.length > 1) {
      // Find core features
      const featureCounts: Record<string, number> = {};
      for (const id of cluster) {
        const s = strategies.find(st => st.id === id);
        if (s) {
          for (const f of s.features) {
            featureCounts[f] = (featureCounts[f] || 0) + 1;
          }
        }
      }
      
      const coreFeatures = Object.entries(featureCounts)
        .filter(([_, count]) => count >= cluster.length * 0.8)
        .map(([feature]) => feature);
      
      clusters.push({ strategies: cluster, coreFeatures });
    }
  }
  
  return { avgSimilarity, clusters };
}
