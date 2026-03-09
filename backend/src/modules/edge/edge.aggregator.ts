/**
 * Edge Aggregator (P5.0.5)
 * 
 * Groups edge statistics by dimension and calculates aggregated metrics
 */

import type { 
  EdgeRow, 
  EdgeAggregate, 
  EdgeDimension, 
  GlobalBaseline 
} from './domain/types.js';
import {
  calcWinRate,
  calcAvgR,
  calcMedianR,
  calcPercentileR,
  calcAvgEV,
  calcEdge,
  calcProfitFactor,
  calcMaxDrawdownR,
  calcSharpeR,
  calcEVCorrelation,
  calcOutcomeCounts,
  calcEdgeScore,
  shrink,
  SHRINKAGE_CONFIG,
} from './edge.metrics.js';

/**
 * Extract key from row based on dimension
 */
export function extractDimensionKey(row: EdgeRow, dimension: EdgeDimension): string {
  switch (dimension) {
    case 'pattern':
      return row.primaryPatternType || 'UNKNOWN';
    case 'family':
      return row.patternFamily || 'OTHER';
    case 'regime':
      return row.regime || 'UNKNOWN';
    case 'geometry':
      // Composite key: maturity + fit error buckets
      return `${row.maturityBucket || 'UNKNOWN'}_${row.fitErrorBucket || 'UNKNOWN'}`;
    case 'ml_bucket':
      return row.mlBucket || 'UNKNOWN';
    case 'stability_bucket':
      return row.stabilityBucket || 'UNKNOWN';
    case 'timeframe':
      return row.timeframe || 'UNKNOWN';
    case 'asset':
      return row.asset || 'UNKNOWN';
    default:
      return 'UNKNOWN';
  }
}

/**
 * Group rows by dimension
 */
export function groupByDimension(
  rows: EdgeRow[],
  dimension: EdgeDimension
): Map<string, EdgeRow[]> {
  const groups = new Map<string, EdgeRow[]>();
  
  for (const row of rows) {
    const key = extractDimensionKey(row, dimension);
    
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(row);
  }
  
  return groups;
}

/**
 * Calculate aggregate for a group of rows
 */
export function calculateAggregate(
  dimension: EdgeDimension,
  key: string,
  rows: EdgeRow[],
  globalBaseline: GlobalBaseline
): EdgeAggregate {
  const sampleSize = rows.length;
  const outcomeCounts = calcOutcomeCounts(rows);
  
  // Raw metrics
  const winRate = calcWinRate(rows);
  const avgR = calcAvgR(rows);
  const medianR = calcMedianR(rows);
  const avgEV = calcAvgEV(rows);
  const edge = calcEdge(rows);
  const profitFactor = calcProfitFactor(rows);
  const maxDrawdownR = calcMaxDrawdownR(rows);
  const sharpeR = calcSharpeR(rows);
  const evCorrelation = calcEVCorrelation(rows);
  
  // Percentiles
  const p10R = calcPercentileR(rows, 10);
  const p50R = calcPercentileR(rows, 50);
  const p90R = calcPercentileR(rows, 90);
  
  // Shrunk metrics (regularized toward global baseline)
  const winRateShrunk = shrink(
    winRate,
    sampleSize,
    globalBaseline.globalWinRate
  );
  
  const avgRShrunk = shrink(
    avgR,
    sampleSize,
    globalBaseline.globalAvgR
  );
  
  const edgeShrunk = shrink(
    edge,
    sampleSize,
    globalBaseline.globalAvgR - globalBaseline.globalAvgEV
  );
  
  // Average stability for score calculation
  const avgStability = rows.reduce((sum, r) => sum + r.stabilityMultiplier, 0) / sampleSize;
  
  // Composite edge score
  const edgeScore = calcEdgeScore(
    avgRShrunk,
    winRateShrunk,
    sampleSize,
    avgStability
  );
  
  return {
    dimension,
    key,
    sampleSize,
    ...outcomeCounts,
    winRate,
    winRateShrunk,
    avgR,
    avgRShrunk,
    medianR,
    p10R,
    p50R,
    p90R,
    avgEV,
    edge,
    edgeShrunk,
    profitFactor,
    maxDrawdownR,
    sharpeR,
    evCorrelation,
    edgeScore,
    updatedAt: new Date(),
  };
}

/**
 * Aggregate all rows by a dimension
 */
export function aggregateByDimension(
  rows: EdgeRow[],
  dimension: EdgeDimension,
  globalBaseline: GlobalBaseline
): EdgeAggregate[] {
  const groups = groupByDimension(rows, dimension);
  const aggregates: EdgeAggregate[] = [];
  
  for (const [key, groupRows] of groups) {
    // Skip groups with too few samples
    if (groupRows.length < 3) continue;
    
    const aggregate = calculateAggregate(
      dimension,
      key,
      groupRows,
      globalBaseline
    );
    
    aggregates.push(aggregate);
  }
  
  // Sort by edge score descending
  aggregates.sort((a, b) => b.edgeScore - a.edgeScore);
  
  return aggregates;
}

/**
 * Aggregate all dimensions
 */
export function aggregateAllDimensions(
  rows: EdgeRow[],
  globalBaseline: GlobalBaseline
): Map<EdgeDimension, EdgeAggregate[]> {
  const dimensions: EdgeDimension[] = [
    'pattern',
    'family',
    'regime',
    'geometry',
    'ml_bucket',
    'stability_bucket',
    'timeframe',
    'asset',
  ];
  
  const results = new Map<EdgeDimension, EdgeAggregate[]>();
  
  for (const dimension of dimensions) {
    const aggregates = aggregateByDimension(rows, dimension, globalBaseline);
    results.set(dimension, aggregates);
  }
  
  return results;
}

/**
 * Get top performers for a dimension
 */
export function getTopPerformers(
  aggregates: EdgeAggregate[],
  limit: number = 10,
  minSamples: number = SHRINKAGE_CONFIG.minSampleForEdge
): EdgeAggregate[] {
  return aggregates
    .filter(a => a.sampleSize >= minSamples)
    .sort((a, b) => b.edgeScore - a.edgeScore)
    .slice(0, limit);
}

/**
 * Get worst performers for a dimension
 */
export function getWorstPerformers(
  aggregates: EdgeAggregate[],
  limit: number = 10,
  minSamples: number = SHRINKAGE_CONFIG.minSampleForEdge
): EdgeAggregate[] {
  return aggregates
    .filter(a => a.sampleSize >= minSamples)
    .sort((a, b) => a.edgeScore - b.edgeScore)
    .slice(0, limit);
}
