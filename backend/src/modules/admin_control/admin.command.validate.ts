/**
 * Phase 3 — Command Validation
 * ==============================
 * Validates admin commands before execution
 */

import {
  AdminCommandType,
  CommandRequest,
  ValidationResult,
  RiskMode,
  AnalysisMode,
} from './admin.command.types.js';

// ═══════════════════════════════════════════════════════════════
// VALID VALUES
// ═══════════════════════════════════════════════════════════════

const VALID_RISK_MODES: RiskMode[] = ['CONSERVATIVE', 'NORMAL', 'AGGRESSIVE', 'SAFE'];
const VALID_ANALYSIS_MODES: AnalysisMode[] = ['QUICK_SCAN', 'STANDARD', 'DEEP_MARKET', 'FULL_ANALYSIS'];

const VALID_MODULES = [
  'ta', 'liquidity', 'context', 'regime', 'scenario',
  'memory', 'fractal', 'physics', 'state', 'graph',
  'market_map', 'decision', 'execution', 'metabrain'
];

const VALID_STRATEGIES = [
  'breakout', 'mean_reversion', 'trend_follow', 'momentum',
  'range_bound', 'liquidity_sweep', 'harmonic', 'divergence'
];

const VALID_CHANNELS = ['chart', 'signals', 'system', 'regime', 'metabrain'];

// ═══════════════════════════════════════════════════════════════
// VALIDATION RULES
// ═══════════════════════════════════════════════════════════════

type ValidationRule = (payload: Record<string, any>) => ValidationResult;

const validationRules: Partial<Record<AdminCommandType, ValidationRule>> = {
  
  [AdminCommandType.SET_RISK_MODE]: (payload) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (!payload.riskMode) {
      errors.push('riskMode is required');
    } else if (!VALID_RISK_MODES.includes(payload.riskMode)) {
      errors.push(`Invalid riskMode. Valid: ${VALID_RISK_MODES.join(', ')}`);
    }
    
    if (payload.riskMode === 'AGGRESSIVE') {
      warnings.push('AGGRESSIVE mode increases risk exposure significantly');
    }
    
    return { valid: errors.length === 0, errors, warnings };
  },
  
  [AdminCommandType.SET_ANALYSIS_MODE]: (payload) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (!payload.analysisMode) {
      errors.push('analysisMode is required');
    } else if (!VALID_ANALYSIS_MODES.includes(payload.analysisMode)) {
      errors.push(`Invalid analysisMode. Valid: ${VALID_ANALYSIS_MODES.join(', ')}`);
    }
    
    if (payload.analysisMode === 'FULL_ANALYSIS') {
      warnings.push('FULL_ANALYSIS mode may increase latency');
    }
    
    return { valid: errors.length === 0, errors, warnings };
  },
  
  [AdminCommandType.TOGGLE_SAFE_MODE]: (payload) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (typeof payload.enabled !== 'boolean') {
      errors.push('enabled must be a boolean');
    }
    
    if (payload.enabled === true) {
      warnings.push('Safe mode will reduce all risk exposure');
    }
    
    return { valid: errors.length === 0, errors, warnings };
  },
  
  [AdminCommandType.ENABLE_STRATEGY]: (payload) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (!payload.strategy) {
      errors.push('strategy is required');
    } else if (!VALID_STRATEGIES.includes(payload.strategy)) {
      warnings.push(`Unknown strategy: ${payload.strategy}. Proceeding anyway.`);
    }
    
    return { valid: errors.length === 0, errors, warnings };
  },
  
  [AdminCommandType.DISABLE_STRATEGY]: (payload) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (!payload.strategy) {
      errors.push('strategy is required');
    }
    
    return { valid: errors.length === 0, errors, warnings };
  },
  
  [AdminCommandType.MODULE_SOFT_GATE]: (payload) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (!payload.module) {
      errors.push('module is required');
    } else if (!VALID_MODULES.includes(payload.module)) {
      errors.push(`Invalid module. Valid: ${VALID_MODULES.join(', ')}`);
    }
    
    if (payload.module === 'metabrain') {
      warnings.push('Gating metabrain may affect system coordination');
    }
    
    return { valid: errors.length === 0, errors, warnings };
  },
  
  [AdminCommandType.MODULE_HARD_GATE]: (payload) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (!payload.module) {
      errors.push('module is required');
    } else if (!VALID_MODULES.includes(payload.module)) {
      errors.push(`Invalid module. Valid: ${VALID_MODULES.join(', ')}`);
    }
    
    warnings.push('Hard gate will completely disable the module');
    
    if (payload.module === 'ta' || payload.module === 'decision') {
      warnings.push('WARNING: This is a core module. Proceed with caution.');
    }
    
    return { valid: errors.length === 0, errors, warnings };
  },
  
  [AdminCommandType.SET_MODULE_WEIGHT]: (payload) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (!payload.module) {
      errors.push('module is required');
    }
    
    if (typeof payload.weight !== 'number') {
      errors.push('weight must be a number');
    } else if (payload.weight < 0 || payload.weight > 2) {
      errors.push('weight must be between 0 and 2');
    }
    
    return { valid: errors.length === 0, errors, warnings };
  },
  
  [AdminCommandType.REALTIME_BROADCAST]: (payload) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    if (!payload.channel) {
      errors.push('channel is required');
    } else if (!VALID_CHANNELS.includes(payload.channel)) {
      errors.push(`Invalid channel. Valid: ${VALID_CHANNELS.join(', ')}`);
    }
    
    return { valid: errors.length === 0, errors, warnings };
  },
  
  [AdminCommandType.MEMORY_CLEANUP]: (payload) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    warnings.push('Memory cleanup will remove old snapshots');
    
    if (payload.olderThanDays && payload.olderThanDays < 7) {
      warnings.push('Cleaning data less than 7 days old may affect analysis');
    }
    
    return { valid: errors.length === 0, errors, warnings };
  },
};

// ═══════════════════════════════════════════════════════════════
// MAIN VALIDATION FUNCTION
// ═══════════════════════════════════════════════════════════════

/**
 * Validate a command before execution
 */
export function validateCommand(command: CommandRequest): ValidationResult {
  // Check if command type is valid
  if (!Object.values(AdminCommandType).includes(command.type)) {
    return {
      valid: false,
      errors: [`Unknown command type: ${command.type}`],
      warnings: [],
    };
  }
  
  // Get validation rule for this command type
  const rule = validationRules[command.type];
  
  if (!rule) {
    // No specific validation, allow with warning
    return {
      valid: true,
      errors: [],
      warnings: [`No validation rules for ${command.type}`],
    };
  }
  
  return rule(command.payload);
}

/**
 * Check if command type is dangerous (requires confirmation)
 */
export function isDangerousCommand(type: AdminCommandType): boolean {
  const dangerousCommands = [
    AdminCommandType.MODULE_HARD_GATE,
    AdminCommandType.MEMORY_CLEANUP,
    AdminCommandType.SYSTEM_RELOAD,
    AdminCommandType.SET_RISK_MODE,
  ];
  
  return dangerousCommands.includes(type);
}

/**
 * Get required payload fields for command type
 */
export function getRequiredFields(type: AdminCommandType): string[] {
  const fieldMap: Partial<Record<AdminCommandType, string[]>> = {
    [AdminCommandType.SET_RISK_MODE]: ['riskMode'],
    [AdminCommandType.SET_ANALYSIS_MODE]: ['analysisMode'],
    [AdminCommandType.TOGGLE_SAFE_MODE]: ['enabled'],
    [AdminCommandType.ENABLE_STRATEGY]: ['strategy'],
    [AdminCommandType.DISABLE_STRATEGY]: ['strategy'],
    [AdminCommandType.MODULE_SOFT_GATE]: ['module'],
    [AdminCommandType.MODULE_HARD_GATE]: ['module'],
    [AdminCommandType.MODULE_ACTIVATE]: ['module'],
    [AdminCommandType.SET_MODULE_WEIGHT]: ['module', 'weight'],
    [AdminCommandType.REALTIME_BROADCAST]: ['channel'],
  };
  
  return fieldMap[type] || [];
}
