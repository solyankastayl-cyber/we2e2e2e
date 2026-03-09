/**
 * Digital Twin Module Index
 */

// Types
export * from './digital_twin.types.js';

// Context
export { buildTwinContext, buildMockTwinContext, validateContext, deriveLiquidityState } from './digital_twin.context.js';

// Branches
export { buildTwinBranches, getDominantBranch, calculateBranchConflict, calculateWeightedFailureRisk } from './digital_twin.branches.js';

// State
export { buildDigitalTwinState, updateTwinStateWithConsistency, updateTwinStateWithCounterfactual, updateTwinStateWithMemory, compareStates, hasSignificantChange } from './digital_twin.state.js';

// Consistency
export { evaluateTwinConsistency, getMostCriticalConflict, isConsistencyAcceptable, getResolutionSuggestions } from './digital_twin.consistency.js';

// Counterfactual
export { buildCounterfactuals, computeScenarioBreakRisk } from './digital_twin.counterfactual.js';

// Reactor
export { handleTwinEvent, detectEventFromContext, subscribeTwinUpdates, emitTwinUpdate } from './digital_twin.reactor.js';

// Storage
export * as twinStorage from './digital_twin.storage.js';

// Controller
export * as twinController from './digital_twin.controller.js';

// Live Context
export { buildLiveTwinContext, checkModuleAvailability } from './digital_twin.live_context.js';

// DT5 — Branch Tree Expansion
export { buildBranchTree, getMainBranch, getLeafNodes, calculateTreeEntropy } from './digital_twin.tree_builder.js';
export { calculateTreeDecisionAdjustment, calculateTreeExecutionAdjustment, getRecommendedRiskMode, getTradingRecommendation } from './digital_twin.tree_scoring.js';
export { registerTreeRoutes } from './digital_twin.tree_routes.js';

// P1.1 — Tree Integration
export {
  getTreeAdjustments,
  createTreeIntegrationResult,
  fetchTreeIntegration,
  fetchTreeAdjustments,
  applyTreeDecisionAdjustment,
  applyTreeExecutionAdjustment,
  applyTreeStopAdjustment,
  getTreePolicyHints,
  getNeutralTreeAdjustments,
  getDefaultTreeStats,
  type TreeAdjustments,
  type TreeIntegrationResult
} from './tree.integration.js';

// Routes
export { registerDigitalTwinRoutes } from './digital_twin.routes.js';
