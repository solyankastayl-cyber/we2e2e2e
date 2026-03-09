/**
 * P1.4 — MetaBrain v2.3 Regime Learning Module Index
 */

// Types
export * from './regime.learning.types.js';

// Core engine
export {
  calculateRegimeConfidence,
  calculateRegimeWeight,
  computeRegimeModuleWeight,
  buildRegimeWeightMap,
  buildAllRegimeWeightMaps,
  getRegimeWeight,
  getRegimeWeightRecord,
  applyRegimeWeight,
  applyWeightDecay,
  getDefaultRegimeWeights,
  getDefaultRegimeWeightMap,
  compareRegimeWeights
} from './regime.learning.js';

// Storage
export {
  RegimeWeightModel,
  saveRegimeWeight,
  saveRegimeWeights,
  getRegimeWeight as getRegimeWeightFromStorage,
  getRegimeWeights,
  getAllRegimeWeights,
  getRegimeWeightMaps,
  getRegimeWeightsMap,
  deleteRegimeWeights,
  resetAllRegimeWeights
} from './regime.learning.storage.js';

// Integration
export {
  fetchRegimeWeights,
  fetchRegimeWeightMap,
  getModuleRegimeWeight,
  applyRegimeWeightToBoost,
  shouldSoftGateByRegime,
  shouldHardGateByRegime,
  getRegimeWeightsForExplain,
  getRegimeLearningState
} from './regime.learning.integration.js';

// Routes
export { registerRegimeLearningRoutes } from './regime.learning.routes.js';
