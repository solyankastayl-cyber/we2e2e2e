/**
 * Phase 3 — Override Registry
 * =============================
 * Manages manual overrides that prevent MetaBrain from auto-reverting changes
 */

import { v4 as uuidv4 } from 'uuid';
import {
  ManualOverride,
  OverrideRequest,
  AdminCommand,
  AdminCommandType,
} from './admin.command.types.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY OVERRIDE STORAGE (in prod would use MongoDB)
// ═══════════════════════════════════════════════════════════════

const overrides: Map<string, ManualOverride> = new Map();
const commandOverrideMap: Map<string, string> = new Map();  // commandId -> overrideId

// ═══════════════════════════════════════════════════════════════
// OVERRIDE FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Create a new override
 */
export async function createOverride(request: OverrideRequest, actor: string = 'admin'): Promise<ManualOverride> {
  const id = `ovr_${uuidv4().slice(0, 8)}`;
  
  const override: ManualOverride = {
    id,
    scope: request.scope,
    field: request.field,
    value: request.value,
    reason: request.reason,
    actor,
    createdAt: Date.now(),
    expiresAt: request.expiresIn ? Date.now() + request.expiresIn : undefined,
    active: true,
  };
  
  overrides.set(id, override);
  
  console.log(`[Override] Created: ${request.scope}.${request.field} = ${JSON.stringify(request.value)}`);
  
  return override;
}

/**
 * Create override from command execution
 */
export async function createOverrideFromCommand(command: AdminCommand): Promise<ManualOverride | null> {
  // Map command types to override scope/field
  const mapping: Partial<Record<AdminCommandType, { scope: ManualOverride['scope']; field: string }>> = {
    [AdminCommandType.SET_RISK_MODE]: { scope: 'metabrain', field: 'riskMode' },
    [AdminCommandType.SET_ANALYSIS_MODE]: { scope: 'metabrain', field: 'analysisMode' },
    [AdminCommandType.TOGGLE_SAFE_MODE]: { scope: 'metabrain', field: 'safeMode' },
    [AdminCommandType.MODULE_SOFT_GATE]: { scope: 'module', field: command.payload.module },
    [AdminCommandType.MODULE_HARD_GATE]: { scope: 'module', field: command.payload.module },
    [AdminCommandType.DISABLE_STRATEGY]: { scope: 'strategy', field: command.payload.strategy },
  };
  
  const config = mapping[command.type];
  if (!config) return null;
  
  // Get value from command result or payload
  const value = command.result || command.payload;
  
  const override = await createOverride({
    scope: config.scope,
    field: config.field,
    value,
    reason: command.reason || `Command ${command.id}`,
    expiresIn: 24 * 60 * 60 * 1000,  // Default 24h expiration
  }, command.actor);
  
  // Map command to override for rollback
  commandOverrideMap.set(command.id, override.id);
  
  return override;
}

/**
 * Check if override exists for scope.field
 */
export async function checkOverride(scope: string, field: string): Promise<ManualOverride | null> {
  // Clean expired overrides first
  await cleanExpiredOverrides();
  
  for (const override of overrides.values()) {
    if (override.scope === scope && override.field === field && override.active) {
      return override;
    }
  }
  
  return null;
}

/**
 * Get override by ID
 */
export async function getOverrideById(id: string): Promise<ManualOverride | null> {
  return overrides.get(id) || null;
}

/**
 * Get all active overrides
 */
export async function getActiveOverrides(): Promise<ManualOverride[]> {
  await cleanExpiredOverrides();
  
  return Array.from(overrides.values())
    .filter(o => o.active)
    .sort((a, b) => b.createdAt - a.createdAt);
}

/**
 * Get overrides by scope
 */
export async function getOverridesByScope(scope: string): Promise<ManualOverride[]> {
  await cleanExpiredOverrides();
  
  return Array.from(overrides.values())
    .filter(o => o.scope === scope && o.active);
}

/**
 * Deactivate an override
 */
export async function deactivateOverride(id: string): Promise<boolean> {
  const override = overrides.get(id);
  if (!override) return false;
  
  override.active = false;
  console.log(`[Override] Deactivated: ${override.scope}.${override.field}`);
  
  return true;
}

/**
 * Remove override completely
 */
export async function removeOverride(id: string): Promise<boolean> {
  const existed = overrides.delete(id);
  
  // Also remove from command map
  for (const [cmdId, ovrId] of commandOverrideMap.entries()) {
    if (ovrId === id) {
      commandOverrideMap.delete(cmdId);
      break;
    }
  }
  
  return existed;
}

/**
 * Remove override created by a command (for rollback)
 */
export async function removeOverrideForCommand(commandId: string): Promise<boolean> {
  const overrideId = commandOverrideMap.get(commandId);
  if (!overrideId) return false;
  
  await deactivateOverride(overrideId);
  commandOverrideMap.delete(commandId);
  
  return true;
}

/**
 * Extend override expiration
 */
export async function extendOverride(id: string, additionalMs: number): Promise<ManualOverride | null> {
  const override = overrides.get(id);
  if (!override) return null;
  
  if (override.expiresAt) {
    override.expiresAt += additionalMs;
  } else {
    override.expiresAt = Date.now() + additionalMs;
  }
  
  return override;
}

/**
 * Clean expired overrides
 */
export async function cleanExpiredOverrides(): Promise<number> {
  const now = Date.now();
  let cleaned = 0;
  
  for (const [id, override] of overrides.entries()) {
    if (override.expiresAt && override.expiresAt < now && override.active) {
      override.active = false;
      cleaned++;
      console.log(`[Override] Expired: ${override.scope}.${override.field}`);
    }
  }
  
  return cleaned;
}

/**
 * Check if MetaBrain should skip auto-adjustment for a field
 */
export async function shouldSkipAutoAdjust(scope: string, field: string): Promise<boolean> {
  const override = await checkOverride(scope, field);
  return override !== null && override.active;
}

/**
 * Get override count
 */
export function getOverrideCount(): number {
  return Array.from(overrides.values()).filter(o => o.active).length;
}

/**
 * Clear all overrides (for testing)
 */
export function clearOverrides(): void {
  overrides.clear();
  commandOverrideMap.clear();
}
