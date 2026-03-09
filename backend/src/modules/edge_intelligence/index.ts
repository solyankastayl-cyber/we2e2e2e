/**
 * Phase 7 — Edge Intelligence Module
 * 
 * Understands WHERE the system makes money
 */

// Types
export * from './edge_intel.types.js';

// Extractor
export {
  tradeToEdgeRecord,
  extractDimensionValue,
  groupByDimension,
  groupByDimensions,
  filterRecords,
  extractEdgeDataBatch
} from './edge_intel.extractor.js';

// Aggregator
export {
  calcWinRate,
  calcAvgR,
  calcMedianR,
  calcProfitFactor,
  calcSharpe,
  calcMaxDD,
  calcEdgeScore,
  shrinkEstimate,
  calculateGroupStats,
  aggregateByDimension,
  aggregateAllDimensions,
  getTopPerformers,
  getWorstPerformers
} from './edge_intel.aggregator.js';

// Attribution
export {
  calculateIndividualContributions,
  calculateCombinedEffect,
  calculateSynergy,
  findBestCombinations,
  calculateEdgeMultiplier
} from './edge_intel.attribution.js';

// Storage
export {
  EdgeRecordModel,
  EdgeStatsModel,
  EdgeAttributionModel,
  saveEdgeRecords,
  saveEdgeStats,
  saveEdgeAttributions,
  getEdgeRecords,
  getEdgeStatsByDimension,
  getTopAttributions,
  getGlobalBaseline
} from './edge_intel.storage.js';

// Routes
export { registerEdgeIntelligenceRoutes } from './edge_intel.routes.js';
