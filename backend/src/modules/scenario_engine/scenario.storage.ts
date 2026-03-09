/**
 * Phase 6 — Scenario Storage
 * 
 * MongoDB persistence for market scenarios
 */

import mongoose, { Schema, Document } from 'mongoose';
import { MarketScenario, ScenarioSimulationResult } from './scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// MONGOOSE SCHEMAS
// ═══════════════════════════════════════════════════════════════

export interface IMarketScenario extends Document {
  scenarioId: string;
  asset: string;
  timeframe: string;
  direction: string;
  probability: number;
  expectedMoveATR: number;
  path: string[];
  events: string[];
  states: string[];
  confidence: number;
  score: number;
  generatedAt: Date;
  expiresAt?: Date;
  outcome?: {
    realized: boolean;
    actualPath?: string[];
    actualMoveATR?: number;
    evaluatedAt?: Date;
  };
}

const MarketScenarioSchema = new Schema<IMarketScenario>({
  scenarioId: { type: String, required: true, unique: true, index: true },
  asset: { type: String, required: true, index: true },
  timeframe: { type: String, required: true, index: true },
  direction: { type: String, required: true, enum: ['BULL', 'BEAR', 'NEUTRAL'] },
  probability: { type: Number, required: true },
  expectedMoveATR: { type: Number, required: true },
  path: [{ type: String }],
  events: [{ type: String }],
  states: [{ type: String }],
  confidence: { type: Number, required: true },
  score: { type: Number, required: true, index: true },
  generatedAt: { type: Date, required: true, index: true },
  expiresAt: { type: Date },
  outcome: {
    realized: { type: Boolean },
    actualPath: [{ type: String }],
    actualMoveATR: { type: Number },
    evaluatedAt: { type: Date }
  }
}, {
  collection: 'ta_market_scenarios',
  timestamps: true
});

// Compound indexes
MarketScenarioSchema.index({ asset: 1, timeframe: 1, generatedAt: -1 });
MarketScenarioSchema.index({ direction: 1, probability: -1 });

export const MarketScenarioModel = mongoose.model<IMarketScenario>('MarketScenario', MarketScenarioSchema);

// ═══════════════════════════════════════════════════════════════
// SIMULATION RESULT SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IScenarioSimResult extends Document {
  asset: string;
  timeframe: string;
  timestamp: Date;
  scenarioIds: string[];
  primaryScenarioId?: string;
  bullishProbability: number;
  bearishProbability: number;
  neutralProbability: number;
  recommendedAction: string;
  actionConfidence: number;
  inputState: {
    physicsState?: string;
    energyScore?: number;
    trendDirection?: string;
  };
}

const ScenarioSimResultSchema = new Schema<IScenarioSimResult>({
  asset: { type: String, required: true, index: true },
  timeframe: { type: String, required: true, index: true },
  timestamp: { type: Date, required: true, index: true },
  scenarioIds: [{ type: String }],
  primaryScenarioId: { type: String },
  bullishProbability: { type: Number, required: true },
  bearishProbability: { type: Number, required: true },
  neutralProbability: { type: Number, required: true },
  recommendedAction: { type: String, required: true },
  actionConfidence: { type: Number, required: true },
  inputState: {
    physicsState: { type: String },
    energyScore: { type: Number },
    trendDirection: { type: String }
  }
}, {
  collection: 'ta_scenario_simulations',
  timestamps: true
});

ScenarioSimResultSchema.index({ asset: 1, timeframe: 1, timestamp: -1 });

export const ScenarioSimResultModel = mongoose.model<IScenarioSimResult>('ScenarioSimResult', ScenarioSimResultSchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save scenarios to database
 */
export async function saveScenarios(scenarios: MarketScenario[]): Promise<void> {
  if (scenarios.length === 0) return;
  
  const operations = scenarios.map(scenario => ({
    updateOne: {
      filter: { scenarioId: scenario.scenarioId },
      update: { $set: scenario },
      upsert: true
    }
  }));
  
  await MarketScenarioModel.bulkWrite(operations);
}

/**
 * Save simulation result
 */
export async function saveSimulationResult(result: ScenarioSimulationResult): Promise<void> {
  // Save individual scenarios
  await saveScenarios(result.scenarios);
  
  // Save simulation result
  const simResult = new ScenarioSimResultModel({
    asset: result.asset,
    timeframe: result.timeframe,
    timestamp: result.timestamp,
    scenarioIds: result.scenarios.map(s => s.scenarioId),
    primaryScenarioId: result.primaryScenario?.scenarioId,
    bullishProbability: result.bullishProbability,
    bearishProbability: result.bearishProbability,
    neutralProbability: result.neutralProbability,
    recommendedAction: result.recommendedAction,
    actionConfidence: result.actionConfidence,
    inputState: {}
  });
  
  await simResult.save();
}

/**
 * Get latest scenarios for asset
 */
export async function getLatestScenarios(
  asset: string,
  timeframe: string,
  limit: number = 10
): Promise<IMarketScenario[]> {
  return MarketScenarioModel
    .find({ asset, timeframe })
    .sort({ generatedAt: -1 })
    .limit(limit)
    .lean();
}

/**
 * Get active (non-expired) scenarios
 */
export async function getActiveScenarios(
  asset: string,
  timeframe: string
): Promise<IMarketScenario[]> {
  const now = new Date();
  
  return MarketScenarioModel
    .find({
      asset,
      timeframe,
      $or: [
        { expiresAt: { $gt: now } },
        { expiresAt: { $exists: false } }
      ]
    })
    .sort({ score: -1 })
    .lean();
}

/**
 * Update scenario outcome
 */
export async function updateScenarioOutcome(
  scenarioId: string,
  outcome: {
    realized: boolean;
    actualPath?: string[];
    actualMoveATR?: number;
  }
): Promise<void> {
  await MarketScenarioModel.updateOne(
    { scenarioId },
    { 
      $set: { 
        outcome: {
          ...outcome,
          evaluatedAt: new Date()
        }
      }
    }
  );
}

/**
 * Get scenario statistics
 */
export async function getScenarioStats(
  asset?: string,
  timeframe?: string,
  daysBack: number = 30
): Promise<{
  total: number;
  byDirection: Record<string, number>;
  avgAccuracy: number;
  topPaths: Array<{ path: string; count: number; accuracy: number }>;
}> {
  const matchStage: any = {
    generatedAt: { $gte: new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000) }
  };
  
  if (asset) matchStage.asset = asset;
  if (timeframe) matchStage.timeframe = timeframe;
  
  const stats = await MarketScenarioModel.aggregate([
    { $match: matchStage },
    {
      $group: {
        _id: null,
        total: { $sum: 1 },
        bullCount: { $sum: { $cond: [{ $eq: ['$direction', 'BULL'] }, 1, 0] } },
        bearCount: { $sum: { $cond: [{ $eq: ['$direction', 'BEAR'] }, 1, 0] } },
        neutralCount: { $sum: { $cond: [{ $eq: ['$direction', 'NEUTRAL'] }, 1, 0] } },
        realizedCount: { $sum: { $cond: ['$outcome.realized', 1, 0] } },
        evaluatedCount: { $sum: { $cond: [{ $ne: ['$outcome', null] }, 1, 0] } }
      }
    }
  ]);
  
  // Get top paths
  const topPaths = await MarketScenarioModel.aggregate([
    { $match: matchStage },
    {
      $group: {
        _id: { $reduce: { input: '$path', initialValue: '', in: { $concat: ['$$value', '->', '$$this'] } } },
        count: { $sum: 1 },
        realizedCount: { $sum: { $cond: ['$outcome.realized', 1, 0] } },
        evaluatedCount: { $sum: { $cond: [{ $ne: ['$outcome', null] }, 1, 0] } }
      }
    },
    { $sort: { count: -1 } },
    { $limit: 10 }
  ]);
  
  const result = stats[0] || { total: 0, bullCount: 0, bearCount: 0, neutralCount: 0, realizedCount: 0, evaluatedCount: 0 };
  
  return {
    total: result.total,
    byDirection: {
      BULL: result.bullCount,
      BEAR: result.bearCount,
      NEUTRAL: result.neutralCount
    },
    avgAccuracy: result.evaluatedCount > 0 ? result.realizedCount / result.evaluatedCount : 0,
    topPaths: topPaths.map(p => ({
      path: p._id.substring(2), // Remove leading '->'
      count: p.count,
      accuracy: p.evaluatedCount > 0 ? p.realizedCount / p.evaluatedCount : 0
    }))
  };
}

/**
 * Clean up expired scenarios
 */
export async function cleanupExpiredScenarios(): Promise<number> {
  const result = await MarketScenarioModel.deleteMany({
    expiresAt: { $lt: new Date() },
    'outcome.realized': { $exists: false }
  });
  
  return result.deletedCount;
}
