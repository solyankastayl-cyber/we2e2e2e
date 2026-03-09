/**
 * Phase 10 — Execution Intelligence Module
 * 
 * Position sizing, risk management, portfolio control
 */

// Types
export * from './execution.types.js';

// Position Sizing
export {
  calculatePositionSize,
  calculateConfidenceMultiplier,
  calculateEdgeMultiplier,
  calculateRegimeMultiplier,
  calculatePortfolioMultiplier,
  calculateKellyFraction,
  calculateKellyPositionSize
} from './execution.position.js';

// Risk Management
export {
  calculateRiskStatus,
  getCorrelationGroup,
  calculateCorrelatedExposure,
  checkCorrelationLimits,
  calculateCurrentDrawdown,
  calculateMaxDrawdown,
  calculateRiskReductionFactor,
  shouldPauseTrading
} from './execution.risk.js';

// Portfolio Management
export {
  createPortfolio,
  addPosition,
  updatePositionPrices,
  closePosition,
  calculateAllocations,
  getAvailableAllocation,
  calculatePortfolioStats,
  getPositionsByStrategy
} from './execution.portfolio.js';

// Execution Planning
export {
  createExecutionPlan,
  validateExecutionPlan,
  createExecutionPlansBatch
} from './execution.plan.js';
export type { SignalInput } from './execution.plan.js';

// Storage
export {
  ExecutionPlanModel,
  PortfolioModel,
  saveExecutionPlan,
  getExecutionPlans,
  getPendingPlans,
  updatePlanStatus,
  savePortfolio,
  getPortfolio,
  getDefaultPortfolio,
  getExecutionStats
} from './execution.storage.js';

// Routes
export { registerExecutionRoutes } from './execution.routes.js';
