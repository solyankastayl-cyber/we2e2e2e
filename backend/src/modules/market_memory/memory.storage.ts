/**
 * MM1 — Memory Storage
 * 
 * MongoDB operations for memory snapshots
 */

import mongoose from 'mongoose';
import { MarketMemorySnapshot, MemoryOutcome } from './memory.types.js';

// ═══════════════════════════════════════════════════════════════
// SCHEMA
// ═══════════════════════════════════════════════════════════════

const MemoryOutcomeSchema = new mongoose.Schema({
  direction: { type: String, enum: ['BULL', 'BEAR', 'NEUTRAL'] },
  moveATR: { type: Number },
  scenarioResolved: { type: String },
  barsToResolution: { type: Number }
}, { _id: false });

const MarketMemorySchema = new mongoose.Schema({
  snapshotId: { type: String, required: true, unique: true, index: true },
  
  asset: { type: String, required: true, index: true },
  timeframe: { type: String, required: true, index: true },
  ts: { type: Number, required: true, index: true },
  
  regime: { type: String, required: true },
  marketState: { type: String, required: true },
  physicsState: { type: String, required: true },
  liquidityState: { type: String, required: true },
  dominantScenario: { type: String },
  
  energy: { type: Number },
  instability: { type: Number },
  confidence: { type: Number },
  
  featureVector: [{ type: Number }],
  
  outcome: MemoryOutcomeSchema,
  
  createdAt: { type: Date, default: Date.now },
  resolvedAt: { type: Date }
}, {
  collection: 'ta_market_memory',
  timestamps: false
});

// Compound indexes
MarketMemorySchema.index({ asset: 1, timeframe: 1, ts: -1 });
MarketMemorySchema.index({ regime: 1, marketState: 1 });
MarketMemorySchema.index({ 'outcome.direction': 1 });

const MemoryModel = mongoose.models.MarketMemory ||
  mongoose.model('MarketMemory', MarketMemorySchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save memory snapshot
 */
export async function saveMemorySnapshot(snapshot: MarketMemorySnapshot): Promise<void> {
  await MemoryModel.create(snapshot);
}

/**
 * Get memory snapshot by ID
 */
export async function getMemorySnapshot(snapshotId: string): Promise<MarketMemorySnapshot | null> {
  const doc = await MemoryModel.findOne({ snapshotId }).lean();
  return doc ? mapDocToSnapshot(doc) : null;
}

/**
 * Get all snapshots for asset/timeframe
 */
export async function getMemorySnapshots(
  asset: string,
  timeframe: string,
  limit: number = 1000
): Promise<MarketMemorySnapshot[]> {
  const docs = await MemoryModel
    .find({ asset, timeframe })
    .sort({ ts: -1 })
    .limit(limit)
    .lean();
  
  return docs.map(mapDocToSnapshot);
}

/**
 * Get resolved snapshots (with outcome)
 */
export async function getResolvedSnapshots(
  asset?: string,
  timeframe?: string,
  limit: number = 1000
): Promise<MarketMemorySnapshot[]> {
  const query: Record<string, unknown> = {
    outcome: { $exists: true },
    resolvedAt: { $exists: true }
  };
  
  if (asset) query.asset = asset;
  if (timeframe) query.timeframe = timeframe;
  
  const docs = await MemoryModel
    .find(query)
    .sort({ ts: -1 })
    .limit(limit)
    .lean();
  
  return docs.map(mapDocToSnapshot);
}

/**
 * Get snapshots by regime
 */
export async function getSnapshotsByRegime(
  regime: string,
  limit: number = 500
): Promise<MarketMemorySnapshot[]> {
  const docs = await MemoryModel
    .find({ regime, outcome: { $exists: true } })
    .sort({ ts: -1 })
    .limit(limit)
    .lean();
  
  return docs.map(mapDocToSnapshot);
}

/**
 * Update snapshot with outcome
 */
export async function updateSnapshotOutcome(
  snapshotId: string,
  outcome: MemoryOutcome
): Promise<void> {
  await MemoryModel.updateOne(
    { snapshotId },
    { 
      $set: { 
        outcome,
        resolvedAt: new Date()
      }
    }
  );
}

/**
 * Count memory snapshots
 */
export async function countMemorySnapshots(
  asset?: string,
  timeframe?: string
): Promise<number> {
  const query: Record<string, unknown> = {};
  if (asset) query.asset = asset;
  if (timeframe) query.timeframe = timeframe;
  
  return MemoryModel.countDocuments(query);
}

/**
 * Count resolved snapshots
 */
export async function countResolvedSnapshots(
  asset?: string,
  timeframe?: string
): Promise<number> {
  const query: Record<string, unknown> = {
    outcome: { $exists: true }
  };
  if (asset) query.asset = asset;
  if (timeframe) query.timeframe = timeframe;
  
  return MemoryModel.countDocuments(query);
}

/**
 * Delete old snapshots (retention policy)
 */
export async function cleanupOldSnapshots(keepDays: number = 365): Promise<number> {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - keepDays);
  
  const result = await MemoryModel.deleteMany({
    createdAt: { $lt: cutoffDate }
  });
  
  return result.deletedCount || 0;
}

/**
 * Get memory statistics
 */
export async function getMemoryStats(): Promise<{
  totalSnapshots: number;
  resolvedSnapshots: number;
  assetTimeframes: Array<{ asset: string; timeframe: string; count: number }>;
  outcomeDistribution: Record<string, number>;
}> {
  const total = await MemoryModel.countDocuments();
  const resolved = await MemoryModel.countDocuments({ outcome: { $exists: true } });
  
  const byAsset = await MemoryModel.aggregate([
    { $group: { _id: { asset: '$asset', timeframe: '$timeframe' }, count: { $sum: 1 } } },
    { $project: { _id: 0, asset: '$_id.asset', timeframe: '$_id.timeframe', count: 1 } }
  ]);
  
  const outcomes = await MemoryModel.aggregate([
    { $match: { 'outcome.direction': { $exists: true } } },
    { $group: { _id: '$outcome.direction', count: { $sum: 1 } } }
  ]);
  
  const outcomeDistribution: Record<string, number> = {};
  for (const o of outcomes) {
    outcomeDistribution[o._id] = o.count;
  }
  
  return {
    totalSnapshots: total,
    resolvedSnapshots: resolved,
    assetTimeframes: byAsset,
    outcomeDistribution
  };
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function mapDocToSnapshot(doc: Record<string, unknown>): MarketMemorySnapshot {
  return {
    snapshotId: doc.snapshotId as string,
    asset: doc.asset as string,
    timeframe: doc.timeframe as string,
    ts: doc.ts as number,
    regime: doc.regime as MarketMemorySnapshot['regime'],
    marketState: doc.marketState as MarketMemorySnapshot['marketState'],
    physicsState: doc.physicsState as MarketMemorySnapshot['physicsState'],
    liquidityState: doc.liquidityState as MarketMemorySnapshot['liquidityState'],
    dominantScenario: doc.dominantScenario as string,
    energy: doc.energy as number,
    instability: doc.instability as number,
    confidence: doc.confidence as number,
    featureVector: doc.featureVector as number[],
    outcome: doc.outcome as MemoryOutcome | undefined,
    createdAt: doc.createdAt as Date,
    resolvedAt: doc.resolvedAt as Date | undefined
  };
}
