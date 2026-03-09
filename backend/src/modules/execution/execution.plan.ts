/**
 * Phase 10 — Execution Plan Builder
 * 
 * Creates actionable execution plans from signals
 */

import { v4 as uuidv4 } from 'uuid';
import {
  ExecutionPlan,
  PositionSizeRequest,
  Portfolio,
  RiskLimits,
  DEFAULT_RISK_LIMITS,
  ExecutionConfig,
  DEFAULT_EXECUTION_CONFIG
} from './execution.types.js';
import { calculatePositionSize } from './execution.position.js';
import { calculateRiskStatus, checkCorrelationLimits } from './execution.risk.js';

// ═══════════════════════════════════════════════════════════════
// SIGNAL INPUT
// ═══════════════════════════════════════════════════════════════

export interface SignalInput {
  // Asset
  asset: string;
  timeframe: string;
  currentPrice: number;
  atr: number;
  
  // Direction
  direction: 'LONG' | 'SHORT';
  
  // Strategy
  strategyId: string;
  entryRule: string;
  
  // Levels (in price)
  entryPrice: number;
  stopATR: number;
  target1ATR: number;
  target2ATR?: number;
  
  // Quality
  confidence: number;
  edgeScore: number;
  regimeBoost: number;
  scenarioProbability: number;
  
  // MetaBrain integration (Phase 11)
  metaRiskMultiplier?: number;
  
  // P0: Memory integration
  memoryRiskAdjustment?: number;
  
  // Optional
  useTrailingStop?: boolean;
}

// ═══════════════════════════════════════════════════════════════
// MAIN PLAN BUILDER
// ═══════════════════════════════════════════════════════════════

/**
 * Create execution plan from signal
 */
export function createExecutionPlan(
  signal: SignalInput,
  portfolio: Portfolio,
  limits: RiskLimits = DEFAULT_RISK_LIMITS,
  config: ExecutionConfig = DEFAULT_EXECUTION_CONFIG
): ExecutionPlan | { error: string; reason: string } {
  
  // 1. Check if we can trade
  const riskStatus = calculateRiskStatus(portfolio, limits);
  
  if (!riskStatus.canOpenTrade) {
    return {
      error: 'CANNOT_TRADE',
      reason: riskStatus.warnings.join('; ') || 'Trading not allowed'
    };
  }
  
  // 2. Check correlation limits
  const correlationCheck = checkCorrelationLimits(
    signal.asset,
    limits.maxRiskPerTrade,
    portfolio.positions,
    limits.maxCorrelatedRisk
  );
  
  if (!correlationCheck.allowed) {
    return {
      error: 'CORRELATION_LIMIT',
      reason: `Would exceed correlated risk in ${correlationCheck.group}: ${correlationCheck.currentExposure}%`
    };
  }
  
  // 3. Calculate stop and targets in price
  const stopPrice = signal.direction === 'LONG'
    ? signal.entryPrice - signal.atr * signal.stopATR
    : signal.entryPrice + signal.atr * signal.stopATR;
  
  const target1Price = signal.direction === 'LONG'
    ? signal.entryPrice + signal.atr * signal.target1ATR
    : signal.entryPrice - signal.atr * signal.target1ATR;
  
  const target2Price = signal.target2ATR
    ? (signal.direction === 'LONG'
        ? signal.entryPrice + signal.atr * signal.target2ATR
        : signal.entryPrice - signal.atr * signal.target2ATR)
    : undefined;
  
  // 4. Calculate position size
  const sizeRequest: PositionSizeRequest = {
    accountSize: portfolio.accountSize,
    baseRiskPct: config.baseRiskPct,
    asset: signal.asset,
    direction: signal.direction,
    entryPrice: signal.entryPrice,
    stopPrice,
    atr: signal.atr,
    confidence: signal.confidence,
    edgeScore: signal.edgeScore,
    regimeBoost: signal.regimeBoost,
    metaRiskMultiplier: signal.metaRiskMultiplier,  // MetaBrain integration
    memoryRiskAdjustment: signal.memoryRiskAdjustment  // P0: Memory integration
  };
  
  const sizeResult = calculatePositionSize(
    sizeRequest,
    riskStatus.currentPortfolioRisk,
    limits,
    config
  );
  
  // 5. Check if size is meaningful
  if (sizeResult.positionSizePct < 0.1) {
    return {
      error: 'SIZE_TOO_SMALL',
      reason: 'Calculated position size is too small to execute'
    };
  }
  
  // 6. Build execution plan
  const plan: ExecutionPlan = {
    planId: `EXEC_${uuidv4().slice(0, 8).toUpperCase()}`,
    asset: signal.asset,
    direction: signal.direction,
    strategyId: signal.strategyId,
    
    entryType: signal.entryRule.includes('LIMIT') ? 'LIMIT' : 
               signal.entryRule.includes('STOP') ? 'STOP' : 'MARKET',
    entryPrice: signal.entryPrice,
    entryCondition: signal.entryRule,
    
    positionSizePct: sizeResult.positionSizePct,
    positionSizeUnits: sizeResult.positionSizeAbsolute,
    
    stopPrice,
    stopATR: signal.stopATR,
    riskPct: sizeResult.riskPct,
    riskAbsolute: sizeResult.riskAbsolute,
    
    target1Price,
    target1ATR: signal.target1ATR,
    target2Price,
    target2ATR: signal.target2ATR,
    
    useTrailingStop: signal.useTrailingStop ?? config.useTrailingByDefault,
    trailingActivation: 1.5,
    trailingDistance: 1.0,
    
    validUntil: new Date(Date.now() + 24 * 60 * 60 * 1000),  // 24h
    maxBarsInTrade: 50,
    
    signalQuality: {
      confidence: signal.confidence,
      edgeScore: signal.edgeScore,
      regimeBoost: signal.regimeBoost,
      scenarioProbability: signal.scenarioProbability
    },
    
    status: 'PENDING',
    createdAt: new Date()
  };
  
  return plan;
}

// ═══════════════════════════════════════════════════════════════
// PLAN VALIDATION
// ═══════════════════════════════════════════════════════════════

/**
 * Validate execution plan
 */
export function validateExecutionPlan(plan: ExecutionPlan): { valid: boolean; issues: string[] } {
  const issues: string[] = [];
  
  // Check position size
  if (plan.positionSizePct <= 0) {
    issues.push('Invalid position size');
  }
  
  // Check risk
  if (plan.riskPct <= 0 || plan.riskPct > 5) {
    issues.push(`Unusual risk level: ${plan.riskPct}%`);
  }
  
  // Check stop placement
  if (plan.direction === 'LONG') {
    if (plan.stopPrice >= plan.entryPrice) {
      issues.push('Stop must be below entry for LONG');
    }
    if (plan.target1Price <= plan.entryPrice) {
      issues.push('Target must be above entry for LONG');
    }
  } else {
    if (plan.stopPrice <= plan.entryPrice) {
      issues.push('Stop must be above entry for SHORT');
    }
    if (plan.target1Price >= plan.entryPrice) {
      issues.push('Target must be below entry for SHORT');
    }
  }
  
  // Check R:R
  const stopDist = Math.abs(plan.entryPrice - plan.stopPrice);
  const targetDist = Math.abs(plan.target1Price - plan.entryPrice);
  const rr = stopDist > 0 ? targetDist / stopDist : 0;
  
  if (rr < 1) {
    issues.push(`Risk/Reward ratio too low: ${rr.toFixed(2)}`);
  }
  
  // Check signal quality
  if (plan.signalQuality.confidence < 0.4) {
    issues.push('Low confidence signal');
  }
  
  return {
    valid: issues.length === 0,
    issues
  };
}

// ═══════════════════════════════════════════════════════════════
// BATCH PLANNING
// ═══════════════════════════════════════════════════════════════

/**
 * Create execution plans for multiple signals
 */
export function createExecutionPlansBatch(
  signals: SignalInput[],
  portfolio: Portfolio,
  limits: RiskLimits = DEFAULT_RISK_LIMITS,
  config: ExecutionConfig = DEFAULT_EXECUTION_CONFIG
): { plans: ExecutionPlan[]; rejected: Array<{ signal: SignalInput; reason: string }> } {
  const plans: ExecutionPlan[] = [];
  const rejected: Array<{ signal: SignalInput; reason: string }> = [];
  
  // Sort by signal quality
  const sortedSignals = [...signals].sort((a, b) => {
    const scoreA = a.confidence * a.edgeScore * a.regimeBoost;
    const scoreB = b.confidence * b.edgeScore * b.regimeBoost;
    return scoreB - scoreA;
  });
  
  // Create a temporary portfolio to track allocations
  let tempPortfolio = { ...portfolio };
  
  for (const signal of sortedSignals) {
    const result = createExecutionPlan(signal, tempPortfolio, limits, config);
    
    if ('error' in result) {
      rejected.push({ signal, reason: result.reason });
    } else {
      plans.push(result);
      
      // Update temp portfolio
      tempPortfolio = {
        ...tempPortfolio,
        totalRisk: tempPortfolio.totalRisk + result.riskPct,
        totalExposure: tempPortfolio.totalExposure + result.positionSizePct
      };
    }
  }
  
  return { plans, rejected };
}
