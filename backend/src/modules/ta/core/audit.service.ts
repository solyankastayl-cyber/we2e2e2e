/**
 * Decision Audit System
 * 
 * Tracks every layer of the decision pipeline for replay and debugging
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuid } from 'uuid';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface RunRecord {
  runId: string;
  asset: string;
  timeframe: string;
  window: number;
  modelId: string;
  featureSchemaVersion: string;
  timestamp: Date;
  duration?: number;
  status: 'RUNNING' | 'DONE' | 'FAILED';
  error?: string;
}

export interface AuditRecord {
  runId: string;
  layer: AuditLayer;
  timestamp: Date;
  inputHash?: string;
  outputHash?: string;
  data: Record<string, any>;
  metrics?: Record<string, number>;
}

export type AuditLayer = 
  | 'patterns'
  | 'discovery'
  | 'geometry'
  | 'gates'
  | 'graph'
  | 'regime'
  | 'ml'
  | 'stability'
  | 'scenario'
  | 'quality'
  | 'ranking';

export interface DecisionRecord {
  runId: string;
  asset: string;
  timeframe: string;
  timestamp: Date;
  
  // Top scenario
  topScenario: {
    scenarioId: string;
    patternType: string;
    direction: 'LONG' | 'SHORT';
    entry: number;
    stop: number;
    target1: number;
    target2?: number;
  };
  
  // Probabilities
  probability: number;
  ev: number;
  evBeforeML: number;
  evAfterML: number;
  
  // Multipliers
  qualityMultiplier: number;
  stabilityMultiplier: number;
  scenarioMultiplier: number;
  
  // Ranking
  ranking: Array<{
    scenarioId: string;
    patternType: string;
    finalScore: number;
  }>;
  
  // Model info
  modelId: string;
  featureSchemaVersion: string;
}

// ═══════════════════════════════════════════════════════════════
// COLLECTIONS
// ═══════════════════════════════════════════════════════════════

const COLLECTION_RUNS = 'ta_runs';
const COLLECTION_AUDIT = 'ta_decision_audit';
const COLLECTION_DECISIONS = 'ta_decisions';

// ═══════════════════════════════════════════════════════════════
// AUDIT SERVICE
// ═══════════════════════════════════════════════════════════════

export class DecisionAuditService {
  private db: Db;
  private runsCol: Collection;
  private auditCol: Collection;
  private decisionsCol: Collection;
  
  constructor(db: Db) {
    this.db = db;
    this.runsCol = db.collection(COLLECTION_RUNS);
    this.auditCol = db.collection(COLLECTION_AUDIT);
    this.decisionsCol = db.collection(COLLECTION_DECISIONS);
  }
  
  /**
   * Initialize indexes
   */
  async ensureIndexes(): Promise<void> {
    // Runs
    await this.runsCol.createIndex({ runId: 1 }, { unique: true });
    await this.runsCol.createIndex({ asset: 1, timeframe: 1, timestamp: -1 });
    await this.runsCol.createIndex({ status: 1 });
    
    // Audit
    await this.auditCol.createIndex({ runId: 1, layer: 1 });
    await this.auditCol.createIndex({ timestamp: -1 });
    
    // Decisions
    await this.decisionsCol.createIndex({ runId: 1 }, { unique: true });
    await this.decisionsCol.createIndex({ asset: 1, timeframe: 1, timestamp: -1 });
    
    console.log('[Audit] Indexes created');
  }
  
  /**
   * Start a new run
   */
  async startRun(params: {
    asset: string;
    timeframe: string;
    window: number;
    modelId: string;
    featureSchemaVersion: string;
  }): Promise<string> {
    const runId = `run_${Date.now()}_${uuid().slice(0, 8)}`;
    
    const record: RunRecord = {
      runId,
      ...params,
      timestamp: new Date(),
      status: 'RUNNING',
    };
    
    await this.runsCol.insertOne(record);
    return runId;
  }
  
  /**
   * Complete a run
   */
  async completeRun(runId: string, duration: number): Promise<void> {
    await this.runsCol.updateOne(
      { runId },
      { $set: { status: 'DONE', duration } }
    );
  }
  
  /**
   * Fail a run
   */
  async failRun(runId: string, error: string): Promise<void> {
    await this.runsCol.updateOne(
      { runId },
      { $set: { status: 'FAILED', error } }
    );
  }
  
  /**
   * Write audit record for a layer
   */
  async writeAudit(
    runId: string,
    layer: AuditLayer,
    data: Record<string, any>,
    metrics?: Record<string, number>
  ): Promise<void> {
    const record: AuditRecord = {
      runId,
      layer,
      timestamp: new Date(),
      data,
      metrics,
      inputHash: this.hashObject(data),
    };
    
    await this.auditCol.insertOne(record);
  }
  
  /**
   * Save final decision
   */
  async saveDecision(decision: DecisionRecord): Promise<void> {
    await this.decisionsCol.updateOne(
      { runId: decision.runId },
      { $set: decision },
      { upsert: true }
    );
  }
  
  /**
   * Get run by ID
   */
  async getRun(runId: string): Promise<RunRecord | null> {
    return this.runsCol.findOne({ runId }) as any;
  }
  
  /**
   * Get audit trail for run
   */
  async getAuditTrail(runId: string): Promise<AuditRecord[]> {
    return this.auditCol
      .find({ runId })
      .sort({ timestamp: 1 })
      .toArray() as any;
  }
  
  /**
   * Get decision for run
   */
  async getDecision(runId: string): Promise<DecisionRecord | null> {
    return this.decisionsCol.findOne({ runId }) as any;
  }
  
  /**
   * Get recent runs
   */
  async getRecentRuns(limit: number = 100): Promise<RunRecord[]> {
    return this.runsCol
      .find()
      .sort({ timestamp: -1 })
      .limit(limit)
      .toArray() as any;
  }
  
  /**
   * Simple hash for deterministic replay check
   */
  private hashObject(obj: any): string {
    const str = JSON.stringify(obj);
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return hash.toString(16);
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

let auditService: DecisionAuditService | null = null;

export function getDecisionAuditService(db: Db): DecisionAuditService {
  if (!auditService) {
    auditService = new DecisionAuditService(db);
  }
  return auditService;
}

export function createDecisionAuditService(db: Db): DecisionAuditService {
  return new DecisionAuditService(db);
}
