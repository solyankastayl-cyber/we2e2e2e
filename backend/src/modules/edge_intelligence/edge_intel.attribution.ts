/**
 * Phase 7 — Edge Attribution
 * 
 * Determines which dimension combinations create edge
 */

import { v4 as uuidv4 } from 'uuid';
import {
  EdgeRecord,
  EdgeAttribution,
  EdgeDimension,
  EdgeIntelligenceConfig,
  DEFAULT_EDGE_CONFIG
} from './edge_intel.types.js';
import { groupByDimensions, extractDimensionValue } from './edge_intel.extractor.js';
import { calcProfitFactor, calcWinRate, calcAvgR } from './edge_intel.aggregator.js';

// ═══════════════════════════════════════════════════════════════
// ATTRIBUTION ANALYSIS
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate individual dimension contributions
 */
export function calculateIndividualContributions(
  records: EdgeRecord[],
  dimensions: EdgeDimension[]
): Map<string, number> {
  const contributions = new Map<string, number>();
  
  for (const dimension of dimensions) {
    const groups = new Map<string, EdgeRecord[]>();
    
    for (const record of records) {
      const key = extractDimensionValue(record, dimension);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(record);
    }
    
    for (const [key, groupRecords] of groups) {
      if (groupRecords.length >= 10) {
        const pf = calcProfitFactor(groupRecords);
        contributions.set(`${dimension}:${key}`, pf);
      }
    }
  }
  
  return contributions;
}

/**
 * Calculate combined dimension effect
 */
export function calculateCombinedEffect(
  records: EdgeRecord[],
  dimensions: EdgeDimension[],
  values: string[]
): { pf: number; sampleSize: number } | null {
  // Filter records matching all dimension values
  const filtered = records.filter(record => {
    for (let i = 0; i < dimensions.length; i++) {
      if (extractDimensionValue(record, dimensions[i]) !== values[i]) {
        return false;
      }
    }
    return true;
  });
  
  if (filtered.length < 10) return null;
  
  return {
    pf: calcProfitFactor(filtered),
    sampleSize: filtered.length
  };
}

/**
 * Calculate synergy between dimensions
 */
export function calculateSynergy(
  combinedPF: number,
  individualPFs: number[]
): number {
  if (individualPFs.length === 0) return 1;
  
  // Expected combined PF if independent
  const expectedPF = individualPFs.reduce((product, pf) => {
    // Normalize around 1
    const normalized = pf > 1 ? 1 + (pf - 1) * 0.5 : 1 - (1 - pf) * 0.5;
    return product * normalized;
  }, 1);
  
  // Synergy = actual / expected
  if (expectedPF === 0) return combinedPF > 1 ? 2 : 0.5;
  return combinedPF / expectedPF;
}

// ═══════════════════════════════════════════════════════════════
// MAIN ATTRIBUTION
// ═══════════════════════════════════════════════════════════════

/**
 * Find best dimension combinations
 */
export function findBestCombinations(
  records: EdgeRecord[],
  config: EdgeIntelligenceConfig = DEFAULT_EDGE_CONFIG
): EdgeAttribution[] {
  const attributions: EdgeAttribution[] = [];
  const dimensions: EdgeDimension[] = ['PATTERN', 'STATE', 'LIQUIDITY', 'SCENARIO'];
  
  // Calculate individual contributions
  const individualContribs = calculateIndividualContributions(records, dimensions);
  
  // Try 2-dimension combinations
  for (let i = 0; i < dimensions.length; i++) {
    for (let j = i + 1; j < dimensions.length; j++) {
      const dim1 = dimensions[i];
      const dim2 = dimensions[j];
      
      const groups = groupByDimensions(records, [dim1, dim2]);
      
      for (const [key, groupRecords] of groups) {
        if (groupRecords.length < config.minSampleSize) continue;
        
        const [val1, val2] = key.split('|');
        const combinedPF = calcProfitFactor(groupRecords);
        
        // Get individual PFs
        const indiv1 = individualContribs.get(`${dim1}:${val1}`) || 1;
        const indiv2 = individualContribs.get(`${dim2}:${val2}`) || 1;
        
        const synergy = calculateSynergy(combinedPF, [indiv1, indiv2]);
        
        // Only include if there's meaningful edge
        if (combinedPF > 1.2 || combinedPF < 0.8) {
          const totalContrib = Math.abs(indiv1 - 1) + Math.abs(indiv2 - 1);
          
          attributions.push({
            attributionId: `ATTR_${uuidv4().slice(0, 8)}`,
            dimensions: [
              { dimension: dim1, value: val1 },
              { dimension: dim2, value: val2 }
            ],
            individualEdges: [
              { 
                dimension: dim1, 
                value: val1, 
                pfAlone: indiv1,
                contributionPct: totalContrib > 0 ? Math.abs(indiv1 - 1) / totalContrib * 100 : 50
              },
              { 
                dimension: dim2, 
                value: val2, 
                pfAlone: indiv2,
                contributionPct: totalContrib > 0 ? Math.abs(indiv2 - 1) / totalContrib * 100 : 50
              }
            ],
            combinedPF,
            synergy,
            sampleSize: groupRecords.length,
            confidence: Math.min(1, groupRecords.length / (config.minSampleSize * 2)),
            calculatedAt: new Date()
          });
        }
      }
    }
  }
  
  // Try 3-dimension combinations (if depth allows)
  if (config.attributionDepth >= 3) {
    for (let i = 0; i < dimensions.length; i++) {
      for (let j = i + 1; j < dimensions.length; j++) {
        for (let k = j + 1; k < dimensions.length; k++) {
          const dims = [dimensions[i], dimensions[j], dimensions[k]];
          const groups = groupByDimensions(records, dims);
          
          for (const [key, groupRecords] of groups) {
            if (groupRecords.length < config.minSampleSize * 1.5) continue;
            
            const vals = key.split('|');
            const combinedPF = calcProfitFactor(groupRecords);
            
            // Get individual PFs
            const indivPFs = dims.map((d, idx) => 
              individualContribs.get(`${d}:${vals[idx]}`) || 1
            );
            
            const synergy = calculateSynergy(combinedPF, indivPFs);
            
            // Only include strong edges with 3 dimensions
            if (combinedPF > 1.4 || combinedPF < 0.7) {
              const totalContrib = indivPFs.reduce((sum, pf) => sum + Math.abs(pf - 1), 0);
              
              attributions.push({
                attributionId: `ATTR_${uuidv4().slice(0, 8)}`,
                dimensions: dims.map((d, idx) => ({ dimension: d, value: vals[idx] })),
                individualEdges: dims.map((d, idx) => ({
                  dimension: d,
                  value: vals[idx],
                  pfAlone: indivPFs[idx],
                  contributionPct: totalContrib > 0 ? Math.abs(indivPFs[idx] - 1) / totalContrib * 100 : 33
                })),
                combinedPF,
                synergy,
                sampleSize: groupRecords.length,
                confidence: Math.min(1, groupRecords.length / (config.minSampleSize * 3)),
                calculatedAt: new Date()
              });
            }
          }
        }
      }
    }
  }
  
  // Sort by combined PF (edge strength)
  return attributions.sort((a, b) => {
    // Prefer high synergy + high PF
    const scoreA = a.combinedPF * a.synergy * a.confidence;
    const scoreB = b.combinedPF * b.synergy * b.confidence;
    return scoreB - scoreA;
  }).slice(0, config.topPerformersCount * 2);
}

// ═══════════════════════════════════════════════════════════════
// EDGE MULTIPLIER CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate edge multiplier for decision engine
 */
export function calculateEdgeMultiplier(
  pattern: string,
  state: string,
  scenario: string | undefined,
  liquidity: string | undefined,
  attributions: EdgeAttribution[]
): { multiplier: number; confidence: number; basedOn: string } {
  let bestMultiplier = 1;
  let bestConfidence = 0;
  let basedOn = 'NONE';
  
  for (const attr of attributions) {
    // Check if attribution matches current context
    let matches = 0;
    let totalDims = attr.dimensions.length;
    
    for (const dim of attr.dimensions) {
      switch (dim.dimension) {
        case 'PATTERN':
          if (dim.value === pattern) matches++;
          break;
        case 'STATE':
          if (dim.value === state) matches++;
          break;
        case 'SCENARIO':
          if (scenario && dim.value === scenario) matches++;
          break;
        case 'LIQUIDITY':
          if (liquidity && dim.value === liquidity) matches++;
          break;
      }
    }
    
    // Full match
    if (matches === totalDims) {
      const multiplier = attr.combinedPF > 1 
        ? 1 + (attr.combinedPF - 1) * 0.3 
        : 1 - (1 - attr.combinedPF) * 0.3;
      
      if (attr.confidence > bestConfidence) {
        bestMultiplier = multiplier;
        bestConfidence = attr.confidence;
        basedOn = attr.dimensions.map(d => d.dimension).join('+');
      }
    }
  }
  
  return {
    multiplier: Math.max(0.7, Math.min(1.3, bestMultiplier)),
    confidence: bestConfidence,
    basedOn
  };
}
