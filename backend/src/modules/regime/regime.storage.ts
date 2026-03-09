/**
 * Phase 9 — Regime Storage
 * 
 * MongoDB persistence for regime history
 */

import mongoose, { Schema, Document } from 'mongoose';
import { 
  MarketRegime, 
  RegimeFeatures, 
  RegimeHistoryRecord, 
  RegimeTransition,
  BASE_REGIME_TRANSITIONS
} from './regime.types.js';

// ═══════════════════════════════════════════════════════════════
// MONGOOSE SCHEMAS
// ═══════════════════════════════════════════════════════════════

export interface IRegimeHistory extends Document {
  asset: string;
  timeframe: string;
  timestamp: Date;
  regime: string;
  confidence: number;
  features: RegimeFeatures;
  duration?: number;
}

const RegimeFeaturesSchema = new Schema({
  trendStrength: { type: Number, required: true },
  trendDirection: { type: Number, required: true },
  volatility: { type: Number, required: true },
  volatilityTrend: { type: Number, required: true },
  compression: { type: Number, required: true },
  compressionTrend: { type: Number, required: true },
  rangeScore: { type: Number, required: true },
  rangeWidth: { type: Number, required: true },
  liquidityActivity: { type: Number, required: true },
  liquidityBias: { type: Number, required: true },
  momentum: { type: Number, required: true },
  momentumDivergence: { type: Number, required: true },
  volumeProfile: { type: Number, required: true },
  volumeTrend: { type: Number, required: true }
}, { _id: false });

const RegimeHistorySchema = new Schema<IRegimeHistory>({
  asset: { type: String, required: true, index: true },
  timeframe: { type: String, required: true, index: true },
  timestamp: { type: Date, required: true, index: true },
  regime: { type: String, required: true, index: true },
  confidence: { type: Number, required: true },
  features: { type: RegimeFeaturesSchema, required: true },
  duration: { type: Number }
}, {
  collection: 'ta_market_regimes',
  timestamps: true
});

// Compound indexes
RegimeHistorySchema.index({ asset: 1, timeframe: 1, timestamp: -1 });
RegimeHistorySchema.index({ regime: 1, timestamp: -1 });

export const RegimeHistoryModel = mongoose.model<IRegimeHistory>('RegimeHistory', RegimeHistorySchema);

// ═══════════════════════════════════════════════════════════════
// REGIME TRANSITIONS SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IRegimeTransition extends Document {
  from: string;
  to: string;
  probability: number;
  avgDuration: number;
  sampleSize: number;
  asset?: string;
  timeframe?: string;
  updatedAt: Date;
}

const RegimeTransitionSchema = new Schema<IRegimeTransition>({
  from: { type: String, required: true, index: true },
  to: { type: String, required: true, index: true },
  probability: { type: Number, required: true },
  avgDuration: { type: Number, required: true },
  sampleSize: { type: Number, required: true },
  asset: { type: String, index: true },
  timeframe: { type: String, index: true },
  updatedAt: { type: Date, required: true }
}, {
  collection: 'ta_regime_transitions',
  timestamps: true
});

RegimeTransitionSchema.index({ from: 1, to: 1 }, { unique: true });

export const RegimeTransitionModel = mongoose.model<IRegimeTransition>('RegimeTransition', RegimeTransitionSchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save regime history record
 */
export async function saveRegimeHistory(record: RegimeHistoryRecord): Promise<void> {
  await RegimeHistoryModel.create(record);
}

/**
 * Get latest regime for asset
 */
export async function getLatestRegime(
  asset: string,
  timeframe: string
): Promise<IRegimeHistory | null> {
  return RegimeHistoryModel
    .findOne({ asset, timeframe })
    .sort({ timestamp: -1 })
    .lean();
}

/**
 * Get regime history
 */
export async function getRegimeHistory(
  asset: string,
  timeframe: string,
  limit: number = 100
): Promise<IRegimeHistory[]> {
  return RegimeHistoryModel
    .find({ asset, timeframe })
    .sort({ timestamp: -1 })
    .limit(limit)
    .lean();
}

/**
 * Get regime transitions (calculated from history)
 */
export async function getRegimeTransitions(
  asset?: string,
  timeframe?: string
): Promise<RegimeTransition[]> {
  // First check if we have stored transitions
  const query: any = {};
  if (asset) query.asset = asset;
  if (timeframe) query.timeframe = timeframe;
  
  const stored = await RegimeTransitionModel.find(query).lean();
  
  if (stored.length > 0) {
    return stored.map(t => ({
      from: t.from as MarketRegime,
      to: t.to as MarketRegime,
      probability: t.probability,
      avgDuration: t.avgDuration,
      sampleSize: t.sampleSize
    }));
  }
  
  // Return base transitions with defaults
  return BASE_REGIME_TRANSITIONS.map(t => ({
    ...t,
    avgDuration: 10,
    sampleSize: 100
  }));
}

/**
 * Calculate transitions from history
 */
export async function calculateTransitions(
  asset?: string,
  timeframe?: string
): Promise<RegimeTransition[]> {
  const matchStage: any = {};
  if (asset) matchStage.asset = asset;
  if (timeframe) matchStage.timeframe = timeframe;
  
  const history = await RegimeHistoryModel
    .find(matchStage)
    .sort({ asset: 1, timeframe: 1, timestamp: 1 })
    .lean();
  
  if (history.length < 2) {
    return BASE_REGIME_TRANSITIONS.map(t => ({ ...t, avgDuration: 10, sampleSize: 100 }));
  }
  
  // Count transitions
  const transitionCounts: Record<string, { count: number; durations: number[] }> = {};
  const fromCounts: Record<string, number> = {};
  
  for (let i = 1; i < history.length; i++) {
    const prev = history[i - 1];
    const curr = history[i];
    
    // Only count if same asset/tf
    if (prev.asset !== curr.asset || prev.timeframe !== curr.timeframe) continue;
    
    // Only count if regime changed
    if (prev.regime === curr.regime) continue;
    
    const key = `${prev.regime}|${curr.regime}`;
    if (!transitionCounts[key]) {
      transitionCounts[key] = { count: 0, durations: [] };
    }
    transitionCounts[key].count++;
    if (prev.duration) {
      transitionCounts[key].durations.push(prev.duration);
    }
    
    fromCounts[prev.regime] = (fromCounts[prev.regime] || 0) + 1;
  }
  
  // Calculate probabilities
  const transitions: RegimeTransition[] = [];
  
  for (const [key, data] of Object.entries(transitionCounts)) {
    const [from, to] = key.split('|');
    const fromTotal = fromCounts[from] || 1;
    const avgDuration = data.durations.length > 0 
      ? data.durations.reduce((a, b) => a + b, 0) / data.durations.length 
      : 10;
    
    transitions.push({
      from: from as MarketRegime,
      to: to as MarketRegime,
      probability: data.count / fromTotal,
      avgDuration,
      sampleSize: data.count
    });
  }
  
  // Save transitions
  if (transitions.length > 0) {
    const operations = transitions.map(t => ({
      updateOne: {
        filter: { from: t.from, to: t.to, asset, timeframe },
        update: { 
          $set: { 
            ...t, 
            asset, 
            timeframe,
            updatedAt: new Date() 
          } 
        },
        upsert: true
      }
    }));
    await RegimeTransitionModel.bulkWrite(operations);
  }
  
  return transitions;
}

/**
 * Get regime statistics
 */
export async function getRegimeStats(
  asset?: string,
  timeframe?: string,
  daysBack: number = 30
): Promise<{
  total: number;
  byRegime: Record<string, number>;
  avgDuration: Record<string, number>;
  mostCommon: string;
  currentRegime?: string;
}> {
  const dateFrom = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000);
  const matchStage: any = { timestamp: { $gte: dateFrom } };
  if (asset) matchStage.asset = asset;
  if (timeframe) matchStage.timeframe = timeframe;
  
  const records = await RegimeHistoryModel.find(matchStage).sort({ timestamp: -1 }).lean();
  
  const byRegime: Record<string, number> = {};
  const durations: Record<string, number[]> = {};
  
  for (const r of records) {
    byRegime[r.regime] = (byRegime[r.regime] || 0) + 1;
    if (r.duration) {
      if (!durations[r.regime]) durations[r.regime] = [];
      durations[r.regime].push(r.duration);
    }
  }
  
  const avgDuration: Record<string, number> = {};
  for (const [regime, durs] of Object.entries(durations)) {
    avgDuration[regime] = durs.reduce((a, b) => a + b, 0) / durs.length;
  }
  
  let mostCommon = 'COMPRESSION';
  let maxCount = 0;
  for (const [regime, count] of Object.entries(byRegime)) {
    if (count > maxCount) {
      maxCount = count;
      mostCommon = regime;
    }
  }
  
  return {
    total: records.length,
    byRegime,
    avgDuration,
    mostCommon,
    currentRegime: records[0]?.regime
  };
}
