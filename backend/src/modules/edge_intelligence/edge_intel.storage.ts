/**
 * Phase 7 — Edge Intelligence Storage
 * 
 * MongoDB persistence for edge data
 */

import mongoose, { Schema, Document } from 'mongoose';
import { EdgeRecord, EdgeStats, EdgeAttribution } from './edge_intel.types.js';

// ═══════════════════════════════════════════════════════════════
// EDGE RECORD SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IEdgeRecord extends Document {
  tradeId: string;
  asset: string;
  timeframe: string;
  entryTime: Date;
  exitTime?: Date;
  pattern: string;
  patternFamily?: string;
  fractal?: string;
  scenario?: string;
  state: string;
  liquidity: string;
  marketState?: string;
  physicsState?: string;
  resultR: number;
  outcome: string;
  entryScore: number;
  entryConfidence: number;
  energyScore?: number;
  graphBoost?: number;
  stateBoost?: number;
}

const EdgeRecordSchema = new Schema<IEdgeRecord>({
  tradeId: { type: String, required: true, unique: true, index: true },
  asset: { type: String, required: true, index: true },
  timeframe: { type: String, required: true, index: true },
  entryTime: { type: Date, required: true, index: true },
  exitTime: { type: Date },
  pattern: { type: String, required: true, index: true },
  patternFamily: { type: String, index: true },
  fractal: { type: String, index: true },
  scenario: { type: String, index: true },
  state: { type: String, required: true, index: true },
  liquidity: { type: String, required: true, index: true },
  marketState: { type: String },
  physicsState: { type: String },
  resultR: { type: Number, required: true },
  outcome: { type: String, required: true, enum: ['WIN', 'LOSS', 'BREAKEVEN'] },
  entryScore: { type: Number, required: true },
  entryConfidence: { type: Number, required: true },
  energyScore: { type: Number },
  graphBoost: { type: Number },
  stateBoost: { type: Number }
}, {
  collection: 'ta_edge_records',
  timestamps: true
});

// Compound indexes
EdgeRecordSchema.index({ pattern: 1, state: 1 });
EdgeRecordSchema.index({ asset: 1, timeframe: 1, entryTime: -1 });

export const EdgeRecordModel = mongoose.model<IEdgeRecord>('EdgeRecord', EdgeRecordSchema);

// ═══════════════════════════════════════════════════════════════
// EDGE STATS SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IEdgeStats extends Document {
  dimension: string;
  key: string;
  sampleSize: number;
  wins: number;
  losses: number;
  breakevens: number;
  winRate: number;
  avgR: number;
  medianR: number;
  profitFactor: number;
  sharpe: number;
  maxDD: number;
  edgeScore: number;
  edgeShrunk: number;
  confidence: number;
  statisticalSignificance: number;
  updatedAt: Date;
}

const EdgeStatsSchema = new Schema<IEdgeStats>({
  dimension: { type: String, required: true, index: true },
  key: { type: String, required: true, index: true },
  sampleSize: { type: Number, required: true },
  wins: { type: Number, required: true },
  losses: { type: Number, required: true },
  breakevens: { type: Number, required: true },
  winRate: { type: Number, required: true },
  avgR: { type: Number, required: true },
  medianR: { type: Number, required: true },
  profitFactor: { type: Number, required: true },
  sharpe: { type: Number, required: true },
  maxDD: { type: Number, required: true },
  edgeScore: { type: Number, required: true, index: true },
  edgeShrunk: { type: Number, required: true },
  confidence: { type: Number, required: true },
  statisticalSignificance: { type: Number, required: true },
  updatedAt: { type: Date, required: true }
}, {
  collection: 'ta_edge_stats',
  timestamps: true
});

EdgeStatsSchema.index({ dimension: 1, key: 1 }, { unique: true });

export const EdgeStatsModel = mongoose.model<IEdgeStats>('EdgeStats', EdgeStatsSchema);

// ═══════════════════════════════════════════════════════════════
// EDGE ATTRIBUTION SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IEdgeAttribution extends Document {
  attributionId: string;
  dimensions: Array<{ dimension: string; value: string }>;
  individualEdges: Array<{ 
    dimension: string; 
    value: string; 
    pfAlone: number;
    contributionPct: number;
  }>;
  combinedPF: number;
  synergy: number;
  sampleSize: number;
  confidence: number;
  calculatedAt: Date;
}

const EdgeAttributionSchema = new Schema<IEdgeAttribution>({
  attributionId: { type: String, required: true, unique: true, index: true },
  dimensions: [{
    dimension: { type: String, required: true },
    value: { type: String, required: true }
  }],
  individualEdges: [{
    dimension: { type: String, required: true },
    value: { type: String, required: true },
    pfAlone: { type: Number, required: true },
    contributionPct: { type: Number, required: true }
  }],
  combinedPF: { type: Number, required: true, index: true },
  synergy: { type: Number, required: true },
  sampleSize: { type: Number, required: true },
  confidence: { type: Number, required: true },
  calculatedAt: { type: Date, required: true }
}, {
  collection: 'ta_edge_attribution',
  timestamps: true
});

export const EdgeAttributionModel = mongoose.model<IEdgeAttribution>('EdgeAttribution', EdgeAttributionSchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save edge records
 */
export async function saveEdgeRecords(records: EdgeRecord[]): Promise<void> {
  if (records.length === 0) return;
  
  const operations = records.map(record => ({
    updateOne: {
      filter: { tradeId: record.tradeId },
      update: { $set: record },
      upsert: true
    }
  }));
  
  await EdgeRecordModel.bulkWrite(operations);
}

/**
 * Save edge stats
 */
export async function saveEdgeStats(stats: EdgeStats[]): Promise<void> {
  if (stats.length === 0) return;
  
  const operations = stats.map(stat => ({
    updateOne: {
      filter: { dimension: stat.dimension, key: stat.key },
      update: { $set: stat },
      upsert: true
    }
  }));
  
  await EdgeStatsModel.bulkWrite(operations);
}

/**
 * Save edge attributions
 */
export async function saveEdgeAttributions(attributions: EdgeAttribution[]): Promise<void> {
  if (attributions.length === 0) return;
  
  const operations = attributions.map(attr => ({
    updateOne: {
      filter: { attributionId: attr.attributionId },
      update: { $set: attr },
      upsert: true
    }
  }));
  
  await EdgeAttributionModel.bulkWrite(operations);
}

/**
 * Get edge records
 */
export async function getEdgeRecords(
  filter: {
    asset?: string;
    timeframe?: string;
    pattern?: string;
    state?: string;
    dateFrom?: Date;
    dateTo?: Date;
  },
  limit: number = 1000
): Promise<IEdgeRecord[]> {
  const query: any = {};
  
  if (filter.asset) query.asset = filter.asset;
  if (filter.timeframe) query.timeframe = filter.timeframe;
  if (filter.pattern) query.pattern = filter.pattern;
  if (filter.state) query.state = filter.state;
  if (filter.dateFrom || filter.dateTo) {
    query.entryTime = {};
    if (filter.dateFrom) query.entryTime.$gte = filter.dateFrom;
    if (filter.dateTo) query.entryTime.$lte = filter.dateTo;
  }
  
  return EdgeRecordModel.find(query).sort({ entryTime: -1 }).limit(limit).lean();
}

/**
 * Get edge stats by dimension
 */
export async function getEdgeStatsByDimension(
  dimension: string
): Promise<IEdgeStats[]> {
  return EdgeStatsModel.find({ dimension }).sort({ edgeScore: -1 }).lean();
}

/**
 * Get top attributions
 */
export async function getTopAttributions(
  limit: number = 20
): Promise<IEdgeAttribution[]> {
  return EdgeAttributionModel.find({})
    .sort({ combinedPF: -1, confidence: -1 })
    .limit(limit)
    .lean();
}

/**
 * Get global baseline
 */
export async function getGlobalBaseline(
  daysBack: number = 180
): Promise<{ winRate: number; avgR: number; profitFactor: number; totalTrades: number }> {
  const dateFrom = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000);
  
  const records = await EdgeRecordModel.find({ entryTime: { $gte: dateFrom } }).lean();
  
  if (records.length === 0) {
    return { winRate: 0.5, avgR: 0, profitFactor: 1, totalTrades: 0 };
  }
  
  const wins = records.filter(r => r.outcome === 'WIN').length;
  const avgR = records.reduce((sum, r) => sum + r.resultR, 0) / records.length;
  
  const grossWin = records.filter(r => r.resultR > 0).reduce((sum, r) => sum + r.resultR, 0);
  const grossLoss = Math.abs(records.filter(r => r.resultR < 0).reduce((sum, r) => sum + r.resultR, 0));
  const profitFactor = grossLoss > 0 ? grossWin / grossLoss : (grossWin > 0 ? 10 : 1);
  
  return {
    winRate: wins / records.length,
    avgR,
    profitFactor,
    totalTrades: records.length
  };
}
