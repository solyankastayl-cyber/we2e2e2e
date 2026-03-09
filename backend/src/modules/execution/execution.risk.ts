/**
 * Phase 10 — Risk Management Engine
 * 
 * Portfolio risk tracking and limits enforcement
 */

import {
  RiskLimits,
  DEFAULT_RISK_LIMITS,
  RiskStatus,
  Portfolio,
  PortfolioPosition,
  AssetCorrelation,
  CORRELATION_GROUPS
} from './execution.types.js';

// ═══════════════════════════════════════════════════════════════
// RISK STATUS CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate current risk status from portfolio
 */
export function calculateRiskStatus(
  portfolio: Portfolio,
  limits: RiskLimits = DEFAULT_RISK_LIMITS
): RiskStatus {
  const warnings: string[] = [];
  
  // Calculate exposure by asset
  const exposureByAsset: Record<string, number> = {};
  for (const pos of portfolio.positions) {
    const exposure = (pos.positionSize * pos.currentPrice / portfolio.accountSize) * 100;
    exposureByAsset[pos.asset] = (exposureByAsset[pos.asset] || 0) + exposure;
  }
  
  // Calculate correlated exposure
  const correlatedExposure = calculateCorrelatedExposure(portfolio.positions, portfolio.accountSize);
  
  // Total portfolio risk
  const currentPortfolioRisk = portfolio.positions.reduce((sum, p) => sum + p.riskPct, 0);
  
  // Check limits
  if (currentPortfolioRisk > limits.maxPortfolioRisk * 0.8) {
    warnings.push(`Portfolio risk at ${currentPortfolioRisk.toFixed(1)}% (limit: ${limits.maxPortfolioRisk}%)`);
  }
  
  if (portfolio.positions.length >= limits.maxOpenTrades) {
    warnings.push(`Max open trades reached: ${portfolio.positions.length}`);
  }
  
  // Check correlated exposure
  for (const [group, exposure] of Object.entries(correlatedExposure)) {
    if (exposure > limits.maxCorrelatedRisk) {
      warnings.push(`High correlated risk in ${group}: ${exposure.toFixed(1)}%`);
    }
  }
  
  // Check asset exposure
  for (const [asset, exposure] of Object.entries(exposureByAsset)) {
    if (exposure > limits.maxExposurePerAsset) {
      warnings.push(`High exposure in ${asset}: ${exposure.toFixed(1)}%`);
    }
  }
  
  // Check drawdown
  const currentDrawdown = calculateCurrentDrawdown(portfolio);
  if (currentDrawdown > limits.maxDrawdown * 0.7) {
    warnings.push(`Drawdown at ${currentDrawdown.toFixed(1)}% (limit: ${limits.maxDrawdown}%)`);
  }
  
  const availableRisk = Math.max(0, limits.maxPortfolioRisk - currentPortfolioRisk);
  const canOpenTrade = 
    availableRisk > 0 &&
    portfolio.positions.length < limits.maxOpenTrades &&
    currentDrawdown < limits.maxDrawdown;
  
  return {
    currentPortfolioRisk: Math.round(currentPortfolioRisk * 100) / 100,
    currentDrawdown: Math.round(currentDrawdown * 100) / 100,
    openTradesCount: portfolio.positions.length,
    exposureByAsset,
    correlatedExposure,
    availableRisk: Math.round(availableRisk * 100) / 100,
    canOpenTrade,
    warnings
  };
}

// ═══════════════════════════════════════════════════════════════
// CORRELATION ANALYSIS
// ═══════════════════════════════════════════════════════════════

/**
 * Get correlation group for asset
 */
export function getCorrelationGroup(asset: string): string | null {
  for (const [group, assets] of Object.entries(CORRELATION_GROUPS)) {
    if (assets.includes(asset)) {
      return group;
    }
  }
  return null;
}

/**
 * Calculate correlated exposure by group
 */
export function calculateCorrelatedExposure(
  positions: PortfolioPosition[],
  accountSize: number
): Record<string, number> {
  const groupExposure: Record<string, number> = {};
  
  for (const pos of positions) {
    const group = getCorrelationGroup(pos.asset);
    if (group) {
      const exposure = pos.riskPct;
      groupExposure[group] = (groupExposure[group] || 0) + exposure;
    }
  }
  
  return groupExposure;
}

/**
 * Check if adding position would violate correlation limits
 */
export function checkCorrelationLimits(
  newAsset: string,
  newRiskPct: number,
  currentPositions: PortfolioPosition[],
  maxCorrelatedRisk: number
): { allowed: boolean; group?: string; currentExposure?: number } {
  const group = getCorrelationGroup(newAsset);
  if (!group) {
    return { allowed: true };
  }
  
  // Calculate current exposure in this group
  let currentExposure = 0;
  for (const pos of currentPositions) {
    if (getCorrelationGroup(pos.asset) === group) {
      currentExposure += pos.riskPct;
    }
  }
  
  const wouldExceed = (currentExposure + newRiskPct) > maxCorrelatedRisk;
  
  return {
    allowed: !wouldExceed,
    group,
    currentExposure
  };
}

// ═══════════════════════════════════════════════════════════════
// DRAWDOWN CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate current drawdown
 */
export function calculateCurrentDrawdown(portfolio: Portfolio): number {
  // Simple: unrealized loss as % of account
  if (portfolio.unrealizedPnL >= 0) return 0;
  
  return Math.abs(portfolio.unrealizedPnL / portfolio.accountSize) * 100;
}

/**
 * Calculate max drawdown from equity curve
 */
export function calculateMaxDrawdown(equityCurve: number[]): number {
  if (equityCurve.length === 0) return 0;
  
  let peak = equityCurve[0];
  let maxDD = 0;
  
  for (const equity of equityCurve) {
    if (equity > peak) peak = equity;
    const dd = (peak - equity) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }
  
  return maxDD;
}

// ═══════════════════════════════════════════════════════════════
// RISK ADJUSTMENT
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate risk reduction factor based on current state
 */
export function calculateRiskReductionFactor(
  currentDrawdown: number,
  maxDrawdown: number,
  recentLosses: number
): number {
  let factor = 1.0;
  
  // Reduce risk as drawdown increases
  const ddRatio = currentDrawdown / maxDrawdown;
  if (ddRatio > 0.5) {
    factor *= 1 - (ddRatio - 0.5);  // Linear reduction
  }
  
  // Reduce risk after consecutive losses
  if (recentLosses >= 3) {
    factor *= 0.7;
  } else if (recentLosses >= 5) {
    factor *= 0.5;
  }
  
  return Math.max(0.3, factor);
}

/**
 * Check if trading should be paused
 */
export function shouldPauseTrading(
  currentDrawdown: number,
  maxDrawdown: number,
  consecutiveLosses: number
): { pause: boolean; reason?: string } {
  if (currentDrawdown >= maxDrawdown) {
    return { pause: true, reason: 'Max drawdown reached' };
  }
  
  if (consecutiveLosses >= 7) {
    return { pause: true, reason: 'Too many consecutive losses' };
  }
  
  return { pause: false };
}
