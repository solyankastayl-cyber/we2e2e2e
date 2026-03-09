/**
 * Phase 8 — Strategy Storage
 * 
 * MongoDB persistence for strategies
 */

import mongoose, { Schema, Document } from 'mongoose';
import { Strategy, StrategyPerformance, StrategyMatch } from './strategy.types.js';

// ═══════════════════════════════════════════════════════════════
// MONGOOSE SCHEMAS
// ═══════════════════════════════════════════════════════════════

export interface IStrategy extends Document {
  strategyId: string;
  pattern: string;
  state: string;
  liquidity: string;
  scenario?: string;
  regime?: string;
  entryRule: string;
  exitRule: string;
  stopATR: number;
  targetATR: number;
  riskReward: number;
  performance: StrategyPerformance;
  strategyScore: number;
  status: string;
  asset?: string;
  timeframe?: string;
  createdAt: Date;
  updatedAt: Date;
  lastBacktestAt?: Date;
}

const StrategyPerformanceSchema = new Schema({
  trades: { type: Number, required: true },
  wins: { type: Number, required: true },
  losses: { type: Number, required: true },
  breakevens: { type: Number, required: true },
  winRate: { type: Number, required: true },
  avgR: { type: Number, required: true },
  profitFactor: { type: Number, required: true },
  sharpe: { type: Number, required: true },
  maxDD: { type: Number, required: true },
  expectancy: { type: Number, required: true },
  avgWin: { type: Number, required: true },
  avgLoss: { type: Number, required: true },
  avgBarsInTrade: { type: Number, required: true },
  maxConsecutiveLosses: { type: Number, required: true }
}, { _id: false });

const StrategySchema = new Schema<IStrategy>({
  strategyId: { type: String, required: true, unique: true, index: true },
  pattern: { type: String, required: true, index: true },
  state: { type: String, required: true, index: true },
  liquidity: { type: String, required: true, index: true },
  scenario: { type: String, index: true },
  regime: { type: String, index: true },
  entryRule: { type: String, required: true },
  exitRule: { type: String, required: true },
  stopATR: { type: Number, required: true },
  targetATR: { type: Number, required: true },
  riskReward: { type: Number, required: true },
  performance: { type: StrategyPerformanceSchema, required: true },
  strategyScore: { type: Number, required: true, index: true },
  status: { type: String, required: true, enum: ['CANDIDATE', 'ACTIVE', 'PAUSED', 'RETIRED'], index: true },
  asset: { type: String, index: true },
  timeframe: { type: String, index: true },
  createdAt: { type: Date, required: true },
  updatedAt: { type: Date, required: true },
  lastBacktestAt: { type: Date }
}, {
  collection: 'ta_strategies',
  timestamps: true
});

// Compound indexes
StrategySchema.index({ pattern: 1, state: 1, liquidity: 1 });
StrategySchema.index({ status: 1, strategyScore: -1 });
StrategySchema.index({ regime: 1, strategyScore: -1 });

export const StrategyModel = mongoose.model<IStrategy>('Strategy', StrategySchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save strategy
 */
export async function saveStrategy(strategy: Strategy): Promise<void> {
  await StrategyModel.updateOne(
    { strategyId: strategy.strategyId },
    { $set: strategy },
    { upsert: true }
  );
}

/**
 * Save multiple strategies
 */
export async function saveStrategies(strategies: Strategy[]): Promise<void> {
  if (strategies.length === 0) return;
  
  const operations = strategies.map(s => ({
    updateOne: {
      filter: { strategyId: s.strategyId },
      update: { $set: s },
      upsert: true
    }
  }));
  
  await StrategyModel.bulkWrite(operations);
}

/**
 * Get all active strategies
 */
export async function getActiveStrategies(): Promise<IStrategy[]> {
  return StrategyModel.find({ status: 'ACTIVE' })
    .sort({ strategyScore: -1 })
    .lean();
}

/**
 * Get top strategies
 */
export async function getTopStrategies(
  limit: number = 20,
  filters?: {
    regime?: string;
    asset?: string;
    timeframe?: string;
    minScore?: number;
  }
): Promise<IStrategy[]> {
  const query: any = { status: { $in: ['ACTIVE', 'CANDIDATE'] } };
  
  if (filters?.regime) query.regime = filters.regime;
  if (filters?.asset) query.asset = filters.asset;
  if (filters?.timeframe) query.timeframe = filters.timeframe;
  if (filters?.minScore) query.strategyScore = { $gte: filters.minScore };
  
  return StrategyModel.find(query)
    .sort({ strategyScore: -1 })
    .limit(limit)
    .lean();
}

/**
 * Get strategies by pattern
 */
export async function getStrategiesByPattern(pattern: string): Promise<IStrategy[]> {
  return StrategyModel.find({ pattern, status: { $in: ['ACTIVE', 'CANDIDATE'] } })
    .sort({ strategyScore: -1 })
    .lean();
}

/**
 * Get strategies by regime
 */
export async function getStrategiesByRegime(regime: string): Promise<IStrategy[]> {
  return StrategyModel.find({ regime, status: { $in: ['ACTIVE', 'CANDIDATE'] } })
    .sort({ strategyScore: -1 })
    .lean();
}

/**
 * Find matching strategies for current conditions
 */
export async function findMatchingStrategies(
  pattern: string,
  state: string,
  liquidity: string,
  regime?: string
): Promise<StrategyMatch[]> {
  const query: any = { status: { $in: ['ACTIVE', 'CANDIDATE'] } };
  
  // At least pattern should match
  query.pattern = pattern;
  
  const strategies = await StrategyModel.find(query)
    .sort({ strategyScore: -1 })
    .limit(20)
    .lean();
  
  // Score matches
  return strategies.map(s => {
    const dimensions = {
      pattern: s.pattern === pattern,
      state: s.state === state,
      liquidity: s.liquidity === liquidity,
      scenario: true,  // Always true if not specified
      regime: !s.regime || s.regime === regime
    };
    
    // Count matches
    const matchCount = Object.values(dimensions).filter(Boolean).length;
    const matchScore = matchCount / 5;
    
    return {
      strategy: s as unknown as Strategy,
      matchScore,
      dimensions
    };
  }).filter(m => m.matchScore >= 0.4)  // At least 2 dimensions match
    .sort((a, b) => b.matchScore - a.matchScore);
}

/**
 * Update strategy status
 */
export async function updateStrategyStatus(
  strategyId: string,
  status: 'CANDIDATE' | 'ACTIVE' | 'PAUSED' | 'RETIRED'
): Promise<void> {
  await StrategyModel.updateOne(
    { strategyId },
    { $set: { status, updatedAt: new Date() } }
  );
}

/**
 * Get strategy stats
 */
export async function getStrategyStats(): Promise<{
  total: number;
  byStatus: Record<string, number>;
  byPattern: Record<string, number>;
  avgScore: number;
  avgPF: number;
}> {
  const strategies = await StrategyModel.find({}).lean();
  
  const byStatus: Record<string, number> = {};
  const byPattern: Record<string, number> = {};
  let totalScore = 0;
  let totalPF = 0;
  
  for (const s of strategies) {
    byStatus[s.status] = (byStatus[s.status] || 0) + 1;
    byPattern[s.pattern] = (byPattern[s.pattern] || 0) + 1;
    totalScore += s.strategyScore;
    totalPF += s.performance.profitFactor;
  }
  
  return {
    total: strategies.length,
    byStatus,
    byPattern,
    avgScore: strategies.length > 0 ? totalScore / strategies.length : 0,
    avgPF: strategies.length > 0 ? totalPF / strategies.length : 0
  };
}
