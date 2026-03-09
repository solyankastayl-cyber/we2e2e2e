/**
 * Phase 5.1 B2 — Backtest Job Schema & Types
 * 
 * Async job system for long-running backtests
 */

// ═══════════════════════════════════════════════════════════════
// Job Status
// ═══════════════════════════════════════════════════════════════

export type BacktestJobStatus = 
  | 'QUEUED' 
  | 'RUNNING' 
  | 'COMPLETED' 
  | 'FAILED' 
  | 'CANCELLED';

// ═══════════════════════════════════════════════════════════════
// Job Request
// ═══════════════════════════════════════════════════════════════

export interface BacktestJobRequest {
  assets: string[];           // ["BTCUSDT", "ETHUSDT"]
  tf: string;                 // "1D", "4H", etc.
  from: string;               // ISO date
  to: string;                 // ISO date
  seed?: number;              // determinism seed
  configHash?: string;        // config fingerprint
  warmupBars?: number;
  decisionEngine?: 'LIVE' | 'MOCK';  // B3: decision engine type
}

// ═══════════════════════════════════════════════════════════════
// Job Progress
// ═══════════════════════════════════════════════════════════════

export interface BacktestJobProgress {
  pct: number;                // 0-100
  barsDone: number;
  barsTotal: number;
  asset: string | null;       // current asset being processed
  step: string;               // current step description
  updatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// Job Error
// ═══════════════════════════════════════════════════════════════

export interface BacktestJobError {
  message: string;
  stack?: string;
  code?: string;
}

// ═══════════════════════════════════════════════════════════════
// Job Document (MongoDB)
// ═══════════════════════════════════════════════════════════════

export interface BacktestJobDoc {
  _id?: any;
  jobId: string;              // UUID
  
  status: BacktestJobStatus;
  
  createdAt: Date;
  updatedAt: Date;
  completedAt?: Date;
  
  request: BacktestJobRequest;
  
  progress: BacktestJobProgress;
  
  runId?: string;             // Link to ta_backtest_runs when created
  
  cancelRequested: boolean;
  
  error?: BacktestJobError;
}

// ═══════════════════════════════════════════════════════════════
// Create Job Input
// ═══════════════════════════════════════════════════════════════

export interface CreateJobInput {
  assets: string[];
  tf: string;
  from: string;
  to: string;
  seed?: number;
  warmupBars?: number;
  decisionEngine?: 'LIVE' | 'MOCK';
}

// ═══════════════════════════════════════════════════════════════
// Progress Callback
// ═══════════════════════════════════════════════════════════════

export interface ProgressCallback {
  (progress: {
    barsDone: number;
    barsTotal: number;
    asset: string;
    step: string;
  }): void;
}

// ═══════════════════════════════════════════════════════════════
// Cancel Check Callback
// ═══════════════════════════════════════════════════════════════

export interface CancelCheckCallback {
  (): Promise<boolean>;
}

// ═══════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════

export const JOBS_COLLECTION = 'ta_backtest_jobs';

export const JOB_LIMITS = {
  maxAssetsPerJob: 10,
  maxBarsPerAsset: 50000,
  maxConcurrentJobs: 3,
  progressUpdateIntervalMs: 1000,
};
