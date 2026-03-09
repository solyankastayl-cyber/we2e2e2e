/**
 * MetaBrain v2.1 — Storage
 * 
 * MongoDB persistence for module attribution and weights
 */

import mongoose, { Schema, Document } from 'mongoose';
import {
  AnalysisModule,
  ModuleContribution,
  ModuleWeight,
  ModuleWeightHistory,
  ModuleAttributionResult
} from './module_attribution.types.js';

// ═══════════════════════════════════════════════════════════════
// MODULE ATTRIBUTION SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IModuleAttribution extends Document {
  module: string;
  asset?: string;
  timeframe?: string;
  regime?: string;
  winRate: number;
  avgR: number;
  profitFactor: number;
  sharpe: number;
  sampleSize: number;
  confidence: number;
  edgeScore: number;
  impact: string;
  calculatedAt: Date;
}

const ModuleAttributionSchema = new Schema<IModuleAttribution>({
  module: { type: String, required: true, index: true },
  asset: { type: String, index: true },
  timeframe: { type: String, index: true },
  regime: { type: String, index: true },
  winRate: { type: Number, required: true },
  avgR: { type: Number, required: true },
  profitFactor: { type: Number, required: true },
  sharpe: { type: Number, required: true },
  sampleSize: { type: Number, required: true },
  confidence: { type: Number, required: true },
  edgeScore: { type: Number, required: true, index: true },
  impact: { type: String, required: true, enum: ['POSITIVE', 'NEUTRAL', 'NEGATIVE'] },
  calculatedAt: { type: Date, required: true }
}, {
  collection: 'ta_module_attribution',
  timestamps: true
});

ModuleAttributionSchema.index({ module: 1, regime: 1 }, { unique: false });
ModuleAttributionSchema.index({ edgeScore: -1 });

export const ModuleAttributionModel = mongoose.model<IModuleAttribution>('ModuleAttribution', ModuleAttributionSchema);

// ═══════════════════════════════════════════════════════════════
// MODULE WEIGHTS SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IModuleWeight extends Document {
  module: string;
  weight: number;
  rawWeight: number;
  confidence: number;
  basedOnSample: number;
  basedOnEdgeScore: number;
  regime?: string;
  updatedAt: Date;
}

const ModuleWeightSchema = new Schema<IModuleWeight>({
  module: { type: String, required: true, index: true },
  weight: { type: Number, required: true },
  rawWeight: { type: Number, required: true },
  confidence: { type: Number, required: true },
  basedOnSample: { type: Number, required: true },
  basedOnEdgeScore: { type: Number, required: true },
  regime: { type: String, index: true },
  updatedAt: { type: Date, required: true }
}, {
  collection: 'ta_module_weights',
  timestamps: true
});

ModuleWeightSchema.index({ module: 1, regime: 1 }, { unique: true });

export const ModuleWeightModel = mongoose.model<IModuleWeight>('ModuleWeight', ModuleWeightSchema);

// ═══════════════════════════════════════════════════════════════
// MODULE WEIGHT HISTORY SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IModuleWeightHistory extends Document {
  module: string;
  weight: number;
  regime?: string;
  reason: string;
  changedAt: Date;
}

const ModuleWeightHistorySchema = new Schema<IModuleWeightHistory>({
  module: { type: String, required: true, index: true },
  weight: { type: Number, required: true },
  regime: { type: String, index: true },
  reason: { type: String, required: true },
  changedAt: { type: Date, required: true, index: true }
}, {
  collection: 'ta_module_weight_history',
  timestamps: true
});

ModuleWeightHistorySchema.index({ module: 1, changedAt: -1 });

export const ModuleWeightHistoryModel = mongoose.model<IModuleWeightHistory>('ModuleWeightHistory', ModuleWeightHistorySchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save module attributions
 */
export async function saveModuleAttributions(contributions: ModuleContribution[]): Promise<void> {
  if (contributions.length === 0) return;
  
  const operations = contributions.map(contrib => ({
    updateOne: {
      filter: { module: contrib.module },
      update: { $set: contrib },
      upsert: true
    }
  }));
  
  await ModuleAttributionModel.bulkWrite(operations);
}

/**
 * Get module attributions
 */
export async function getModuleAttributions(regime?: string): Promise<IModuleAttribution[]> {
  const query: any = {};
  if (regime) query.regime = regime;
  
  return ModuleAttributionModel.find(query).sort({ edgeScore: -1 }).lean();
}

/**
 * Save module weights
 */
export async function saveModuleWeights(weights: ModuleWeight[]): Promise<void> {
  if (weights.length === 0) return;
  
  const operations = weights.map(weight => ({
    updateOne: {
      filter: { module: weight.module, regime: weight.regime || null },
      update: { $set: weight },
      upsert: true
    }
  }));
  
  await ModuleWeightModel.bulkWrite(operations);
}

/**
 * Get current module weights
 */
export async function getModuleWeights(regime?: string): Promise<IModuleWeight[]> {
  const query: any = {};
  if (regime) {
    query.regime = regime;
  } else {
    query.regime = { $exists: false };
  }
  
  return ModuleWeightModel.find(query).lean();
}

/**
 * Get all module weights including regime-specific
 */
export async function getAllModuleWeights(): Promise<IModuleWeight[]> {
  return ModuleWeightModel.find({}).lean();
}

/**
 * Get weight as map for quick lookup
 */
export async function getModuleWeightMap(regime?: string): Promise<Map<AnalysisModule, number>> {
  const weights = await getModuleWeights(regime);
  const map = new Map<AnalysisModule, number>();
  
  for (const w of weights) {
    map.set(w.module as AnalysisModule, w.weight);
  }
  
  return map;
}

/**
 * Save weight history
 */
export async function saveWeightHistory(history: ModuleWeightHistory[]): Promise<void> {
  if (history.length === 0) return;
  await ModuleWeightHistoryModel.insertMany(history);
}

/**
 * Get weight history for a module
 */
export async function getWeightHistory(
  module: AnalysisModule,
  limit: number = 100
): Promise<IModuleWeightHistory[]> {
  return ModuleWeightHistoryModel.find({ module })
    .sort({ changedAt: -1 })
    .limit(limit)
    .lean();
}

/**
 * Get recent weight changes
 */
export async function getRecentWeightChanges(
  daysBack: number = 30,
  limit: number = 50
): Promise<IModuleWeightHistory[]> {
  const dateFrom = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000);
  
  return ModuleWeightHistoryModel.find({ changedAt: { $gte: dateFrom } })
    .sort({ changedAt: -1 })
    .limit(limit)
    .lean();
}
