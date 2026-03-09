/**
 * Phase 3 — Admin Control Plane Types
 * =====================================
 * Command-based admin system with audit trail,
 * dry-run, rollback, and override registry.
 */

// ═══════════════════════════════════════════════════════════════
// COMMAND TYPES
// ═══════════════════════════════════════════════════════════════

export enum AdminCommandType {
  // MetaBrain Control
  SET_RISK_MODE = 'SET_RISK_MODE',
  SET_ANALYSIS_MODE = 'SET_ANALYSIS_MODE',
  TOGGLE_SAFE_MODE = 'TOGGLE_SAFE_MODE',
  METABRAIN_RECOMPUTE = 'METABRAIN_RECOMPUTE',

  // Strategy Control
  ENABLE_STRATEGY = 'ENABLE_STRATEGY',
  DISABLE_STRATEGY = 'DISABLE_STRATEGY',
  SET_STRATEGY_WEIGHT = 'SET_STRATEGY_WEIGHT',

  // Module Control
  MODULE_SOFT_GATE = 'MODULE_SOFT_GATE',
  MODULE_HARD_GATE = 'MODULE_HARD_GATE',
  MODULE_ACTIVATE = 'MODULE_ACTIVATE',
  SET_MODULE_WEIGHT = 'SET_MODULE_WEIGHT',

  // Memory Control
  MEMORY_REBUILD = 'MEMORY_REBUILD',
  MEMORY_CLEANUP = 'MEMORY_CLEANUP',
  MEMORY_SNAPSHOT = 'MEMORY_SNAPSHOT',

  // Market Map Control
  MARKET_MAP_RECOMPUTE = 'MARKET_MAP_RECOMPUTE',

  // System Control
  SYSTEM_RELOAD = 'SYSTEM_RELOAD',
  SYSTEM_PAUSE = 'SYSTEM_PAUSE',
  SYSTEM_RESUME = 'SYSTEM_RESUME',

  // Realtime Control
  REALTIME_BROADCAST = 'REALTIME_BROADCAST',
  REALTIME_CLEAR_CHANNEL = 'REALTIME_CLEAR_CHANNEL',
}

// ═══════════════════════════════════════════════════════════════
// COMMAND STATUS
// ═══════════════════════════════════════════════════════════════

export enum CommandStatus {
  PENDING = 'PENDING',
  VALIDATED = 'VALIDATED',
  EXECUTED = 'EXECUTED',
  FAILED = 'FAILED',
  ROLLED_BACK = 'ROLLED_BACK',
}

// ═══════════════════════════════════════════════════════════════
// COMMAND INTERFACES
// ═══════════════════════════════════════════════════════════════

export interface AdminCommand {
  id: string;
  type: AdminCommandType;
  payload: Record<string, any>;
  reason?: string;
  actor: string;
  ts: number;
  status: CommandStatus;
  previousState?: Record<string, any>;  // For rollback
  result?: Record<string, any>;
  error?: string;
}

export interface CommandRequest {
  type: AdminCommandType;
  payload: Record<string, any>;
  reason?: string;
  actor?: string;
}

export interface CommandResponse {
  commandId: string;
  status: CommandStatus;
  result?: Record<string, any>;
  error?: string;
}

// ═══════════════════════════════════════════════════════════════
// DRY RUN
// ═══════════════════════════════════════════════════════════════

export interface DryRunImpact {
  affectedModules: string[];
  affectedStrategies: string[];
  riskChange?: number;
  warnings: string[];
  estimatedDowntime?: number;
  reversible: boolean;
}

export interface DryRunResponse {
  command: AdminCommandType;
  valid: boolean;
  impact: DryRunImpact;
  errors?: string[];
}

// ═══════════════════════════════════════════════════════════════
// VALIDATION
// ═══════════════════════════════════════════════════════════════

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

// ═══════════════════════════════════════════════════════════════
// OVERRIDE REGISTRY
// ═══════════════════════════════════════════════════════════════

export interface ManualOverride {
  id: string;
  scope: 'metabrain' | 'module' | 'strategy' | 'system';
  field: string;
  value: any;
  previousValue?: any;
  reason?: string;
  actor: string;
  createdAt: number;
  expiresAt?: number;  // Optional expiration
  active: boolean;
}

export interface OverrideRequest {
  scope: 'metabrain' | 'module' | 'strategy' | 'system';
  field: string;
  value: any;
  reason?: string;
  expiresIn?: number;  // ms
}

// ═══════════════════════════════════════════════════════════════
// AUDIT RECORD
// ═══════════════════════════════════════════════════════════════

export interface AuditRecord {
  id: string;
  commandId: string;
  type: AdminCommandType;
  actor: string;
  ts: number;
  payload: Record<string, any>;
  reason?: string;
  dryRunImpact?: DryRunImpact;
  status: CommandStatus;
  previousState?: Record<string, any>;
  newState?: Record<string, any>;
  duration?: number;
  error?: string;
}

// ═══════════════════════════════════════════════════════════════
// SYSTEM STATUS
// ═══════════════════════════════════════════════════════════════

export interface SystemStatus {
  uptime: number;
  status: 'RUNNING' | 'PAUSED' | 'DEGRADED';
  wsConnections: number;
  signalsToday: number;
  commandsToday: number;
  activeOverrides: number;
  lastCommandAt?: number;
}

export interface ModuleStatus {
  name: string;
  status: 'ACTIVE' | 'SOFT_GATED' | 'HARD_GATED';
  weight: number;
  lastUpdated: number;
}

export interface StrategyStatus {
  name: string;
  active: boolean;
  weight: number;
  signalsToday: number;
}

// ═══════════════════════════════════════════════════════════════
// RISK MODES
// ═══════════════════════════════════════════════════════════════

export type RiskMode = 'CONSERVATIVE' | 'NORMAL' | 'AGGRESSIVE' | 'SAFE';
export type AnalysisMode = 'QUICK_SCAN' | 'STANDARD' | 'DEEP_MARKET' | 'FULL_ANALYSIS';

// ═══════════════════════════════════════════════════════════════
// COMMAND PAYLOADS
// ═══════════════════════════════════════════════════════════════

export interface SetRiskModePayload {
  riskMode: RiskMode;
}

export interface SetAnalysisModePayload {
  analysisMode: AnalysisMode;
}

export interface ToggleSafeModePayload {
  enabled: boolean;
}

export interface StrategyPayload {
  strategy: string;
  weight?: number;
}

export interface ModuleGatePayload {
  module: string;
  weight?: number;
}

export interface RealtimeBroadcastPayload {
  channel: string;
  event?: string;
  data?: Record<string, any>;
}
