/**
 * Phase 3 — System State Service
 * ================================
 * Manages current system state for admin operations
 */

import { getMongoDb } from '../../db/mongoose.js';
import {
  SystemStatus,
  ModuleStatus,
  StrategyStatus,
  RiskMode,
  AnalysisMode,
} from './admin.command.types.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY STATE (for demo, in prod would be from actual services)
// ═══════════════════════════════════════════════════════════════

interface SystemState {
  metabrain: {
    riskMode: RiskMode;
    analysisMode: AnalysisMode;
    safeMode: boolean;
    riskMultiplier: number;
  };
  modules: Map<string, ModuleStatus>;
  strategies: Map<string, StrategyStatus>;
  system: {
    startTime: number;
    status: 'RUNNING' | 'PAUSED' | 'DEGRADED';
  };
}

const startTime = Date.now();

const state: SystemState = {
  metabrain: {
    riskMode: 'NORMAL',
    analysisMode: 'DEEP_MARKET',
    safeMode: false,
    riskMultiplier: 1.0,
  },
  modules: new Map([
    ['ta', { name: 'ta', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
    ['liquidity', { name: 'liquidity', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
    ['context', { name: 'context', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
    ['regime', { name: 'regime', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
    ['scenario', { name: 'scenario', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
    ['memory', { name: 'memory', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
    ['fractal', { name: 'fractal', status: 'ACTIVE', weight: 0.8, lastUpdated: startTime }],
    ['physics', { name: 'physics', status: 'ACTIVE', weight: 0.9, lastUpdated: startTime }],
    ['state', { name: 'state', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
    ['graph', { name: 'graph', status: 'ACTIVE', weight: 0.7, lastUpdated: startTime }],
    ['market_map', { name: 'market_map', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
    ['decision', { name: 'decision', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
    ['execution', { name: 'execution', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
    ['metabrain', { name: 'metabrain', status: 'ACTIVE', weight: 1.0, lastUpdated: startTime }],
  ]),
  strategies: new Map([
    ['breakout', { name: 'breakout', active: true, weight: 1.0, signalsToday: 12 }],
    ['mean_reversion', { name: 'mean_reversion', active: true, weight: 0.8, signalsToday: 8 }],
    ['trend_follow', { name: 'trend_follow', active: true, weight: 1.2, signalsToday: 15 }],
    ['momentum', { name: 'momentum', active: true, weight: 0.9, signalsToday: 6 }],
    ['range_bound', { name: 'range_bound', active: false, weight: 0.5, signalsToday: 0 }],
    ['liquidity_sweep', { name: 'liquidity_sweep', active: true, weight: 0.7, signalsToday: 3 }],
    ['harmonic', { name: 'harmonic', active: true, weight: 0.6, signalsToday: 2 }],
    ['divergence', { name: 'divergence', active: true, weight: 0.7, signalsToday: 4 }],
  ]),
  system: {
    startTime,
    status: 'RUNNING',
  },
};

// ═══════════════════════════════════════════════════════════════
// STATE GETTERS
// ═══════════════════════════════════════════════════════════════

/**
 * Get full system state
 */
export async function getSystemState(): Promise<SystemState> {
  return state;
}

/**
 * Get MetaBrain state
 */
export function getMetaBrainState() {
  return { ...state.metabrain };
}

/**
 * Get all module statuses
 */
export function getModuleStatuses(): ModuleStatus[] {
  return Array.from(state.modules.values());
}

/**
 * Get single module status
 */
export function getModuleStatus(name: string): ModuleStatus | undefined {
  return state.modules.get(name);
}

/**
 * Get all strategy statuses
 */
export function getStrategyStatuses(): StrategyStatus[] {
  return Array.from(state.strategies.values());
}

/**
 * Get single strategy status
 */
export function getStrategyStatus(name: string): StrategyStatus | undefined {
  return state.strategies.get(name);
}

/**
 * Get system status
 */
export function getSystemStatus(): SystemStatus {
  const activeStrategies = Array.from(state.strategies.values())
    .filter(s => s.active);
  
  return {
    uptime: Date.now() - state.system.startTime,
    status: state.system.status,
    wsConnections: 0,  // Would come from realtime module
    signalsToday: activeStrategies.reduce((sum, s) => sum + s.signalsToday, 0),
    commandsToday: 0,  // Would come from audit
    activeOverrides: 0,  // Would come from override registry
  };
}

// ═══════════════════════════════════════════════════════════════
// STATE SETTERS (for command execution)
// ═══════════════════════════════════════════════════════════════

/**
 * Set risk mode
 */
export function setRiskMode(mode: RiskMode): { previous: RiskMode; current: RiskMode } {
  const previous = state.metabrain.riskMode;
  state.metabrain.riskMode = mode;
  
  // Update risk multiplier based on mode
  const multipliers: Record<RiskMode, number> = {
    SAFE: 0.25,
    CONSERVATIVE: 0.5,
    NORMAL: 1.0,
    AGGRESSIVE: 1.5,
  };
  state.metabrain.riskMultiplier = multipliers[mode];
  
  return { previous, current: mode };
}

/**
 * Set analysis mode
 */
export function setAnalysisMode(mode: AnalysisMode): { previous: AnalysisMode; current: AnalysisMode } {
  const previous = state.metabrain.analysisMode;
  state.metabrain.analysisMode = mode;
  return { previous, current: mode };
}

/**
 * Toggle safe mode
 */
export function toggleSafeMode(enabled: boolean): { previous: boolean; current: boolean } {
  const previous = state.metabrain.safeMode;
  state.metabrain.safeMode = enabled;
  
  if (enabled) {
    state.metabrain.riskMultiplier = 0.25;
  } else {
    // Restore based on risk mode
    const multipliers: Record<RiskMode, number> = {
      SAFE: 0.25,
      CONSERVATIVE: 0.5,
      NORMAL: 1.0,
      AGGRESSIVE: 1.5,
    };
    state.metabrain.riskMultiplier = multipliers[state.metabrain.riskMode];
  }
  
  return { previous, current: enabled };
}

/**
 * Set module status
 */
export function setModuleStatus(
  name: string,
  status: 'ACTIVE' | 'SOFT_GATED' | 'HARD_GATED'
): { previous: ModuleStatus | undefined; current: ModuleStatus } {
  const previous = state.modules.get(name);
  
  const updated: ModuleStatus = {
    name,
    status,
    weight: status === 'HARD_GATED' ? 0 : (status === 'SOFT_GATED' ? 0.3 : 1.0),
    lastUpdated: Date.now(),
  };
  
  state.modules.set(name, updated);
  
  return { previous, current: updated };
}

/**
 * Set module weight
 */
export function setModuleWeight(name: string, weight: number): ModuleStatus | undefined {
  const module = state.modules.get(name);
  if (!module) return undefined;
  
  module.weight = weight;
  module.lastUpdated = Date.now();
  
  return module;
}

/**
 * Enable strategy
 */
export function enableStrategy(name: string): StrategyStatus {
  let strategy = state.strategies.get(name);
  
  if (!strategy) {
    strategy = { name, active: true, weight: 1.0, signalsToday: 0 };
  } else {
    strategy.active = true;
  }
  
  state.strategies.set(name, strategy);
  return strategy;
}

/**
 * Disable strategy
 */
export function disableStrategy(name: string): StrategyStatus | undefined {
  const strategy = state.strategies.get(name);
  if (!strategy) return undefined;
  
  strategy.active = false;
  return strategy;
}

/**
 * Set strategy weight
 */
export function setStrategyWeight(name: string, weight: number): StrategyStatus | undefined {
  const strategy = state.strategies.get(name);
  if (!strategy) return undefined;
  
  strategy.weight = weight;
  return strategy;
}

/**
 * Pause system
 */
export function pauseSystem(): void {
  state.system.status = 'PAUSED';
}

/**
 * Resume system
 */
export function resumeSystem(): void {
  state.system.status = 'RUNNING';
}
