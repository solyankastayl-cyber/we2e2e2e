/**
 * Phase 3 — Dry Run Engine
 * ==========================
 * Simulates command execution to show impact before actual execution
 */

import {
  AdminCommandType,
  CommandRequest,
  DryRunImpact,
  DryRunResponse,
} from './admin.command.types.js';
import { validateCommand } from './admin.command.validate.js';
import { getSystemState } from './admin.state.service.js';

// ═══════════════════════════════════════════════════════════════
// IMPACT CALCULATORS
// ═══════════════════════════════════════════════════════════════

type ImpactCalculator = (payload: Record<string, any>) => Promise<DryRunImpact>;

const impactCalculators: Partial<Record<AdminCommandType, ImpactCalculator>> = {
  
  [AdminCommandType.SET_RISK_MODE]: async (payload) => {
    const currentState = await getSystemState();
    const currentRisk = currentState.metabrain?.riskMode || 'NORMAL';
    
    const riskLevels: Record<string, number> = {
      SAFE: 0.25,
      CONSERVATIVE: 0.5,
      NORMAL: 1.0,
      AGGRESSIVE: 1.5,
    };
    
    const currentLevel = riskLevels[currentRisk] || 1.0;
    const newLevel = riskLevels[payload.riskMode] || 1.0;
    const riskChange = (newLevel - currentLevel) / currentLevel;
    
    const affectedStrategies: string[] = [];
    if (payload.riskMode === 'SAFE' || payload.riskMode === 'CONSERVATIVE') {
      affectedStrategies.push('momentum', 'breakout', 'aggressive_trend');
    }
    
    return {
      affectedModules: ['metabrain', 'decision', 'execution'],
      affectedStrategies,
      riskChange: Math.round(riskChange * 100) / 100,
      warnings: riskChange > 0.3 ? ['Significant risk increase'] : [],
      reversible: true,
    };
  },
  
  [AdminCommandType.TOGGLE_SAFE_MODE]: async (payload) => {
    const warnings: string[] = [];
    const affectedStrategies: string[] = [];
    
    if (payload.enabled) {
      affectedStrategies.push('momentum', 'breakout', 'aggressive_trend', 'liquidity_sweep');
      warnings.push('All aggressive strategies will be disabled');
      warnings.push('Risk multiplier will be set to 0.25');
    }
    
    return {
      affectedModules: ['metabrain', 'strategy', 'execution'],
      affectedStrategies,
      riskChange: payload.enabled ? -0.75 : 0,
      warnings,
      reversible: true,
    };
  },
  
  [AdminCommandType.MODULE_SOFT_GATE]: async (payload) => {
    const warnings: string[] = [];
    const affectedModules = [payload.module];
    
    // Calculate cascade effects
    const cascadeMap: Record<string, string[]> = {
      ta: ['decision', 'strategy'],
      scenario: ['market_map', 'decision'],
      memory: ['metabrain', 'decision'],
      regime: ['metabrain', 'strategy'],
    };
    
    const cascaded = cascadeMap[payload.module] || [];
    affectedModules.push(...cascaded);
    
    if (cascaded.length > 0) {
      warnings.push(`Cascade effect on: ${cascaded.join(', ')}`);
    }
    
    return {
      affectedModules: [...new Set(affectedModules)],
      affectedStrategies: [],
      warnings,
      reversible: true,
    };
  },
  
  [AdminCommandType.MODULE_HARD_GATE]: async (payload) => {
    const warnings: string[] = ['Module will be completely disabled'];
    const affectedModules = [payload.module];
    
    const criticalModules = ['ta', 'decision', 'metabrain'];
    if (criticalModules.includes(payload.module)) {
      warnings.push('WARNING: This is a critical module');
      warnings.push('System functionality may be severely impacted');
    }
    
    return {
      affectedModules,
      affectedStrategies: [],
      warnings,
      estimatedDowntime: criticalModules.includes(payload.module) ? 60 : 0,
      reversible: true,
    };
  },
  
  [AdminCommandType.ENABLE_STRATEGY]: async (payload) => {
    return {
      affectedModules: ['strategy', 'execution'],
      affectedStrategies: [payload.strategy],
      warnings: [],
      reversible: true,
    };
  },
  
  [AdminCommandType.DISABLE_STRATEGY]: async (payload) => {
    return {
      affectedModules: ['strategy', 'execution'],
      affectedStrategies: [payload.strategy],
      warnings: ['Strategy signals will be stopped'],
      reversible: true,
    };
  },
  
  [AdminCommandType.MEMORY_CLEANUP]: async (payload) => {
    const olderThanDays = payload.olderThanDays || 30;
    const warnings: string[] = [];
    
    if (olderThanDays < 7) {
      warnings.push('Cleaning recent data may affect analysis quality');
    }
    
    warnings.push(`Will remove snapshots older than ${olderThanDays} days`);
    
    return {
      affectedModules: ['memory', 'metabrain'],
      affectedStrategies: [],
      warnings,
      reversible: false,  // Cannot restore deleted data
    };
  },
  
  [AdminCommandType.MEMORY_REBUILD]: async () => {
    return {
      affectedModules: ['memory', 'memory_index'],
      affectedStrategies: [],
      warnings: ['Memory index will be rebuilt. This may take several minutes.'],
      estimatedDowntime: 120,
      reversible: true,
    };
  },
  
  [AdminCommandType.SYSTEM_RELOAD]: async () => {
    return {
      affectedModules: ['all'],
      affectedStrategies: ['all'],
      warnings: ['All services will be restarted', 'Active connections will be dropped'],
      estimatedDowntime: 30,
      reversible: false,
    };
  },
  
  [AdminCommandType.MARKET_MAP_RECOMPUTE]: async () => {
    return {
      affectedModules: ['market_map', 'chart'],
      affectedStrategies: [],
      warnings: [],
      reversible: true,
    };
  },
  
  [AdminCommandType.REALTIME_BROADCAST]: async (payload) => {
    return {
      affectedModules: ['realtime'],
      affectedStrategies: [],
      warnings: [`Event will be sent to channel: ${payload.channel}`],
      reversible: false,
    };
  },
};

// ═══════════════════════════════════════════════════════════════
// MAIN DRY RUN FUNCTION
// ═══════════════════════════════════════════════════════════════

/**
 * Execute dry run for a command
 */
export async function executeDryRun(command: CommandRequest): Promise<DryRunResponse> {
  // First validate the command
  const validation = validateCommand(command);
  
  if (!validation.valid) {
    return {
      command: command.type,
      valid: false,
      impact: {
        affectedModules: [],
        affectedStrategies: [],
        warnings: [],
        reversible: false,
      },
      errors: validation.errors,
    };
  }
  
  // Get impact calculator
  const calculator = impactCalculators[command.type];
  
  let impact: DryRunImpact;
  
  if (calculator) {
    impact = await calculator(command.payload);
  } else {
    // Default impact for commands without specific calculator
    impact = {
      affectedModules: [],
      affectedStrategies: [],
      warnings: ['No impact simulation available for this command'],
      reversible: true,
    };
  }
  
  // Add validation warnings to impact
  impact.warnings = [...(impact.warnings || []), ...validation.warnings];
  
  return {
    command: command.type,
    valid: true,
    impact,
  };
}

/**
 * Get estimated impact summary
 */
export function getImpactSummary(impact: DryRunImpact): string {
  const parts: string[] = [];
  
  if (impact.affectedModules.length > 0) {
    parts.push(`Affects ${impact.affectedModules.length} module(s)`);
  }
  
  if (impact.affectedStrategies.length > 0) {
    parts.push(`Affects ${impact.affectedStrategies.length} strategy(ies)`);
  }
  
  if (impact.riskChange !== undefined && impact.riskChange !== 0) {
    const direction = impact.riskChange > 0 ? 'increase' : 'decrease';
    parts.push(`Risk ${direction}: ${Math.abs(impact.riskChange * 100).toFixed(0)}%`);
  }
  
  if (impact.estimatedDowntime) {
    parts.push(`Downtime: ~${impact.estimatedDowntime}s`);
  }
  
  if (!impact.reversible) {
    parts.push('⚠️ NOT REVERSIBLE');
  }
  
  return parts.join(' | ');
}
