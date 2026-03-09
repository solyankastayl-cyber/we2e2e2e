/**
 * MetaBrain v2.1 — Learning Layer Module Export
 */

// Types
export * from './module_attribution.types.js';

// Attribution Compute
export {
  computeModuleAttribution,
  filterByModuleActivation,
  splitByActivation,
  calculateEdgeScore,
  computeDifferentialAttribution
} from './module_attribution.compute.js';

// Weights Engine
export {
  computeModuleWeights,
  calculateRawWeight,
  applyShrinkage,
  clampWeight,
  applyRateLimit,
  getDefaultWeights,
  applyModuleWeights,
  getModuleMultiplier,
  createWeightHistoryEntry,
  normalizeWeights,
  getWeightSummary
} from './module_weights.engine.js';

// Data Source
export {
  transformEdgeRecord,
  loadAttributionRecords,
  loadAttributionRecordsInWindow,
  generateSyntheticRecords
} from './module_datasource.js';

// Storage
export {
  ModuleAttributionModel,
  ModuleWeightModel,
  ModuleWeightHistoryModel,
  saveModuleAttributions,
  getModuleAttributions,
  saveModuleWeights,
  getModuleWeights,
  getAllModuleWeights,
  getModuleWeightMap,
  saveWeightHistory,
  getWeightHistory,
  getRecentWeightChanges
} from './module_storage.js';

// Controller
export {
  rebuildModuleAttribution,
  getCurrentWeights,
  getModuleWeight,
  getCurrentAttribution,
  forceRecompute,
  getLearningStatus
} from './module_controller.js';

// Integration (for Decision Engine)
export {
  getLearningWeightMap,
  getLearningWeight,
  applyLearningWeights,
  fetchLearningWeights,
  type LearningWeightMap
} from './learning.integration.js';

// P1.2: Module Gating
export * from './learning.gating.types.js';
export {
  calculateGatingScore,
  determineGateStatus,
  computeModuleGates,
  applyModuleGate,
  applyAllModuleGates,
  calculateGatingSummary,
  isGatingChangeAllowed,
  getDefaultGates,
  isModuleGated,
  getModuleGateStatus
} from './learning.gating.ts';
export {
  applyGatesToWeights,
  getGatedWeights,
  applyGateToBoost,
  getGateStatusesForExplain,
  fetchModuleGates,
  fetchGatingSummary,
  getGatingPressure,
  getGatedModulesForTwin,
  type GatedWeightMap
} from './learning.gating.integration.js';
export {
  ModuleGateModel,
  ModuleGateHistoryModel,
  saveModuleGate,
  saveModuleGates,
  getModuleGate,
  getAllModuleGates,
  getModuleGatesMap,
  saveGateHistory,
  getGateHistory,
  getRecentGateChanges,
  countRecentGateChanges,
  resetAllGates,
  cleanupExpiredGates
} from './learning.gating.storage.js';
export { registerGatingRoutes, rebuildGates } from './learning.gating.routes.js';

// Routes
export { registerLearningRoutes } from './module_routes.js';
