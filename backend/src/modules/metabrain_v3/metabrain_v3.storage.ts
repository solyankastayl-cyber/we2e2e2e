/**
 * MetaBrain v3 — Storage
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import { MetaBrainV3State, MetaBrainV3Action, MetaBrainV3Decision } from './metabrain_v3.types.js';

// ═══════════════════════════════════════════════════════════════
// STATE SCHEMA
// ═══════════════════════════════════════════════════════════════

const MetaBrainV3StateSchema = new Schema({
  asset: { type: String, index: true },
  timeframe: { type: String, index: true },
  
  context: { type: Schema.Types.Mixed, required: true },
  decision: { type: Schema.Types.Mixed, required: true },
  
  createdAt: { type: Date, default: Date.now, index: true }
}, {
  collection: 'ta_metabrain_v3_state'
});

// ═══════════════════════════════════════════════════════════════
// ACTION SCHEMA
// ═══════════════════════════════════════════════════════════════

const MetaBrainV3ActionSchema = new Schema({
  type: { 
    type: String, 
    enum: ['SAFE_MODE_ENTER', 'SAFE_MODE_EXIT', 'RISK_MODE_CHANGE', 
           'ANALYSIS_MODE_CHANGE', 'STRATEGY_CHANGE', 'MODULE_CHANGE'],
    required: true,
    index: true
  },
  previousValue: { type: String, required: true },
  newValue: { type: String, required: true },
  reason: { type: String, required: true },
  triggeredAt: { type: Date, default: Date.now, index: true }
}, {
  collection: 'ta_metabrain_v3_actions'
});

// ═══════════════════════════════════════════════════════════════
// MODELS
// ═══════════════════════════════════════════════════════════════

export const MetaBrainV3StateModel = mongoose.models.MetaBrainV3State ||
  mongoose.model('MetaBrainV3State', MetaBrainV3StateSchema);

export const MetaBrainV3ActionModel = mongoose.models.MetaBrainV3Action ||
  mongoose.model('MetaBrainV3Action', MetaBrainV3ActionSchema);

// ═══════════════════════════════════════════════════════════════
// STATE STORAGE
// ═══════════════════════════════════════════════════════════════

export async function saveMetaBrainV3State(state: MetaBrainV3State): Promise<void> {
  await MetaBrainV3StateModel.create({
    asset: state.asset,
    timeframe: state.timeframe,
    context: state.context,
    decision: state.decision,
    createdAt: state.createdAt
  });
}

export async function getLatestMetaBrainV3State(
  asset?: string,
  timeframe?: string
): Promise<MetaBrainV3State | null> {
  const query: Record<string, any> = {};
  if (asset) query.asset = asset;
  if (timeframe) query.timeframe = timeframe;
  
  const doc = await MetaBrainV3StateModel.findOne(query, { _id: 0 })
    .sort({ createdAt: -1 })
    .lean();
  
  if (!doc) return null;
  
  return doc as unknown as MetaBrainV3State;
}

export async function getMetaBrainV3History(
  limit: number = 50,
  asset?: string,
  timeframe?: string
): Promise<MetaBrainV3State[]> {
  const query: Record<string, any> = {};
  if (asset) query.asset = asset;
  if (timeframe) query.timeframe = timeframe;
  
  const docs = await MetaBrainV3StateModel.find(query, { _id: 0 })
    .sort({ createdAt: -1 })
    .limit(limit)
    .lean();
  
  return docs as unknown as MetaBrainV3State[];
}

// ═══════════════════════════════════════════════════════════════
// ACTION STORAGE
// ═══════════════════════════════════════════════════════════════

export async function saveMetaBrainV3Action(action: MetaBrainV3Action): Promise<void> {
  await MetaBrainV3ActionModel.create(action);
}

export async function getMetaBrainV3Actions(
  limit: number = 50,
  type?: string
): Promise<MetaBrainV3Action[]> {
  const query: Record<string, any> = {};
  if (type) query.type = type;
  
  const docs = await MetaBrainV3ActionModel.find(query, { _id: 0 })
    .sort({ triggeredAt: -1 })
    .limit(limit)
    .lean();
  
  return docs as unknown as MetaBrainV3Action[];
}

// ═══════════════════════════════════════════════════════════════
// CLEANUP
// ═══════════════════════════════════════════════════════════════

export async function cleanOldMetaBrainV3Data(daysToKeep: number = 30): Promise<{
  statesDeleted: number;
  actionsDeleted: number;
}> {
  const cutoff = new Date(Date.now() - daysToKeep * 24 * 60 * 60 * 1000);
  
  const statesResult = await MetaBrainV3StateModel.deleteMany({ createdAt: { $lt: cutoff } });
  const actionsResult = await MetaBrainV3ActionModel.deleteMany({ triggeredAt: { $lt: cutoff } });
  
  return {
    statesDeleted: statesResult.deletedCount,
    actionsDeleted: actionsResult.deletedCount
  };
}
