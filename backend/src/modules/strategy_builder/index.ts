/**
 * Phase 8 — Strategy Builder Module
 * 
 * Auto-generates trading strategies from edge combinations
 */

// Types
export * from './strategy.types.js';

// Generator
export {
  generateStrategyCandidates,
  generateFromAttributions,
  optimizeStrategyParams
} from './strategy.generator.js';
export type { EdgeDimensionData, EdgeCombination } from './strategy.generator.js';

// Simulator
export {
  simulateStrategy,
  evaluateCandidate,
  DEFAULT_SIM_CONFIG
} from './strategy.simulator.js';
export type { TradeSignal, Candle, SimulationConfig } from './strategy.simulator.js';

// Storage
export {
  StrategyModel,
  saveStrategy,
  saveStrategies,
  getActiveStrategies,
  getTopStrategies,
  getStrategiesByPattern,
  getStrategiesByRegime,
  findMatchingStrategies,
  updateStrategyStatus,
  getStrategyStats
} from './strategy.storage.js';

// Routes
export { registerStrategyRoutes } from './strategy.routes.js';
