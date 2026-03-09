/**
 * Phase 9 — Strategy Discovery Engine
 */

export * from './discovery.types.js';
export { buildDataset, generateMockDataset } from './discovery.dataset.js';
export { analyzeFeatureCombinations, findTopCombinations, analyzeFeatures } from './discovery.analyzer.js';
export { generateStrategies, generateStrategy, clusterStrategies } from './discovery.generator.js';
export { createDiscoveryService, getDiscoveryService, type DiscoveryService } from './discovery.service.js';
export { registerDiscoveryRoutes, initDiscoveryIndexes } from './discovery.routes.js';
