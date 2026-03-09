/**
 * P1.3 — MM3 Memory Policy Storage
 * 
 * MongoDB storage for memory policies
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import {
  MemoryContext,
  MemoryPolicy,
  MemoryStrength,
  MemoryPolicyRecord
} from './memory.policy.types.js';

// ═══════════════════════════════════════════════════════════════
// SCHEMA DEFINITION
// ═══════════════════════════════════════════════════════════════

interface MemoryPolicyDoc extends Document {
  asset: string;
  timeframe: string;
  ts: number;
  context: MemoryContext;
  policy: MemoryPolicy;
  strength: string;
  createdAt: Date;
}

const MemoryPolicySchema = new Schema<MemoryPolicyDoc>({
  asset: { type: String, required: true, index: true },
  timeframe: { type: String, required: true, index: true },
  ts: { type: Number, required: true, index: true },
  
  context: {
    confidence: { type: Number, required: true },
    matches: { type: Number, required: true },
    bias: { type: String, enum: ['BULL', 'BEAR', 'NEUTRAL'], required: true },
    historicalWinRate: { type: Number },
    avgMoveATR: { type: Number },
    avgBarsToResolution: { type: Number },
    directionConsistency: { type: Number },
    scenarioConsistency: { type: Number }
  },
  
  policy: {
    riskMultiplier: { type: Number, required: true },
    confidenceAdjustment: { type: Number, required: true },
    signalApprovalThreshold: { type: Number, required: true },
    policyStrength: { type: Number, required: true },
    policyReason: { type: String, required: true },
    biasAlignment: {
      aligned: { type: Boolean },
      multiplier: { type: Number },
      description: { type: String }
    }
  },
  
  strength: { 
    type: String, 
    enum: ['STRONG', 'MODERATE', 'WEAK', 'NONE'],
    required: true 
  },
  
  createdAt: { type: Date, default: Date.now, index: true }
}, {
  collection: 'ta_metabrain_memory_policies'
});

// Compound index for asset + timeframe
MemoryPolicySchema.index({ asset: 1, timeframe: 1, ts: -1 });

// ═══════════════════════════════════════════════════════════════
// MODEL
// ═══════════════════════════════════════════════════════════════

export const MemoryPolicyModel: Model<MemoryPolicyDoc> = mongoose.models.MemoryPolicy ||
  mongoose.model<MemoryPolicyDoc>('MemoryPolicy', MemoryPolicySchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save memory policy
 */
export async function saveMemoryPolicy(record: MemoryPolicyRecord): Promise<void> {
  await MemoryPolicyModel.findOneAndUpdate(
    { asset: record.asset, timeframe: record.timeframe, ts: record.ts },
    {
      context: record.context,
      policy: record.policy,
      strength: record.strength,
      createdAt: record.createdAt
    },
    { upsert: true, new: true }
  );
}

/**
 * Get latest policy for asset/timeframe
 */
export async function getLatestMemoryPolicy(
  asset: string,
  timeframe: string
): Promise<MemoryPolicyRecord | null> {
  const doc = await MemoryPolicyModel.findOne(
    { asset, timeframe },
    { _id: 0 }
  ).sort({ ts: -1 }).lean();
  
  if (!doc) return null;
  
  return {
    asset: doc.asset,
    timeframe: doc.timeframe,
    ts: doc.ts,
    context: doc.context as MemoryContext,
    policy: doc.policy as MemoryPolicy,
    strength: doc.strength as MemoryStrength,
    createdAt: doc.createdAt
  };
}

/**
 * Get policy history
 */
export async function getMemoryPolicyHistory(
  asset: string,
  timeframe: string,
  limit: number = 50
): Promise<MemoryPolicyRecord[]> {
  const docs = await MemoryPolicyModel.find(
    { asset, timeframe },
    { _id: 0 }
  )
    .sort({ ts: -1 })
    .limit(limit)
    .lean();
  
  return docs.map(doc => ({
    asset: doc.asset,
    timeframe: doc.timeframe,
    ts: doc.ts,
    context: doc.context as MemoryContext,
    policy: doc.policy as MemoryPolicy,
    strength: doc.strength as MemoryStrength,
    createdAt: doc.createdAt
  }));
}

/**
 * Get policies by strength
 */
export async function getPoliciesByStrength(
  strength: MemoryStrength,
  limit: number = 100
): Promise<MemoryPolicyRecord[]> {
  const docs = await MemoryPolicyModel.find(
    { strength },
    { _id: 0 }
  )
    .sort({ ts: -1 })
    .limit(limit)
    .lean();
  
  return docs.map(doc => ({
    asset: doc.asset,
    timeframe: doc.timeframe,
    ts: doc.ts,
    context: doc.context as MemoryContext,
    policy: doc.policy as MemoryPolicy,
    strength: doc.strength as MemoryStrength,
    createdAt: doc.createdAt
  }));
}

/**
 * Count policies by strength
 */
export async function countPoliciesByStrength(): Promise<Record<MemoryStrength, number>> {
  const pipeline = [
    { $group: { _id: '$strength', count: { $sum: 1 } } }
  ];
  
  const results = await MemoryPolicyModel.aggregate(pipeline);
  
  const counts: Record<MemoryStrength, number> = {
    'STRONG': 0,
    'MODERATE': 0,
    'WEAK': 0,
    'NONE': 0
  };
  
  for (const r of results) {
    counts[r._id as MemoryStrength] = r.count;
  }
  
  return counts;
}

/**
 * Clean old policies
 */
export async function cleanOldPolicies(daysToKeep: number = 30): Promise<number> {
  const cutoff = new Date(Date.now() - daysToKeep * 24 * 60 * 60 * 1000);
  
  const result = await MemoryPolicyModel.deleteMany({
    createdAt: { $lt: cutoff }
  });
  
  return result.deletedCount;
}
