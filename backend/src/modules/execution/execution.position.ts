/**
 * Phase 10 — Position Sizing Engine
 * 
 * Calculates optimal position size based on risk and signal quality
 */

import {
  PositionSizeRequest,
  PositionSizeResult,
  RiskLimits,
  DEFAULT_RISK_LIMITS,
  ExecutionConfig,
  DEFAULT_EXECUTION_CONFIG
} from './execution.types.js';

// ═══════════════════════════════════════════════════════════════
// MULTIPLIER CALCULATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate confidence multiplier
 * Confidence > 0.5 increases size, < 0.5 decreases
 */
export function calculateConfidenceMultiplier(
  confidence: number,
  config: ExecutionConfig = DEFAULT_EXECUTION_CONFIG
): number {
  // Linear interpolation from minMultiplier to maxMultiplier
  // confidence 0 -> minMultiplier
  // confidence 0.5 -> 1.0
  // confidence 1 -> maxMultiplier
  
  const { confidenceMultiplierMin, confidenceMultiplierMax } = config;
  
  if (confidence <= 0.5) {
    // Scale from min to 1.0
    const t = confidence / 0.5;
    return confidenceMultiplierMin + t * (1 - confidenceMultiplierMin);
  } else {
    // Scale from 1.0 to max
    const t = (confidence - 0.5) / 0.5;
    return 1 + t * (confidenceMultiplierMax - 1);
  }
}

/**
 * Calculate edge multiplier
 * Higher edge score = larger position
 */
export function calculateEdgeMultiplier(
  edgeScore: number,
  config: ExecutionConfig = DEFAULT_EXECUTION_CONFIG
): number {
  const { edgeMultiplierMin, edgeMultiplierMax } = config;
  
  // edgeScore typically -1 to 1
  // Map to multiplier range
  const normalizedEdge = (edgeScore + 1) / 2;  // 0 to 1
  
  return edgeMultiplierMin + normalizedEdge * (edgeMultiplierMax - edgeMultiplierMin);
}

/**
 * Calculate regime multiplier
 * Regime alignment boosts position
 */
export function calculateRegimeMultiplier(regimeBoost: number): number {
  // regimeBoost typically 0.7 to 1.35
  // Just use it directly but clamp
  return Math.max(0.7, Math.min(1.35, regimeBoost));
}

/**
 * Calculate portfolio adjustment multiplier
 * Reduces size when approaching limits
 */
export function calculatePortfolioMultiplier(
  currentPortfolioRisk: number,
  maxPortfolioRisk: number
): number {
  const utilizationPct = currentPortfolioRisk / maxPortfolioRisk;
  
  if (utilizationPct < 0.5) {
    return 1.0;  // Plenty of room
  } else if (utilizationPct < 0.75) {
    return 0.9;  // Getting close
  } else if (utilizationPct < 0.9) {
    return 0.7;  // Reduce significantly
  } else {
    return 0.5;  // Near limit
  }
}

// ═══════════════════════════════════════════════════════════════
// MAIN POSITION SIZING
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate position size
 */
export function calculatePositionSize(
  request: PositionSizeRequest,
  currentPortfolioRisk: number = 0,
  limits: RiskLimits = DEFAULT_RISK_LIMITS,
  config: ExecutionConfig = DEFAULT_EXECUTION_CONFIG
): PositionSizeResult {
  const {
    accountSize,
    baseRiskPct,
    entryPrice,
    stopPrice,
    atr,
    confidence,
    edgeScore,
    regimeBoost,
    metaRiskMultiplier,
    memoryRiskAdjustment,  // P0: Memory risk adjustment
    mtfExecutionAdjustment  // Phase 6.5: MTF execution adjustment
  } = request;
  
  // Calculate stop distance
  const stopDistance = Math.abs(entryPrice - stopPrice);
  const stopDistanceATR = atr > 0 ? stopDistance / atr : 1;
  
  // Calculate multipliers
  const confMultiplier = calculateConfidenceMultiplier(confidence, config);
  const edgeMultiplier = calculateEdgeMultiplier(edgeScore, config);
  const regimeMultiplier = calculateRegimeMultiplier(regimeBoost);
  const portfolioMultiplier = calculatePortfolioMultiplier(currentPortfolioRisk, limits.maxPortfolioRisk);
  const metaMultiplier = metaRiskMultiplier ?? 1.0;  // MetaBrain integration
  const memoryMultiplier = memoryRiskAdjustment ?? 1.0;  // P0: Memory integration
  const mtfMultiplier = mtfExecutionAdjustment ?? 1.0;  // Phase 6.5: MTF integration
  
  // Base position size (from risk formula)
  // positionSize = (accountSize × riskPct) / stopDistance
  const baseRiskAbsolute = accountSize * (baseRiskPct / 100);
  const basePositionSize = stopDistance > 0 ? baseRiskAbsolute / stopDistance : 0;
  
  // Apply multipliers (including MetaBrain, Memory, and MTF)
  const combinedMultiplier = confMultiplier * edgeMultiplier * regimeMultiplier * portfolioMultiplier * metaMultiplier * memoryMultiplier * mtfMultiplier;
  let adjustedPositionSize = basePositionSize * combinedMultiplier;
  
  // Calculate position as % of account
  let positionSizePct = (adjustedPositionSize * entryPrice / accountSize) * 100;
  
  // Calculate actual risk %
  let riskPct = (adjustedPositionSize * stopDistance / accountSize) * 100;
  
  // Apply caps
  let cappedBy: string | undefined;
  const originalSize = positionSizePct;
  
  // Cap 1: Max risk per trade
  if (riskPct > limits.maxRiskPerTrade) {
    const scaleFactor = limits.maxRiskPerTrade / riskPct;
    positionSizePct *= scaleFactor;
    adjustedPositionSize *= scaleFactor;
    riskPct = limits.maxRiskPerTrade;
    cappedBy = 'MAX_RISK_PER_TRADE';
  }
  
  // Cap 2: Would exceed portfolio risk
  const availablePortfolioRisk = limits.maxPortfolioRisk - currentPortfolioRisk;
  if (riskPct > availablePortfolioRisk) {
    const scaleFactor = availablePortfolioRisk / riskPct;
    positionSizePct *= scaleFactor;
    adjustedPositionSize *= scaleFactor;
    riskPct = availablePortfolioRisk;
    cappedBy = 'MAX_PORTFOLIO_RISK';
  }
  
  // Cap 3: Max exposure per asset
  if (positionSizePct > limits.maxExposurePerAsset) {
    const scaleFactor = limits.maxExposurePerAsset / positionSizePct;
    positionSizePct = limits.maxExposurePerAsset;
    adjustedPositionSize *= scaleFactor;
    riskPct *= scaleFactor;
    cappedBy = 'MAX_EXPOSURE_PER_ASSET';
  }
  
  return {
    positionSizePct: Math.round(positionSizePct * 100) / 100,
    positionSizeAbsolute: Math.round(adjustedPositionSize * 100) / 100,
    riskPct: Math.round(riskPct * 100) / 100,
    riskAbsolute: Math.round(adjustedPositionSize * stopDistance * 100) / 100,
    entryPrice,
    stopPrice,
    stopDistanceATR: Math.round(stopDistanceATR * 100) / 100,
    multipliers: {
      base: 1,
      confidence: Math.round(confMultiplier * 100) / 100,
      edge: Math.round(edgeMultiplier * 100) / 100,
      regime: Math.round(regimeMultiplier * 100) / 100,
      portfolio: Math.round(portfolioMultiplier * 100) / 100,
      metaBrain: metaRiskMultiplier !== undefined ? Math.round(metaMultiplier * 100) / 100 : undefined,
      memory: memoryRiskAdjustment !== undefined ? Math.round(memoryMultiplier * 100) / 100 : undefined,  // P0
      mtf: mtfExecutionAdjustment !== undefined ? Math.round(mtfMultiplier * 100) / 100 : undefined  // Phase 6.5
    },
    cappedBy,
    originalSize: cappedBy ? Math.round(originalSize * 100) / 100 : undefined
  };
}

// ═══════════════════════════════════════════════════════════════
// KELLY CRITERION (Advanced)
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate Kelly optimal fraction
 */
export function calculateKellyFraction(
  winRate: number,
  avgWin: number,
  avgLoss: number
): number {
  if (avgLoss === 0) return 0;
  
  const b = avgWin / avgLoss;  // Win/loss ratio
  const p = winRate;
  const q = 1 - winRate;
  
  // Kelly formula: f* = (bp - q) / b
  const kelly = (b * p - q) / b;
  
  // Half-Kelly is often used for safety
  return Math.max(0, kelly * 0.5);
}

/**
 * Calculate position size using Kelly criterion
 */
export function calculateKellyPositionSize(
  accountSize: number,
  winRate: number,
  avgWinR: number,
  avgLossR: number,
  stopDistancePrice: number,
  entryPrice: number
): { positionSizePct: number; kellyFraction: number } {
  const kellyFraction = calculateKellyFraction(winRate, avgWinR, avgLossR);
  
  // Kelly fraction is the optimal fraction of bankroll to risk
  const riskAbsolute = accountSize * kellyFraction;
  const positionSize = stopDistancePrice > 0 ? riskAbsolute / stopDistancePrice : 0;
  const positionSizePct = (positionSize * entryPrice / accountSize) * 100;
  
  return {
    positionSizePct: Math.round(positionSizePct * 100) / 100,
    kellyFraction: Math.round(kellyFraction * 1000) / 1000
  };
}
