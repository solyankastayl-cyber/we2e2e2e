/**
 * MetaBrain v3 — Module Index
 */

// Types
export * from './metabrain_v3.types.js';

// Context builder
export {
  buildMetaBrainV3Context,
  getDefaultContext
} from './metabrain_v3.context.js';

// Safe mode
export {
  checkSafeMode,
  getSafeModeAdjustments,
  type SafeModeCheckResult
} from './metabrain_v3.safemode.js';

// Analysis depth
export {
  decideAnalysisDepth,
  getEnabledModulesForMode,
  type AnalysisDepthDecision
} from './metabrain_v3.analysis_depth.js';

// Strategy
export {
  getStrategiesForRegime,
  getDisabledStrategiesForRegime,
  calculateStrategyMultiplier,
  buildStrategyPolicy
} from './metabrain_v3.strategy.js';

// Optimizer
export {
  determineRiskMode,
  buildModulePolicy,
  buildExecutionPolicy,
  buildConfidencePolicy,
  runMetaBrainV3,
  runMetaBrainV3WithContext,
  getNeutralDecision
} from './metabrain_v3.optimizer.js';

// Storage
export {
  MetaBrainV3StateModel,
  MetaBrainV3ActionModel,
  saveMetaBrainV3State,
  getLatestMetaBrainV3State,
  getMetaBrainV3History,
  saveMetaBrainV3Action,
  getMetaBrainV3Actions,
  cleanOldMetaBrainV3Data
} from './metabrain_v3.storage.js';

// Routes
export { registerMetaBrainV3Routes } from './metabrain_v3.routes.js';
