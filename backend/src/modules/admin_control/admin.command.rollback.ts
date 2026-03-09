/**
 * Phase 3 — Command Rollback Engine
 * ===================================
 * Reverts admin commands to previous state
 */

import {
  AdminCommand,
  AdminCommandType,
  CommandStatus,
  CommandResponse,
} from './admin.command.types.js';
import { getCommandById, updateCommandStatus, saveAuditRecord } from './admin.command.audit.js';
import {
  setRiskMode,
  setAnalysisMode,
  toggleSafeMode,
  setModuleStatus,
  setModuleWeight,
  enableStrategy,
  disableStrategy,
  setStrategyWeight,
  resumeSystem,
  pauseSystem,
} from './admin.state.service.js';
import { removeOverrideForCommand } from './admin.override.registry.js';

// ═══════════════════════════════════════════════════════════════
// ROLLBACK EXECUTORS
// ═══════════════════════════════════════════════════════════════

type RollbackExecutor = (previousState: Record<string, any>, payload: Record<string, any>) => Promise<void>;

const rollbackExecutors: Partial<Record<AdminCommandType, RollbackExecutor>> = {
  
  [AdminCommandType.SET_RISK_MODE]: async (previousState) => {
    if (previousState.riskMode) {
      setRiskMode(previousState.riskMode);
    }
  },
  
  [AdminCommandType.SET_ANALYSIS_MODE]: async (previousState) => {
    if (previousState.analysisMode) {
      setAnalysisMode(previousState.analysisMode);
    }
  },
  
  [AdminCommandType.TOGGLE_SAFE_MODE]: async (previousState) => {
    if (typeof previousState.safeMode === 'boolean') {
      toggleSafeMode(previousState.safeMode);
    }
  },
  
  [AdminCommandType.MODULE_SOFT_GATE]: async (previousState, payload) => {
    if (previousState.module?.status) {
      setModuleStatus(payload.module, previousState.module.status);
    } else {
      // Default to ACTIVE if no previous state
      setModuleStatus(payload.module, 'ACTIVE');
    }
  },
  
  [AdminCommandType.MODULE_HARD_GATE]: async (previousState, payload) => {
    if (previousState.module?.status) {
      setModuleStatus(payload.module, previousState.module.status);
    } else {
      setModuleStatus(payload.module, 'ACTIVE');
    }
  },
  
  [AdminCommandType.MODULE_ACTIVATE]: async (previousState, payload) => {
    if (previousState.module?.status) {
      setModuleStatus(payload.module, previousState.module.status);
    }
  },
  
  [AdminCommandType.SET_MODULE_WEIGHT]: async (previousState, payload) => {
    if (previousState.weight !== undefined) {
      setModuleWeight(payload.module, previousState.weight);
    }
  },
  
  [AdminCommandType.ENABLE_STRATEGY]: async (previousState, payload) => {
    if (previousState.active === false) {
      disableStrategy(payload.strategy);
    }
  },
  
  [AdminCommandType.DISABLE_STRATEGY]: async (previousState, payload) => {
    if (previousState.active === true) {
      enableStrategy(payload.strategy);
    }
  },
  
  [AdminCommandType.SET_STRATEGY_WEIGHT]: async (previousState, payload) => {
    if (previousState.weight !== undefined) {
      setStrategyWeight(payload.strategy, previousState.weight);
    }
  },
  
  [AdminCommandType.SYSTEM_PAUSE]: async () => {
    resumeSystem();
  },
  
  [AdminCommandType.SYSTEM_RESUME]: async () => {
    pauseSystem();
  },
};

// ═══════════════════════════════════════════════════════════════
// NON-REVERSIBLE COMMANDS
// ═══════════════════════════════════════════════════════════════

const NON_REVERSIBLE_COMMANDS = [
  AdminCommandType.MEMORY_CLEANUP,
  AdminCommandType.SYSTEM_RELOAD,
  AdminCommandType.REALTIME_BROADCAST,
];

// ═══════════════════════════════════════════════════════════════
// MAIN ROLLBACK FUNCTION
// ═══════════════════════════════════════════════════════════════

/**
 * Rollback a command by its ID
 */
export async function rollbackCommand(commandId: string): Promise<CommandResponse> {
  // Get original command
  const command = await getCommandById(commandId);
  
  if (!command) {
    return {
      commandId,
      status: CommandStatus.FAILED,
      error: 'Command not found',
    };
  }
  
  // Check if command was executed
  if (command.status !== CommandStatus.EXECUTED) {
    return {
      commandId,
      status: CommandStatus.FAILED,
      error: `Cannot rollback command with status: ${command.status}`,
    };
  }
  
  // Check if command is reversible
  if (NON_REVERSIBLE_COMMANDS.includes(command.type)) {
    return {
      commandId,
      status: CommandStatus.FAILED,
      error: `Command type ${command.type} is not reversible`,
    };
  }
  
  // Check if we have previous state
  if (!command.previousState || Object.keys(command.previousState).length === 0) {
    return {
      commandId,
      status: CommandStatus.FAILED,
      error: 'No previous state available for rollback',
    };
  }
  
  // Get rollback executor
  const executor = rollbackExecutors[command.type];
  
  if (!executor) {
    return {
      commandId,
      status: CommandStatus.FAILED,
      error: `No rollback executor for command type: ${command.type}`,
    };
  }
  
  try {
    // Execute rollback
    await executor(command.previousState, command.payload);
    
    // Update command status
    await updateCommandStatus(commandId, CommandStatus.ROLLED_BACK);
    
    // Remove any override created by this command
    await removeOverrideForCommand(commandId);
    
    // Save rollback as audit record
    const rollbackCommand: AdminCommand = {
      id: `${commandId}_rollback`,
      type: command.type,
      payload: { rollbackOf: commandId, restoredState: command.previousState },
      reason: 'Rollback requested',
      actor: 'admin',
      ts: Date.now(),
      status: CommandStatus.EXECUTED,
      previousState: command.result,
      result: command.previousState,
    };
    
    await saveAuditRecord(rollbackCommand);
    
    console.log(`[Rollback] Command ${commandId} rolled back successfully`);
    
    return {
      commandId,
      status: CommandStatus.ROLLED_BACK,
      result: {
        restoredState: command.previousState,
      },
    };
    
  } catch (err: any) {
    console.error(`[Rollback] Failed to rollback ${commandId}:`, err);
    
    return {
      commandId,
      status: CommandStatus.FAILED,
      error: `Rollback failed: ${err.message}`,
    };
  }
}

/**
 * Check if a command can be rolled back
 */
export async function canRollback(commandId: string): Promise<{
  canRollback: boolean;
  reason?: string;
}> {
  const command = await getCommandById(commandId);
  
  if (!command) {
    return { canRollback: false, reason: 'Command not found' };
  }
  
  if (command.status !== CommandStatus.EXECUTED) {
    return { canRollback: false, reason: `Command status is ${command.status}` };
  }
  
  if (NON_REVERSIBLE_COMMANDS.includes(command.type)) {
    return { canRollback: false, reason: 'Command type is not reversible' };
  }
  
  if (!command.previousState || Object.keys(command.previousState).length === 0) {
    return { canRollback: false, reason: 'No previous state saved' };
  }
  
  if (!rollbackExecutors[command.type]) {
    return { canRollback: false, reason: 'No rollback handler available' };
  }
  
  return { canRollback: true };
}

/**
 * Get rollback info for a command
 */
export async function getRollbackInfo(commandId: string): Promise<{
  command: AdminCommand | null;
  canRollback: boolean;
  previousState: Record<string, any> | null;
  reason?: string;
}> {
  const command = await getCommandById(commandId);
  
  if (!command) {
    return {
      command: null,
      canRollback: false,
      previousState: null,
      reason: 'Command not found',
    };
  }
  
  const { canRollback, reason } = await canRollback(commandId);
  
  return {
    command,
    canRollback,
    previousState: command.previousState || null,
    reason,
  };
}
