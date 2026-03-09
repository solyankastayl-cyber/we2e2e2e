/**
 * P1.2 — Module Gating Storage
 * 
 * MongoDB storage for module gates and gate history
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import {
  ModuleGate,
  ModuleGateStatus,
  ModuleGateHistory,
  GatingSummary
} from './learning.gating.types.js';
import { AnalysisModule, ALL_MODULES } from './module_attribution.types.js';

// ═══════════════════════════════════════════════════════════════
// SCHEMA DEFINITIONS
// ═══════════════════════════════════════════════════════════════

interface ModuleGateDoc extends Document {
  module: string;
  regime?: string;
  status: string;
  reason: string;
  score: number;
  sampleSize: number;
  avgOutcomeImpact: number;
  weight: number;
  gatedUntil?: Date;
  updatedAt: Date;
  createdAt: Date;
}

const ModuleGateSchema = new Schema<ModuleGateDoc>({
  module: { type: String, required: true, index: true },
  regime: { type: String },
  status: { 
    type: String, 
    enum: ['ACTIVE', 'SOFT_GATED', 'HARD_GATED'],
    required: true 
  },
  reason: { type: String, required: true },
  score: { type: Number, required: true },
  sampleSize: { type: Number, required: true },
  avgOutcomeImpact: { type: Number, required: true },
  weight: { type: Number, required: true },
  gatedUntil: { type: Date },
  updatedAt: { type: Date, default: Date.now },
  createdAt: { type: Date, default: Date.now }
}, {
  collection: 'ta_module_gates'
});

// Compound index for module + regime uniqueness
ModuleGateSchema.index({ module: 1, regime: 1 }, { unique: true });

interface ModuleGateHistoryDoc extends Document {
  module: string;
  regime?: string;
  previousStatus: string;
  newStatus: string;
  reason: string;
  score: number;
  changedAt: Date;
  changedBy: string;
}

const ModuleGateHistorySchema = new Schema<ModuleGateHistoryDoc>({
  module: { type: String, required: true, index: true },
  regime: { type: String },
  previousStatus: { type: String, required: true },
  newStatus: { type: String, required: true },
  reason: { type: String, required: true },
  score: { type: Number, required: true },
  changedAt: { type: Date, default: Date.now, index: true },
  changedBy: { type: String, enum: ['AUTO', 'MANUAL', 'GOVERNANCE'], required: true }
}, {
  collection: 'ta_module_gate_history'
});

// ═══════════════════════════════════════════════════════════════
// MODELS
// ═══════════════════════════════════════════════════════════════

export const ModuleGateModel: Model<ModuleGateDoc> = mongoose.models.ModuleGate ||
  mongoose.model<ModuleGateDoc>('ModuleGate', ModuleGateSchema);

export const ModuleGateHistoryModel: Model<ModuleGateHistoryDoc> = mongoose.models.ModuleGateHistory ||
  mongoose.model<ModuleGateHistoryDoc>('ModuleGateHistory', ModuleGateHistorySchema);

// ═══════════════════════════════════════════════════════════════
// GATE STORAGE FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save or update a module gate
 */
export async function saveModuleGate(gate: ModuleGate): Promise<void> {
  await ModuleGateModel.findOneAndUpdate(
    { module: gate.module, regime: gate.regime ?? null },
    {
      status: gate.status,
      reason: gate.reason,
      score: gate.score,
      sampleSize: gate.sampleSize,
      avgOutcomeImpact: gate.avgOutcomeImpact,
      weight: gate.weight,
      gatedUntil: gate.gatedUntil ? new Date(gate.gatedUntil) : undefined,
      updatedAt: new Date(gate.updatedAt)
    },
    { upsert: true, new: true }
  );
}

/**
 * Save multiple gates
 */
export async function saveModuleGates(gates: ModuleGate[]): Promise<void> {
  const operations = gates.map(gate => ({
    updateOne: {
      filter: { module: gate.module, regime: gate.regime ?? null },
      update: {
        $set: {
          status: gate.status,
          reason: gate.reason,
          score: gate.score,
          sampleSize: gate.sampleSize,
          avgOutcomeImpact: gate.avgOutcomeImpact,
          weight: gate.weight,
          gatedUntil: gate.gatedUntil ? new Date(gate.gatedUntil) : undefined,
          updatedAt: new Date(gate.updatedAt)
        },
        $setOnInsert: {
          createdAt: new Date()
        }
      },
      upsert: true
    }
  }));
  
  await ModuleGateModel.bulkWrite(operations);
}

/**
 * Get gate for a module
 */
export async function getModuleGate(
  module: AnalysisModule,
  regime?: string
): Promise<ModuleGate | null> {
  const doc = await ModuleGateModel.findOne({
    module,
    regime: regime ?? null
  });
  
  if (!doc) return null;
  
  return {
    module: doc.module as AnalysisModule,
    regime: doc.regime,
    status: doc.status as ModuleGateStatus,
    reason: doc.reason,
    score: doc.score,
    sampleSize: doc.sampleSize,
    avgOutcomeImpact: doc.avgOutcomeImpact,
    weight: doc.weight,
    gatedUntil: doc.gatedUntil?.getTime(),
    updatedAt: doc.updatedAt.getTime(),
    createdAt: doc.createdAt.getTime()
  };
}

/**
 * Get all gates
 */
export async function getAllModuleGates(regime?: string): Promise<ModuleGate[]> {
  const query = regime !== undefined 
    ? { $or: [{ regime: regime }, { regime: null }] }
    : {};
  
  const docs = await ModuleGateModel.find(query).lean();
  
  return docs.map(doc => ({
    module: doc.module as AnalysisModule,
    regime: doc.regime,
    status: doc.status as ModuleGateStatus,
    reason: doc.reason,
    score: doc.score,
    sampleSize: doc.sampleSize,
    avgOutcomeImpact: doc.avgOutcomeImpact,
    weight: doc.weight,
    gatedUntil: doc.gatedUntil?.getTime(),
    updatedAt: doc.updatedAt.getTime(),
    createdAt: doc.createdAt.getTime()
  }));
}

/**
 * Get gates as Map
 */
export async function getModuleGatesMap(regime?: string): Promise<Map<string, ModuleGate>> {
  const gates = await getAllModuleGates(regime);
  const map = new Map<string, ModuleGate>();
  
  for (const gate of gates) {
    const key = gate.regime ? `${gate.module}:${gate.regime}` : gate.module;
    map.set(key, gate);
  }
  
  return map;
}

// ═══════════════════════════════════════════════════════════════
// GATE HISTORY FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save gate history entry
 */
export async function saveGateHistory(history: ModuleGateHistory): Promise<void> {
  await ModuleGateHistoryModel.create({
    module: history.module,
    regime: history.regime,
    previousStatus: history.previousStatus,
    newStatus: history.newStatus,
    reason: history.reason,
    score: history.score,
    changedAt: history.changedAt,
    changedBy: history.changedBy
  });
}

/**
 * Get gate history for a module
 */
export async function getGateHistory(
  module: AnalysisModule,
  regime?: string,
  limit: number = 50
): Promise<ModuleGateHistory[]> {
  const query: Record<string, any> = { module };
  if (regime) query.regime = regime;
  
  const docs = await ModuleGateHistoryModel
    .find(query)
    .sort({ changedAt: -1 })
    .limit(limit)
    .lean();
  
  return docs.map(doc => ({
    module: doc.module as AnalysisModule,
    regime: doc.regime,
    previousStatus: doc.previousStatus as ModuleGateStatus,
    newStatus: doc.newStatus as ModuleGateStatus,
    reason: doc.reason,
    score: doc.score,
    changedAt: doc.changedAt,
    changedBy: doc.changedBy as 'AUTO' | 'MANUAL' | 'GOVERNANCE'
  }));
}

/**
 * Get recent gate changes (for governance check)
 */
export async function getRecentGateChanges(hours: number = 24): Promise<ModuleGateHistory[]> {
  const since = new Date(Date.now() - hours * 60 * 60 * 1000);
  
  const docs = await ModuleGateHistoryModel
    .find({ changedAt: { $gte: since } })
    .sort({ changedAt: -1 })
    .lean();
  
  return docs.map(doc => ({
    module: doc.module as AnalysisModule,
    regime: doc.regime,
    previousStatus: doc.previousStatus as ModuleGateStatus,
    newStatus: doc.newStatus as ModuleGateStatus,
    reason: doc.reason,
    score: doc.score,
    changedAt: doc.changedAt,
    changedBy: doc.changedBy as 'AUTO' | 'MANUAL' | 'GOVERNANCE'
  }));
}

/**
 * Count recent gate changes for a module
 */
export async function countRecentGateChanges(
  module: AnalysisModule,
  hours: number = 24
): Promise<number> {
  const since = new Date(Date.now() - hours * 60 * 60 * 1000);
  
  return ModuleGateHistoryModel.countDocuments({
    module,
    changedAt: { $gte: since }
  });
}

// ═══════════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Reset all gates to ACTIVE
 */
export async function resetAllGates(): Promise<number> {
  const result = await ModuleGateModel.updateMany(
    {},
    {
      $set: {
        status: 'ACTIVE',
        reason: 'Manual reset',
        gatedUntil: null,
        updatedAt: new Date()
      }
    }
  );
  
  return result.modifiedCount;
}

/**
 * Delete expired hard gates (past gatedUntil)
 */
export async function cleanupExpiredGates(): Promise<number> {
  const now = new Date();
  
  const result = await ModuleGateModel.updateMany(
    {
      status: 'HARD_GATED',
      gatedUntil: { $lt: now }
    },
    {
      $set: {
        status: 'ACTIVE',
        reason: 'Hard gate duration expired',
        gatedUntil: null,
        updatedAt: now
      }
    }
  );
  
  return result.modifiedCount;
}
