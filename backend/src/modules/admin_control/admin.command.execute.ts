/**
 * Phase 3 — Command Execution Engine
 * ====================================
 * Executes validated admin commands
 */

import { v4 as uuidv4 } from 'uuid';
import {
  AdminCommand,
  AdminCommandType,
  CommandRequest,
  CommandResponse,
  CommandStatus,
} from './admin.command.types.js';
import { validateCommand } from './admin.command.validate.js';
import { executeDryRun } from './admin.command.dryrun.js';
import { saveAuditRecord, getCommandById, updateCommandStatus } from './admin.command.audit.js';
import {
  setRiskMode,
  setAnalysisMode,
  toggleSafeMode,
  setModuleStatus,
  setModuleWeight,
  enableStrategy,
  disableStrategy,
  setStrategyWeight,
  pauseSystem,
  resumeSystem,
  getMetaBrainState,
  getModuleStatus,
  getStrategyStatus,
} from './admin.state.service.js';
import { checkOverride, createOverrideFromCommand } from './admin.override.registry.js';

// ═══════════════════════════════════════════════════════════════
// COMMAND EXECUTORS
// ═══════════════════════════════════════════════════════════════

type CommandExecutor = (payload: Record<string, any>) => Promise<{
  result: Record<string, any>;
  previousState: Record<string, any>;
}>;

const executors: Partial<Record<AdminCommandType, CommandExecutor>> = {
  
  [AdminCommandType.SET_RISK_MODE]: async (payload) => {
    const { previous, current } = setRiskMode(payload.riskMode);
    return {
      result: { riskMode: current },
      previousState: { riskMode: previous },
    };
  },
  
  [AdminCommandType.SET_ANALYSIS_MODE]: async (payload) => {
    const { previous, current } = setAnalysisMode(payload.analysisMode);
    return {
      result: { analysisMode: current },
      previousState: { analysisMode: previous },
    };
  },
  
  [AdminCommandType.TOGGLE_SAFE_MODE]: async (payload) => {
    const { previous, current } = toggleSafeMode(payload.enabled);
    return {
      result: { safeMode: current },
      previousState: { safeMode: previous },
    };
  },
  
  [AdminCommandType.METABRAIN_RECOMPUTE]: async () => {
    // In real system, would trigger metabrain recomputation
    const state = getMetaBrainState();
    return {
      result: { recomputed: true, state },
      previousState: {},
    };
  },
  
  [AdminCommandType.MODULE_SOFT_GATE]: async (payload) => {
    const { previous, current } = setModuleStatus(payload.module, 'SOFT_GATED');
    return {
      result: { module: current },
      previousState: previous ? { module: previous } : {},
    };
  },
  
  [AdminCommandType.MODULE_HARD_GATE]: async (payload) => {
    const { previous, current } = setModuleStatus(payload.module, 'HARD_GATED');
    return {
      result: { module: current },
      previousState: previous ? { module: previous } : {},
    };
  },
  
  [AdminCommandType.MODULE_ACTIVATE]: async (payload) => {
    const { previous, current } = setModuleStatus(payload.module, 'ACTIVE');
    return {
      result: { module: current },
      previousState: previous ? { module: previous } : {},
    };
  },
  
  [AdminCommandType.SET_MODULE_WEIGHT]: async (payload) => {
    const previous = getModuleStatus(payload.module);
    const current = setModuleWeight(payload.module, payload.weight);
    return {
      result: { module: current },
      previousState: previous ? { weight: previous.weight } : {},
    };
  },
  
  [AdminCommandType.ENABLE_STRATEGY]: async (payload) => {
    const previous = getStrategyStatus(payload.strategy);
    const current = enableStrategy(payload.strategy);
    return {
      result: { strategy: current },
      previousState: previous ? { active: previous.active } : {},
    };
  },
  
  [AdminCommandType.DISABLE_STRATEGY]: async (payload) => {
    const previous = getStrategyStatus(payload.strategy);
    const current = disableStrategy(payload.strategy);
    return {
      result: { strategy: current },
      previousState: previous ? { active: previous.active } : {},
    };
  },
  
  [AdminCommandType.SET_STRATEGY_WEIGHT]: async (payload) => {
    const previous = getStrategyStatus(payload.strategy);
    const current = setStrategyWeight(payload.strategy, payload.weight);
    return {
      result: { strategy: current },
      previousState: previous ? { weight: previous.weight } : {},
    };
  },
  
  [AdminCommandType.MEMORY_REBUILD]: async () => {
    // In real system, would trigger memory index rebuild
    return {
      result: { rebuildStarted: true, estimatedTime: 120 },
      previousState: {},
    };
  },
  
  [AdminCommandType.MEMORY_CLEANUP]: async (payload) => {
    const olderThanDays = payload.olderThanDays || 30;
    // In real system, would clean old snapshots
    return {
      result: { cleanupStarted: true, olderThanDays },
      previousState: {},
    };
  },
  
  [AdminCommandType.MEMORY_SNAPSHOT]: async () => {
    // In real system, would create memory snapshot
    return {
      result: { snapshotCreated: true, ts: Date.now() },
      previousState: {},
    };
  },
  
  [AdminCommandType.MARKET_MAP_RECOMPUTE]: async () => {
    // In real system, would trigger market map recomputation
    return {
      result: { recomputed: true },
      previousState: {},
    };
  },
  
  [AdminCommandType.SYSTEM_PAUSE]: async () => {
    pauseSystem();
    return {
      result: { status: 'PAUSED' },
      previousState: { status: 'RUNNING' },
    };
  },
  
  [AdminCommandType.SYSTEM_RESUME]: async () => {
    resumeSystem();
    return {
      result: { status: 'RUNNING' },
      previousState: { status: 'PAUSED' },
    };
  },
  
  [AdminCommandType.SYSTEM_RELOAD]: async () => {
    // In real system, would trigger service reload
    return {
      result: { reloadStarted: true },
      previousState: {},
    };
  },
  
  [AdminCommandType.REALTIME_BROADCAST]: async (payload) => {
    // In real system, would broadcast to channel
    return {
      result: { 
        broadcasted: true, 
        channel: payload.channel,
        event: payload.event || 'TEST_EVENT',
      },
      previousState: {},
    };
  },
};

// ═══════════════════════════════════════════════════════════════
// MAIN EXECUTION FUNCTION
// ═══════════════════════════════════════════════════════════════

/**
 * Execute an admin command
 */
export async function executeCommand(request: CommandRequest): Promise<CommandResponse> {
  const startTime = Date.now();
  
  // Generate command ID
  const commandId = `cmd_${uuidv4().slice(0, 8)}`;
  
  // Validate command
  const validation = validateCommand(request);
  if (!validation.valid) {
    const failedCommand: AdminCommand = {
      id: commandId,
      type: request.type,
      payload: request.payload,
      reason: request.reason,
      actor: request.actor || 'admin',
      ts: startTime,
      status: CommandStatus.FAILED,
      error: validation.errors.join('; '),
    };
    
    await saveAuditRecord(failedCommand);
    
    return {
      commandId,
      status: CommandStatus.FAILED,
      error: validation.errors.join('; '),
    };
  }
  
  // Check for manual overrides that might conflict
  const overrideCheck = await checkOverrideConflict(request);
  if (overrideCheck.conflict) {
    return {
      commandId,
      status: CommandStatus.FAILED,
      error: `Conflict with active override: ${overrideCheck.message}`,
    };
  }
  
  // Get executor
  const executor = executors[request.type];
  
  if (!executor) {
    return {
      commandId,
      status: CommandStatus.FAILED,
      error: `No executor for command type: ${request.type}`,
    };
  }
  
  // Execute dry run for impact assessment
  const dryRun = await executeDryRun(request);
  
  try {
    // Execute command
    const { result, previousState } = await executor(request.payload);
    
    const command: AdminCommand = {
      id: commandId,
      type: request.type,
      payload: request.payload,
      reason: request.reason,
      actor: request.actor || 'admin',
      ts: startTime,
      status: CommandStatus.EXECUTED,
      previousState,
      result,
    };
    
    // Save audit record
    await saveAuditRecord(command, dryRun.impact);
    
    // Create override if needed
    if (shouldCreateOverride(request.type)) {
      await createOverrideFromCommand(command);
    }
    
    return {
      commandId,
      status: CommandStatus.EXECUTED,
      result,
    };
    
  } catch (err: any) {
    const failedCommand: AdminCommand = {
      id: commandId,
      type: request.type,
      payload: request.payload,
      reason: request.reason,
      actor: request.actor || 'admin',
      ts: startTime,
      status: CommandStatus.FAILED,
      error: err.message,
    };
    
    await saveAuditRecord(failedCommand, dryRun.impact);
    
    return {
      commandId,
      status: CommandStatus.FAILED,
      error: err.message,
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

async function checkOverrideConflict(request: CommandRequest): Promise<{ conflict: boolean; message?: string }> {
  // Check if there's an active override that conflicts with this command
  const scopeMap: Partial<Record<AdminCommandType, string>> = {
    [AdminCommandType.SET_RISK_MODE]: 'metabrain',
    [AdminCommandType.SET_ANALYSIS_MODE]: 'metabrain',
    [AdminCommandType.TOGGLE_SAFE_MODE]: 'metabrain',
  };
  
  const scope = scopeMap[request.type];
  if (!scope) return { conflict: false };
  
  const fieldMap: Partial<Record<AdminCommandType, string>> = {
    [AdminCommandType.SET_RISK_MODE]: 'riskMode',
    [AdminCommandType.SET_ANALYSIS_MODE]: 'analysisMode',
    [AdminCommandType.TOGGLE_SAFE_MODE]: 'safeMode',
  };
  
  const field = fieldMap[request.type];
  if (!field) return { conflict: false };
  
  const override = await checkOverride(scope, field);
  if (override && override.active) {
    return {
      conflict: true,
      message: `Active override on ${scope}.${field} (expires: ${override.expiresAt ? new Date(override.expiresAt).toISOString() : 'never'})`,
    };
  }
  
  return { conflict: false };
}

function shouldCreateOverride(type: AdminCommandType): boolean {
  // Commands that should create overrides to prevent MetaBrain from reverting
  const overrideCommands = [
    AdminCommandType.SET_RISK_MODE,
    AdminCommandType.TOGGLE_SAFE_MODE,
    AdminCommandType.MODULE_SOFT_GATE,
    AdminCommandType.MODULE_HARD_GATE,
    AdminCommandType.DISABLE_STRATEGY,
  ];
  
  return overrideCommands.includes(type);
}

/**
 * Get command by ID (for rollback)
 */
export async function getCommand(commandId: string): Promise<AdminCommand | null> {
  return getCommandById(commandId);
}
