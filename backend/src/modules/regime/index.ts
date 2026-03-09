/**
 * Phase 9 — Regime Intelligence Engine Module
 * 
 * Market regime classification and transitions
 */

// Types
export * from './regime.types.js';

// Features
export { calculateRegimeFeatures } from './regime.features.js';
export type { CandleInput } from './regime.features.js';

// Classifier
export { 
  detectRegime, 
  detectRegimeSmoothed, 
  getRegimeBoost 
} from './regime.classifier.js';

// Storage
export {
  RegimeHistoryModel,
  RegimeTransitionModel,
  saveRegimeHistory,
  getLatestRegime,
  getRegimeHistory,
  getRegimeTransitions,
  calculateTransitions,
  getRegimeStats
} from './regime.storage.js';

// Routes
export { registerRegimeRoutes } from './regime.routes.js';
