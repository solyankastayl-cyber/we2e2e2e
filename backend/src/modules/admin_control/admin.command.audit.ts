/**
 * Phase 3 — Audit Trail
 * =======================
 * Logs all admin commands for history and accountability
 */

import { v4 as uuidv4 } from 'uuid';
import {
  AdminCommand,
  AuditRecord,
  CommandStatus,
  DryRunImpact,
} from './admin.command.types.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY AUDIT STORAGE (in prod would use MongoDB)
// ═══════════════════════════════════════════════════════════════

const auditLog: AuditRecord[] = [];
const commandMap: Map<string, AdminCommand> = new Map();

// ═══════════════════════════════════════════════════════════════
// AUDIT FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save audit record for a command
 */
export async function saveAuditRecord(
  command: AdminCommand,
  dryRunImpact?: DryRunImpact
): Promise<AuditRecord> {
  const record: AuditRecord = {
    id: `audit_${uuidv4().slice(0, 8)}`,
    commandId: command.id,
    type: command.type,
    actor: command.actor,
    ts: command.ts,
    payload: command.payload,
    reason: command.reason,
    dryRunImpact,
    status: command.status,
    previousState: command.previousState,
    newState: command.result,
    duration: Date.now() - command.ts,
    error: command.error,
  };
  
  auditLog.push(record);
  commandMap.set(command.id, command);
  
  // Keep only last 1000 records in memory
  if (auditLog.length > 1000) {
    auditLog.shift();
  }
  
  console.log(`[Audit] ${command.type} by ${command.actor}: ${command.status}`);
  
  return record;
}

/**
 * Get command by ID
 */
export async function getCommandById(commandId: string): Promise<AdminCommand | null> {
  return commandMap.get(commandId) || null;
}

/**
 * Update command status
 */
export async function updateCommandStatus(
  commandId: string,
  status: CommandStatus,
  error?: string
): Promise<void> {
  const command = commandMap.get(commandId);
  if (command) {
    command.status = status;
    if (error) command.error = error;
  }
  
  // Also update audit log
  const record = auditLog.find(r => r.commandId === commandId);
  if (record) {
    record.status = status;
    if (error) record.error = error;
  }
}

/**
 * Get all audit records
 */
export async function getAuditRecords(options?: {
  limit?: number;
  offset?: number;
  actor?: string;
  status?: CommandStatus;
  fromTs?: number;
  toTs?: number;
}): Promise<{ records: AuditRecord[]; total: number }> {
  let filtered = [...auditLog];
  
  // Apply filters
  if (options?.actor) {
    filtered = filtered.filter(r => r.actor === options.actor);
  }
  
  if (options?.status) {
    filtered = filtered.filter(r => r.status === options.status);
  }
  
  if (options?.fromTs) {
    filtered = filtered.filter(r => r.ts >= options.fromTs!);
  }
  
  if (options?.toTs) {
    filtered = filtered.filter(r => r.ts <= options.toTs!);
  }
  
  // Sort by timestamp descending (newest first)
  filtered.sort((a, b) => b.ts - a.ts);
  
  const total = filtered.length;
  
  // Apply pagination
  const offset = options?.offset || 0;
  const limit = options?.limit || 50;
  
  filtered = filtered.slice(offset, offset + limit);
  
  return { records: filtered, total };
}

/**
 * Get recent commands for a specific type
 */
export async function getRecentCommandsByType(
  type: string,
  limit: number = 10
): Promise<AuditRecord[]> {
  return auditLog
    .filter(r => r.type === type)
    .sort((a, b) => b.ts - a.ts)
    .slice(0, limit);
}

/**
 * Get command history for an actor
 */
export async function getActorHistory(
  actor: string,
  limit: number = 50
): Promise<AuditRecord[]> {
  return auditLog
    .filter(r => r.actor === actor)
    .sort((a, b) => b.ts - a.ts)
    .slice(0, limit);
}

/**
 * Get daily command count
 */
export function getDailyCommandCount(): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayTs = today.getTime();
  
  return auditLog.filter(r => r.ts >= todayTs).length;
}

/**
 * Get audit statistics
 */
export async function getAuditStats(): Promise<{
  total: number;
  today: number;
  executed: number;
  failed: number;
  rolledBack: number;
}> {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayTs = today.getTime();
  
  const todayRecords = auditLog.filter(r => r.ts >= todayTs);
  
  return {
    total: auditLog.length,
    today: todayRecords.length,
    executed: auditLog.filter(r => r.status === CommandStatus.EXECUTED).length,
    failed: auditLog.filter(r => r.status === CommandStatus.FAILED).length,
    rolledBack: auditLog.filter(r => r.status === CommandStatus.ROLLED_BACK).length,
  };
}

/**
 * Clear audit log (for testing)
 */
export function clearAuditLog(): void {
  auditLog.length = 0;
  commandMap.clear();
}
