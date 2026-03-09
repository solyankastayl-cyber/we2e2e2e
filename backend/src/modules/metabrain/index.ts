/**
 * MetaBrain v1 — Module Export
 */

// Types
export * from './metabrain.types.js';

// Context Builder
export {
  buildMetaBrainContext,
  getDefaultContext,
  classifyVolatility,
  calculateEdgeHealth,
  assessMarketCondition
} from './metabrain.context.js';
export type {
  RegimeSource,
  StateSource,
  PhysicsSource,
  PortfolioSource,
  EdgeSource,
  StrategySource,
  GovernanceSource
} from './metabrain.context.js';

// Risk Mode Engine
export {
  computeRiskMode,
  validateModeTransition,
  calculateRiskScore,
  riskScoreToMode
} from './metabrain.risk_mode.js';

// Policy Engine
export {
  buildMetaDecision,
  generateStrategyPolicies,
  determineSignalThresholds
} from './metabrain.policy.js';
export type { StrategyPolicyResult, SignalThresholds } from './metabrain.policy.js';

// Controller
export {
  runMetaBrain,
  getCurrentState,
  getCurrentDecision,
  forceRecompute,
  getRiskMultiplier,
  getConfidenceThreshold,
  getStrategyMultiplier
} from './metabrain.controller.js';

// Storage
export {
  MetaBrainStateModel,
  MetaBrainActionModel,
  getMetaBrainState,
  saveMetaBrainState,
  saveMetaBrainAction,
  getRecentActions,
  getModeChangesToday,
  getLastModeChangeTime,
  getActionStats
} from './metabrain.storage.js';

// Routes
export { registerMetaBrainRoutes } from './metabrain.routes.js';
