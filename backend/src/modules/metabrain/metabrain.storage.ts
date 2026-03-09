/**
 * MetaBrain v1 — Storage
 * 
 * MongoDB persistence for MetaBrain state and actions
 */

import mongoose, { Schema, Document } from 'mongoose';
import {
  MetaBrainState,
  MetaBrainAction,
  MetaBrainDecision,
  MetaBrainContext
} from './metabrain.types.js';

// ═══════════════════════════════════════════════════════════════
// METABRAIN STATE SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IMetaBrainState extends Document {
  stateId: string;
  currentRiskMode: string;
  currentDecision: MetaBrainDecision;
  currentContext: MetaBrainContext;
  riskModeHistory: Array<{ mode: string; at: Date; reason: string[] }>;
  totalDecisions: number;
  modeChangesToday: number;
  systemHealth: string;
  updatedAt: Date;
}

const MetaBrainStateSchema = new Schema<IMetaBrainState>({
  stateId: { type: String, required: true, unique: true, default: 'MAIN' },
  currentRiskMode: { type: String, required: true },
  currentDecision: { type: Schema.Types.Mixed, required: true },
  currentContext: { type: Schema.Types.Mixed, required: true },
  riskModeHistory: [{
    mode: { type: String },
    at: { type: Date },
    reason: [{ type: String }]
  }],
  totalDecisions: { type: Number, default: 0 },
  modeChangesToday: { type: Number, default: 0 },
  systemHealth: { type: String, default: 'HEALTHY' },
  updatedAt: { type: Date, required: true }
}, {
  collection: 'ta_metabrain_state',
  timestamps: true
});

export const MetaBrainStateModel = mongoose.model<IMetaBrainState>('MetaBrainState', MetaBrainStateSchema);

// ═══════════════════════════════════════════════════════════════
// METABRAIN ACTIONS SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IMetaBrainAction extends Document {
  actionId: string;
  timestamp: Date;
  actionType: string;
  from: any;
  to: any;
  contextSnapshot: any;
  reason: string[];
}

const MetaBrainActionSchema = new Schema<IMetaBrainAction>({
  actionId: { type: String, required: true, unique: true, index: true },
  timestamp: { type: Date, required: true, index: true },
  actionType: { type: String, required: true, index: true },
  from: { type: Schema.Types.Mixed },
  to: { type: Schema.Types.Mixed },
  contextSnapshot: { type: Schema.Types.Mixed },
  reason: [{ type: String }]
}, {
  collection: 'ta_metabrain_actions',
  timestamps: true
});

MetaBrainActionSchema.index({ actionType: 1, timestamp: -1 });

export const MetaBrainActionModel = mongoose.model<IMetaBrainAction>('MetaBrainAction', MetaBrainActionSchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Get or create MetaBrain state
 */
export async function getMetaBrainState(): Promise<IMetaBrainState | null> {
  return MetaBrainStateModel.findOne({ stateId: 'MAIN' }).lean();
}

/**
 * Save MetaBrain state
 */
export async function saveMetaBrainState(state: Partial<IMetaBrainState>): Promise<void> {
  await MetaBrainStateModel.updateOne(
    { stateId: 'MAIN' },
    { 
      $set: { 
        ...state, 
        stateId: 'MAIN',
        updatedAt: new Date() 
      } 
    },
    { upsert: true }
  );
}

/**
 * Save MetaBrain action
 */
export async function saveMetaBrainAction(action: MetaBrainAction): Promise<void> {
  await MetaBrainActionModel.create(action);
}

/**
 * Get recent actions
 */
export async function getRecentActions(
  limit: number = 50,
  actionType?: string
): Promise<IMetaBrainAction[]> {
  const query: any = {};
  if (actionType) query.actionType = actionType;
  
  return MetaBrainActionModel.find(query)
    .sort({ timestamp: -1 })
    .limit(limit)
    .lean();
}

/**
 * Get mode change count for today
 */
export async function getModeChangesToday(): Promise<number> {
  const startOfDay = new Date();
  startOfDay.setHours(0, 0, 0, 0);
  
  const count = await MetaBrainActionModel.countDocuments({
    actionType: 'SET_RISK_MODE',
    timestamp: { $gte: startOfDay }
  });
  
  return count;
}

/**
 * Get last mode change time
 */
export async function getLastModeChangeTime(): Promise<Date | null> {
  const lastAction = await MetaBrainActionModel.findOne({ actionType: 'SET_RISK_MODE' })
    .sort({ timestamp: -1 })
    .lean();
  
  return lastAction?.timestamp || null;
}

/**
 * Get action statistics
 */
export async function getActionStats(daysBack: number = 30): Promise<{
  total: number;
  byType: Record<string, number>;
  modeDistribution: Record<string, number>;
}> {
  const dateFrom = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000);
  
  const actions = await MetaBrainActionModel.find({ timestamp: { $gte: dateFrom } }).lean();
  
  const byType: Record<string, number> = {};
  const modeDistribution: Record<string, number> = {};
  
  for (const action of actions) {
    byType[action.actionType] = (byType[action.actionType] || 0) + 1;
    if (action.actionType === 'SET_RISK_MODE' && action.to) {
      modeDistribution[action.to] = (modeDistribution[action.to] || 0) + 1;
    }
  }
  
  return {
    total: actions.length,
    byType,
    modeDistribution
  };
}
