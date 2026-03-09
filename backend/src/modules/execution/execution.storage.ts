/**
 * Phase 10 — Execution Storage
 * 
 * MongoDB persistence for execution data
 */

import mongoose, { Schema, Document } from 'mongoose';
import { ExecutionPlan, Portfolio, PortfolioPosition } from './execution.types.js';

// ═══════════════════════════════════════════════════════════════
// EXECUTION PLAN SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IExecutionPlan extends Document {
  planId: string;
  asset: string;
  direction: string;
  strategyId: string;
  entryType: string;
  entryPrice: number;
  entryCondition?: string;
  positionSizePct: number;
  positionSizeUnits: number;
  stopPrice: number;
  stopATR: number;
  riskPct: number;
  riskAbsolute: number;
  target1Price: number;
  target1ATR: number;
  target2Price?: number;
  target2ATR?: number;
  useTrailingStop: boolean;
  trailingActivation?: number;
  trailingDistance?: number;
  validUntil?: Date;
  maxBarsInTrade?: number;
  signalQuality: {
    confidence: number;
    edgeScore: number;
    regimeBoost: number;
    scenarioProbability: number;
  };
  status: string;
  executedAt?: Date;
  cancelledAt?: Date;
  createdAt: Date;
}

const ExecutionPlanSchema = new Schema<IExecutionPlan>({
  planId: { type: String, required: true, unique: true, index: true },
  asset: { type: String, required: true, index: true },
  direction: { type: String, required: true, enum: ['LONG', 'SHORT'] },
  strategyId: { type: String, required: true, index: true },
  entryType: { type: String, required: true },
  entryPrice: { type: Number, required: true },
  entryCondition: { type: String },
  positionSizePct: { type: Number, required: true },
  positionSizeUnits: { type: Number, required: true },
  stopPrice: { type: Number, required: true },
  stopATR: { type: Number, required: true },
  riskPct: { type: Number, required: true },
  riskAbsolute: { type: Number, required: true },
  target1Price: { type: Number, required: true },
  target1ATR: { type: Number, required: true },
  target2Price: { type: Number },
  target2ATR: { type: Number },
  useTrailingStop: { type: Boolean, required: true },
  trailingActivation: { type: Number },
  trailingDistance: { type: Number },
  validUntil: { type: Date },
  maxBarsInTrade: { type: Number },
  signalQuality: {
    confidence: { type: Number, required: true },
    edgeScore: { type: Number, required: true },
    regimeBoost: { type: Number, required: true },
    scenarioProbability: { type: Number, required: true }
  },
  status: { type: String, required: true, enum: ['PENDING', 'ACTIVE', 'FILLED', 'CANCELLED', 'EXPIRED'], index: true },
  executedAt: { type: Date },
  cancelledAt: { type: Date },
  createdAt: { type: Date, required: true }
}, {
  collection: 'ta_execution_plans',
  timestamps: true
});

ExecutionPlanSchema.index({ status: 1, createdAt: -1 });
ExecutionPlanSchema.index({ asset: 1, status: 1 });

export const ExecutionPlanModel = mongoose.model<IExecutionPlan>('ExecutionPlan', ExecutionPlanSchema);

// ═══════════════════════════════════════════════════════════════
// PORTFOLIO SCHEMA
// ═══════════════════════════════════════════════════════════════

export interface IPortfolio extends Document {
  portfolioId: string;
  accountSize: number;
  positions: PortfolioPosition[];
  totalRisk: number;
  totalExposure: number;
  unrealizedPnL: number;
  realizedPnL: number;
  winCount: number;
  lossCount: number;
  updatedAt: Date;
}

const PortfolioPositionSchema = new Schema({
  positionId: { type: String, required: true },
  asset: { type: String, required: true },
  direction: { type: String, required: true },
  strategyId: { type: String, required: true },
  entryPrice: { type: Number, required: true },
  currentPrice: { type: Number, required: true },
  positionSize: { type: Number, required: true },
  riskPct: { type: Number, required: true },
  stopPrice: { type: Number, required: true },
  target1Price: { type: Number, required: true },
  target2Price: { type: Number },
  unrealizedR: { type: Number, required: true },
  unrealizedPnL: { type: Number, required: true },
  entryTime: { type: Date, required: true },
  barsInTrade: { type: Number, required: true }
}, { _id: false });

const PortfolioSchema = new Schema<IPortfolio>({
  portfolioId: { type: String, required: true, unique: true, index: true },
  accountSize: { type: Number, required: true },
  positions: [PortfolioPositionSchema],
  totalRisk: { type: Number, required: true },
  totalExposure: { type: Number, required: true },
  unrealizedPnL: { type: Number, required: true },
  realizedPnL: { type: Number, required: true },
  winCount: { type: Number, required: true },
  lossCount: { type: Number, required: true },
  updatedAt: { type: Date, required: true }
}, {
  collection: 'ta_portfolios',
  timestamps: true
});

export const PortfolioModel = mongoose.model<IPortfolio>('Portfolio', PortfolioSchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save execution plan
 */
export async function saveExecutionPlan(plan: ExecutionPlan): Promise<void> {
  await ExecutionPlanModel.updateOne(
    { planId: plan.planId },
    { $set: plan },
    { upsert: true }
  );
}

/**
 * Get execution plans
 */
export async function getExecutionPlans(
  filters?: {
    asset?: string;
    status?: string;
    strategyId?: string;
  },
  limit: number = 50
): Promise<IExecutionPlan[]> {
  const query: any = {};
  if (filters?.asset) query.asset = filters.asset;
  if (filters?.status) query.status = filters.status;
  if (filters?.strategyId) query.strategyId = filters.strategyId;
  
  return ExecutionPlanModel.find(query)
    .sort({ createdAt: -1 })
    .limit(limit)
    .lean();
}

/**
 * Get pending plans
 */
export async function getPendingPlans(): Promise<IExecutionPlan[]> {
  return ExecutionPlanModel.find({ status: 'PENDING' })
    .sort({ createdAt: -1 })
    .lean();
}

/**
 * Update plan status
 */
export async function updatePlanStatus(
  planId: string,
  status: 'PENDING' | 'ACTIVE' | 'FILLED' | 'CANCELLED' | 'EXPIRED'
): Promise<void> {
  const update: any = { status };
  if (status === 'FILLED') update.executedAt = new Date();
  if (status === 'CANCELLED') update.cancelledAt = new Date();
  
  await ExecutionPlanModel.updateOne({ planId }, { $set: update });
}

/**
 * Save portfolio
 */
export async function savePortfolio(portfolio: Portfolio): Promise<void> {
  await PortfolioModel.updateOne(
    { portfolioId: portfolio.portfolioId },
    { $set: portfolio },
    { upsert: true }
  );
}

/**
 * Get portfolio
 */
export async function getPortfolio(portfolioId: string): Promise<IPortfolio | null> {
  return PortfolioModel.findOne({ portfolioId }).lean();
}

/**
 * Get default portfolio
 */
export async function getDefaultPortfolio(): Promise<IPortfolio | null> {
  return PortfolioModel.findOne({}).sort({ updatedAt: -1 }).lean();
}

/**
 * Get execution stats
 */
export async function getExecutionStats(
  daysBack: number = 30
): Promise<{
  totalPlans: number;
  byStatus: Record<string, number>;
  byAsset: Record<string, number>;
  avgRiskPct: number;
  avgPositionSizePct: number;
}> {
  const dateFrom = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000);
  
  const plans = await ExecutionPlanModel.find({ createdAt: { $gte: dateFrom } }).lean();
  
  const byStatus: Record<string, number> = {};
  const byAsset: Record<string, number> = {};
  let totalRisk = 0;
  let totalSize = 0;
  
  for (const p of plans) {
    byStatus[p.status] = (byStatus[p.status] || 0) + 1;
    byAsset[p.asset] = (byAsset[p.asset] || 0) + 1;
    totalRisk += p.riskPct;
    totalSize += p.positionSizePct;
  }
  
  return {
    totalPlans: plans.length,
    byStatus,
    byAsset,
    avgRiskPct: plans.length > 0 ? Math.round(totalRisk / plans.length * 100) / 100 : 0,
    avgPositionSizePct: plans.length > 0 ? Math.round(totalSize / plans.length * 100) / 100 : 0
  };
}
