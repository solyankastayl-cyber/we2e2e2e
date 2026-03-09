/**
 * Digital Twin Storage
 * 
 * MongoDB operations for twin state persistence
 */

import mongoose from 'mongoose';
import { DigitalTwinState, DEFAULT_TWIN_CONFIG, DigitalTwinConfig } from './digital_twin.types.js';

// ═══════════════════════════════════════════════════════════════
// SCHEMA
// ═══════════════════════════════════════════════════════════════

const TwinBranchSchema = new mongoose.Schema({
  branchId: { type: String, required: true },
  path: [{ type: String }],
  direction: { type: String, enum: ['BULL', 'BEAR', 'NEUTRAL'] },
  probability: { type: Number },
  expectedMoveATR: { type: Number },
  failureRisk: { type: Number }
}, { _id: false });

const TwinConflictSchema = new mongoose.Schema({
  type: { type: String, required: true },
  modules: [{ type: String }],
  severity: { type: String },
  severityScore: { type: Number },
  description: { type: String },
  resolution: { type: String }
}, { _id: false });

const CounterfactualBranchSchema = new mongoose.Schema({
  branchId: { type: String },
  triggerEvent: { type: String },
  path: [{ type: String }],
  direction: { type: String },
  probability: { type: Number },
  expectedMoveATR: { type: Number },
  riskToMainScenario: { type: Number }
}, { _id: false });

const CounterfactualResultSchema = new mongoose.Schema({
  mainScenarioId: { type: String },
  mainScenarioProb: { type: Number },
  alternatives: [CounterfactualBranchSchema],
  scenarioBreakRisk: { type: Number },
  dominantAlternative: CounterfactualBranchSchema
}, { _id: false });

const DigitalTwinStateSchema = new mongoose.Schema({
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
  
  branches: [TwinBranchSchema],
  
  consistencyScore: { type: Number },
  conflicts: [TwinConflictSchema],
  
  counterfactual: CounterfactualResultSchema,
  
  computedAt: { type: Date, default: Date.now },
  version: { type: Number, default: 1 }
}, {
  collection: 'ta_digital_twin_state',
  timestamps: true
});

// Compound index for queries
DigitalTwinStateSchema.index({ asset: 1, timeframe: 1, ts: -1 });
DigitalTwinStateSchema.index({ dominantScenario: 1 });
DigitalTwinStateSchema.index({ computedAt: -1 });

const DigitalTwinModel = mongoose.models.DigitalTwinState || 
  mongoose.model('DigitalTwinState', DigitalTwinStateSchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save twin state (creates new record, doesn't overwrite)
 */
export async function saveTwinState(state: DigitalTwinState): Promise<void> {
  await DigitalTwinModel.create(state);
}

/**
 * Get latest twin state
 */
export async function getLatestTwinState(
  asset: string,
  timeframe: string
): Promise<DigitalTwinState | null> {
  const doc = await DigitalTwinModel
    .findOne({ asset, timeframe })
    .sort({ ts: -1 })
    .lean();
  
  return doc ? mapDocToState(doc) : null;
}

/**
 * Get twin state at specific timestamp
 */
export async function getTwinStateAt(
  asset: string,
  timeframe: string,
  ts: number
): Promise<DigitalTwinState | null> {
  const doc = await DigitalTwinModel
    .findOne({ asset, timeframe, ts: { $lte: ts } })
    .sort({ ts: -1 })
    .lean();
  
  return doc ? mapDocToState(doc) : null;
}

/**
 * Get twin state history
 */
export async function getTwinStateHistory(
  asset: string,
  timeframe: string,
  limit: number = 100,
  fromTs?: number,
  toTs?: number
): Promise<DigitalTwinState[]> {
  const query: Record<string, unknown> = { asset, timeframe };
  
  if (fromTs || toTs) {
    query.ts = {};
    if (fromTs) (query.ts as Record<string, number>).$gte = fromTs;
    if (toTs) (query.ts as Record<string, number>).$lte = toTs;
  }
  
  const docs = await DigitalTwinModel
    .find(query)
    .sort({ ts: -1 })
    .limit(limit)
    .lean();
  
  return docs.map(mapDocToState);
}

/**
 * Get states by dominant scenario
 */
export async function getStatesByScenario(
  asset: string,
  timeframe: string,
  scenarioId: string,
  limit: number = 50
): Promise<DigitalTwinState[]> {
  const docs = await DigitalTwinModel
    .find({ asset, timeframe, dominantScenario: scenarioId })
    .sort({ ts: -1 })
    .limit(limit)
    .lean();
  
  return docs.map(mapDocToState);
}

/**
 * Get states with low consistency
 */
export async function getLowConsistencyStates(
  asset: string,
  timeframe: string,
  threshold: number = 0.5,
  limit: number = 50
): Promise<DigitalTwinState[]> {
  const docs = await DigitalTwinModel
    .find({ 
      asset, 
      timeframe, 
      consistencyScore: { $lt: threshold }
    })
    .sort({ ts: -1 })
    .limit(limit)
    .lean();
  
  return docs.map(mapDocToState);
}

/**
 * Get states with high break risk
 */
export async function getHighBreakRiskStates(
  asset: string,
  timeframe: string,
  threshold: number = 0.5,
  limit: number = 50
): Promise<DigitalTwinState[]> {
  const docs = await DigitalTwinModel
    .find({ 
      asset, 
      timeframe, 
      'counterfactual.scenarioBreakRisk': { $gt: threshold }
    })
    .sort({ ts: -1 })
    .limit(limit)
    .lean();
  
  return docs.map(mapDocToState);
}

/**
 * Count states for asset/timeframe
 */
export async function countTwinStates(
  asset: string,
  timeframe: string
): Promise<number> {
  return DigitalTwinModel.countDocuments({ asset, timeframe });
}

/**
 * Delete old states (retention policy)
 */
export async function cleanupOldStates(
  keepDays: number = DEFAULT_TWIN_CONFIG.keepHistoryDays
): Promise<number> {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - keepDays);
  
  const result = await DigitalTwinModel.deleteMany({
    computedAt: { $lt: cutoffDate }
  });
  
  return result.deletedCount || 0;
}

/**
 * Get unique assets with twin data
 */
export async function getTrackedAssets(): Promise<Array<{ asset: string; timeframe: string }>> {
  const results = await DigitalTwinModel.aggregate([
    {
      $group: {
        _id: { asset: '$asset', timeframe: '$timeframe' }
      }
    },
    {
      $project: {
        _id: 0,
        asset: '$_id.asset',
        timeframe: '$_id.timeframe'
      }
    }
  ]);
  
  return results;
}

// ═══════════════════════════════════════════════════════════════
// AGGREGATION QUERIES
// ═══════════════════════════════════════════════════════════════

/**
 * Get regime distribution over time
 */
export async function getRegimeDistribution(
  asset: string,
  timeframe: string,
  days: number = 30
): Promise<Record<string, number>> {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - days);
  
  const results = await DigitalTwinModel.aggregate([
    {
      $match: {
        asset,
        timeframe,
        computedAt: { $gte: cutoffDate }
      }
    },
    {
      $group: {
        _id: '$regime',
        count: { $sum: 1 }
      }
    }
  ]);
  
  const distribution: Record<string, number> = {};
  const total = results.reduce((sum, r) => sum + r.count, 0);
  
  for (const r of results) {
    distribution[r._id] = total > 0 ? r.count / total : 0;
  }
  
  return distribution;
}

/**
 * Get average consistency by regime
 */
export async function getConsistencyByRegime(
  asset: string,
  timeframe: string,
  days: number = 30
): Promise<Record<string, number>> {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - days);
  
  const results = await DigitalTwinModel.aggregate([
    {
      $match: {
        asset,
        timeframe,
        computedAt: { $gte: cutoffDate },
        consistencyScore: { $exists: true }
      }
    },
    {
      $group: {
        _id: '$regime',
        avgConsistency: { $avg: '$consistencyScore' }
      }
    }
  ]);
  
  const byRegime: Record<string, number> = {};
  for (const r of results) {
    byRegime[r._id] = r.avgConsistency;
  }
  
  return byRegime;
}

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Map MongoDB document to DigitalTwinState
 */
function mapDocToState(doc: Record<string, unknown>): DigitalTwinState {
  return {
    asset: doc.asset as string,
    timeframe: doc.timeframe as string,
    ts: doc.ts as number,
    regime: doc.regime as DigitalTwinState['regime'],
    marketState: doc.marketState as DigitalTwinState['marketState'],
    physicsState: doc.physicsState as DigitalTwinState['physicsState'],
    liquidityState: doc.liquidityState as DigitalTwinState['liquidityState'],
    dominantScenario: doc.dominantScenario as string,
    energy: doc.energy as number,
    instability: doc.instability as number,
    confidence: doc.confidence as number,
    branches: doc.branches as DigitalTwinState['branches'],
    consistencyScore: doc.consistencyScore as number | undefined,
    conflicts: doc.conflicts as DigitalTwinState['conflicts'],
    counterfactual: doc.counterfactual as DigitalTwinState['counterfactual'],
    computedAt: doc.computedAt as Date,
    version: doc.version as number
  };
}
