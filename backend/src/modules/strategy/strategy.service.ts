/**
 * Phase 5 — Strategy Service
 * ============================
 * Core strategy management operations
 */

import { v4 as uuidv4 } from 'uuid';
import {
  Strategy,
  StrategyConditions,
  StrategyRisk,
  StrategyPerformance,
  StrategyAllocation,
} from './strategy.types.js';
import { STRATEGY_REGISTRY, getEnabledStrategies } from './strategy.registry.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY STRATEGY STORAGE (extends registry)
// ═══════════════════════════════════════════════════════════════

const customStrategies: Map<string, Strategy> = new Map();

// ═══════════════════════════════════════════════════════════════
// STRATEGY CRUD
// ═══════════════════════════════════════════════════════════════

/**
 * Get all strategies (registry + custom)
 */
export function getAllStrategies(): Strategy[] {
  return [...STRATEGY_REGISTRY, ...customStrategies.values()];
}

/**
 * Get strategy by ID
 */
export function getStrategy(id: string): Strategy | undefined {
  const fromRegistry = STRATEGY_REGISTRY.find(s => s.id === id);
  if (fromRegistry) return fromRegistry;
  return customStrategies.get(id);
}

/**
 * Create new custom strategy
 */
export function createStrategy(
  name: string,
  description: string,
  conditions: StrategyConditions,
  risk: StrategyRisk,
  allocation: number
): Strategy {
  const id = `custom_${uuidv4().slice(0, 8)}`;
  
  const strategy: Strategy = {
    id,
    name,
    description,
    enabled: false,  // Start disabled
    conditions,
    risk,
    allocation,
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
  
  customStrategies.set(id, strategy);
  return strategy;
}

/**
 * Update strategy
 */
export function updateStrategy(
  id: string,
  updates: Partial<Omit<Strategy, 'id' | 'createdAt'>>
): Strategy | null {
  const strategy = getStrategy(id);
  if (!strategy) return null;
  
  // Can't update registry strategies except enabled/allocation
  const isRegistry = STRATEGY_REGISTRY.some(s => s.id === id);
  
  if (isRegistry) {
    const idx = STRATEGY_REGISTRY.findIndex(s => s.id === id);
    if (updates.enabled !== undefined) {
      STRATEGY_REGISTRY[idx].enabled = updates.enabled;
    }
    if (updates.allocation !== undefined) {
      STRATEGY_REGISTRY[idx].allocation = updates.allocation;
    }
    STRATEGY_REGISTRY[idx].updatedAt = Date.now();
    return STRATEGY_REGISTRY[idx];
  }
  
  const custom = customStrategies.get(id);
  if (!custom) return null;
  
  Object.assign(custom, updates, { updatedAt: Date.now() });
  return custom;
}

/**
 * Activate strategy
 */
export function activateStrategy(id: string): boolean {
  const updated = updateStrategy(id, { enabled: true });
  return updated !== null;
}

/**
 * Deactivate strategy
 */
export function deactivateStrategy(id: string): boolean {
  const updated = updateStrategy(id, { enabled: false });
  return updated !== null;
}

/**
 * Delete custom strategy
 */
export function deleteStrategy(id: string): boolean {
  // Can't delete registry strategies
  if (STRATEGY_REGISTRY.some(s => s.id === id)) {
    return false;
  }
  return customStrategies.delete(id);
}

// ═══════════════════════════════════════════════════════════════
// ALLOCATION
// ═══════════════════════════════════════════════════════════════

/**
 * Get allocation summary
 */
export function getAllocations(): StrategyAllocation[] {
  return getAllStrategies()
    .filter(s => s.enabled)
    .map(s => ({
      strategyId: s.id,
      name: s.name,
      capitalWeight: s.allocation,
      enabled: s.enabled,
    }));
}

/**
 * Rebalance allocations to sum to 1.0
 */
export function rebalanceAllocations(): void {
  const enabled = getAllStrategies().filter(s => s.enabled);
  const totalAlloc = enabled.reduce((sum, s) => sum + s.allocation, 0);
  
  if (totalAlloc === 0) return;
  
  for (const strategy of enabled) {
    const newAlloc = strategy.allocation / totalAlloc;
    updateStrategy(strategy.id, { allocation: Math.round(newAlloc * 100) / 100 });
  }
}

/**
 * Set allocation for a strategy
 */
export function setAllocation(id: string, allocation: number): boolean {
  if (allocation < 0 || allocation > 1) return false;
  const updated = updateStrategy(id, { allocation });
  return updated !== null;
}

// ═══════════════════════════════════════════════════════════════
// PERFORMANCE
// ═══════════════════════════════════════════════════════════════

/**
 * Update strategy performance
 */
export function updatePerformance(id: string, performance: StrategyPerformance): boolean {
  const strategy = getStrategy(id);
  if (!strategy) return false;
  
  strategy.performance = performance;
  strategy.updatedAt = Date.now();
  
  return true;
}

/**
 * Get performance summary for all strategies
 */
export function getPerformanceSummary(): {
  strategies: { id: string; name: string; performance: StrategyPerformance | undefined }[];
  avgWinRate: number;
  avgProfitFactor: number;
  totalTrades: number;
} {
  const all = getAllStrategies();
  const withPerf = all.filter(s => s.performance);
  
  const avgWinRate = withPerf.length > 0
    ? withPerf.reduce((sum, s) => sum + (s.performance?.winRate || 0), 0) / withPerf.length
    : 0;
    
  const avgProfitFactor = withPerf.length > 0
    ? withPerf.reduce((sum, s) => sum + (s.performance?.profitFactor || 0), 0) / withPerf.length
    : 0;
    
  const totalTrades = withPerf.reduce((sum, s) => sum + (s.performance?.totalTrades || 0), 0);
  
  return {
    strategies: all.map(s => ({
      id: s.id,
      name: s.name,
      performance: s.performance,
    })),
    avgWinRate: Math.round(avgWinRate * 100) / 100,
    avgProfitFactor: Math.round(avgProfitFactor * 100) / 100,
    totalTrades,
  };
}

// ═══════════════════════════════════════════════════════════════
// STATISTICS
// ═══════════════════════════════════════════════════════════════

/**
 * Get strategy statistics
 */
export function getStrategyStats(): {
  total: number;
  enabled: number;
  registry: number;
  custom: number;
  totalAllocation: number;
} {
  const all = getAllStrategies();
  const enabled = all.filter(s => s.enabled);
  
  return {
    total: all.length,
    enabled: enabled.length,
    registry: STRATEGY_REGISTRY.length,
    custom: customStrategies.size,
    totalAllocation: Math.round(enabled.reduce((sum, s) => sum + s.allocation, 0) * 100) / 100,
  };
}
