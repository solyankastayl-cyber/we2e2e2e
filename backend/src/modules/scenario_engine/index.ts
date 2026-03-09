/**
 * Phase 6 — Scenario Engine Module
 * 
 * Market Scenario Simulator 2.0
 * Models market BEHAVIOR, not just price paths
 */

// Types
export * from './scenario.types.js';

// Generator
export { 
  generateScenarios,
  generateFromTemplates,
  generateDynamicScenarios,
  determineCurrentState,
  mapPhysicsToState,
  calculatePathProbability,
  getTransitionProbability
} from './scenario.generator.js';

// Simulator
export {
  simulateScenarios,
  refineWithMonteCarlo,
  analyzeCriticalPoints,
  compareScenarios
} from './scenario.simulator.js';

// Scoring
export {
  calculateScenarioScore,
  scoreScenarios,
  selectTopScenarios,
  calculateScenarioEV,
  calculateRiskAdjustedScore,
  rankScenarios
} from './scenario.scoring.js';

// Storage
export {
  MarketScenarioModel,
  ScenarioSimResultModel,
  saveScenarios,
  saveSimulationResult,
  getLatestScenarios,
  getActiveScenarios,
  updateScenarioOutcome,
  getScenarioStats,
  cleanupExpiredScenarios
} from './scenario.storage.js';

// Routes
export { registerScenarioRoutes } from './scenario.routes.js';
