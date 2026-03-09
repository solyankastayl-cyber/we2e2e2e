/**
 * Phase 9.5 — Edge Validation for Discovery
 */

export * from './edge.types.js';
export { analyzeRegimeRobustness, analyzeMarketRobustness, analyzeStability, buildRobustnessScore } from './edge.robustness.js';
export { analyzeSimilarity, filterRedundantStrategies, calculateFeatureOverlap } from './edge.similarity.js';
export { calculateConfidenceScore, calculateSampleScore, determineLifecycleStatus } from './edge.confidence.js';
export { createEdgeValidationService, getEdgeValidationService, type EdgeValidationService } from './edge.service.js';
export { registerEdgeValidationRoutes, initEdgeValidationIndexes } from './edge.routes.js';
