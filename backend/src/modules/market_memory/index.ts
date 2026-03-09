/**
 * Market Memory Engine — Index
 */

// Types
export * from './memory.types.js';

// Snapshot
export { buildMemorySnapshot, buildMemorySnapshotFromRaw, resolveSnapshotOutcome } from './memory.snapshot.js';

// Vector
export { buildFeatureVector, cosineSimilarity, euclideanDistance, weightedSimilarity } from './memory.vector.js';

// Search
export { searchSimilarSnapshots, searchSimilarSnapshotsInMemory, summarizeMemoryMatches } from './memory.search.js';

// Boost
export { buildMemoryBoost, applyMemoryBoostToScenario, getScenarioMemoryBoost, applyRiskAdjustment } from './memory.boost.js';

// Controller
export * as memoryController from './memory.controller.js';

// Storage
export * as memoryStorage from './memory.storage.js';

// Routes
export { registerMemoryRoutes } from './memory.routes.js';
